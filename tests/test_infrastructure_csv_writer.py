from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opcua_client.domain.alarm import Alarm
from opcua_client.infrastructure.csv_writer import CSVAlarmWriter


def _make_alarm(alarm_id: str) -> Alarm:
    return Alarm.from_values(
        alarm_id=alarm_id,
        condition_name="Overheat",
        source_name="Motor1",
        message="too hot",
        severity=900,
        timestamp_utc=datetime.now(timezone.utc),
        retain=True,
        active_state=True,
        acked_state=False,
        event_type="ConditionType",
        event_id="evt-1",
        raw="dummy",
    )


def test_csv_writer_creates_header_and_writes_row(tmp_path: Path) -> None:
    target = tmp_path / "alarms.csv"
    writer = CSVAlarmWriter(str(target))
    writer.write_alarm(_make_alarm("ns=2;s=alarm-1"))

    content = target.read_text(encoding="utf-8")
    assert "condition_id" in content
    assert "ns=2;s=alarm-1" in content


def test_csv_writer_reads_alarm_history(tmp_path: Path) -> None:
    target = tmp_path / "alarms.csv"
    writer = CSVAlarmWriter(str(target))
    writer.write_alarm(_make_alarm("ns=2;s=alarm-1"))
    writer.write_alarm(_make_alarm("ns=2;s=alarm-2"))

    history = writer.get_alarm_history(limit=10)
    assert len(history) == 2
    assert str(history[0].alarm_id) == "ns=2;s=alarm-1"
