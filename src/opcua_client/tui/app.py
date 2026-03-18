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
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Static, TabbedContent, TabPane, Button

from opcua_client.domain.alarm import Alarm
from opcua_client.domain.connection import AuthPolicy
from opcua_client.config.env_defaults import get_formatted_str
from opcua_client.config.runtime_config import RuntimeConfig
from opcua_client.infrastructure.asyncua_compat import patch_create_session_server_uri
from opcua_client.ops.condition_refresh import condition_refresh_with_retry
from opcua_client.ops.collector import CSV_HEADERS, subscribe as collector_subscribe
from opcua_client.security.cert_paths import ensure_client_certificates
from opcua_client.infrastructure.asyncua_adapter import event_to_alarm

from .widgets.alarm_table import AlarmTableWidget
from .widgets.config_panel import ConfigPanel
from .widgets.connection_status import ConnectionStatusWidget
from .widgets.log_stream import TuiSqliteLogHandler
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
                    "s: Toggle node multi-selection",
                    "Esc: Clear node multi-selection",
                    "c: Copy selected Node IDs",
                    "l: Copy all logs",
                    "e: Copy error logs",
                    "↑/↓: Previous/next sibling node (when Node Tree is focused)",
                    "→: Expand node or focus first child",
                    "←: Collapse node or focus parent",
                    "t: Toggle Alarms / Node Info tab",
                    "a: Show Alarms tab",
                    "?: Help",
                    "r: Reconnect",
                    "p: Toggle config panel",
                    "v: Toggle Logs tab",
                    "q: Quit",
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

        splash.update(
            Text("\n".join(rendered + ["", "[ Press Enter / Esc to continue ]"]), style=f"bold {RETRO_GREEN}")
        )
        await asyncio.sleep(0.65)
        self.dismiss(None)


