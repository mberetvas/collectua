from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from opcua_client.ops import collector


class _DummyNodeId:
    def __init__(self, value: str) -> None:
        self._value = value

    def to_string(self) -> str:
        return self._value


class _DummyState:
    def __init__(self, value: Any) -> None:
        self.Id = value


class _DummyEvent:
    def __init__(
        self,
        *,
        condition_id: Any | None = None,
        retain: Any | None = None,
        active_state: Any | None = None,
        acked_state: Any | None = None,
    ) -> None:
        # Attributes used by AlarmHandler.event_notification
        self.Time = "2024-01-01T00:00:00Z"
        self.EventType = "BaseEventType"
        self.SourceName = "SRC"
        self.Message = "msg"
        self.Severity = 1
        self.ConditionName = "cond"
        self.EventId = "evt-1"
        # Condition-related attributes
        if condition_id is not None:
            self.ConditionId = condition_id
        if retain is not None:
            self.Retain = retain
        if active_state is not None:
            self.ActiveState = active_state
        if acked_state is not None:
            self.AckedState = acked_state

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"DummyEvent({self.ConditionName})"


def test_condition_id_from_event_variants() -> None:
    handler = collector.AlarmHandler("dummy.csv")

    # NodeId with to_string
    node_id = _DummyNodeId("ns=1;i=1001")
    assert handler._condition_id_from_event(type("E", (), {"ConditionId": node_id})) == "ns=1;i=1001"

    # Object with to_string method
    class Obj:
        def to_string(self) -> str:
            return "custom"

    assert handler._condition_id_from_event(type("E", (), {"ConditionId": Obj()})) == "custom"

    # String fallback
    assert handler._condition_id_from_event(type("E", (), {"ConditionId": "plain"})) == "plain"

    # Missing ConditionId
    assert handler._condition_id_from_event(type("E", (), {})()) is None


def test_bool_from_state_variants() -> None:
    handler = collector.AlarmHandler("dummy.csv")

    assert handler._bool_from_state(True) is True
    assert handler._bool_from_state(False) is False
    assert handler._bool_from_state(_DummyState(True)) is True
    assert handler._bool_from_state(_DummyState(0)) is False
    assert handler._bool_from_state(None) is None

    class Bad:
        def __bool__(self) -> bool:
            raise ValueError("nope")

    assert handler._bool_from_state(Bad()) is None


def test_update_active_alarms_lifecycle(tmp_path: Path) -> None:
    csv_path = tmp_path / "alarms.csv"
    handler = collector.AlarmHandler(str(csv_path))

    row_base = {
        "condition_name": "cond",
        "source_name": "SRC",
        "message": "msg",
        "severity": "1",
        "timestamp_utc": "2024-01-01T00:00:00Z",
        "raw": "raw",
    }

    # New alarm with retain=True
    handler._update_active_alarms(
        {**row_base, "condition_id": "id-1", "retain": True, "active_state": True, "acked_state": False},
        event=None,
    )
    active = handler.get_active_alarms()
    assert "id-1" in active
    assert active["id-1"].retain is True

    # Update same alarm with retain="false" should clear it
    handler._update_active_alarms(
        {**row_base, "condition_id": "id-1", "retain": "false", "active_state": False, "acked_state": True},
        event=None,
    )
    active = handler.get_active_alarms()
    assert "id-1" not in active

    # retain=None results in an active alarm with retain set to None.
    handler._update_active_alarms({**row_base, "condition_id": "id-2", "retain": None}, event=None)
    active = handler.get_active_alarms()
    assert "id-2" in active
    assert active["id-2"].retain is None


def test_event_notification_writes_csv_and_updates_alarms(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    csv_path = tmp_path / "alarms.csv"
    handler = collector.AlarmHandler(str(csv_path))

    event = _DummyEvent(
        condition_id=_DummyNodeId("ns=1;i=42"),
        retain=True,
        active_state=_DummyState(True),
        acked_state=_DummyState(False),
    )

    handler.event_notification(event)

    # CSV should exist and contain a header plus one data row.
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    header = lines[0].split(",")
    assert all(col in header for col in collector.CSV_HEADERS)

    active = handler.get_active_alarms()
    assert "ns=1;i=42" in active

    # Ensure at least one INFO log line was produced.
    assert any("Listening" not in r.getMessage() for r in caplog.records)


@dataclass
class _FakeSubscription:
    subscription_id: int = 1

    async def subscribe_events(self, *, sourcenode, evtypes, where_clause_generation: bool) -> None:  # pragma: no cover
        self.sourcenode = sourcenode
        self.evtypes = evtypes
        self.where_clause_generation = where_clause_generation


class _FakeClient:
    def __init__(self) -> None:
        self.created_with: dict[str, Any] = {}
        self.node = object()

    async def create_subscription(self, period: int, handler: Any) -> _FakeSubscription:
        self.created_with = {"period": period, "handler": handler}
        return _FakeSubscription()

    def get_node(self, nodeid: Any) -> Any:
        self.node = object()
        return self.node


def test_subscribe_creates_subscription_and_runs_condition_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeClient()
    calls: dict[str, Any] = {}

    async def fake_condition_refresh(*, server_node, subscription_id: int, logger, is_active=None) -> None:
        calls["server_node"] = server_node
        calls["subscription_id"] = subscription_id
        calls["logger_name"] = logger.name
        calls["is_active"] = is_active

    monkeypatch.setattr(collector, "condition_refresh_with_retry", fake_condition_refresh)

    # is_active=None => _run_condition_refresh is awaited inline.
    sub = asyncio.run(
        collector.subscribe(
            client=fake_client,
            handler=object(),
            publish_interval_ms=123,
            enable_condition_refresh=True,
            is_active=None,
        )
    )

    assert isinstance(sub, _FakeSubscription)
    assert fake_client.created_with["period"] == 123
    assert "handler" in fake_client.created_with
    assert calls["server_node"] is fake_client.node
    assert calls["subscription_id"] == sub.subscription_id
    assert calls["is_active"] is None


def test_subscribe_skips_condition_refresh_when_not_active(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeClient()
    called: dict[str, bool] = {"refresh": False}

    async def fake_condition_refresh(**kwargs: Any) -> None:
        called["refresh"] = True

    monkeypatch.setattr(collector, "condition_refresh_with_retry", fake_condition_refresh)

    # is_active returns False, so background task should short-circuit before calling condition_refresh.
    def is_active() -> bool:
        return False

    sub = asyncio.run(
        collector.subscribe(
            client=fake_client,
            handler=object(),
            publish_interval_ms=100,
            enable_condition_refresh=True,
            is_active=is_active,
        )
    )

    assert isinstance(sub, _FakeSubscription)

    # Allow background task (if any) to run.
    asyncio.run(asyncio.sleep(0.1))

    assert called["refresh"] is False

