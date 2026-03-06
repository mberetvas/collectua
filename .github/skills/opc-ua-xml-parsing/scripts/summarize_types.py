import sys
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Dict

UA_NS = "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"
UA = f"{{{UA_NS}}}"

# HasTypeDefinition forward reference
HAS_TYPE_DEF = "i=40"

NODE_CLASSES = [
    "UAObject", "UAVariable", "UAMethod",
    "UAObjectType", "UAVariableType", "UADataType", "UAReferenceType",
]


def build_alias_map(root: ET.Element) -> Dict[str, str]:
    alias_map: Dict[str, str] = {}
    for alias_el in root.findall(f"{UA}Aliases/{UA}Alias"):
        alias_map[alias_el.attrib.get("Alias", "")] = alias_el.text or ""
    return alias_map


def build_display_name_map(root: ET.Element) -> Dict[str, str]:
    """Build NodeId -> DisplayName for all nodes so type names can be resolved."""
    display_names: Dict[str, str] = {}
    for cls in NODE_CLASSES:
        for node_el in root.findall(f".//{UA}{cls}"):
            node_id = node_el.attrib.get("NodeId", "")
            dn_el = node_el.find(f"{UA}DisplayName")
            if node_id:
                display_names[node_id] = dn_el.text if dn_el is not None else node_id
    return display_names


def summarize_types(xml_filename: str) -> None:
    tree = ET.parse(xml_filename)
    root = tree.getroot()

    alias_map = build_alias_map(root)
    display_names = build_display_name_map(root)

    def resolve(ref_type: str) -> str:
        return alias_map.get(ref_type, ref_type)

    type_counter: Counter = Counter()

    for cls in NODE_CLASSES:
        for node_el in root.findall(f".//{UA}{cls}"):
            for ref_el in node_el.findall(f"{UA}References/{UA}Reference"):
                ref_type = resolve(ref_el.attrib.get("ReferenceType", ""))
                is_forward = ref_el.attrib.get("IsForward", "true").lower() != "false"
                target = (ref_el.text or "").strip()
                if ref_type == HAS_TYPE_DEF and is_forward and target:
                    type_counter[target] += 1

    if not type_counter:
        print("No HasTypeDefinition references found.")
        return

    print(f"{'Type NodeId':<30}  {'DisplayName':<35}  {'Instances':>9}")
    print("-" * 80)
    for type_id, count in type_counter.most_common():
        name = display_names.get(type_id, "(external)")
        print(f"{type_id:<30}  {name:<35}  {count:>9}")

    print("-" * 80)
    print(f"{'TOTAL':<30}  {'':35}  {sum(type_counter.values()):>9}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python summarize_types.py <nodeset.xml>")
        sys.exit(1)
    summarize_types(sys.argv[1])
