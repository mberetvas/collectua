"""
Phase 1 — Smoke Test: Browse PLC server node tree to discover alarm/event nodes.
Connect to S1500 OPC UA server (no security) and print the address space tree.
"""

import asyncio
import logging

from asyncua import Client, ua

ENDPOINT = "opc.tcp://10.205.139.4:4840"
MAX_DEPTH = 3
TIMEOUT = 30.0

_logger = logging.getLogger("asyncua")


async def _browse_recursive(node, depth: int, max_depth: int):
    """Recursively print the server node tree up to max_depth."""
    if depth > max_depth:
        return
    try:
        name = (await node.read_browse_name()).to_string()
        node_id = node.nodeid.to_string()
        node_class = await node.read_node_class()
        print(f"{'  ' * depth}├── {name}  [{node_id}]  ({node_class.name})")
        for child in await node.get_children():
            await _browse_recursive(child, depth + 1, max_depth)
    except ua.UaError as e:
        print(f"{'  ' * depth}├── [error: {e}]")


async def run(endpoint: str = ENDPOINT, max_depth: int = MAX_DEPTH, timeout: float = TIMEOUT):
    """Browse the OPC UA object tree. Core callable for CLI and future TUI."""
    client = Client(url=endpoint, timeout=timeout)
    try:
        await client.connect()
        print(f"Connected to {endpoint}\n")

        objects = client.nodes.objects
        print(f"=== Server Node Tree (depth {max_depth}) ===\n")
        await _browse_recursive(objects, depth=0, max_depth=max_depth)

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
