from __future__ import annotations

import logging

from rich.text import Text
from textual.widgets import RichLog


class LogStreamWidget(RichLog):
    def on_mount(self) -> None:
        self.border_title = "Logs"


class TuiLogHandler(logging.Handler):
    def __init__(self, widget: LogStreamWidget):
        super().__init__()
        self.widget = widget
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.widget.write(Text(msg, style=self._style_for(record.levelno)))
        except Exception:
            self.handleError(record)

    @staticmethod
    def _style_for(level: int) -> str:
        if level >= logging.ERROR:
            return "bold #f7768e"
        if level >= logging.WARNING:
            return "bold #e0af68"
        if level >= logging.INFO:
            return "#9ece6a"
        return "#7aa2f7"
