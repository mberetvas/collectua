from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Protocol

from asyncua import Client

from opcua_client.domain.alarm import Alarm, AlarmId
from opcua_client.infrastructure.asyncua_adapter import event_to_alarm
from opcua_client.infrastructure.csv_writer import CSVAlarmWriter
from opcua_client.infrastructure.repositories import AlarmRepository


class AlarmSink(Protocol):
    def on_alarm(self, alarm: Alarm) -> None: ...


class AlarmCollectionService:
    """Use-case: collect alarms from an OPC UA subscription and persist them."""

    def __init__(
        self,
        *,
        repository: AlarmRepository,
        writer: CSVAlarmWriter | None = None,
        sink: AlarmSink | None = None,
    ) -> None:
        self._repository = repository
        self._writer = writer
        self._sink = sink

    def handle_event(self, event: Any) -> Alarm:
        alarm = event_to_alarm(event)
        self._repository.add(alarm)
        if self._writer is not None:
            self._writer.write_alarm(alarm)
        if self._sink is not None:
            self._sink.on_alarm(alarm)
        return alarm

    def get_active_by_id(self, alarm_id: str | AlarmId) -> Alarm | None:
        key = AlarmId(str(alarm_id)) if not isinstance(alarm_id, AlarmId) else alarm_id
        return self._repository.get_by_id(key)

    def to_row(self, alarm: Alarm) -> Mapping[str, str]:
        """Bridge for legacy UI/CSV expectations (stringly-typed dict)."""

        payload = asdict(alarm)
        return {
            "timestamp_utc": alarm.timestamp_utc.isoformat(),
            "event_type": alarm.event_type,
            "source_name": alarm.source_name,
            "message": alarm.message,
            "severity": alarm.severity.value,
            "condition_name": alarm.condition_name,
            "event_id": alarm.event_id,
            "condition_id": str(alarm.alarm_id),
            "retain": "" if alarm.retain is None else str(bool(alarm.retain)),
            "active_state": "" if alarm.active_state is None else str(bool(alarm.active_state)),
            "acked_state": "" if alarm.acked_state is None else str(bool(alarm.acked_state)),
            "raw": alarm.raw or str(payload),
        }


async def subscribe_alarms(
    *,
    client: Client,
    handler: Any,
    publish_interval_ms: int,
    nodes: list[str] | None = None,
) -> Any:
    """Thin wrapper to keep legacy subscribe flow stable.

    The existing collector uses asyncua subscription callbacks; this helper exists
    for future migration of subscription wiring into the application layer.
    """

    subscription = await client.create_subscription(publish_interval_ms, handler)
    if nodes:
        for node_id in nodes:
            node = client.get_node(node_id)
            await subscription.subscribe_data_change(node)
    return subscription

