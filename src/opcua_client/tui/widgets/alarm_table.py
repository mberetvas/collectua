from __future__ import annotations

from collections import deque
from datetime import datetime

from rich.text import Text
from textual.widgets import DataTable

from opcua_client.domain.alarm import Alarm


class AlarmTableWidget(DataTable):
    def __init__(self, max_rows: int = 1000, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_rows = max_rows
        self._keys = deque()
        self._alarms_by_key: dict[object, Alarm] = {}

    def on_mount(self) -> None:
        self.border_title = "Live Alarms"
        self.cursor_type = "row"
        self.add_columns("Time", "Severity", "Source", "Message", "Condition")

    def add_event(self, alarm: Alarm) -> None:
        ts = self._format_time(alarm.timestamp_utc.isoformat())
        sev = alarm.severity.value
        src = alarm.source_name
        msg = alarm.message
        cond = alarm.condition_name

        sev_cell = Text(sev, style=self._severity_style(sev))
        key = self.add_row(ts, sev_cell, src, msg, cond)
        self._keys.append(key)
        self._alarms_by_key[key] = alarm
        self._trim_rows_if_needed()
        try:
            self.scroll_end(animate=False)
        except Exception:
            pass

    def _trim_rows_if_needed(self) -> None:
        while len(self._keys) > self.max_rows:
            key = self._keys.popleft()
            self._alarms_by_key.pop(key, None)
            try:
                self.remove_row(key)
            except Exception:
                continue

    def get_selected_alarm(self) -> Alarm | None:
        row_index = self.cursor_row
        if row_index < 0 or row_index >= len(self._keys):
            return None
        try:
            key = list(self._keys)[row_index]
        except IndexError:
            return None
        return self._alarms_by_key.get(key)

    @staticmethod
    def _severity_style(severity: str) -> str:
        try:
            value = int(severity)
        except (TypeError, ValueError):
            return "#8aff80"

        if value >= 700:
            return "bold #ff5f5f"
        if value >= 400:
            return "bold #ffbf4d"
        return "bold #8aff80"

    @staticmethod
    def _format_time(timestamp: str) -> str:
        if not timestamp:
            return "-"
        try:
            ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return ts.strftime("%H:%M:%S")
        except ValueError:
            return timestamp[:8] if len(timestamp) >= 8 else timestamp
