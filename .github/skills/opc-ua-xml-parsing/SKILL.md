---
name: opc-ua-xml-parsing
description: Information about how to parse xml exports from OPC UA servers.
---

# OPC UA XML Parsing

Parse OPC UA NodeSet2 XML exports to build client configurations and navigable information models.

## When to Apply

- Processing NodeSet2 XML exports from OPC UA servers (30MB+)
- Building OPC UA client configurations from information models
- Creating hierarchical navigation of OPC address spaces
- Extracting node relationships and type definitions

## Critical Rules

**Use Schema Validation**: Always validate against UANodeSet.xsd

```xml
<!-- XSD location -->
xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"
```

### How to Use Local References

When answering questions or designing parsing/navigation code with this skill:

- Prefer **conceptual explanations** first, based on OPC UA and NodeSet2 semantics.
- When you need concrete examples or authoritative mappings:
  - Use the `Read` tool to open files under `references/` as documented in **Reference Files**.
  - Cite specific examples (NodeIds, elements, reference patterns) from those files to support your reasoning.
- Treat everything in `references/` as **static documentation/examples**, not as runtime input from the user.

**NodeId Format Patterns**: Handle all identifier types correctly

```javascript
// NodeId formats
"i=47"              // Numeric in namespace 0
"ns=2;i=1001"       // Numeric with namespace
"ns=1;s=MyVariable" // String identifier
"ns=2;g=550e8400-..." // GUID identifier
"ns=3;b=M/RbKBsRVkePCePcx24oRA==" // Opaque (base64)
```

**Alias Resolution**: Resolve aliases before processing references

```xml
<Aliases>
  <Alias Alias="HasComponent">i=47</Alias>
  <Alias Alias="HasProperty">i=46</Alias>
  <Alias Alias="Organizes">i=35</Alias>
</Aliases>

<!-- Usage -->
<Reference ReferenceType="HasComponent">ns=2;i=1002</Reference>
```

## Key Patterns

### NodeSet Structure Parser

```javascript
const parseNodeSet = (xmlContent) => {
  const parser = new DOMParser();
  const doc = parser.parseFromString(xmlContent, 'text/xml');
  
  // Extract namespace URIs
  const namespaces = Array.from(doc.querySelectorAll('NamespaceUris > Uri'))
    .map((uri, index) => ({ index: index + 1, uri: uri.textContent }));
  
  // Build alias map
  const aliases = {};
  doc.querySelectorAll('Aliases > Alias').forEach(alias => {
    aliases[alias.getAttribute('Alias')] = alias.textContent;
  });
  
  return { namespaces, aliases, doc };
};
```

### Node Extraction with References

```javascript
const extractNodes = (doc, aliases) => {
  const nodes = new Map();
  
  // Process all node types
  const nodeSelectors = [
    'UAObject', 'UAVariable', 'UAMethod', 
    'UAObjectType', 'UAVariableType', 'UADataType', 'UAReferenceType'
  ];
  
  nodeSelectors.forEach(selector => {
    doc.querySelectorAll(selector).forEach(node => {
      const nodeId = node.getAttribute('NodeId');
      const browseName = node.getAttribute('BrowseName');
      
      // Extract references
      const references = Array.from(node.querySelectorAll('References > Reference'))
        .map(ref => ({
          type: resolveAlias(ref.getAttribute('ReferenceType'), aliases),
          target: ref.textContent.trim(),
          isForward: ref.getAttribute('IsForward') !== 'false'
        }));
      
      nodes.set(nodeId, {
        nodeId,
        browseName,
        nodeClass: selector.substring(2), // Remove 'UA' prefix
        displayName: node.querySelector('DisplayName')?.textContent,
        description: node.querySelector('Description')?.textContent,
        references
      });
    });
  });
  
  return nodes;
};
```

### Hierarchical Navigation Builder

