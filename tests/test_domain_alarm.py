from __future__ import annotations

from datetime import datetime, timezone

import pytest

from opcua_client.domain.alarm import Alarm, AlarmId, AlarmSeverity
from opcua_client.domain.exceptions import AlarmValidationError, InvalidAlarmSeverity


def test_alarm_id_validation() -> None:
    with pytest.raises(AlarmValidationError):
        AlarmId("")


def test_alarm_severity_mapping() -> None:
    assert AlarmSeverity.from_value(100) == AlarmSeverity.LOW
    assert AlarmSeverity.from_value(350) == AlarmSeverity.MEDIUM
    assert AlarmSeverity.from_value(700) == AlarmSeverity.HIGH
    assert AlarmSeverity.from_value(900) == AlarmSeverity.CRITICAL
    assert AlarmSeverity.from_value("critical") == AlarmSeverity.CRITICAL


def test_alarm_severity_invalid_text_raises() -> None:
    with pytest.raises(InvalidAlarmSeverity):
        AlarmSeverity.from_value("banana")


def test_alarm_entity_state_helpers() -> None:
    alarm = Alarm.from_values(
        alarm_id="ns=2;s=alarm-1",
        condition_name="Overheat",
        source_name="Motor1",
        message="Motor overheat",
        severity=850,
        timestamp_utc=datetime.now(timezone.utc),
        retain=True,
        active_state=True,
        acked_state=False,
    )
    assert alarm.is_retained() is True
    assert alarm.is_active() is True
    assert alarm.is_acknowledged() is False


def test_alarm_timestamp_must_be_parseable() -> None:
    with pytest.raises(AlarmValidationError):
        Alarm.from_values(
            alarm_id="id-1",
            condition_name="x",
            source_name="y",
            message="m",
            severity=1,
            timestamp_utc="not-a-date",
        )
