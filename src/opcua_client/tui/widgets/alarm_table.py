from __future__ import annotations

from collections import deque
from datetime import datetime

from rich.text import Text
from textual.widgets import DataTable


class AlarmTableWidget(DataTable):
    def __init__(self, max_rows: int = 1000, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_rows = max_rows
        self._keys = deque()

    def on_mount(self) -> None:
        self.border_title = "Live Alarms"
        self.cursor_type = "row"
        self.add_columns("Time", "Severity", "Source", "Message", "Condition")

    def add_event(self, row: dict[str, str]) -> None:
        ts = self._format_time(row.get("timestamp_utc", ""))
        sev = row.get("severity", "")
        src = row.get("source_name", "")
        msg = row.get("message", "")
        cond = row.get("condition_name", "")

        sev_cell = Text(sev, style=self._severity_style(sev))
        key = self.add_row(ts, sev_cell, src, msg, cond)
        self._keys.append(key)
        self._trim_rows_if_needed()
        try:
            self.scroll_end(animate=False)
        except Exception:
            pass

    def _trim_rows_if_needed(self) -> None:
        while len(self._keys) > self.max_rows:
            key = self._keys.popleft()
            try:
                self.remove_row(key)
            except Exception:
                continue

    @staticmethod
    def _severity_style(severity: str) -> str:
        try:
            value = int(severity)
        except (TypeError, ValueError):
            return "white"

        if value >= 700:
            return "bold #f7768e"
        if value >= 400:
            return "bold #e0af68"
        return "bold #9ece6a"

    @staticmethod
    def _format_time(timestamp: str) -> str:
        if not timestamp:
            return "-"
        try:
            ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return ts.strftime("%H:%M:%S")
        except ValueError:
            return timestamp[:8] if len(timestamp) >= 8 else timestamp
