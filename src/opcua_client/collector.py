"""
OPC UA Alarm Collector — MVP

Long-running script that:
  - Connects to S1500 OPC UA server (no security)
    - Subscribes to alarms/events (ConditionType)
  - Prints to console + appends to CSV
  - Auto-reconnects if connection drops
"""

import asyncio
import csv
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from asyncua import Client, ua

from opcua_client.condition_refresh import condition_refresh_with_retry

# ──────────────────────── CONFIG ────────────────────────
CSV_FILE = "alarms.csv"
PUBLISH_INTERVAL_MS = 500
RECONNECT_DELAY_SEC = 5
TIMEOUT = 30.0
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


@dataclass(frozen=True)
class ActiveAlarm:
    """In-memory snapshot of an active alarm/condition keyed by ConditionId."""

    condition_id: str
    condition_name: str
    source_name: str
    message: str
    severity: str
    timestamp_utc: str
    retain: Optional[bool]
    active_state: Optional[bool]
    acked_state: Optional[bool]
    raw: str


class AlarmHandler:
    """
    Event handler for OPC UA subscriptions.
    On each event notification: prints to console and appends to CSV.
    """

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self._ensure_csv_header()
        self._active_alarms: Dict[str, ActiveAlarm] = {}

    def _ensure_csv_header(self):
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)

    @staticmethod
    def _condition_id_from_event(event) -> Optional[str]:
        value = getattr(event, "ConditionId", None)
        if value is None:
            return None
        # asyncua typically exposes a NodeId or Variant-like object; fall back to str().
        if isinstance(value, ua.NodeId):
            return value.to_string()
        to_string = getattr(value, "to_string", None)
        if callable(to_string):
            return to_string()
        return str(value)

    @staticmethod
    def _bool_from_state(state) -> Optional[bool]:
        if state is None:
            return None
        # Common A&C pattern: state.Id is a Variant/boolean; otherwise interpret directly.
        try:
            inner = getattr(state, "Id", state)
        except Exception:
            inner = state
        try:
            return bool(inner)
        except Exception:
            return None

    def _update_active_alarms(self, row: Mapping[str, Any], event) -> None:
        condition_id = row.get("condition_id")
        if not condition_id:
            return

        retain = row.get("retain")
        active_state = row.get("active_state")
        acked_state = row.get("acked_state")

        if isinstance(retain, str):
            retain_normalized: Optional[bool] = retain.lower() == "true"
        else:
            retain_normalized = bool(retain) if retain is not None else None

        active_alarm = ActiveAlarm(
            condition_id=condition_id,
            condition_name=str(row.get("condition_name", "")),
            source_name=str(row.get("source_name", "")),
            message=str(row.get("message", "")),
            severity=str(row.get("severity", "")),
            timestamp_utc=str(row.get("timestamp_utc", "")),
            retain=retain_normalized,
            active_state=bool(active_state) if active_state is not None else None,
            acked_state=bool(acked_state) if acked_state is not None else None,
            raw=str(row.get("raw", "")),
        )

        if retain_normalized is False:
            if condition_id in self._active_alarms:
                _logger.debug("Clearing active alarm for ConditionId=%s", condition_id)
                self._active_alarms.pop(condition_id, None)
            return

        _logger.debug("Upserting active alarm for ConditionId=%s", condition_id)
        self._active_alarms[condition_id] = active_alarm

    def get_active_alarms(self) -> Mapping[str, ActiveAlarm]:
        """Return a read-only view of the currently active alarms."""
        return dict(self._active_alarms)

    def event_notification(self, event):
        """Called automatically by asyncua on each event."""
        try:
            _logger.debug("RAW EVENT RECEIVED: %s", event)
            row = {
                "timestamp_utc": str(getattr(event, "Time", datetime.now(timezone.utc))),
                "event_type": str(getattr(event, "EventType", "")),
                "source_name": str(getattr(event, "SourceName", "")),
                "message": str(getattr(event, "Message", "")),
                "severity": str(getattr(event, "Severity", "")),
                "condition_name": str(getattr(event, "ConditionName", "")),
                "event_id": str(getattr(event, "EventId", "")),
                "condition_id": self._condition_id_from_event(event),
                "retain": getattr(event, "Retain", None),
                "active_state": self._bool_from_state(getattr(event, "ActiveState", None)),
                "acked_state": self._bool_from_state(getattr(event, "AckedState", None)),
                "raw": str(event),
            }

            self._update_active_alarms(row, event)

            _logger.info(
                "[%s]  SEV=%s  SRC=%s  MSG=%s",
                row["timestamp_utc"],
                row["severity"],
                row["source_name"],
                row["message"],
            )

            with open(self.csv_path, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                writer.writerow(row)

        except Exception:
            _logger.exception("Failed to process event")

    def status_change_notification(self, status):
        _logger.warning("Subscription status changed: %s", status)


async def connect(endpoint: str, timeout: float = TIMEOUT) -> Client:
    """Create and connect an OPC UA client (no security)."""
    client = Client(url=endpoint, timeout=timeout)
    await client.connect()
    _logger.info("Connected to %s", endpoint)
    return client


async def subscribe(client: Client, handler: AlarmHandler, publish_interval_ms: int = PUBLISH_INTERVAL_MS):
    """Subscribe to all alarm events from the Server node."""
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

    # Delay ConditionRefresh slightly so the subscription is fully established.
    await asyncio.sleep(2.0)
    await condition_refresh_with_retry(
        server_node=server_node,
        subscription_id=subscription.subscription_id,
        logger=_logger,
    )

    return subscription


async def run(
    endpoint: str,
    csv_file: str = CSV_FILE,
    publish_interval_ms: int = PUBLISH_INTERVAL_MS,
    reconnect_delay_sec: int = RECONNECT_DELAY_SEC,
    timeout: float = TIMEOUT,
):
    """Main loop with auto-reconnect. Core callable for CLI and future TUI."""
    handler = AlarmHandler(csv_file)

    while True:
        client = None
        subscription = None

        try:
            client = await connect(endpoint, timeout=timeout)
            subscription = await subscribe(client, handler, publish_interval_ms=publish_interval_ms)

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
