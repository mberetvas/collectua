from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, List

from opcua_client.ops import browse


@dataclass
class _DummyNodeId:
    NamespaceIndex: int

    def to_string(self) -> str:
        return f"ns={self.NamespaceIndex};i=1"


@dataclass
class _DummyNode:
    nodeid: _DummyNodeId
    name: str
    node_class_name: str = "Object"
    children: list["_DummyNode"] = field(default_factory=list)
    raise_error: bool = False

    async def get_children(self, nodeclassmask: Any) -> List["_DummyNode"]:  # pragma: no cover - simple passthrough
        return self.children

    async def read_browse_name(self):
        if self.raise_error:
            from asyncua import ua

            raise ua.UaError("boom")

        class _Name:
            def __init__(self, s: str) -> None:
                self._s = s

            def to_string(self) -> str:
                return self._s

        return _Name(self.name)

    async def read_node_class(self):
        class _Cls:
            def __init__(self, name: str) -> None:
                self.name = name

        return _Cls(self.node_class_name)


def test_browse_recursive_basic_tree_no_filter() -> None:
    leaf = _DummyNode(nodeid=_DummyNodeId(2), name="Leaf")
    child = _DummyNode(nodeid=_DummyNodeId(2), name="Child", children=[leaf])
    root = _DummyNode(nodeid=_DummyNodeId(0), name="Root", children=[child])

    lines = asyncio.run(browse._browse_recursive(root, depth=0, max_depth=2, target_namespaces=set()))

    assert any("Root" in line for line in lines)
    assert any("Child" in line for line in lines)
    assert any("Leaf" in line for line in lines)


def test_browse_recursive_filters_non_target_namespaces() -> None:
    # Root/child in bridge namespace 0, grandchild in target namespace 2.
    # This matches current implementation behavior: recursion only continues
    # through target namespaces and namespace 0 bridge nodes.
    grandchild = _DummyNode(nodeid=_DummyNodeId(2), name="GrandChild")
    child = _DummyNode(nodeid=_DummyNodeId(0), name="BridgeChild", children=[grandchild])
    root = _DummyNode(nodeid=_DummyNodeId(0), name="Root", children=[child])

    lines = asyncio.run(browse._browse_recursive(root, depth=0, max_depth=3, target_namespaces={2}))

    joined = "\n".join(lines)
    # Bridge ns=0 and target ns=2 should appear.
    assert "Root" in joined
    assert "GrandChild" in joined
    assert "BridgeChild" in joined


def test_browse_recursive_respects_max_depth() -> None:
    depth2 = _DummyNode(nodeid=_DummyNodeId(0), name="Depth2")
    depth1 = _DummyNode(nodeid=_DummyNodeId(0), name="Depth1", children=[depth2])
    root = _DummyNode(nodeid=_DummyNodeId(0), name="Root", children=[depth1])

    lines = asyncio.run(browse._browse_recursive(root, depth=0, max_depth=1, target_namespaces=set()))

    joined = "\n".join(lines)
    assert "Root" in joined
    assert "Depth1" in joined
    assert "Depth2" not in joined


def test_browse_recursive_handles_ua_error() -> None:
    # Node configured to raise UaError from read_browse_name.
    problematic = _DummyNode(nodeid=_DummyNodeId(1), name="X", raise_error=True)

    lines = asyncio.run(browse._browse_recursive(problematic, depth=0, max_depth=0, target_namespaces=set()))

    assert len(lines) == 1
    assert "[error:" in lines[0]

