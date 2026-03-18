from __future__ import annotations

import pytest

from opcua_client.domain.exceptions import InvalidNodeId, NodeValidationError
from opcua_client.domain.node import Node, NodeClass, NodeId, NodeTree


def test_node_id_validation() -> None:
    with pytest.raises(InvalidNodeId):
        NodeId("")


def test_node_class_mapping() -> None:
    assert NodeClass.from_value("Object") == NodeClass.OBJECT
    assert NodeClass.from_value("Variable") == NodeClass.VARIABLE
    assert NodeClass.from_value("UnknownType") == NodeClass.UNKNOWN


def test_node_validation_rules() -> None:
    with pytest.raises(NodeValidationError):
        Node(
            node_id=NodeId("ns=1;i=1"),
            display_name="A",
            browse_name="",
            node_class=NodeClass.OBJECT,
            namespace_index=0,
        )


def test_node_tree_add_find_children() -> None:
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
    tree = NodeTree()
    tree.add(root)
    tree.add(child)

    assert tree.find_by_id(root.node_id) == root
    assert tree.get_children(root.node_id) == [child]
