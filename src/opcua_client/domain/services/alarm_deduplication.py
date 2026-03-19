from __future__ import annotations

from dataclasses import dataclass

from opcua_client.domain.alarm import Alarm


@dataclass
class AlarmDeduplicationResult:
    should_emit: bool
    reason: str


class AlarmDeduplicator:
    """Deduplicate alarm updates by (AlarmId, key state fields).

    This is intentionally conservative: if any key field changes, emit.
    """

    def __init__(self) -> None:
        self._last_by_id: dict[str, Alarm] = {}

    def consider(self, alarm: Alarm) -> AlarmDeduplicationResult:
        key = str(alarm.alarm_id)
        previous = self._last_by_id.get(key)
        if previous is None:
            self._last_by_id[key] = alarm
            return AlarmDeduplicationResult(should_emit=True, reason="first_seen")

        if _equivalent(previous, alarm):
            return AlarmDeduplicationResult(should_emit=False, reason="no_material_change")

        self._last_by_id[key] = alarm
        return AlarmDeduplicationResult(should_emit=True, reason="material_change")


def _equivalent(a: Alarm, b: Alarm) -> bool:
    return (
        a.retain == b.retain
        and a.active_state == b.active_state
        and a.acked_state == b.acked_state
        and a.severity == b.severity
        and a.message == b.message
        and a.source_name == b.source_name
        and a.condition_name == b.condition_name
    )

