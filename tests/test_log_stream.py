from __future__ import annotations

import logging
import sqlite3
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
    conn.execute(
        "INSERT INTO logs (timestamp_utc, levelno, levelname, logger_name, message) "
        "VALUES ('2000-01-01T00:00:00+00:00', ?, ?, ?, ?)",
        (logging.INFO, "INFO", "test.logger", "old message"),
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
    handler.emit(record)

    rows = handler.fetch_since(last_id=0)
    messages = [row.message for row in rows]
    # Old message should have been removed, only formatted new record should remain
    assert any("new message" in msg for msg in messages)
    assert not any("old message" in msg for msg in messages)