class AlarmRow(Message):
    def __init__(self, alarm: Alarm) -> None:
        super().__init__()
        self.alarm = alarm
        # Compatibility for existing tests/widgets expecting a row dict.
        self.row = {
            "timestamp_utc": alarm.timestamp_utc.isoformat(),
            "event_type": alarm.event_type,
            "source_name": alarm.source_name,
            "message": alarm.message,
            "severity": alarm.severity.value,
            "condition_name": alarm.condition_name,
            "event_id": alarm.event_id,
            "condition_id": str(alarm.alarm_id),
            "retain": "" if alarm.retain is None else str(bool(alarm.retain)),
            "active_state": "" if alarm.active_state is None else str(bool(alarm.active_state)),
            "acked_state": "" if alarm.acked_state is None else str(bool(alarm.acked_state)),
            "raw": alarm.raw,
        }


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
        self._active_alarms: Dict[str, Alarm] = {}

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

        alarm = Alarm.from_values(
            alarm_id=str(condition_id),
            condition_name=str(row.get("condition_name", "")),
            source_name=str(row.get("source_name", "")),
            message=str(row.get("message", "")),
            severity=row.get("severity"),
            timestamp_utc=str(row.get("timestamp_utc", "")),
            retain=retain_normalized,
            active_state=bool(active_state) if active_state is not None else None,
            acked_state=bool(acked_state) if acked_state is not None else None,
            event_type=str(row.get("event_type", "")),
            event_id=str(row.get("event_id", "")),
            raw=str(row.get("raw", "")),
        )

        if retain_normalized is False:
            if condition_id in self._active_alarms:
                _logger.debug("Clearing active alarm for ConditionId=%s", condition_id)
                self._active_alarms.pop(condition_id, None)
            return

        _logger.debug("Upserting active alarm for ConditionId=%s", condition_id)
        self._active_alarms[condition_id] = alarm

    def get_active_alarms(self) -> Mapping[str, Alarm]:
        """Return a read-only view of the currently active alarms."""
        return dict(self._active_alarms)

    def event_notification(self, event) -> None:
        try:
            _logger.debug("RAW EVENT RECEIVED: %s", event)
            alarm = event_to_alarm(event)
            row = {
                "timestamp_utc": alarm.timestamp_utc.isoformat(),
                "event_type": alarm.event_type,
                "source_name": alarm.source_name,
                "message": alarm.message,
                "severity": alarm.severity.value,
                "condition_name": alarm.condition_name,
                "event_id": alarm.event_id,
                "condition_id": str(alarm.alarm_id),
                "retain": alarm.retain,
                "active_state": alarm.active_state,
                "acked_state": alarm.acked_state,
                "raw": alarm.raw,
            }

            self._update_active_alarms(row)

            with open(self.csv_path, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                writer.writerow(row)

            self.app.post_message(AlarmRow(alarm))

        except Exception:
            _logger.exception("Failed to process event")

    def status_change_notification(self, status) -> None:
        _logger.warning("Subscription status changed: %s", status)


class OpcuaTuiApp(App[None]):
    CSS_PATH = "theme.tcss"
    TITLE = "collectua"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "reconnect", "Reconnect"),
        Binding("t", "toggle_main_tab", "Toggle Main Tab"),
        Binding("a", "show_alarm_tab", "Show Alarms"),
        Binding("s", "toggle_node_selection", "Toggle Node Selection"),
        Binding("escape", "clear_node_selection", "Clear Node Selection"),
        Binding("c", "copy_selected_node_id", "Copy Node IDs"),
        Binding("l", "copy_logs", "Copy Logs"),
        Binding("e", "copy_errors", "Copy Errors"),
        Binding("?", "help", "Help"),
        Binding("v", "toggle_logs", "Toggle Logs"),
        Binding("p", "toggle_config", "Toggle Config"),
        Binding("/", "focus_search", "Search"),
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
        self._log_handler: TuiSqliteLogHandler | None = None
        self._log_refresh_task: asyncio.Task | None = None
        self._last_log_row_id: int = 0
        self._selected_node: dict[str, Any] | None = None
        self._pending_focus_first_child_node_ids: set[str] = set()
        self._search_query: str = ""
        self._search_results: list[Any] = []
        self._search_index: int = 0

    # #region agent log
    def _agent_log(self, *, runId: str, hypothesisId: str, location: str, message: str, data: dict) -> None:
        import json
        import time

        payload = {
            "sessionId": "3adc8d",
            "runId": runId,
            "hypothesisId": hypothesisId,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        try:
            with open("debug-3adc8d.log", "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # #endregion agent log

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ConnectionStatusWidget(id="connection-status")
        with Horizontal(id="main-grid"):
            with Vertical(id="left-column"):
                yield Input(placeholder="Search loaded nodes...", id="node-search")
                yield NodeTreeWidget(id="node-tree")
                yield ConfigPanel(id="config-panel")
            with Vertical(id="right-column"):
                with TabbedContent(id="tabbed-panel"):
                    with TabPane("Live Alarms", id="tab-alarms"):
                        yield AlarmTableWidget(id="alarm-table")
                    with TabPane("Node Info", id="tab-node-info"):
                        yield NodeInfoPanelWidget(id="node-info-content")
                    with TabPane("Logs", id="tab-logs"):
                        from .widgets.log_stream import LogStreamWidget

                        with Vertical(id="log-panel"):
                            with Horizontal(id="log-actions"):
                                yield Button("Copy Logs", id="btn-copy-logs", variant="default")
                                yield Button("Copy Errors", id="btn-copy-errors", variant="error")
                            yield LogStreamWidget(id="log-stream")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one(ConfigPanel).set_config(asdict(self.config))

        # Determine log DB path: use explicit config or default to user app data dir.
        db_path = self.config.log_db_path
        if not db_path:
            user_home = Path.home()
            log_dir = user_home / ".collectua" / "tui"
            log_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(log_dir / "logs.db")

        log_stream = self.query_one("#log-stream")
        self._log_handler = TuiSqliteLogHandler(
            Path(db_path),
            retention_days=self.config.log_retention_days,
        )
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

        # Start the refresh loop if Logs tab is active by default, otherwise wait for activation.
        tabbed = self.query_one("#tabbed-panel", TabbedContent)
        if tabbed.active == "tab-logs":
            self._start_log_refresh_loop()

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

    def action_toggle_logs(self) -> None:
        tabbed = self.query_one("#tabbed-panel", TabbedContent)
        tabbed.active = "tab-logs" if tabbed.active != "tab-logs" else "tab-alarms"

    def _start_log_refresh_loop(self) -> None:
        """Start the background task that periodically refreshes logs from SQLite."""
        if self._log_refresh_task is None or self._log_refresh_task.done():
            self._log_refresh_task = asyncio.create_task(self._run_log_refresh_loop())

    def _stop_log_refresh_loop(self) -> None:
        """Cancel the background log refresh task."""
        if self._log_refresh_task and not self._log_refresh_task.done():
            self._log_refresh_task.cancel()
            self._log_refresh_task = None

    async def _run_log_refresh_loop(self) -> None:
        """Periodically query SQLite for new log entries and update the LogStreamWidget."""
        if not self._log_handler:
            return

        interval = self.config.log_refresh_interval_sec
        while not self._shutdown_requested:
            try:
                # Query new rows since last_id.
                new_rows = self._log_handler.fetch_since(self._last_log_row_id, limit=1000)
                if new_rows:
                    # Import style_for_level locally to avoid circular import.
                    from .widgets.log_stream import style_for_level

                    log_stream = self.query_one("#log-stream")
                    for row in new_rows:
                        formatted = f"{row.timestamp_utc[:19]} {row.levelname} {row.logger_name}: {row.message}"
                        log_stream.add_entry(
                            Text(formatted, style=style_for_level(row.levelno)),
                            levelno=row.levelno,
                        )
                    self._last_log_row_id = new_rows[-1].id
            except Exception:
                _logger.exception("Error refreshing logs from SQLite")

            await asyncio.sleep(interval)

    def _load_all_logs(self) -> None:
        """Load all logs from SQLite into the widget (used when switching to Logs tab)."""
        if not self._log_handler:
            return

        try:
            from .widgets.log_stream import style_for_level

            # Fetch the most recent rows (descending) to show newest first.
            self._log_handler.acquire()
            try:
                cur = self._log_handler._conn.execute(
                    "SELECT id, timestamp_utc, levelno, levelname, logger_name, message "
                    "FROM logs ORDER BY id DESC LIMIT 1000"
                )
                rows = cur.fetchall()
            finally:
                self._log_handler.release()

            if rows:
                log_stream = self.query_one("#log-stream")
                log_stream.clear()
                # rows are newest-first; we want newest at top of widget, so iterate reversed.
                for row in reversed(rows):
                    row_id, ts, levelno, lvlname, logger_name, msg = row
                    formatted = f"{ts[:19]} {lvlname} {logger_name}: {msg}"
                    log_stream.add_entry(
                        Text(formatted, style=style_for_level(levelno)),
                        levelno=levelno,
                    )
                    self._last_log_row_id = row_id
        except Exception:
            _logger.exception("Error loading all logs from SQLite")

    def _copy_to_clipboard_robust(self, text: str) -> None:
        """Try Textual clipboard first; fall back to pyperclip."""
        try:
            self.copy_to_clipboard(text)
        except Exception:
            import pyperclip
            pyperclip.copy(text)

    def action_copy_logs(self) -> None:
        try:
            log_stream = self.query_one("#log-stream")
            export_text = getattr(log_stream, "export_text", None)
            text = export_text() if callable(export_text) else ""

            if not text.strip():
                self.notify("No logs to copy yet.", timeout=2.0)
                self._agent_log(
                    runId="post-fix",
                    hypothesisId="LOGCOPY",
                    location="src/opcua_client/tui/app.py:action_copy_logs",
                    message="Copy logs requested but buffer was empty",
                    data={},
                )
                return

            self._copy_to_clipboard_robust(text)
            self.notify("Copied logs to clipboard.", timeout=2.0)
            self._agent_log(
                runId="post-fix",
                hypothesisId="LOGCOPY",
                location="src/opcua_client/tui/app.py:action_copy_logs",
                message="Copied log buffer to clipboard",
                data={"chars": len(text), "lines": text.count("\n")},
            )
        except Exception as exc:
            _logger.exception("Failed to copy logs to clipboard")
            self.notify(f"Failed to copy logs: {exc}", timeout=3.0)
            self._agent_log(
                runId="post-fix",
                hypothesisId="LOGCOPY",
                location="src/opcua_client/tui/app.py:action_copy_logs",
                message="Copy logs failed",
                data={"error": str(exc)},
            )

    def action_copy_errors(self) -> None:
        try:
            log_stream = self.query_one("#log-stream")
            export_text = getattr(log_stream, "export_text", None)
            text = export_text(min_level=logging.ERROR) if callable(export_text) else ""

            if not text.strip():
                self.notify("No errors to copy yet.", timeout=2.0)
                return

            self._copy_to_clipboard_robust(text)
            self.notify("Copied error logs to clipboard.", timeout=2.0)
        except Exception as exc:
            _logger.exception("Failed to copy error logs to clipboard")
            self.notify(f"Failed to copy errors: {exc}", timeout=3.0)

    @on(Button.Pressed, "#btn-copy-logs")
    def on_copy_logs_button(self) -> None:
        self.action_copy_logs()

    @on(Button.Pressed, "#btn-copy-errors")
    def on_copy_errors_button(self) -> None:
        self.action_copy_errors()

    async def _create_client(self) -> Client:
        conn = self.config.connection
        auth_policy = AuthPolicy.from_value(conn.auth_policy)
        client = Client(url=conn.url, timeout=conn.timeout)
        client.application_uri = get_formatted_str(
            "OPCUA_CLIENT_APP_URI_TEMPLATE",
            "urn:{hostname}:foobar:myclient",
            hostname=socket.gethostname(),
        )
        client.session_timeout = conn.session_timeout
        client.uaclient.request_timeout = conn.request_timeout

        if conn.username:
            client.set_user(conn.username)
        if conn.password:
            client.set_password(conn.password)

        if conn.security_mode != "None_":
            # Always use the global/default client certificate material for secure connections.
            if conn.cert_file and conn.key_file:
                cert_file, key_file = conn.cert_file, conn.key_file
            else:
                cert_file, key_file = ensure_client_certificates()
            await client.set_security_string(
                f"{auth_policy.to_asyncua_format()},{conn.security_mode},{cert_file},{key_file}"
            )
            replacement_server_uri = conn.url
            try:
                endpoints = await client.connect_and_get_server_endpoints()
                for endpoint in endpoints:
                    policy_short = (getattr(endpoint, "SecurityPolicyUri", "") or "").rsplit("#", 1)[-1] or "None"
                    mode_name = getattr(getattr(endpoint, "SecurityMode", None), "name", "")
                    normalized_mode = "None_" if mode_name == "None" else mode_name
                    if policy_short == auth_policy.value and normalized_mode == conn.security_mode:
                        advertised_uri = str(getattr(getattr(endpoint, "Server", None), "ApplicationUri", "") or "")
                        if advertised_uri:
                            replacement_server_uri = advertised_uri
                        break
            except Exception:
                pass
            patch_create_session_server_uri(client, replacement_server_uri)
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
        self.query_one(AlarmTableWidget).add_event(message.alarm)

    def on_connection_state(self, message: ConnectionState) -> None:
        status = self.query_one(ConnectionStatusWidget)
        status.endpoint = self.config.connection.url
        status.security_mode = self.config.connection.security_mode
        status.connected = message.connected
        status.reconnecting = message.reconnecting
        status.error = message.error

    def on_node_tree_data(self, message: NodeTreeData) -> None:
        self.query_one(NodeTreeWidget).set_tree_data(message.tree_data)
        self.query_one(NodeInfoPanelWidget).set_copy_feedback("")

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

    def action_toggle_node_selection(self) -> None:
        tree = self.query_one(NodeTreeWidget)
        if not tree.has_focus:
            return

        node_id, is_selected = tree.toggle_cursor_selection()
        panel = self.query_one(NodeInfoPanelWidget)
        if not node_id:
            panel.set_copy_feedback("Current row is not selectable.")
            return

        if is_selected:
            panel.set_copy_feedback(f"Added to selection: {node_id}")
        else:
            panel.set_copy_feedback(f"Removed from selection: {node_id}")

    def action_clear_node_selection(self) -> None:
        tree = self.query_one(NodeTreeWidget)
        if not tree.has_focus:
            return

        cleared = tree.clear_selected_nodes()
        panel = self.query_one(NodeInfoPanelWidget)
        if cleared:
            panel.set_copy_feedback(f"Cleared selection ({cleared} node IDs).")
        else:
            panel.set_copy_feedback("No node selections to clear.")

    def _copy_node_id_to_clipboard(self, node_ids: list[str]) -> None:
        panel = self.query_one(NodeInfoPanelWidget)

        if not node_ids:
            panel.set_copy_feedback("No node selected to copy.")
            return

        payload = "\n".join(node_ids)
        try:
            self.copy_to_clipboard(payload)
            if len(node_ids) == 1:
                panel.set_copy_feedback(f"Copied Node ID: {node_ids[0]}")
                _logger.info("Copied selected Node ID to clipboard")
            else:
                panel.set_copy_feedback(f"Copied {len(node_ids)} Node IDs")
                _logger.info("Copied %d selected Node IDs to clipboard", len(node_ids))
        except Exception as exc:
            panel.set_copy_feedback(f"Copy failed: {exc}")
            _logger.exception("Failed to copy selected Node ID to clipboard")

    def action_copy_selected_node_id(self) -> None:
        tree = self.query_one(NodeTreeWidget)
        selected_node_ids = tree.get_selected_node_ids()
        if selected_node_ids:
            self._copy_node_id_to_clipboard(selected_node_ids)
            return

        node_id: str | None = None
        if self._selected_node:
            node_id = str(self._selected_node.get("id", "")) or None
        self._copy_node_id_to_clipboard([node_id] if node_id else [])

    @on(NodeInfoPanelWidget.CopyNodeIdRequested)
    def on_node_info_copy_requested(self, message: NodeInfoPanelWidget.CopyNodeIdRequested) -> None:
        self.action_copy_selected_node_id()

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

    def action_focus_search(self) -> None:
        search_input = self.query_one("#node-search", Input)
        search_input.focus()

    @on(Input.Submitted, "#node-search")
    def action_search_nodes(self, event: Input.Submitted) -> None:
        query = event.value.strip().lower()
        tree = self.query_one("#node-tree", NodeTreeWidget)

        if not query:
            self._search_query = ""
            self._search_results = []
            event.control.border_title = ""
            return

        if self._search_query != query:
            self._search_query = query
            self._search_results = []
            self._search_index = 0

            def _search_recursive(node: Any) -> None:
                if tree.is_placeholder_node(node):
                    return

                node_data = getattr(node, "data", None)
                if isinstance(node_data, dict):
                    name = str(node_data.get("name", "")).lower()
                    if query in name:
                        self._search_results.append(node)

                for child in node.children:
                    _search_recursive(child)

            _search_recursive(tree.root)
        else:
            if self._search_results:
                self._search_index = (self._search_index + 1) % len(self._search_results)

        if self._search_results:
            target_node = self._search_results[self._search_index]

            parent = getattr(target_node, "parent", None)
            while parent is not None:
                if getattr(parent, "allow_expand", False) and not getattr(parent, "is_expanded", False):
                    parent.expand()
                parent = getattr(parent, "parent", None)

            tree.focus_node(target_node)
            event.control.border_title = f"Matches ({self._search_index + 1}/{len(self._search_results)})"
        else:
            event.control.border_title = "No matches"

    def action_toggle_main_tab(self) -> None:
        tabbed = self.query_one("#tabbed-panel", TabbedContent)
        tabbed.active = "tab-node-info" if tabbed.active == "tab-alarms" else "tab-alarms"

    def action_show_alarm_tab(self) -> None:
        self.query_one("#tabbed-panel", TabbedContent).active = "tab-alarms"

    @on(TabbedContent.TabActivated, "#tabbed-panel")
    def on_main_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        # Use the activated pane's id to decide whether to start/stop log refresh.
        tab_id = getattr(event.pane, "id", None)
        if tab_id == "tab-logs":
            # When entering Logs tab, load all existing logs and start the refresh loop.
            self._load_all_logs()
            self._start_log_refresh_loop()
        else:
            # When leaving Logs tab, stop the refresh loop.
            self._stop_log_refresh_loop()

    async def action_quit(self) -> None:
        self._shutdown_requested = True
        self._stop_log_refresh_loop()
        if self._runner_task and not self._runner_task.done():
            self._runner_task.cancel()
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass

        await self._cleanup_client()
        if self._log_handler:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler.close()
        self.exit()
