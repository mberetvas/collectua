import sys
from lxml import etree

def validate_xml(xml_file, xsd_file):
    # Parse schema
    with open(xsd_file, 'rb') as f:
        schema_root = etree.XML(f.read())
    schema = etree.XMLSchema(schema_root)

    # Parse document
    with open(xml_file, 'rb') as f:
        doc = etree.parse(f)

    # Validate
    if schema.validate(doc):
        print("✅ XML is valid!")
        return True
    else:
        print("❌ XML failed validation.")
        for error in schema.error_log:
            print(f"  Line {error.line}: {error.message}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python validate_nodes.py <nodeset.xml> <nodeset.xsd>")
        sys.exit(1)
    ok = validate_xml(sys.argv[1], sys.argv[2])
    sys.exit(0 if ok else 1)