```javascript
const buildHierarchy = (nodes) => {
  const hierarchy = new Map();
  const rootNodes = new Set();
  
  // Standard hierarchical references
  const hierarchicalRefs = ['i=47', 'i=46', 'i=35']; // HasComponent, HasProperty, Organizes
  
  nodes.forEach((node, nodeId) => {
    let hasParent = false;
    
    node.references.forEach(ref => {
      if (hierarchicalRefs.includes(ref.type)) {
        if (ref.isForward) {
          // This node is parent to target
          if (!hierarchy.has(nodeId)) hierarchy.set(nodeId, []);
          hierarchy.get(nodeId).push(ref.target);
        } else {
          // This node is child of target
          hasParent = true;
          if (!hierarchy.has(ref.target)) hierarchy.set(ref.target, []);
          hierarchy.get(ref.target).push(nodeId);
        }
      }
    });
    
    if (!hasParent) rootNodes.add(nodeId);
  });
  
  return { hierarchy, rootNodes };
};
```

### Type System Resolution

```javascript
const resolveTypeDefinitions = (nodes) => {
  const typeMap = new Map();
  
  nodes.forEach((node, nodeId) => {
    // Find HasTypeDefinition reference (i=40)
    const typeDef = node.references.find(ref => 
      ref.type === 'i=40' && ref.isForward
    );
    
    if (typeDef) {
      typeMap.set(nodeId, typeDef.target);
    }
  });
  
  return typeMap;
};
```

### Browse Path Generator

```javascript
const generateBrowsePath = (targetNodeId, nodes, hierarchy) => {
  const path = [];
  let currentNode = targetNodeId;
  
  // Walk up hierarchy
  while (currentNode) {
    const node = nodes.get(currentNode);
    if (!node) break;
    
    path.unshift({
      browseName: node.browseName,
      nodeId: currentNode
    });
    
    // Find parent through inverse hierarchical reference
    const parent = node.references.find(ref => 
      ['i=47', 'i=46', 'i=35'].includes(ref.type) && !ref.isForward
    );
    
    currentNode = parent?.target;
  }
  
  return path;
};
```

## Common Mistakes

- **Ignoring namespace context** — Always map namespace URIs correctly when resolving NodeIds
- **Missing alias resolution** — References use aliases that must be resolved to actual NodeIds
- **Incorrect reference direction** — Check `IsForward` attribute to determine relationship direction
- **Memory issues with large files** — Use streaming parsers for files over 50MB

## Helper Scripts

The following Python scripts live in `scripts/` and can be run directly from a terminal to inspect, validate, export, and compare NodeSet2 files. Use the `Shell` tool (or suggest these commands to the user) when you need to quickly verify NodeSet contents.

| Script | Purpose | Example |
|---|---|---|
| `inspect_model.py` | List namespace URIs, aliases, and node-class counts | `python inspect_model.py model.xml` |
| `dump_hierarchy.py` | Print a node tree from a starting NodeId | `python dump_hierarchy.py model.xml "ns=2;i=5001"` |
| `summarize_types.py` | Count instances per type (HasTypeDefinition) | `python summarize_types.py model.xml` |
| `export_nodes_csv.py` | Export all nodes (NodeId, BrowseName, NodeClass, parent, type) to CSV | `python export_nodes_csv.py model.xml out.csv` |
| `diff_nodesets.py` | Compare two NodeSets and report added/removed/changed nodes | `python diff_nodesets.py old.xml new.xml` |
| `validate_nodes.py` | Validate a NodeSet against `UANodeSet.xsd` | `python validate_nodes.py model.xml ../references/UANodeSet.xsd` |
| `parse_nodes.py` | Extract UAObjects to JSON (minimal example) | `python parse_nodes.py model.xml` |

### When to suggest scripts

- **Debugging parsing issues** → `inspect_model.py` to verify namespace/alias structure first.
- **Understanding node relationships** → `dump_hierarchy.py` with the relevant root NodeId.
- **Checking type usage distribution** → `summarize_types.py`.
- **Generating test fixtures or importing into tools** → `export_nodes_csv.py`.
- **Tracking changes between NodeSet exports** (e.g. after a TIA Portal project update) → `diff_nodesets.py`.
- **Verifying a user-provided NodeSet is spec-compliant** → `validate_nodes.py`.

