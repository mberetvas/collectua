import sys
import xml.etree.ElementTree as ET
from collections import Counter

UA_NS = "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"
UA = f"{{{UA_NS}}}"

NODE_CLASSES = [
    "UAObject", "UAVariable", "UAMethod",
    "UAObjectType", "UAVariableType", "UADataType", "UAReferenceType",
]


def inspect_model(xml_filename: str) -> None:
    tree = ET.parse(xml_filename)
    root = tree.getroot()

    print("=== Namespace URIs ===")
    ns_uris = root.findall(f"{UA}NamespaceUris/{UA}Uri")
    if ns_uris:
        for idx, uri_el in enumerate(ns_uris, start=1):
            print(f"  {idx} -> {uri_el.text}")
    else:
        print("  (none declared — only namespace 0 used)")

    print("\n=== Aliases ===")
    aliases = root.findall(f"{UA}Aliases/{UA}Alias")
    if aliases:
        for alias_el in aliases:
            print(f"  {alias_el.attrib.get('Alias'):30s} -> {alias_el.text}")
    else:
        print("  (no aliases declared)")

    print("\n=== Node Class Counts ===")
    counts: Counter = Counter()
    for cls in NODE_CLASSES:
        count = len(root.findall(f".//{UA}{cls}"))
        counts[cls] = count
        if count:
            print(f"  {cls:20s}: {count}")
    total = sum(counts.values())
    print(f"  {'TOTAL':20s}: {total}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python inspect_model.py <nodeset.xml>")
        sys.exit(1)
    inspect_model(sys.argv[1])
