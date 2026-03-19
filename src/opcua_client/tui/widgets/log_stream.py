from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

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

    def export_text(
        self, min_level: int = logging.NOTSET, exact_level: int | None = None
    ) -> str:
        """
        Export the current buffer as plain text in the same order as rendered
        (newest first). Pass ``min_level`` to include only entries at or above
        that severity (e.g. ``logging.ERROR``). Pass ``exact_level`` to include
        only that exact severity.
        """
        # Rich/Textual renderables are stored oldest->newest; UI shows newest->oldest.
        lines: list[str] = []
        for levelno, entry in reversed(self._entries):
            if exact_level is not None and levelno != exact_level:
                continue
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
                timestamp_epoch REAL NOT NULL,
                levelno INTEGER NOT NULL,
                levelname TEXT NOT NULL,
                logger_name TEXT NOT NULL,
                message TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp_utc)"
        )
        self._ensure_timestamp_epoch_column()
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_logs_timestamp_epoch ON logs(timestamp_epoch)"
        )
        self._conn.commit()
        self._last_cleanup: datetime = datetime.now(timezone.utc)
        # Optional async queue for offloading writes from the UI event loop.
        # When set by the TUI application, `emit` will enqueue records instead
        # of writing to SQLite synchronously.
        self._async_queue = None
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s", "%Y-%m-%dT%H:%M:%S"
            )
        )
        self.createLock()

    def _ensure_timestamp_epoch_column(self) -> None:
        columns = self._conn.execute("PRAGMA table_info(logs)").fetchall()
        if any(str(column[1]) == "timestamp_epoch" for column in columns):
            return

        self._conn.execute("ALTER TABLE logs ADD COLUMN timestamp_epoch REAL")
        rows = self._conn.execute(
            "SELECT id, timestamp_utc FROM logs WHERE timestamp_epoch IS NULL"
        ).fetchall()
        for row_id, timestamp_utc in rows:
            parsed_epoch = self._parse_timestamp_utc(timestamp_utc)
            # Keep malformed legacy rows from breaking startup.
            self._conn.execute(
                "UPDATE logs SET timestamp_epoch = ? WHERE id = ?",
                (parsed_epoch if parsed_epoch is not None else 0.0, row_id),
            )

    @staticmethod
    def _parse_timestamp_utc(value: str) -> float | None:
        try:
            normalized = value.strip()
            if normalized.endswith("Z"):
                normalized = f"{normalized[:-1]}+00:00"
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except Exception:
            return None

    def set_async_queue(self, queue) -> None:
        """
        Configure an asyncio-compatible queue used to offload writes.

        The queue is intentionally untyped here to avoid importing asyncio in
        this module; the TUI app passes in an `asyncio.Queue` instance.
        """
        self._async_queue = queue

    def _write_record_sync(
        self,
        *,
        timestamp: str,
        timestamp_epoch: float,
        levelno: int,
        levelname: str,
        logger_name: str,
        message: str,
    ) -> None:
        self.acquire()
        try:
            self._conn.execute(
                "INSERT INTO logs (timestamp_utc, timestamp_epoch, levelno, levelname, logger_name, message) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    timestamp,
                    timestamp_epoch,
                    levelno,
                    levelname,
                    logger_name,
                    message,
                ),
            )
            now = datetime.now(timezone.utc)
            if now - self._last_cleanup >= timedelta(seconds=60):
                cutoff = now - timedelta(days=self.retention_days)
                self._conn.execute(
                    "DELETE FROM logs WHERE timestamp_epoch < ?",
                    (cutoff.timestamp(),),
                )
                self._last_cleanup = now
            self._conn.commit()
        except Exception:
            self.handleError(record)
        finally:
            self.release()

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()
        timestamp_epoch = now.timestamp()

        # When an async queue is configured (TUI context), enqueue the payload
        # so SQLite writes can happen in a dedicated worker task instead of
        # blocking the logging caller.
        if self._async_queue is not None:
            try:
                self._async_queue.put_nowait(
                    (
                        timestamp,
                        timestamp_epoch,
                        record.levelno,
                        record.levelname,
                        record.name,
                        msg,
                    )
                )
                return
            except Exception:
                # Fall back to synchronous behavior on enqueue failures.
                pass

        self._write_record_sync(
            timestamp=timestamp,
            timestamp_epoch=timestamp_epoch,
            levelno=record.levelno,
            levelname=record.levelname,
            logger_name=record.name,
            message=msg,
        )

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

    def fetch_recent(self, limit: int = 1000) -> List[SqliteLogRow]:
        """
        Fetch the most recent rows ordered descending by id (newest first).
        """
        self.acquire()
        try:
            cur = self._conn.execute(
                "SELECT id, timestamp_utc, levelno, levelname, logger_name, message "
                "FROM logs ORDER BY id DESC LIMIT ?",
                (limit,),
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
