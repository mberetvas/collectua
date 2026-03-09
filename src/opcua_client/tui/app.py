from __future__ import annotations

import asyncio
import csv
import logging
import os
import socket

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from asyncua import Client, ua
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from opcua_client.runtime_config import RuntimeConfig

from .widgets.alarm_table import AlarmTableWidget
from .widgets.config_panel import ConfigPanel
from .widgets.connection_status import ConnectionStatusWidget
from .widgets.log_stream import TuiLogHandler
from .widgets.node_info_panel import NodeInfoPanelWidget
from .widgets.node_tree import NodeTreeWidget

CSV_HEADERS = [
    "timestamp_utc",
    "event_type",
    "source_name",
    "message",
    "severity",
    "condition_name",
    "event_id",
    "raw",
]

_logger = logging.getLogger("tui")


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss", "Close"), Binding("enter", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        yield Static(
            "\n".join(
                [
                    "[b]OPC UA TUI Help[/b]",
                    "",
                    "Tab: Focus next panel",
                    "F6: Toggle Alarms / Node Info tab",
                    "F1: Help",
                    "F5: Reconnect",
                    "F9: Toggle config panel",
                    "F10 / q: Quit",
                    "",
                    "This dashboard is read-only and streams alarms/events in real-time.",
                    "Press ESC or Enter to close.",
                ]
            ),
            id="help-modal",
        )

    def action_dismiss(self) -> None:
        self.dismiss(None)


class AlarmRow(Message):
    def __init__(self, row: dict[str, str]) -> None:
        super().__init__()
        self.row = row


class ConnectionState(Message):
    def __init__(self, connected: bool, reconnecting: bool = False, error: str = "") -> None:
        super().__init__()
        self.connected = connected
        self.reconnecting = reconnecting
        self.error = error


class NodeTreeData(Message):
    def __init__(self, tree_data: dict[str, Any]) -> None:
        super().__init__()
        self.tree_data = tree_data


class NodeSelected(Message):
    def __init__(self, node_data: dict[str, Any]) -> None:
        super().__init__()
        self.node_data = node_data


