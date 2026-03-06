import sys
import csv
import xml.etree.ElementTree as ET
from typing import Dict, Optional

UA_NS = "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"
UA = f"{{{UA_NS}}}"

# Hierarchical references (HasComponent, HasProperty, Organizes)
HIERARCHICAL_REFS = {"i=47", "i=46", "i=35"}
# HasTypeDefinition
HAS_TYPE_DEF = "i=40"

NODE_CLASSES = [
    "UAObject", "UAVariable", "UAMethod",
    "UAObjectType", "UAVariableType", "UADataType", "UAReferenceType",
]

CSV_FIELDS = [
    "NodeId", "BrowseName", "DisplayName", "NodeClass",
    "ParentNodeId", "TypeDefinition", "Description",
]


def build_alias_map(root: ET.Element) -> Dict[str, str]:
    alias_map: Dict[str, str] = {}
    for alias_el in root.findall(f"{UA}Aliases/{UA}Alias"):
        alias_map[alias_el.attrib.get("Alias", "")] = alias_el.text or ""
    return alias_map


def export_nodes_csv(xml_filename: str, csv_filename: str) -> int:
    """Parse the NodeSet and write to CSV. Returns the number of rows written."""
    tree = ET.parse(xml_filename)
    root = tree.getroot()
    alias_map = build_alias_map(root)

    def resolve(ref_type: str) -> str:
        return alias_map.get(ref_type, ref_type)

    rows = []
    for cls in NODE_CLASSES:
        for node_el in root.findall(f".//{UA}{cls}"):
            node_id = node_el.attrib.get("NodeId", "")
            browse_name = node_el.attrib.get("BrowseName", "")
            dn_el = node_el.find(f"{UA}DisplayName")
            display_name = dn_el.text if dn_el is not None else ""
            desc_el = node_el.find(f"{UA}Description")
            description = desc_el.text if desc_el is not None else ""

            parent_id: Optional[str] = None
            type_def: Optional[str] = None

            for ref_el in node_el.findall(f"{UA}References/{UA}Reference"):
                ref_type = resolve(ref_el.attrib.get("ReferenceType", ""))
                is_forward = ref_el.attrib.get("IsForward", "true").lower() != "false"
                target = (ref_el.text or "").strip()

                # Inverse hierarchical reference -> parent
                if ref_type in HIERARCHICAL_REFS and not is_forward and target:
                    parent_id = target

                # Forward HasTypeDefinition
                if ref_type == HAS_TYPE_DEF and is_forward and target:
                    type_def = target

            rows.append({
                "NodeId": node_id,
                "BrowseName": browse_name,
                "DisplayName": display_name,
                "NodeClass": cls[2:],  # strip "UA" prefix
                "ParentNodeId": parent_id or "",
                "TypeDefinition": type_def or "",
                "Description": description,
            })

    with open(csv_filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python export_nodes_csv.py <nodeset.xml> <output.csv>")
        sys.exit(1)

    xml_file, csv_file = sys.argv[1], sys.argv[2]
    count = export_nodes_csv(xml_file, csv_file)
    print(f"Exported {count} nodes to {csv_file}")
