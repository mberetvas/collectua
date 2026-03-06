import sys
import xml.etree.ElementTree as ET
from typing import Dict, List, NamedTuple

UA_NS = "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"
UA = f"{{{UA_NS}}}"

# Hierarchical forward references (HasComponent, HasProperty, Organizes)
HIERARCHICAL_REFS = {"i=47", "i=46", "i=35"}

NODE_CLASSES = [
    "UAObject", "UAVariable", "UAMethod",
    "UAObjectType", "UAVariableType", "UADataType", "UAReferenceType",
]


class NodeInfo(NamedTuple):
    browse_name: str
    display_name: str
    node_class: str
    children: List[str]  # forward hierarchical reference targets


def build_index(root: ET.Element) -> tuple[Dict[str, NodeInfo], Dict[str, str]]:
    """Return (nodes, alias_map)."""
    alias_map: Dict[str, str] = {}
    for alias_el in root.findall(f"{UA}Aliases/{UA}Alias"):
        alias_map[alias_el.attrib.get("Alias", "")] = alias_el.text or ""

    def resolve(ref_type: str) -> str:
        return alias_map.get(ref_type, ref_type)

    nodes: Dict[str, NodeInfo] = {}
    for cls in NODE_CLASSES:
        for node_el in root.findall(f".//{UA}{cls}"):
            node_id = node_el.attrib.get("NodeId", "")
            browse_name = node_el.attrib.get("BrowseName", node_id)
            dn_el = node_el.find(f"{UA}DisplayName")
            display_name = dn_el.text if dn_el is not None else browse_name

            children: List[str] = []
            for ref_el in node_el.findall(f"{UA}References/{UA}Reference"):
                ref_type = resolve(ref_el.attrib.get("ReferenceType", ""))
                is_forward = ref_el.attrib.get("IsForward", "true").lower() != "false"
                target = (ref_el.text or "").strip()
                if ref_type in HIERARCHICAL_REFS and is_forward and target:
                    children.append(target)

            nodes[node_id] = NodeInfo(browse_name, display_name, cls[2:], children)

    return nodes, alias_map


def print_tree(
    node_id: str,
    nodes: Dict[str, NodeInfo],
    depth: int = 0,
    visited: set | None = None,
) -> None:
    if visited is None:
        visited = set()
    if node_id in visited:
        print("  " * depth + f"[cycle detected: {node_id}]")
        return
    visited.add(node_id)

    info = nodes.get(node_id)
    if info is None:
        print("  " * depth + f"[unknown node: {node_id}]")
        return

    print("  " * depth + f"{info.browse_name}  [{info.node_class}]  ({node_id})")
    for child_id in info.children:
        print_tree(child_id, nodes, depth + 1, visited)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python dump_hierarchy.py <nodeset.xml> <start-nodeid>")
        print("  Example: python dump_hierarchy.py model.xml 'ns=2;i=5001'")
        sys.exit(1)

    xml_file, start_id = sys.argv[1], sys.argv[2]
    tree = ET.parse(xml_file)
    root = tree.getroot()
    nodes, _ = build_index(root)

    if start_id not in nodes:
        # Try partial match (convenient when using short IDs)
        matches = [nid for nid in nodes if start_id in nid]
        if len(matches) == 1:
            start_id = matches[0]
        elif len(matches) > 1:
            print(f"Ambiguous start NodeId '{start_id}'. Candidates:")
            for m in matches:
                print(f"  {m}")
            sys.exit(1)
        else:
            print(f"NodeId '{start_id}' not found in {xml_file}.")
            sys.exit(1)

    print_tree(start_id, nodes)
