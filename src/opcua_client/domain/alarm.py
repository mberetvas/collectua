from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .exceptions import AlarmValidationError, InvalidAlarmSeverity


class AlarmSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_value(cls, value: str | int | None) -> "AlarmSeverity":
        if value is None:
            return cls.LOW

        if isinstance(value, int):
            if value >= 800:
                return cls.CRITICAL
            if value >= 600:
                return cls.HIGH
            if value >= 300:
                return cls.MEDIUM
            return cls.LOW

        normalized = str(value).strip().upper()
        if normalized in cls.__members__:
            return cls[normalized]

        try:
            numeric = int(normalized)
        except ValueError as exc:
            raise InvalidAlarmSeverity(f"Unsupported alarm severity value: {value!r}") from exc
        return cls.from_value(numeric)


@dataclass(frozen=True)
class AlarmId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise AlarmValidationError("AlarmId cannot be empty")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Alarm:
    alarm_id: AlarmId
    condition_name: str
    source_name: str
    message: str
    severity: AlarmSeverity
    timestamp_utc: datetime
    retain: bool | None = None
    active_state: bool | None = None
    acked_state: bool | None = None
    event_type: str = ""
    event_id: str = ""
    raw: str = ""

    def __post_init__(self) -> None:
        if not self.condition_name.strip():
            raise AlarmValidationError("condition_name cannot be empty")
        if not self.source_name.strip():
            raise AlarmValidationError("source_name cannot be empty")
        if self.timestamp_utc.tzinfo is None:
            raise AlarmValidationError("timestamp_utc must be timezone-aware")

    @classmethod
    def from_values(
        cls,
        *,
        alarm_id: str,
        condition_name: str,
        source_name: str,
        message: str,
        severity: str | int | None,
        timestamp_utc: datetime | str | None,
        retain: bool | None = None,
        active_state: bool | None = None,
        acked_state: bool | None = None,
        event_type: str = "",
        event_id: str = "",
        raw: str = "",
    ) -> "Alarm":
        parsed_timestamp = _parse_timestamp(timestamp_utc)
        return cls(
            alarm_id=AlarmId(alarm_id),
            condition_name=condition_name,
            source_name=source_name,
            message=message,
            severity=AlarmSeverity.from_value(severity),
            timestamp_utc=parsed_timestamp,
            retain=retain,
            active_state=active_state,
            acked_state=acked_state,
            event_type=event_type,
            event_id=event_id,
            raw=raw,
        )

    def is_active(self) -> bool:
        return bool(self.active_state)

    def is_acknowledged(self) -> bool:
        return bool(self.acked_state)

    def is_retained(self) -> bool:
        return bool(self.retain)


def _parse_timestamp(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise AlarmValidationError(f"Invalid timestamp value: {value!r}") from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
