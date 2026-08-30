# RQ-01 Data Storage Foundation

A minimal, text-based **Knowledge Graph** storage foundation for the AI tool.
Only two kinds of data exist — **Node** and **Relationship** — every field is
plain text, no domain schema is enforced. Phase 0 uses **JSON file storage**.

## Structure

```
Source/
  knowledge_graph/
    models.py          # Node, Relationship (item 1 & 2)
    persistence.py     # JSON file storage / Project layout (item 8)
    repositories.py    # Node & Relationship repositories, CRUD (item 3 & 4)
    indexes.py         # Node title index & Relationship index (item 5 & 6)
    integrity.py       # Unique id + reference validation (item 10)
    traversal.py       # Graph traversal, inbound/outbound (item 7)
    import_export.py   # Backup / restore (item 11)
    rebuild_index.py   # Rebuild indexes from storage (item 12)
    graph.py           # KnowledgeGraph facade (versioning, item 9)
  tests/
    test_acceptance.py # Definition-of-Done checklist tests
  main.py              # Runnable demo
```

## Project layout on disk

```
Project/
  project.json
  nodes/<node-id>.json
  relationships/<relationship-id>.json
  indexes/
    node-title-index.json
    relationship-index.json
```

## Usage

```python
from knowledge_graph import KnowledgeGraph

kg = KnowledgeGraph("./MyProject", name="World")

luffy = kg.create_node(title="Luffy", content="Captain")
zoro = kg.create_node(title="Zoro", content="Swordsman")
kg.create_relationship(luffy.id, zoro.id, metadata=["dong doi", "thay tro"])

kg.find_node_by_title("Zoro")             # fast title lookup
kg.get_relationships_of_node(luffy.id)     # traceability without full scan
kg.get_connected_nodes(luffy.id, "outbound")
```

## Run

```powershell
# from the Source/ folder (use `python` if `py` is unavailable)
py -3 main.py                              # demo
py -3 -m unittest discover -s tests -v     # acceptance tests
```

## Gemini API Key

Create `Source/.env` locally and put the key there:

```text
GEMINI_API_KEY=your_gemini_api_key_here
```

`Source/.env` is ignored by git. Keep `Source/.env.example` as the committed template.

## Acceptance checklist coverage

| Area | Covered |
|------|---------|
| Node / Relationship model | ✅ |
| Node / Relationship persistence | ✅ |
| CRUD (node & relationship) | ✅ |
| Node / Relationship index + rebuild | ✅ |
| Get relationships of node, connected nodes, inbound/outbound | ✅ |
| Unique id + relationship reference validation | ✅ |
| Persistence survives restart | ✅ |
| Import / Export | ✅ |
| Version field on Node & Relationship | ✅ |
