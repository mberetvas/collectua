from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from asyncua import ua

from .exceptions import InvalidNodeId, NodeValidationError


@dataclass(frozen=True)
class NodeId:
    value: str

    @classmethod
    def from_value(cls, value: str | ua.NodeId) -> "NodeId":
        if isinstance(value, ua.NodeId):
            return cls(value=value.to_string())
        return cls(value=str(value))

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise InvalidNodeId("NodeId cannot be empty")

    def __str__(self) -> str:
        return self.value


class NodeClass(str, Enum):
    OBJECT = "Object"
    VARIABLE = "Variable"
    METHOD = "Method"
    OBJECT_TYPE = "ObjectType"
    VARIABLE_TYPE = "VariableType"
    REFERENCE_TYPE = "ReferenceType"
    DATA_TYPE = "DataType"
    VIEW = "View"
    UNKNOWN = "Unknown"

    @classmethod
    def from_value(cls, value: ua.NodeClass | str | None) -> "NodeClass":
        if value is None:
            return cls.UNKNOWN
        if isinstance(value, ua.NodeClass):
            text = value.name
        else:
            text = str(value)
        for item in cls:
            if item.value.lower() == text.lower() or item.name.lower() == text.lower():
                return item
        return cls.UNKNOWN


@dataclass(frozen=True)
class Node:
    node_id: NodeId
    display_name: str
    browse_name: str
    node_class: NodeClass
    namespace_index: int
    parent_node_id: NodeId | None = None

    def __post_init__(self) -> None:
        if self.namespace_index < 0:
            raise NodeValidationError("namespace_index must be >= 0")
        if not self.browse_name.strip():
            raise NodeValidationError("browse_name cannot be empty")

    def is_variable(self) -> bool:
        return self.node_class == NodeClass.VARIABLE

    def is_object(self) -> bool:
        return self.node_class == NodeClass.OBJECT

    def is_method(self) -> bool:
        return self.node_class == NodeClass.METHOD


@dataclass
class NodeTree:
    _nodes: dict[str, Node] = field(default_factory=dict)
    _children: dict[str, list[str]] = field(default_factory=dict)

    def add(self, node: Node) -> None:
        key = str(node.node_id)
        self._nodes[key] = node
        if node.parent_node_id is None:
            return
        parent = str(node.parent_node_id)
        self._children.setdefault(parent, [])
        if key not in self._children[parent]:
            self._children[parent].append(key)

    def find_by_id(self, node_id: NodeId | str) -> Node | None:
        key = str(node_id) if isinstance(node_id, NodeId) else str(node_id)
        return self._nodes.get(key)

    def get_children(self, parent_node_id: NodeId | str) -> list[Node]:
        key = str(parent_node_id) if isinstance(parent_node_id, NodeId) else str(parent_node_id)
        child_keys = self._children.get(key, [])
        return [self._nodes[child_key] for child_key in child_keys if child_key in self._nodes]
