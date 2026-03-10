from __future__ import annotations

from datetime import datetime

from textual.reactive import reactive
from textual.widgets import Static

RETRO_OK = "#8aff80"
RETRO_WARN = "#ffbf4d"
RETRO_ERR = "#ff5f5f"
RETRO_ACCENT = "#6ee768"


def _fmt_uptime(seconds: int) -> str:
    hours, rem = divmod(max(seconds, 0), 3600)
    minutes, sec = divmod(rem, 60)
    return f"{hours:02}:{minutes:02}:{sec:02}"


class ConnectionStatusWidget(Static):
    connected = reactive(False)
    reconnecting = reactive(False)
    endpoint = reactive("-")
    security_mode = reactive("None_")
    error = reactive("")
    _uptime_seconds = reactive(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._connected_since: datetime | None = None

    def on_mount(self) -> None:
        self.border_title = "Connection"
        self.set_interval(1.0, self._tick)
        self._refresh_content()

    def watch_connected(self, connected: bool) -> None:
        if connected and self._connected_since is None:
            self._connected_since = datetime.now()
            self._uptime_seconds = 0
        if not connected:
            self._connected_since = None
            self._uptime_seconds = 0
        self._refresh_content()

    def watch_reconnecting(self, reconnecting: bool) -> None:
        self._refresh_content()

    def watch_error(self, error: str) -> None:
        self._refresh_content()

    def _tick(self) -> None:
        if self.connected and self._connected_since is not None:
            self._uptime_seconds = int((datetime.now() - self._connected_since).total_seconds())
            self._refresh_content()

    def _refresh_content(self) -> None:
        if self.connected:
            color = RETRO_OK
            status = "Connected"
        elif self.reconnecting:
            color = RETRO_WARN
            status = "Reconnecting"
        else:
            color = RETRO_ERR
            status = "Disconnected"

        msg = self.error.strip()
        if len(msg) > 64:
            msg = msg[:61] + "..."

        line = (
            f"[bold {color}]● {status}[/]  "
            f"[{RETRO_ACCENT}]{self.endpoint}[/]  "
            f"security=[{RETRO_WARN}]{self.security_mode}[/]  "
            f"uptime=[{RETRO_OK}]{_fmt_uptime(self._uptime_seconds)}[/]"
        )
        if msg:
            line += f"  err=[{RETRO_WARN}]{msg}[/]"

        self.update(line)
