from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from opcua_client.domain.alarm import Alarm

CSV_HEADERS = [
    "timestamp_utc",
    "event_type",
    "source_name",
    "message",
    "severity",
    "condition_name",
    "event_id",
    "condition_id",
    "retain",
    "active_state",
    "acked_state",
    "raw",
]


class CSVAlarmWriter:
    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            with self.file_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
                writer.writeheader()

    def write_alarm(self, alarm: Alarm) -> None:
        row = {
            "timestamp_utc": alarm.timestamp_utc.isoformat(),
            "event_type": alarm.event_type,
            "source_name": alarm.source_name,
            "message": alarm.message,
            "severity": alarm.severity.value,
            "condition_name": alarm.condition_name,
            "event_id": alarm.event_id,
            "condition_id": str(alarm.alarm_id),
            "retain": alarm.retain,
            "active_state": alarm.active_state,
            "acked_state": alarm.acked_state,
            "raw": alarm.raw,
        }
        with self.file_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
            writer.writerow(row)

    def get_alarm_history(self, limit: int = 100) -> list[Alarm]:
        history: list[Alarm] = []
        with self.file_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if len(history) >= limit:
                    break
                history.append(
                    Alarm.from_values(
                        alarm_id=str(row.get("condition_id", "")),
                        condition_name=str(row.get("condition_name", "")),
                        source_name=str(row.get("source_name", "")),
                        message=str(row.get("message", "")),
                        severity=str(row.get("severity", "LOW")),
                        timestamp_utc=str(row.get("timestamp_utc", datetime.now(timezone.utc).isoformat())),
                        retain=_parse_bool(row.get("retain")),
                        active_state=_parse_bool(row.get("active_state")),
                        acked_state=_parse_bool(row.get("acked_state")),
                        event_type=str(row.get("event_type", "")),
                        event_id=str(row.get("event_id", "")),
                        raw=str(row.get("raw", "")),
                    )
                )
        return history


def _parse_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    return None
