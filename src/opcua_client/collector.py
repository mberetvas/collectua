"""
OPC UA Alarm Collector — MVP

Long-running script that:
  - Connects to S1500 OPC UA server (no security)
    - Subscribes to alarms/events (ConditionType)
  - Prints to console + appends to CSV
  - Auto-reconnects if connection drops
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Protocol

from asyncua import Client, ua

from opcua_client.condition_refresh import condition_refresh_with_retry
from opcua_client.domain.alarm import Alarm
from opcua_client.env_defaults import get_float, get_int, get_str
from opcua_client.infrastructure.asyncua_adapter import event_to_alarm
from opcua_client.infrastructure.csv_writer import CSVAlarmWriter
from opcua_client.infrastructure.repositories import InMemoryAlarmRepository

# ──────────────────────── CONFIG ────────────────────────
CSV_FILE = get_str("OPCUA_CSV_FILE", "alarms.csv")
PUBLISH_INTERVAL_MS = get_int("OPCUA_PUBLISH_INTERVAL_MS", 500)
RECONNECT_DELAY_SEC = get_int("OPCUA_RECONNECT_DELAY_SEC", 5)
TIMEOUT = get_float("OPCUA_TIMEOUT", 30.0)
# ────────────────────────────────────────────────────────

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

_logger = logging.getLogger("collector")


class AlarmEventHandler(Protocol):
    """
    Minimal protocol for alarm/event handlers used by the collector core.

    Both CLI and TUI handlers implement this implicitly (duck-typing).
    """

    def event_notification(self, event) -> None: ...

    def status_change_notification(self, status) -> None: ...


class AlarmHandler:
    """
    Event handler for OPC UA subscriptions.
    On each event notification: prints to console and appends to CSV.
    """

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self._writer = CSVAlarmWriter(csv_path)
        self._alarms = InMemoryAlarmRepository()
        self._alarm_index: dict[str, Alarm] = {}

    @staticmethod
    def _condition_id_from_event(event) -> Optional[str]:
        """Compatibility helper (used by tests)."""

        value = getattr(event, "ConditionId", None)
        if value is None:
            return None
        if isinstance(value, ua.NodeId):
            return value.to_string()
        to_string = getattr(value, "to_string", None)
        if callable(to_string):
            return str(to_string())
        return str(value)

    @staticmethod
    def _bool_from_state(state) -> Optional[bool]:
        """Compatibility helper (used by tests)."""

        if state is None:
            return None
        try:
            inner = getattr(state, "Id", state)
        except Exception:
            inner = state
        try:
            return bool(inner)
        except Exception:
            return None

    def _update_active_alarms(self, row_or_alarm: Mapping[str, Any] | Alarm, event: Any = None) -> None:
        """Compatibility: accepts either a row mapping (legacy) or a domain Alarm."""

        _ = event
        if isinstance(row_or_alarm, Alarm):
            alarm = row_or_alarm
        else:
            condition_id = row_or_alarm.get("condition_id")
            if not condition_id:
                return
            alarm = Alarm.from_values(
                alarm_id=str(condition_id),
                condition_name=str(row_or_alarm.get("condition_name", "")),
                source_name=str(row_or_alarm.get("source_name", "")),
                message=str(row_or_alarm.get("message", "")),
                severity=row_or_alarm.get("severity"),
                timestamp_utc=row_or_alarm.get("timestamp_utc"),
                retain=_normalize_optional_bool(row_or_alarm.get("retain")),
                active_state=_normalize_optional_bool(row_or_alarm.get("active_state")),
                acked_state=_normalize_optional_bool(row_or_alarm.get("acked_state")),
                event_type=str(row_or_alarm.get("event_type", "")),
                event_id=str(row_or_alarm.get("event_id", "")),
                raw=str(row_or_alarm.get("raw", "")),
            )

        _logger.debug("Upserting alarm for ConditionId=%s", alarm.alarm_id)
        self._alarms.add(alarm)
        self._alarm_index[str(alarm.alarm_id)] = alarm

    def get_active_alarms(self) -> Mapping[str, Alarm]:
        """Return a read-only view of the currently active alarms."""
        return {alarm_id: alarm for alarm_id, alarm in self._alarm_index.items() if alarm.retain is not False}

    def event_notification(self, event):
        """Called automatically by asyncua on each event."""
        try:
            _logger.debug("RAW EVENT RECEIVED: %s", event)
            alarm = event_to_alarm(event)
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

            self._update_active_alarms(alarm)

            _logger.info(
                "[%s]  SEV=%s  SRC=%s  MSG=%s",
                row["timestamp_utc"],
                row["severity"],
                row["source_name"],
                row["message"],
            )

            self._writer.write_alarm(alarm)

        except Exception:
            _logger.exception("Failed to process event")

    def status_change_notification(self, status):
        _logger.warning("Subscription status changed: %s", status)


def _normalize_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        return None
    try:
        return bool(value)
    except Exception:
        return None


async def connect(endpoint: str, timeout: float = TIMEOUT) -> Client:
    """Create and connect an OPC UA client (no security).

    This helper is primarily used by the CLI collector loop. The TUI uses its
    own client factory that also configures security, but reuses the shared
    subscription helpers below.
    """
    client = Client(url=endpoint, timeout=timeout)
    await client.connect()
    _logger.info("Connected to %s", endpoint)
    return client


async def subscribe(
    client: Client,
    handler: AlarmEventHandler,
    publish_interval_ms: int = PUBLISH_INTERVAL_MS,
    *,
    enable_condition_refresh: bool = True,
    is_active: Optional[Callable[[], bool]] = None,
):
    """
    Subscribe to all alarm events from the Server node.

    This is the shared subscription helper used by both the CLI collector loop
    and the TUI dashboard. It encapsulates the subscription creation,
    event-type selection and optional ConditionRefresh.
    """
    subscription = await client.create_subscription(
        period=publish_interval_ms,
        handler=handler,
    )

    server_node = client.get_node(ua.ObjectIds.Server)
    # Subscribe to both BaseEventType (general) and ConditionType (Siemens A&C alarms).
    # where_clause_generation=False prevents asyncua from building a strict EventFilter
    # WhereClause that Siemens S7-1500 rejects, causing silent event drops.
    await subscription.subscribe_events(
        sourcenode=server_node,
        evtypes=[ua.ObjectIds.BaseEventType, ua.ObjectIds.ConditionType],
        where_clause_generation=False,
    )
    _logger.info("Subscribed to BaseEventType and ConditionType alarms & events")

    if enable_condition_refresh:

        async def _run_condition_refresh() -> None:
            # Delay ConditionRefresh slightly so the subscription is fully established.
            await asyncio.sleep(2.0)
            if is_active is not None and not is_active():
                _logger.info(
                    "Skipping ConditionRefresh for SubscriptionId=%s: collector no longer active",
                    subscription.subscription_id,
                )
                return

            await condition_refresh_with_retry(
                server_node=server_node,
                subscription_id=subscription.subscription_id,
                logger=_logger,
                is_active=is_active,
            )

        # For long-running UI integrations, run ConditionRefresh in the background so it
        # does not block the caller. For simple CLI usage we can run it inline.
        if is_active is None:
            await _run_condition_refresh()
        else:
            asyncio.create_task(_run_condition_refresh())

    return subscription


async def run(
    endpoint: str,
    csv_file: str = CSV_FILE,
    publish_interval_ms: int = PUBLISH_INTERVAL_MS,
    reconnect_delay_sec: int = RECONNECT_DELAY_SEC,
    timeout: float = TIMEOUT,
):
    """Main loop with auto-reconnect. Core callable for the CLI.

    This is a thin wrapper around the shared subscription helper and AlarmHandler.
    """
    handler = AlarmHandler(csv_file)

    while True:
        client = None
        subscription = None

        try:
            client = await connect(endpoint, timeout=timeout)
            subscription = await subscribe(
                client,
                handler,
                publish_interval_ms=publish_interval_ms,
                enable_condition_refresh=True,
                is_active=None,
            )

            _logger.info("Listening for alarms... (Ctrl+C to stop)")
            while True:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            _logger.info("Stopped by user")
            break

        except Exception:
            _logger.exception("Connection error")
            _logger.info("Reconnecting in %ds...", reconnect_delay_sec)
            await asyncio.sleep(reconnect_delay_sec)

        finally:
            try:
                if subscription:
                    await subscription.delete()
            except Exception:
                pass
            try:
                if client:
                    await client.disconnect()
                    _logger.info("Disconnected")
            except Exception:
                pass


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    print("=" * 50)
    print("  OPC UA Alarm Collector — MVP")
    print("=" * 50)
    asyncio.run(run())


if __name__ == "__main__":
    main()
