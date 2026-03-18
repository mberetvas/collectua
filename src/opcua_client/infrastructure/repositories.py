from __future__ import annotations

from abc import ABC, abstractmethod

from opcua_client.domain.alarm import Alarm, AlarmId
from opcua_client.domain.node import Node, NodeId, NodeTree


class AlarmRepository(ABC):
    @abstractmethod
    def add(self, alarm: Alarm) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, alarm_id: AlarmId) -> Alarm | None:
        raise NotImplementedError

    @abstractmethod
    def list_active(self) -> list[Alarm]:
        raise NotImplementedError


class InMemoryAlarmRepository(AlarmRepository):
    def __init__(self) -> None:
        self._store: dict[str, Alarm] = {}

    def add(self, alarm: Alarm) -> None:
        self._store[str(alarm.alarm_id)] = alarm

    def get_by_id(self, alarm_id: AlarmId) -> Alarm | None:
        return self._store.get(str(alarm_id))

    def list_active(self) -> list[Alarm]:
        return [alarm for alarm in self._store.values() if alarm.is_retained()]


class NodeRepository(ABC):
    @abstractmethod
    def add(self, node: Node) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, node_id: NodeId) -> Node | None:
        raise NotImplementedError

    @abstractmethod
    def list_children(self, parent_id: NodeId) -> list[Node]:
        raise NotImplementedError


class InMemoryNodeRepository(NodeRepository):
    def __init__(self) -> None:
        self._tree = NodeTree()

    def add(self, node: Node) -> None:
        self._tree.add(node)

    def get_by_id(self, node_id: NodeId) -> Node | None:
        return self._tree.find_by_id(node_id)

    def list_children(self, parent_id: NodeId) -> list[Node]:
        return self._tree.get_children(parent_id)
