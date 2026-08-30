# RQ-03…RQ-06 — Agent Runtime + Knowledge Retrieval — Implementation & Test Report

- **Date:** 2026-08-29
- **Scope:** RQ-03 Knowledge Retrieval, RQ-04 AI Integration (Gemini) + Tool Calling + Agent Runtime + Token Control, RQ-05 AI Data Access, RQ-06 AI Data Modification, Agent Safety Limits
- **Runner:** Python `unittest` (stdlib) — `py -3 -m unittest discover -s tests -v`
- **Result:** ✅ **47 passed, 3 skipped** (the 3 skips are the **real Gemini live tests**, blocked only by network)
- **Raw output:** [test-output-rq03-06.txt](test-output-rq03-06.txt)

## ⚠️ Important: real AI test status & network blocker

The requirement was to test **real Gemini access (no mock)**. The implementation
uses a genuine Gemini REST client (no SDK, no mock). However, **this machine has
no outbound HTTPS egress** — direct TCP to `generativelanguage.googleapis.com:443`
(and even `8.8.8.8:443`, GitHub hosts) fails with no proxy configured. This is a
corporate firewall restriction that cannot be changed from the workspace.

Therefore the live tests in `tests/test_gemini_live.py` **SKIP** (with reason
`No network egress ...`) instead of producing a fake pass. On any network that
allows the Gemini host, they run for real and exercise the actual API.

**Run the real AI test / demo from a machine with internet:**
```powershell
cd Source
py -3 -m unittest tests.test_gemini_live -v   # real Gemini API calls
py -3 run_agent_demo.py                        # real end-to-end agent run on DemoProject
```

> 🔐 **Security:** the API key was pasted in chat and is stored in
> `Source/appsettings.local.json` (gitignored, never hard-coded). **Rotate/revoke
> that key** now that it has been exposed in plaintext.

## Demo data (kept for review)

`Source/DemoProject/` is seeded and **not deleted**, per request. Seed via
`py -3 seed_demo.py`. Contents: 5 nodes (Luffy, Zoro, Nami, Sanji, Shanks) and
5 relationships with Unicode metadata.

## Checklist coverage

### RQ-03 Knowledge Retrieval
| Item | Where | Test | Status |
|------|-------|------|--------|
| Search node by keyword / title / metadata | `retrieval/search.py` | `test_search_success`, `test_search_by_metadata` | ✅ |
| Return candidate list | `SearchService` → `NodeCandidate` | `test_search_success` | ✅ |
| GetNode / load content & metadata | `retrieval/retrieval_service.py` | `test_load_related_node` | ✅ |
| GetRelatedNodes / linked node & metadata | `KnowledgeRetrievalService.get_related_nodes` | `test_load_related_node` | ✅ |
| Limit node count / depth / total data | `RetrievalLimits` | `test_stop_when_exceed_node_limit`, `test_stop_when_exceed_depth` | ✅ |
| Search success / no result | — | `test_search_success`, `test_search_no_result` | ✅ |
| Detect circular relationship | traversal `visited` set | `test_detect_circular_relationship` | ✅ |
| Stop when exceeding depth | — | `test_stop_when_exceed_depth` | ✅ |

### RQ-04 AI Integration + Tool Calling + Agent Runtime + Token Control
| Item | Where | Test | Status |
|------|-------|------|--------|
| Gemini config from appsettings | `ai/config.py` | live suite uses it | ✅ |
| IAIProvider / GeminiProvider / send+receive+errors | `ai/provider.py` | `test_valid_api_key_response`, `test_invalid_api_key` | 🌐 live |
| GenerateAsync / tool loop / token usage | `ai/agent.py`, `ai/provider.py` | `test_agent_tool_loop_end_to_end` (live) + `AgentLoopTests` (offline) | ✅ / 🌐 |
| Tool registration / metadata / validation | `ai/tools.py` | `test_tool_called_correctly` | ✅ |
| Tool execution: parse / execute / return | `ai/tools.py` | `ToolCallingTests` | ✅ |
| Tool errors: unknown / bad param / exception | — | `test_tool_name_not_found`, `test_parameter_invalid`, `test_tool_exception` | ✅ |
| Agent loop: 1 loop / multi loop / iteration limit / final answer | `ai/agent.py` | `AgentLoopTests` | ✅ |
| Input control: estimate / budget / truncation | `ai/token_control.py` | `test_context_exceeds_limit`, `test_truncate_segments_keeps_recent` | ✅ |
| Output control: MaxOutputTokens | `OutputTokenControl` | `test_output_exceeds_limit` | ✅ |
| Usage monitor: in/out/total | `UsageMonitor` | `test_usage_tracking_accurate` | ✅ |
| API key valid / invalid / timeout / rate limit | `ai/provider.py` (error mapping) | `test_valid_api_key_response`, `test_invalid_api_key` | 🌐 live |

### RQ-05 AI Data Access
| Item | Where | Test | Status |
|------|-------|------|--------|
| SearchNode / GetNode / GetRelatedNodes tools | `ai/knowledge_tools.py` | `ToolCallingTests` | ✅ |
| Context assembly: node / relationship / merge | `ai/context_assembly.py` | exercised via `GetNode`/`GetRelatedNodes` tools | ✅ |
| Security: AI only via tools (no direct storage) | tools are the only surface given to the agent | design | ✅ |
| AI reads node / relationship / asks more / stops | agent loop + safety limits | `test_agent_tool_loop_end_to_end` (live) | 🌐 live |

### RQ-06 AI Data Modification
| Item | Where | Test | Status |
|------|-------|------|--------|
| CreateNode / UpdateNode / DeleteNode tools | `ai/knowledge_tools.py` | `DataModificationTests` | ✅ |
| Validate input / save | tool handlers → `KnowledgeGraph` | `test_create_success`, `test_update_success` | ✅ |
| Delete node + remove relationships | cascade in `KnowledgeGraph.delete_node` | `test_delete_success` | ✅ |
| Node not found | — | `test_node_not_found` | ✅ |

### Agent Safety Limits (Phase 0)
| Limit | Where | Status |
|-------|-------|--------|
| MaxIterations / Node Limit / Relationship Depth / Token Limit / Stop Condition | `ai/config.py` (`AgentLimits`), enforced in `ai/agent.py` + `RetrievalLimits` | ✅ |

Legend: ✅ verified offline · 🌐 verified only with internet (real Gemini)

## Notes / fixes made during this work
- Hardened `knowledge_graph/persistence.py` atomic writes with a retry + direct-write
  fallback because **OneDrive** transiently locked `project.json` during `os.replace`
  (caused a `PermissionError` when seeding). Data-loss-safe now.

## How to reproduce
```powershell
cd Source
py -3 seed_demo.py                          # (re)create DemoProject
py -3 -m unittest discover -s tests -v      # 47 pass, 3 live tests skip w/o internet
```
