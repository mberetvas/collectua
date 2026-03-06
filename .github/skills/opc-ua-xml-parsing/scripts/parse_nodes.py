import sys
import xml.etree.ElementTree as ET
import json

def parse_opcua_nodeset(xml_filename):
    tree = ET.parse(xml_filename)
    root = tree.getroot()
    ns = {'ua': 'http://opcfoundation.org/UA/2011/03/UANodeSet.xsd'}

    nodes = []
    for node in root.findall('.//ua:UAObject', ns):
        nodeid = node.attrib.get('NodeId')
        name = node.find('ua:DisplayName', ns).text if node.find('ua:DisplayName', ns) is not None else None
        nodes.append({'nodeid': nodeid, 'name': name})

    return nodes

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python parse_nodes.py <nodeset.xml>")
        sys.exit(1)
    nodes = parse_opcua_nodeset(sys.argv[1])
    print(json.dumps(nodes, indent=2))