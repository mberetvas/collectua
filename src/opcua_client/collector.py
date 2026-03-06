"""
OPC UA Alarm Collector — MVP

Long-running script that:
  - Connects to S1500 OPC UA server (no security)
  - Subscribes to alarms/events (BaseEventType)
  - Prints to console + appends to CSV
  - Auto-reconnects if connection drops
"""

import asyncio
import csv
import logging
import os
from datetime import datetime, timezone

from asyncua import Client, ua

# ──────────────────────── CONFIG ────────────────────────
ENDPOINT = "opc.tcp://10.205.139.4:4840"
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
    "raw",
]

_logger = logging.getLogger("collector")


class AlarmHandler:
    """
    Event handler for OPC UA subscriptions.
    On each event notification: prints to console and appends to CSV.
    """

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self._ensure_csv_header()

    def _ensure_csv_header(self):
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)

    def event_notification(self, event):
        """Called automatically by asyncua on each event."""
        try:
            row = {
                "timestamp_utc": str(getattr(event, "Time", datetime.now(timezone.utc))),
                "event_type": str(getattr(event, "EventType", "")),
                "source_name": str(getattr(event, "SourceName", "")),
                "message": str(getattr(event, "Message", "")),
                "severity": str(getattr(event, "Severity", "")),
                "condition_name": str(getattr(event, "ConditionName", "")),
                "event_id": str(getattr(event, "EventId", "")),
                "raw": str(event),
            }

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
    await subscription.subscribe_events(
        sourcenode=server_node,
        evtypes=ua.ObjectIds.BaseEventType,
    )

    _logger.info("Subscribed to alarms & events")
    return subscription


async def run(
    endpoint: str = ENDPOINT,
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
