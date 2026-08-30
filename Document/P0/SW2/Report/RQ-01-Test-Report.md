# RQ-01 Data Storage Foundation — Test Report

- **Date:** 2026-08-29
- **Component:** Knowledge Graph storage foundation (`Source/knowledge_graph`)
- **Runner:** Python `unittest` (stdlib) — `py -3 -m unittest discover -s tests -v`
- **Result:** ✅ **24 / 24 passed** (0 failed, 0 errors) — no fixes required
- **Raw output:** [test-output.txt](test-output.txt)

## Summary

| Suite | File | Tests | Passed |
|-------|------|-------|--------|
| Base acceptance (DoD) | `tests/test_acceptance.py` | 11 | 11 |
| Extended (P1 + P2) | `tests/test_extended.py` | 13 | 13 |
| **Total** | | **24** | **24** |

## P1 — Required (directly verify requirements)

| # | Scenario | Test | Status |
|---|----------|------|--------|
| 1 | Project Isolation | `test_project_isolation` | ✅ |
| 2 | Relationship Version Increment | `test_relationship_version_increment` | ✅ |
| 3 | Delete Node Impact (cascade — Option 1) | `test_delete_node_removes_relationships` | ✅ |
| 4 | Unicode Node Content (VI / JA / ZH) | `test_unicode_node_content` | ✅ |
| 5 | Unicode Relationship Metadata | `test_unicode_relationship_metadata` | ✅ |

## P2 — Hardening

| # | Scenario | Test | Status |
|---|----------|------|--------|
| 6 | Restart + Rebuild Index | `test_restart_then_rebuild_index` | ✅ |
| 7 | Auto Node ID Generation (N001..N003) | `test_auto_node_id_generation` | ✅ |
| 8 | Auto Relationship ID Generation (R001..R003) | `test_auto_relationship_id_generation` | ✅ |
| 9 | Multiple Relationships (len == 4) | `test_multiple_relationships` | ✅ |
| 10 | Bidirectional Traversal (`both` → A, C) | `test_bidirectional_traversal` | ✅ |
| 11 | Import/Export Preserve IDs | `test_import_export_preserve_ids` | ✅ |
| 12 | Empty Project (no crash) | `test_empty_project` | ✅ |
| 13 | Rebuild Index After Index File Loss | `test_rebuild_index_after_index_deletion` | ✅ |

## Notes on behavior decisions

- **Delete Node Impact:** the implementation uses **Option 1 (cascade delete)** — deleting
  a Node automatically removes every Relationship attached to it and cleans the indexes.
  This keeps the graph valid with no dangling references.
- **Unicode:** all JSON is written with `ensure_ascii=False` + UTF-8, so Vietnamese,
  Japanese and Chinese text round-trips with no mojibake or corruption after reload.
- **Project isolation:** each `KnowledgeGraph` maps to a separate Project directory, so
  data in one Project never leaks into another.
- **ID preservation on import:** `import_nodes` keeps original ids (e.g. `N001`, `N002`)
  and does not regenerate them.

## Definition of Done (mở rộng) — status

All 13 extended checklist items are implemented and covered by passing tests.
**RQ-01 is production-ready for Phase 0.**

## How to reproduce

```powershell
cd Source
py -3 -m unittest discover -s tests -v
```
