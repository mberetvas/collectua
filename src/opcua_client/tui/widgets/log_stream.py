from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Tuple

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


def style_for_level(level: int) -> str:
    if level >= logging.ERROR:
        return "bold #ff5f5f"
    if level >= logging.WARNING:
        return "bold #ffbf4d"
    if level >= logging.INFO:
        return "#8aff80"
    return "#6ee768"


@dataclass
class SqliteLogRow:
    id: int
    timestamp_utc: str
    levelno: int
    levelname: str
    logger_name: str
    message: str


class TuiSqliteLogHandler(logging.Handler):
    """
    Logging handler that writes records to a SQLite database so the TUI Logs tab
    can query and render them on demand.
    """

    def __init__(self, db_path: Path, retention_days: int = 7) -> None:
        super().__init__()
        self.db_path = db_path
        self.retention_days = max(retention_days, 1)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT NOT NULL,
                levelno INTEGER NOT NULL,
                levelname TEXT NOT NULL,
                logger_name TEXT NOT NULL,
                message TEXT NOT NULL
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp_utc)")
        self._conn.commit()
        self._last_cleanup: datetime = datetime.now(timezone.utc)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%Y-%m-%dT%H:%M:%S"))
        self.createLock()

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        timestamp = datetime.now(timezone.utc).isoformat()
        self.acquire()
        try:
            self._conn.execute(
                "INSERT INTO logs (timestamp_utc, levelno, levelname, logger_name, message) VALUES (?, ?, ?, ?, ?)",
                (timestamp, record.levelno, record.levelname, record.name, msg),
            )
            now = datetime.now(timezone.utc)
            if now - self._last_cleanup >= timedelta(seconds=60):
                cutoff = now - timedelta(days=self.retention_days)
                self._conn.execute("DELETE FROM logs WHERE timestamp_utc < ?", (cutoff.isoformat(),))
                self._last_cleanup = now
            self._conn.commit()
        except Exception:
            self.handleError(record)
        finally:
            self.release()

    def fetch_since(self, last_id: int, limit: int = 1000) -> List[SqliteLogRow]:
        """
        Fetch rows with id > last_id ordered ascending so callers can append
        them in chronological order.
        """
        self.acquire()
        try:
            cur = self._conn.execute(
                "SELECT id, timestamp_utc, levelno, levelname, logger_name, message "
                "FROM logs WHERE id > ? ORDER BY id ASC LIMIT ?",
                (last_id, limit),
            )
            rows = [
                SqliteLogRow(
                    id=row[0],
                    timestamp_utc=row[1],
                    levelno=row[2],
                    levelname=row[3],
                    logger_name=row[4],
                    message=row[5],
                )
                for row in cur.fetchall()
            ]
            return rows
        finally:
            self.release()

    def close(self) -> None:
        try:
            if getattr(self, "_conn", None) is not None:
                self._conn.close()
        finally:
            super().close()
