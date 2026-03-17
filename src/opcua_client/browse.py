"""
Phase 1 — Smoke Test: Browse PLC server node tree to discover alarm/event nodes.
Connect to S1500 OPC UA server (no security) and print the address space tree.
"""

import asyncio
import logging
from typing import Any

from asyncua import Client, ua

from .env_defaults import get_float, get_int

MAX_DEPTH = get_int("OPCUA_MAX_DEPTH", 10)
TIMEOUT = get_float("OPCUA_TIMEOUT", 30.0)

_logger = logging.getLogger("asyncua")


async def _node_sort_name(node: Any) -> str:
    """Resolve a stable display name for sorting child nodes."""
    read_display_name = getattr(node, "read_display_name", None)
    if callable(read_display_name):
        try:
            display_name = await read_display_name()
            text = getattr(display_name, "Text", None)
            if isinstance(text, str):
                return text
        except ua.UaError:
            pass

    read_browse_name = getattr(node, "read_browse_name", None)
    if callable(read_browse_name):
        try:
            browse_name = await read_browse_name()
            to_string = getattr(browse_name, "to_string", None)
            if callable(to_string):
                return str(to_string())
            return str(browse_name)
        except ua.UaError:
            pass

    return str(getattr(node, "name", ""))


async def _browse_recursive(node, depth: int, max_depth: int, target_namespaces: set[int]) -> list[str]:
    """Recursively collect tree lines up to max_depth with optional namespace filtering."""
    if depth > max_depth:
        return []

    ns_index = int(node.nodeid.NamespaceIndex)
    is_target_namespace = not target_namespaces or ns_index in target_namespaces
    is_bridge_namespace = ns_index == 0

    if not is_target_namespace and not is_bridge_namespace:
        return []

    child_lines: list[str] = []

    if depth < max_depth:
        children = await node.get_children(
            nodeclassmask=ua.NodeClass.Object | ua.NodeClass.Variable | ua.NodeClass.Method
        )

        named_children: list[tuple[str, Any]] = []
        for child in children:
            display_name = await _node_sort_name(child)
            named_children.append((display_name, child))

        for _name, child in sorted(named_children, key=lambda item: item[0].lower()):
            child_lines.extend(await _browse_recursive(child, depth + 1, max_depth, target_namespaces))

    include_self = is_target_namespace or bool(child_lines)
    if not include_self:
        return []

    try:
        name = (await node.read_browse_name()).to_string()
        node_id = node.nodeid.to_string()
        node_class = await node.read_node_class()
        current_line = f"{'  ' * depth}├── {name}  [{node_id}]  ({node_class.name})"
        return [current_line, *child_lines]
    except ua.UaError as e:
        return [f"{'  ' * depth}├── [error: {e}]", *child_lines]


async def run(
    endpoint: str,
    max_depth: int = MAX_DEPTH,
    target_namespaces: list[int] | None = None,
    timeout: float = TIMEOUT,
):
    """Browse the OPC UA object tree. Core callable for CLI and future TUI."""
    target_ns_set = set(target_namespaces or [])
    client = Client(url=endpoint, timeout=timeout)
    try:
        await client.connect()
        print(f"Connected to {endpoint}\n")

        objects = client.nodes.objects
        namespace_info = f"all namespaces" if not target_ns_set else f"namespaces {sorted(target_ns_set)}"
        print(f"=== Server Node Tree (depth {max_depth}, {namespace_info}) ===\n")
        lines = await _browse_recursive(objects, depth=0, max_depth=max_depth, target_namespaces=target_ns_set)
        for line in lines:
            print(line)

    finally:
        await client.disconnect()
        print("\nDisconnected")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    main()
