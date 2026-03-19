from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from opcua_client.tui.widgets.log_stream import SqliteLogRow, TuiSqliteLogHandler


def test_sqlite_handler_writes_and_reads_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "logs.db"
    handler = TuiSqliteLogHandler(db_path, retention_days=7)

    record1 = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="first message",
        args=(),
        exc_info=None,
    )
    record2 = logging.LogRecord(
        name="test.logger",
        level=logging.ERROR,
        pathname=__file__,
        lineno=0,
        msg="second message",
        args=(),
        exc_info=None,
    )

    handler.emit(record1)
    handler.emit(record2)

    rows = handler.fetch_since(last_id=0)
    assert len(rows) == 2
    assert [row.message for row in rows] == [
        handler.format(record1),
        handler.format(record2),
    ]
    assert rows[0].levelno == logging.INFO
    assert rows[1].levelno == logging.ERROR


def test_sqlite_handler_retention_drops_old_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "logs.db"
    handler = TuiSqliteLogHandler(db_path, retention_days=1)

    # Insert a row directly with an old timestamp
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    old_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)
    conn.execute(
        "INSERT INTO logs (timestamp_utc, timestamp_epoch, levelno, levelname, logger_name, message) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (old_dt.isoformat(), old_dt.timestamp(), logging.INFO, "INFO", "test.logger", "old message"),
    )
    conn.commit()
    conn.close()

    # Emitting a new record should trigger retention cleanup eventually
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="new message",
        args=(),
        exc_info=None,
    )
    handler._last_cleanup = datetime.now(timezone.utc) - timedelta(seconds=61)
    handler.emit(record)

    rows = handler.fetch_since(last_id=0)
    messages = [row.message for row in rows]
    # Old message should have been removed, only formatted new record should remain
    assert any("new message" in msg for msg in messages)
    assert not any("old message" in msg for msg in messages)


def test_sqlite_handler_migrates_legacy_schema_and_backfills_epoch(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_logs.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            levelno INTEGER NOT NULL,
            levelname TEXT NOT NULL,
            logger_name TEXT NOT NULL,
            message TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO logs (timestamp_utc, levelno, levelname, logger_name, message) VALUES (?, ?, ?, ?, ?)",
        ("2024-01-01T12:00:00Z", logging.INFO, "INFO", "legacy.logger", "legacy row"),
    )
    conn.commit()
    conn.close()

    handler = TuiSqliteLogHandler(db_path, retention_days=7)
    pragma_rows = handler._conn.execute("PRAGMA table_info(logs)").fetchall()
    column_names = {str(row[1]) for row in pragma_rows}
    assert "timestamp_epoch" in column_names

    epoch_value = handler._conn.execute(
        "SELECT timestamp_epoch FROM logs WHERE message = 'legacy row'"
    ).fetchone()
    assert epoch_value is not None
    assert isinstance(epoch_value[0], float)
    assert epoch_value[0] > 0

    handler.close()


def test_sqlite_handler_retention_uses_epoch_not_text_order(tmp_path: Path) -> None:
    db_path = tmp_path / "logs.db"
    handler = TuiSqliteLogHandler(db_path, retention_days=1)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=handler.retention_days)
    old_dt = cutoff - timedelta(seconds=2)
    recent_dt = cutoff + timedelta(seconds=2)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute(
        "INSERT INTO logs (timestamp_utc, timestamp_epoch, levelno, levelname, logger_name, message) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            old_dt.replace(microsecond=123000).isoformat(),
            old_dt.timestamp(),
            logging.INFO,
            "INFO",
            "test.logger",
            "old mixed format",
        ),
    )
    conn.execute(
        "INSERT INTO logs (timestamp_utc, timestamp_epoch, levelno, levelname, logger_name, message) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            recent_dt.replace(microsecond=0).isoformat(),
            recent_dt.timestamp(),
            logging.INFO,
            "INFO",
            "test.logger",
            "recent no fractional",
        ),
    )
    conn.commit()
    conn.close()

    # Force cleanup on next emit.
    handler._last_cleanup = now - timedelta(seconds=61)
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="trigger cleanup",
        args=(),
        exc_info=None,
    )
    handler.emit(record)

    rows = handler.fetch_since(last_id=0)
    messages = [row.message for row in rows]
    assert not any("old mixed format" in msg for msg in messages)
    assert any("recent no fractional" in msg for msg in messages)
