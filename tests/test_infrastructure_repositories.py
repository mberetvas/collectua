from __future__ import annotations

from datetime import datetime, timezone

from opcua_client.domain.alarm import Alarm
from opcua_client.domain.node import Node, NodeClass, NodeId
from opcua_client.infrastructure.repositories import InMemoryAlarmRepository, InMemoryNodeRepository


def _make_alarm(alarm_id: str, retain: bool = True) -> Alarm:
    return Alarm.from_values(
        alarm_id=alarm_id,
        condition_name="Overheat",
        source_name="Motor1",
        message="too hot",
        severity=900,
        timestamp_utc=datetime.now(timezone.utc),
        retain=retain,
        active_state=True,
        acked_state=False,
    )


def test_in_memory_alarm_repository() -> None:
    repo = InMemoryAlarmRepository()
    alarm_active = _make_alarm("ns=2;s=alarm-1", retain=True)
    alarm_cleared = _make_alarm("ns=2;s=alarm-2", retain=False)
    repo.add(alarm_active)
    repo.add(alarm_cleared)

    assert repo.get_by_id(alarm_active.alarm_id) == alarm_active
    assert repo.list_active() == [alarm_active]


def test_in_memory_node_repository() -> None:
    repo = InMemoryNodeRepository()
    root = Node(
        node_id=NodeId("ns=1;i=1"),
        display_name="Root",
        browse_name="Root",
        node_class=NodeClass.OBJECT,
        namespace_index=1,
    )
    child = Node(
        node_id=NodeId("ns=1;i=2"),
        display_name="Child",
        browse_name="Child",
        node_class=NodeClass.VARIABLE,
        namespace_index=1,
        parent_node_id=root.node_id,
    )
    repo.add(root)
    repo.add(child)

    assert repo.get_by_id(root.node_id) == root
    assert repo.list_children(root.node_id) == [child]
