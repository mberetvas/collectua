import sys
import xml.etree.ElementTree as ET
from typing import Dict, NamedTuple

UA_NS = "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"
UA = f"{{{UA_NS}}}"

NODE_CLASSES = [
    "UAObject", "UAVariable", "UAMethod",
    "UAObjectType", "UAVariableType", "UADataType", "UAReferenceType",
]


class NodeSnapshot(NamedTuple):
    browse_name: str
    display_name: str
    node_class: str


def load_snapshot(xml_filename: str) -> Dict[str, NodeSnapshot]:
    """Parse a NodeSet and return a minimal NodeId -> NodeSnapshot map."""
    tree = ET.parse(xml_filename)
    root = tree.getroot()

    snapshot: Dict[str, NodeSnapshot] = {}
    for cls in NODE_CLASSES:
        for node_el in root.findall(f".//{UA}{cls}"):
            node_id = node_el.attrib.get("NodeId", "")
            browse_name = node_el.attrib.get("BrowseName", "")
            dn_el = node_el.find(f"{UA}DisplayName")
            display_name = dn_el.text if dn_el is not None else ""
            if node_id:
                snapshot[node_id] = NodeSnapshot(browse_name, display_name, cls[2:])

    return snapshot


def diff_nodesets(old_file: str, new_file: str) -> None:
    old = load_snapshot(old_file)
    new = load_snapshot(new_file)

    old_ids = set(old)
    new_ids = set(new)

    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)
    common = old_ids & new_ids

    changed = []
    for node_id in sorted(common):
        o, n = old[node_id], new[node_id]
        diffs = []
        if o.browse_name != n.browse_name:
            diffs.append(f"BrowseName: '{o.browse_name}' -> '{n.browse_name}'")
        if o.display_name != n.display_name:
            diffs.append(f"DisplayName: '{o.display_name}' -> '{n.display_name}'")
        if o.node_class != n.node_class:
            diffs.append(f"NodeClass: '{o.node_class}' -> '{n.node_class}'")
        if diffs:
            changed.append((node_id, new[node_id], diffs))

    print(f"Comparing:")
    print(f"  OLD: {old_file}  ({len(old)} nodes)")
    print(f"  NEW: {new_file}  ({len(new)} nodes)")
    print()

    print(f"=== ADDED ({len(added)}) ===")
    for node_id in added:
        n = new[node_id]
        print(f"  + {node_id}  [{n.node_class}]  {n.browse_name}")

    print(f"\n=== REMOVED ({len(removed)}) ===")
    for node_id in removed:
        o = old[node_id]
        print(f"  - {node_id}  [{o.node_class}]  {o.browse_name}")

    print(f"\n=== CHANGED ({len(changed)}) ===")
    for node_id, snap, diffs in changed:
        print(f"  ~ {node_id}  [{snap.node_class}]  {snap.browse_name}")
        for d in diffs:
            print(f"      {d}")

    print()
    print(f"Summary: {len(added)} added, {len(removed)} removed, {len(changed)} changed")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python diff_nodesets.py <old_nodeset.xml> <new_nodeset.xml>")
        sys.exit(1)
    diff_nodesets(sys.argv[1], sys.argv[2])
