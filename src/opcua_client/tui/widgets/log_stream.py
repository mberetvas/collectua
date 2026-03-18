from __future__ import annotations

import logging

from rich.text import Text
from textual.widgets import RichLog


class LogStreamWidget(RichLog):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._entries: list[tuple[int, Text]] = []

    def on_mount(self) -> None:
        self.border_title = "Logs"
        # Disable auto scroll so the view doesn't jump back to the
        # bottom while the user is scrolling through earlier log lines.
        self.auto_scroll = False

    def add_entry(self, entry: Text, levelno: int = logging.NOTSET) -> None:
        """Add a log entry, rendering newest entries at the top."""
        self._entries.append((levelno, entry))

        max_lines = getattr(self, "max_lines", None)
        if isinstance(max_lines, int) and max_lines > 0:
            overflow = len(self._entries) - max_lines
            if overflow > 0:
                self._entries = self._entries[overflow:]

        self.clear()
        for _level, renderable in reversed(self._entries):
            # scroll_end=False so we don't jump the viewport while the
            # user is reading older entries.
            self.write(renderable, scroll_end=False)

    def export_text(self, min_level: int = logging.NOTSET) -> str:
        """
        Export the current buffer as plain text in the same order as rendered
        (newest first).  Pass ``min_level`` to include only entries at or above
        that severity (e.g. ``logging.ERROR``).
        """
        # Rich/Textual renderables are stored oldest->newest; UI shows newest->oldest.
        lines: list[str] = []
        for levelno, entry in reversed(self._entries):
            if levelno < min_level:
                continue
            try:
                lines.append(entry.plain)
            except Exception:
                lines.append(str(entry))
        return "\n".join(lines).rstrip() + ("\n" if lines else "")


class TuiLogHandler(logging.Handler):
    def __init__(self, widget: LogStreamWidget):
        super().__init__()
        self.widget = widget
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.widget.add_entry(Text(msg, style=self._style_for(record.levelno)), levelno=record.levelno)
        except Exception:
            self.handleError(record)

    @staticmethod
    def _style_for(level: int) -> str:
        if level >= logging.ERROR:
            return "bold #ff5f5f"
        if level >= logging.WARNING:
            return "bold #ffbf4d"
        if level >= logging.INFO:
            return "#8aff80"
        return "#6ee768"
