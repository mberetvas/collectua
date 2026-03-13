from __future__ import annotations

import asyncio
import csv
import logging
import os
import socket

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from asyncua import Client, ua
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from opcua_client.runtime_config import RuntimeConfig
from opcua_client.cert_paths import ensure_client_certificates
from opcua_client.condition_refresh import condition_refresh_with_retry
from opcua_client.collector import CSV_HEADERS, ActiveAlarm, subscribe as collector_subscribe

from .widgets.alarm_table import AlarmTableWidget
from .widgets.config_panel import ConfigPanel
from .widgets.connection_status import ConnectionStatusWidget
from .widgets.log_stream import TuiLogHandler
from .widgets.node_info_panel import NodeInfoPanelWidget
from .widgets.node_tree import NodeTreeWidget

_logger = logging.getLogger("tui")
RETRO_GREEN = "#8aff80"
RETRO_AMBER = "#ffbf4d"
RETRO_RED = "#ff5f5f"


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss", "Close"), Binding("enter", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        yield Static(
            "\n".join(
                [
                    "[b]OPC UA TUI Help[/b]",
                    "",
                    "Tab: Focus next panel",
                    "↑/↓: Previous/next sibling node (when Node Tree is focused)",
                    "→: Expand node or focus first child",
                    "←: Collapse node or focus parent",
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


class StartupSplashScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss", "Skip"), Binding("enter", "dismiss", "Skip")]

    def __init__(self, ascii_art_path: Path) -> None:
        super().__init__()
        self._ascii_art_path = ascii_art_path
        self._animation_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="splash-modal")

    async def on_mount(self) -> None:
        self._animation_task = asyncio.create_task(self._run_animation())

    async def on_unmount(self) -> None:
        if self._animation_task and not self._animation_task.done():
            self._animation_task.cancel()
            try:
                await self._animation_task
            except asyncio.CancelledError:
                pass

    def action_dismiss(self) -> None:
        self.dismiss(None)

    def _read_ascii_lines(self) -> list[str]:
        try:
            raw = self._ascii_art_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            raw = [
                "collectua",
                "",
                "OPC UA Command Center",
            ]
        return [line.rstrip() for line in raw]

    async def _run_animation(self) -> None:
        splash = self.query_one("#splash-modal", Static)
        lines = self._read_ascii_lines()
        rendered: list[str] = []

        for line in lines:
            rendered.append(line)
            splash.update(Text("\n".join(rendered), style=f"bold {RETRO_GREEN}"))
            await asyncio.sleep(0.08)

        splash.update(Text("\n".join(rendered + ["", "[ Press Enter / Esc to continue ]"]), style=f"bold {RETRO_GREEN}"))
        await asyncio.sleep(0.65)
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
        self._active_alarms: Dict[str, ActiveAlarm] = {}

    def _ensure_csv_header(self) -> None:
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)

    @staticmethod
    def _condition_id_from_event(event) -> Optional[str]:
        value = getattr(event, "ConditionId", None)
        if value is None:
            return None
        if isinstance(value, ua.NodeId):
            return value.to_string()
        to_string = getattr(value, "to_string", None)
        if callable(to_string):
            return to_string()
        return str(value)

    @staticmethod
    def _bool_from_state(state) -> Optional[bool]:
        if state is None:
            return None
        try:
            inner = getattr(state, "Id", state)
        except Exception:
            inner = state
        try:
            return bool(inner)
        except Exception:
            return None

    def _update_active_alarms(self, row: Mapping[str, Any]) -> None:
        condition_id = row.get("condition_id")
        if not condition_id:
            return

        retain = row.get("retain")
        active_state = row.get("active_state")
        acked_state = row.get("acked_state")

        if isinstance(retain, str):
            retain_normalized: Optional[bool] = retain.lower() == "true"
        else:
            retain_normalized = bool(retain) if retain is not None else None

        active_alarm = ActiveAlarm(
            condition_id=condition_id,
            condition_name=str(row.get("condition_name", "")),
            source_name=str(row.get("source_name", "")),
            message=str(row.get("message", "")),
            severity=str(row.get("severity", "")),
            timestamp_utc=str(row.get("timestamp_utc", "")),
            retain=retain_normalized,
            active_state=bool(active_state) if active_state is not None else None,
            acked_state=bool(acked_state) if acked_state is not None else None,
            raw=str(row.get("raw", "")),
        )

        if retain_normalized is False:
            if condition_id in self._active_alarms:
                _logger.debug("Clearing active alarm for ConditionId=%s", condition_id)
                self._active_alarms.pop(condition_id, None)
            return

        _logger.debug("Upserting active alarm for ConditionId=%s", condition_id)
        self._active_alarms[condition_id] = active_alarm

    def get_active_alarms(self) -> Mapping[str, ActiveAlarm]:
        """Return a read-only view of the currently active alarms."""
        return dict(self._active_alarms)

    def event_notification(self, event) -> None:
        try:
            _logger.debug("RAW EVENT RECEIVED: %s", event)
            row = {
                "timestamp_utc": str(getattr(event, "Time", datetime.now(timezone.utc))),
                "event_type": str(getattr(event, "EventType", "")),
                "source_name": str(getattr(event, "SourceName", "")),
                "message": str(getattr(event, "Message", "")),
                "severity": str(getattr(event, "Severity", "")),
                "condition_name": str(getattr(event, "ConditionName", "")),
                "event_id": str(getattr(event, "EventId", "")),
                "condition_id": self._condition_id_from_event(event),
                "retain": getattr(event, "Retain", None),
                "active_state": self._bool_from_state(getattr(event, "ActiveState", None)),
                "acked_state": self._bool_from_state(getattr(event, "AckedState", None)),
                "raw": str(event),
            }

            self._update_active_alarms(row)

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
    TITLE = "collectua"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("f10", "quit", "Quit"),
        Binding("f5", "reconnect", "Reconnect"),
        Binding("f6", "toggle_main_tab", "Toggle Main Tab"),
        Binding("shift+f6", "show_alarm_tab", "Show Alarms"),
        Binding("f1", "help", "Help"),
        Binding("f8", "toggle_logs", "Toggle Logs"),
        Binding("f9", "toggle_config", "Toggle Config"),
        Binding("tab", "focus_next_panel", "Next Panel"),
        Binding("right", "expand_or_focus_right", "Expand/Right", show=False),
        Binding("left", "collapse_or_focus_left", "Collapse/Left", show=False),
        Binding("up", "focus_previous", "Up", show=False),
        Binding("down", "focus_next", "Down", show=False),
    ]

    def __init__(self, config: RuntimeConfig):
        super().__init__()
        self.config = config
        self._ascii_art_path = Path(__file__).resolve().parents[3] / "ascii_art.md"
        self._client: Client | None = None
        self._subscription = None
        self._runner_task: asyncio.Task | None = None
        self._node_value_task: asyncio.Task | None = None
        self._shutdown_requested = False
        self._log_handler: TuiLogHandler | None = None
        self._selected_node: dict[str, Any] | None = None
        self._pending_focus_first_child_node_ids: set[str] = set()
        # 0 = default layout, 1 = right-column logs, 2 = full-screen logs
        self._log_mode: int = 0

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
                from .widgets.log_stream import LogStreamWidget

                yield LogStreamWidget(id="log-stream")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one(ConfigPanel).set_config(asdict(self.config))

        log_stream = self.query_one("#log-stream")
        self._log_handler = TuiLogHandler(log_stream)
        root_logger = logging.getLogger()

        # When launched via the CLI, logging is configured with a console StreamHandler that
        # writes to stdout/stderr. In TUI mode we want log records to appear only inside the
        # in-app log panel, not in the terminal itself, so we remove any existing console
        # stream handlers and rely on the TUI handler (plus any file handlers) instead.
        for handler in list(root_logger.handlers):
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                root_logger.removeHandler(handler)

        root_logger.addHandler(self._log_handler)
        root_logger.setLevel(getattr(logging, self.config.log_level.upper(), logging.INFO))

        # Do not block the Mount message handler on splash dismissal.
        # Textual screen lifecycle callbacks are message-pump driven, so startup
        # continues from the dismiss callback once the splash is gone.
        self.push_screen(
            StartupSplashScreen(self._ascii_art_path),
            callback=lambda _result: self._start_connection_supervisor(),
        )

    def _start_connection_supervisor(self) -> None:
        if self._runner_task and not self._runner_task.done():
            return
        self._runner_task = asyncio.create_task(self._run_connection_supervisor())

    def _apply_log_mode(self) -> None:
        log_stream = self.query_one("#log-stream")
        config_panel = self.query_one(ConfigPanel)
        tabbed = self.query_one("#tabbed-panel", TabbedContent)
        header = self.query_one(Header)
        status = self.query_one("#connection-status", ConnectionStatusWidget)
        left_column = self.query_one("#left-column")
        right_column = self.query_one("#right-column")
        footer = self.query_one(Footer)

        if self._log_mode == 0:
            # Default: full dashboard layout.
            header.display = True
            status.display = True
            left_column.display = True
            right_column.display = True
            footer.display = True

            log_stream.display = True
            log_stream.styles.height = None  # defer to CSS (fixed height)
            right_column.styles.width = None

            tabbed.display = True
            config_panel.display = True
        elif self._log_mode == 1:
            # Full-width/right-column logs, hide config panel.
            header.display = True
            status.display = True
            left_column.display = True
            right_column.display = True
            footer.display = True

            log_stream.display = True
            log_stream.styles.height = "1fr"
            right_column.styles.width = None

            tabbed.display = False
            config_panel.display = False
        else:
            # Full-screen logs: hide main content except connection status + footer.
            header.display = False
            status.display = True
            left_column.display = False
            footer.display = True

            right_column.display = True
            right_column.styles.width = "1fr"

            log_stream.display = True
            log_stream.styles.height = "1fr"

            tabbed.display = False
            config_panel.display = False

    def action_toggle_logs(self) -> None:
        self._log_mode = (self._log_mode + 1) % 3
        self._apply_log_mode()

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
            # Always use the global/default client certificate material for secure connections.
            cert_file, key_file = ensure_client_certificates()
            await client.set_security_string(f"{conn.auth_policy},{conn.security_mode},{cert_file},{key_file}")
            selected_endpoint_app_uri = ""
            try:
                eps = await client.connect_and_get_server_endpoints()
                for ep in eps:
                    policy_short = ((getattr(ep, "SecurityPolicyUri", "") or "").rsplit("#", 1)[-1] or "None")
                    mode_name = getattr(getattr(ep, "SecurityMode", None), "name", "")
                    normalized_mode = "None_" if mode_name == "None" else mode_name
                    if policy_short == conn.auth_policy and normalized_mode == conn.security_mode:
                        selected_endpoint_app_uri = str(getattr(getattr(ep, "Server", None), "ApplicationUri", "") or "")
                        break
            except Exception:
                pass
            if selected_endpoint_app_uri:
                original_create_session = client.uaclient.create_session

                async def _patched_create_session(parameters):
                    parameters.ServerUri = selected_endpoint_app_uri
                    return await original_create_session(parameters)

                client.uaclient.create_session = _patched_create_session

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
        initial_max_depth = min(1, self.config.browse.max_depth)
        target_ns = set(self.config.browse.target_namespaces)
        tree_data = await self._browse_nodes(
            self._client.nodes.objects,
            depth=0,
            max_depth=initial_max_depth,
            target_namespaces=target_ns,
        )
        if not tree_data:
            tree_data = {
                "id": self._client.nodes.objects.nodeid.to_string(),
                "name": "Objects",
                "cls": "Object",
                "children": [],
                "type": None,
                "ns": 0,
                "depth": 0,
                "expandable": False,
            }
        self.post_message(NodeTreeData(tree_data))

    async def _browse_nodes(
        self,
        node,
        depth: int,
        max_depth: int,
        target_namespaces: set[int],
    ) -> dict[str, Any] | None:
        ns_index = int(node.nodeid.NamespaceIndex)
        is_target_namespace = not target_namespaces or ns_index in target_namespaces
        is_bridge_namespace = ns_index == 0

        if not is_target_namespace and not is_bridge_namespace:
            return None

        node_class = await node.read_node_class()
        children: list[dict[str, Any]] = []

        if depth < max_depth and node_class == ua.NodeClass.Object:
            for child in await node.get_children(
                nodeclassmask=ua.NodeClass.Object | ua.NodeClass.Variable | ua.NodeClass.Method
            ):
                child_tree = await self._browse_nodes(child, depth + 1, max_depth, target_namespaces)
                if child_tree:
                    children.append(child_tree)

        if children:
            children.sort(key=lambda c: str(c.get("name", "")).lower())

        include_node = depth == 0 or is_target_namespace or bool(children)
        if not include_node:
            return None

        if node_class != ua.NodeClass.Variable:
            var_type = None
        else:
            try:
                var_type = (await node.read_data_type_as_variant_type()).name
            except ua.UaError:
                var_type = None

        expandable = node_class == ua.NodeClass.Object and depth < self.config.browse.max_depth and depth >= max_depth

        return {
            "id": node.nodeid.to_string(),
            "name": (await node.read_display_name()).Text,
            "cls": node_class.name,
            "children": children,
            "type": var_type,
            "ns": ns_index,
            "depth": depth,
            "expandable": expandable,
        }

    async def _fetch_child_tree_data(self, node_data: dict[str, Any]) -> list[dict[str, Any]]:
        if not self._client:
            return []

        node_id = str(node_data.get("id", ""))
        if not node_id:
            return []

        node = self._client.get_node(node_id)
        parent_depth = int(node_data.get("depth", 0))
        max_depth = min(parent_depth + 1, self.config.browse.max_depth)
        target_ns = set(self.config.browse.target_namespaces)
        refreshed = await self._browse_nodes(node, parent_depth, max_depth, target_ns)
        if not refreshed:
            return []
        return refreshed.get("children", [])

    async def on_tree_node_expanded(self, event) -> None:
        tree_node = event.node
        node_data = getattr(tree_node, "data", None)
        if not isinstance(node_data, dict):
            return
        node_id = str(node_data.get("id", ""))

        if not node_data.get("expandable"):
            return

        tree_widget = self.query_one(NodeTreeWidget)
        if not tree_widget.has_placeholder(tree_node):
            return

        try:
            child_nodes = await self._fetch_child_tree_data(node_data)
        except Exception as exc:
            _logger.exception("Failed to lazy-load node children")
            tree_widget.remove_placeholder(tree_node)
            tree_node.add(f"⚠ Failed to load: {exc}", data={"_load_error": True}, allow_expand=False)
            if node_id:
                self._pending_focus_first_child_node_ids.discard(node_id)
            return

        tree_widget.remove_placeholder(tree_node)
        if child_nodes:
            tree_widget.add_children(tree_node, child_nodes)
            node_data["children"] = child_nodes
            tree_node.data = node_data
        else:
            node_data["expandable"] = False
            tree_node.data = node_data
            tree_node.allow_expand = False

        if node_id and node_id in self._pending_focus_first_child_node_ids:
            self._pending_focus_first_child_node_ids.discard(node_id)
            tree_widget.focus_first_child(tree_node)

    async def _run_collector_loop(self) -> None:
        if not self._client:
            return
        client = self._client
        handler = TuiAlarmHandler(self.config.collect.csv_file, self)

        self._subscription = await collector_subscribe(
            client,
            handler,
            publish_interval_ms=self.config.collect.publish_interval_ms,
            # The TUI performs its own ConditionRefresh with a subscription-id
            # guard so we disable the built-in refresh in the shared helper.
            enable_condition_refresh=False,
            is_active=None,
        )

        subscription = self._subscription
        server_node = client.get_node(ua.ObjectIds.Server)
        subscription_id = subscription.subscription_id

        async def _run_condition_refresh() -> None:
            await asyncio.sleep(2.0)
            if (
                self._shutdown_requested
                or self._client is not client
                or self._subscription is not subscription
                or getattr(self._subscription, "subscription_id", None) != subscription_id
            ):
                _logger.info(
                    "Skipping ConditionRefresh for SubscriptionId=%s: client or subscription no longer active",
                    subscription_id,
                )
                return

            await condition_refresh_with_retry(
                server_node=server_node,
                subscription_id=subscription_id,
                logger=_logger,
                is_active=lambda: (
                    not self._shutdown_requested
                    and self._client is client
                    and self._subscription is subscription
                    and getattr(self._subscription, "subscription_id", None) == subscription_id
                ),
            )

        asyncio.create_task(_run_condition_refresh())

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
                panel.display_node(node_data, value_text=f"[{RETRO_AMBER}]Loading...[/{RETRO_AMBER}]")
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
                    value_text=f"[{RETRO_RED}]Unavailable[/{RETRO_RED}]",
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
                value_text=f"[bold {RETRO_GREEN}]{value_rendered}[/bold {RETRO_GREEN}]",
                value_status=f"Read at {datetime.now().strftime('%H:%M:%S')}",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Keep node metadata visible even when value read fails.
            if self._selected_node and self._selected_node.get("id") == node_id:
                self.query_one(NodeInfoPanelWidget).display_node(
                    node_data,
                    value_text=f"[{RETRO_RED}]Read failed[/{RETRO_RED}]",
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

    def action_expand_or_focus_right(self) -> None:
        tree = self.query_one(NodeTreeWidget)
        if not tree.has_focus:
            return

        node = tree.cursor_node
        if node is None:
            return

        if node.allow_expand and not node.is_expanded:
            node_data = getattr(node, "data", None)
            node.expand()
            if tree.focus_first_child(node):
                return
            if isinstance(node_data, dict):
                node_id = str(node_data.get("id", ""))
                if node_id:
                    self._pending_focus_first_child_node_ids.add(node_id)
            return

        if node.is_expanded:
            tree.focus_first_child(node)

    def action_collapse_or_focus_left(self) -> None:
        tree = self.query_one(NodeTreeWidget)
        if not tree.has_focus:
            return

        node = tree.cursor_node
        if node is None:
            return

        if node.allow_expand and node.is_expanded:
            node.collapse()
            tree.focus_node(node)
            return

        tree.focus_parent(node)

    def action_focus_previous(self) -> None:
        tree = self.query_one(NodeTreeWidget)
        if not tree.has_focus:
            return

        node = tree.cursor_node
        if node is None:
            return

        tree.focus_previous_sibling(node)

    def action_focus_next(self) -> None:
        tree = self.query_one(NodeTreeWidget)
        if not tree.has_focus:
            return

        node = tree.cursor_node
        if node is None:
            return

        tree.focus_next_sibling(node)

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