class TuiAlarmHandler:
    def __init__(self, csv_path: str, app: "OpcuaTuiApp"):
        self.csv_path = csv_path
        self.app = app
        self._ensure_csv_header()

    def _ensure_csv_header(self) -> None:
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)

    def event_notification(self, event) -> None:
        try:
            row = {
                "timestamp_utc": str(getattr(event, "Time", datetime.now(timezone.utc))),
                "event_type": str(getattr(event, "EventType", "")),
                "source_name": str(getattr(event, "SourceName", "")),
                "message": str(getattr(event, "Message", "")),
                "severity": str(getattr(event, "Severity", "")),
                "condition_name": str(getattr(event, "ConditionName", "")),
                "event_id": str(getattr(event, "EventId", "")),
                "raw": str(event),
            }

            with open(self.csv_path, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                writer.writerow(row)

            self.app.post_message(AlarmRow(row))

        except Exception:
            _logger.exception("Failed to process event")

    def status_change_notification(self, status) -> None:
        _logger.warning("Subscription status changed: %s", status)


class OpcuaTuiApp(App[None]):
    CSS_PATH = "theme.tcss"
    TITLE = "OPC UA Command Center"
    SUB_TITLE = "htop/btop-inspired dashboard"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("f10", "quit", "Quit"),
        Binding("f5", "reconnect", "Reconnect"),
        Binding("f6", "toggle_main_tab", "Toggle Main Tab"),
        Binding("shift+f6", "show_alarm_tab", "Show Alarms"),
        Binding("f1", "help", "Help"),
        Binding("f9", "toggle_config", "Toggle Config"),
        Binding("tab", "focus_next_panel", "Next Panel"),
    ]

    def __init__(self, config: RuntimeConfig):
        super().__init__()
        self.config = config
        self._client: Client | None = None
        self._subscription = None
        self._runner_task: asyncio.Task | None = None
        self._node_value_task: asyncio.Task | None = None
        self._shutdown_requested = False
        self._log_handler: TuiLogHandler | None = None
        self._selected_node: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ConnectionStatusWidget(id="connection-status")
        with Horizontal(id="main-grid"):
            with Vertical(id="left-column"):
                yield NodeTreeWidget(id="node-tree")
                yield ConfigPanel(id="config-panel")
            with Vertical(id="right-column"):
                with TabbedContent(id="tabbed-panel"):
                    with TabPane("Live Alarms", id="tab-alarms"):
                        yield AlarmTableWidget(id="alarm-table")
                    with TabPane("Node Info", id="tab-node-info"):
                        yield NodeInfoPanelWidget(id="node-info-content")
                yield Static("Logs", classes="panel-title")
                from .widgets.log_stream import LogStreamWidget

                yield LogStreamWidget(id="log-stream")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one(ConfigPanel).set_config(asdict(self.config))

        log_stream = self.query_one("#log-stream")
        self._log_handler = TuiLogHandler(log_stream)
        root_logger = logging.getLogger()
        root_logger.addHandler(self._log_handler)
        root_logger.setLevel(getattr(logging, self.config.log_level.upper(), logging.INFO))

        self._runner_task = asyncio.create_task(self._run_connection_supervisor())

    async def _create_client(self) -> Client:
        conn = self.config.connection
        client = Client(url=conn.url, timeout=conn.timeout)
        client.application_uri = f"urn:{socket.gethostname()}:foobar:myclient"
        client.session_timeout = conn.session_timeout
        client.uaclient.request_timeout = conn.request_timeout

        if conn.username:
            client.set_user(conn.username)
        if conn.password:
            client.set_password(conn.password)

        if conn.security_mode != "None_":
            await client.set_security_string(
                f"{conn.auth_policy},{conn.security_mode},{conn.cert_file},{conn.key_file}"
            )

        return client

    async def _run_connection_supervisor(self) -> None:
        reconnect_delay = self.config.collect.reconnect_delay_sec
        while not self._shutdown_requested:
            try:
                self.post_message(ConnectionState(connected=False, reconnecting=True, error="Connecting..."))
                self._client = await self._create_client()
                await self._client.connect()
                self.post_message(ConnectionState(connected=True, reconnecting=False, error=""))
                _logger.info("Connected to %s", self.config.connection.url)

                await self._load_node_tree()
                await self._run_collector_loop()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                _logger.exception("Connection loop error")
                self.post_message(ConnectionState(connected=False, reconnecting=True, error=str(exc)))
                await asyncio.sleep(reconnect_delay)
            finally:
                await self._cleanup_client()

    async def _cleanup_client(self) -> None:
        if self._node_value_task and not self._node_value_task.done():
            self._node_value_task.cancel()
            try:
                await self._node_value_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        self._node_value_task = None

        try:
            if self._subscription:
                await self._subscription.delete()
        except Exception:
            pass
        finally:
            self._subscription = None

        try:
            if self._client:
                await self._client.disconnect()
        except Exception:
            pass
        finally:
            self._client = None

    async def _load_node_tree(self) -> None:
        if not self._client:
            return
        tree_data = await self._browse_nodes(
            self._client.nodes.objects, depth=0, max_depth=self.config.browse.max_depth
        )
        self.post_message(NodeTreeData(tree_data))

    async def _browse_nodes(self, node, depth: int, max_depth: int) -> dict[str, Any]:
        node_class = await node.read_node_class()
        children: list[dict[str, Any]] = []

        if depth < max_depth:
            for child in await node.get_children():
                if await child.read_node_class() in [ua.NodeClass.Object, ua.NodeClass.Variable]:
                    children.append(await self._browse_nodes(child, depth + 1, max_depth))

        if node_class != ua.NodeClass.Variable:
            var_type = None
        else:
            try:
                var_type = (await node.read_data_type_as_variant_type()).name
            except ua.UaError:
                var_type = None

        return {
            "id": node.nodeid.to_string(),
            "name": (await node.read_display_name()).Text,
            "cls": node_class.name,
            "children": children,
            "type": var_type,
        }

    async def _run_collector_loop(self) -> None:
        if not self._client:
            return
        handler = TuiAlarmHandler(self.config.collect.csv_file, self)
        self._subscription = await self._client.create_subscription(
            period=self.config.collect.publish_interval_ms,
            handler=handler,
        )
        server_node = self._client.get_node(ua.ObjectIds.Server)
        await self._subscription.subscribe_events(
            sourcenode=server_node,
            evtypes=ua.ObjectIds.BaseEventType,
        )
        _logger.info("Subscribed to BaseEventType events")

        while not self._shutdown_requested and self._client:
            await asyncio.sleep(1)

    def on_alarm_row(self, message: AlarmRow) -> None:
        self.query_one(AlarmTableWidget).add_event(message.row)

    def on_connection_state(self, message: ConnectionState) -> None:
        status = self.query_one(ConnectionStatusWidget)
        status.endpoint = self.config.connection.url
        status.security_mode = self.config.connection.security_mode
        status.connected = message.connected
        status.reconnecting = message.reconnecting
        status.error = message.error

    def on_node_tree_data(self, message: NodeTreeData) -> None:
        self.query_one(NodeTreeWidget).set_tree_data(message.tree_data)

    def on_tree_node_selected(self, event) -> None:
        if event.node.data:
            node_data = event.node.data
            self._selected_node = node_data

            panel = self.query_one(NodeInfoPanelWidget)
            node_class = str(node_data.get("cls", ""))

            if node_class == "Variable":
                panel.display_node(node_data, value_text="[yellow]Loading...[/yellow]")
                if self._node_value_task and not self._node_value_task.done():
                    self._node_value_task.cancel()
                self._node_value_task = asyncio.create_task(self._read_selected_node_value(node_data))
            else:
                panel.display_node(
                    node_data,
                    value_text="[dim]N/A (not a variable node)[/dim]",
                )

    async def _read_selected_node_value(self, node_data: dict[str, Any]) -> None:
        node_id = str(node_data.get("id", ""))
        if not node_id:
            return

        try:
            if not self._client:
                self.query_one(NodeInfoPanelWidget).display_node(
                    node_data,
                    value_text="[red]Unavailable[/red]",
                    value_status="Disconnected from server",
                )
                return

            node = self._client.get_node(node_id)
            value = await node.read_value()

            # Skip stale updates if user has selected a different node meanwhile.
            if not self._selected_node or self._selected_node.get("id") != node_id:
                return

            value_rendered = str(value)
            if len(value_rendered) > 160:
                value_rendered = f"{value_rendered[:157]}..."

            self.query_one(NodeInfoPanelWidget).display_node(
                node_data,
                value_text=f"[bold #9ece6a]{value_rendered}[/bold #9ece6a]",
                value_status=f"Read at {datetime.now().strftime('%H:%M:%S')}",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Keep node metadata visible even when value read fails.
            if self._selected_node and self._selected_node.get("id") == node_id:
                self.query_one(NodeInfoPanelWidget).display_node(
                    node_data,
                    value_text="[red]Read failed[/red]",
                    value_status=str(exc),
                )

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_toggle_config(self) -> None:
        panel = self.query_one("#config-panel")
        panel.display = not panel.display

    async def action_reconnect(self) -> None:
        _logger.info("Manual reconnect requested")
        if self._runner_task and not self._runner_task.done():
            self._runner_task.cancel()
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass
        await self._cleanup_client()
        self._runner_task = asyncio.create_task(self._run_connection_supervisor())

    def action_focus_next_panel(self) -> None:
        self.screen.focus_next()

    def action_toggle_main_tab(self) -> None:
        tabbed = self.query_one("#tabbed-panel", TabbedContent)
        tabbed.active = "tab-node-info" if tabbed.active == "tab-alarms" else "tab-alarms"

    def action_show_alarm_tab(self) -> None:
        self.query_one("#tabbed-panel", TabbedContent).active = "tab-alarms"

    async def action_quit(self) -> None:
        self._shutdown_requested = True
        if self._runner_task and not self._runner_task.done():
            self._runner_task.cancel()
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass

        await self._cleanup_client()
        if self._log_handler:
            logging.getLogger().removeHandler(self._log_handler)
        self.exit()