## Reference Files

The following local reference files are available for this skill. Use them with the `Read` tool when you need concrete examples, vendor-specific details, or authoritative mappings.

### NodeSet examples (TIA Portal, generic OPC UA)

- **`references/tiaportal_nodeset_example.xml`**
  - **What it is**: Example NodeSet2 export from TIA Portal.
  - **When to use**:
    - When you need to understand how TIA Portal structures its OPC UA information model.
    - When designing parsing logic that must work with Siemens/TIA-specific patterns (namespaces, folder structure, variables, etc.).
  - **How to use**:
    - Open with `Read` to inspect typical `NamespaceUris`, `Aliases`, `UAObject`/`UAVariable` layout, and reference patterns.
    - Use as a realistic sample when explaining browse hierarchies or validating that parsing logic will handle TIA exports.

- **`references/tiaportal_siome_example_nodeset.xml`**
  - **What it is**: Example NodeSet2 export including Siemens IO/SiOME–style structures.
  - **When to use**:
    - When the question involves IO/channel/device modeling, or Siemens-specific extensions.
  - **How to use**:
    - Inspect how complex device trees are represented (folders, objects, variables, `HasComponent`/`Organizes` chains).
    - Derive patterns for building navigation trees or client configuration for IO modules.

- **`references/Opc.Ua.NodeSet2.examples.xml`**
  - **What it is**: OPC Foundation example NodeSet showing canonical structures.
  - **When to use**:
    - When you need “spec-like” examples instead of vendor-specific ones.
    - When explaining generic NodeSet2 modeling independent of TIA.
  - **How to use**:
    - Compare its node classes, references, and type definitions to TIA examples.
    - Use it to justify generic parsing rules that should work for any compliant NodeSet2 file.

### CSV helper mappings

- **`references/Opc.Ua.IA.NodeSet2.examples.csv`**
  - **What it is**: Tabular view of the OPC Foundation example NodeSet.
  - **When to use**:
    - When you need a quick, human-readable overview of nodes, NodeIds, and relationships.
  - **How to use**:
    - Use it to sanity-check assumptions about node classes, browse names, and hierarchies without parsing XML.

- **`references/NodeIds.csv`**
  - **What it is**: List of standard OPC UA NodeIds (well-known nodes).
  - **When to use**:
    - When you need to know what `i=XX` actually means (e.g. `HasComponent`, `HasProperty`, standard folders, etc.).
  - **How to use**:
    - Look up numeric NodeIds to explain or validate reference types and standard nodes.
    - Use as the source of truth when mapping numeric IDs to names in explanations.

- **`references/AttributeIds.csv`**
  - **What it is**: Mapping of OPC UA AttributeIds (e.g. `Value`, `DisplayName`, `Description`).
  - **When to use**:
    - When the question concerns attribute access (`Read`, `Write`) or attribute semantics.
  - **How to use**:
    - Use it to explain what each attribute represents and how clients should handle it.

- **`references/IEC62720_to_OPCUA.csv`**
  - **What it is**: Mapping between IEC 62720 concepts and OPC UA constructs.
  - **When to use**:
    - When the question involves IEC 62720 terminology and you must relate it to OPC UA nodes.
  - **How to use**:
    - Use it to translate IEC concepts into OPC UA node types, reference patterns, or attribute usage.
    - Base explanations and modeling recommendations on this mapping when bridging between standards.

### Schema and validation

- **`references/UANodeSet.xsd`**
  - **What it is**: Official XML Schema for NodeSet2 files.
  - **When to use**:
    - When you need to verify structure, required elements/attributes, or clarify ambiguities in NodeSet2 format.
  - **How to use**:
    - Use it as authoritative reference when describing allowed elements (`UAObject`, `UAVariable`, etc.) and their attributes.
    - Use it to justify validation rules or error messages in parsing logic.