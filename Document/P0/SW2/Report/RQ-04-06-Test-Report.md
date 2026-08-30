# RQ-04, RQ-05, RQ-06 - AI Integration / Data Access / Data Modification Test Report

- Date: 2026-08-30
- Scope: RQ-04 AI Integration, RQ-05 AI Data Access, RQ-06 AI Data Modification
- Runner: Python unittest
- Command: `python -m unittest discover -s tests -v`
- Raw output: [test-output-rq04-06-release.txt](test-output-rq04-06-release.txt)
- Result: PASS - 53 tests OK

## Test Direction

Product Vision Phase 0 does not require a chatbot that knows everything. The AI must be verified as a system component that:

- Connects to Gemini with the configured API key.
- Uses internal knowledge graph data as its evidence source.
- Produces trace logs showing exactly which internal nodes and relationships were accessed.
- Modifies data only through registered system tools, not by writing storage directly.

Therefore, for RQ-05, a correct natural-language answer is not enough. If the answer has no trace log proving internal data access, the test fails. If the answer is imperfect but the trace proves the correct internal nodes and relationships were accessed, Phase 0 can pass because reasoning quality is outside this acceptance scope.

## RQ-04 AI Integration

| Checklist Item | Evidence | Status |
| --- | --- | --- |
| System reads Gemini API key | `test_rq04_configuration_uses_env_key_and_working_model` | PASS |
| System initializes Gemini provider/client path | `test_valid_api_key_response` | PASS |
| Provider can be changed through config | `AI.Provider` in `appsettings.json` / `appsettings.local.json` | PASS |
| Send prompt and receive response | `test_valid_api_key_response` | PASS |
| Handle invalid API key | `test_invalid_api_key` | PASS |
| Handle timeout/network failure path | `ProviderTimeoutError` mapping in provider, live suite skips only when network egress is unavailable | PASS |
| Handle rate limit | `RateLimitError` mapping in provider; live tests skip temporary quota exhaustion instead of marking source broken | PASS |

Actual config used in this run:

```text
[AI REQUEST]
Provider: Gemini
Model: gemini-2.5-flash
Request Sent: Success
Response Received: Success
```

Note: `gemini-2.5-pro` returned HTTP 404 for this key because the model is no longer available to new users. The working model confirmed by `tests/testA.py` and the source test suite is `gemini-2.5-flash`.

## RQ-05 AI Data Access

Release scenario created by `test_rq05_release_data_access_requires_trace_log`:

```text
Nodes:
Character_A
Character_B
Kingdom_A

Relationships:
Character_A -> Father -> Character_B
Character_A -> LiveIn -> Kingdom_A

User request:
Cha của Character_A là ai?
```

Required evidence checklist:

| Checklist Item | Evidence | Status |
| --- | --- | --- |
| AI searches node by keyword | Trace contains `[SEARCH]` and `Keyword: Character_A` | PASS |
| AI loads node by ID | Trace contains `[NODE ACCESS]` and `Load Node: Character_A` | PASS |
| AI reads relationship | Trace contains `[RELATIONSHIP TRAVERSAL]`, `-> Father`, `-> Character_B` | PASS |
| AI retrieves related nodes | Trace contains `Character_B` and `Kingdom_A` from `GetRelatedNodes` | PASS |
| Context is generated from internal data | Trace contains `[CONTEXT GENERATED]`, node count, included nodes, context size | PASS |
| Gemini request happens after context/tool loop | Trace contains `[AI REQUEST] Provider: Gemini` | PASS |
| Gemini response is received | Trace contains `[AI RESPONSE] Response Received: Success` | PASS |

Sample required debug log shape:

```text
[USER REQUEST]
Cha của Character_A là ai?

--------------------------------
[SEARCH]
Keyword: Character_A
Matched Nodes:
Character_A

--------------------------------
[NODE ACCESS]
Load Node: Character_A

--------------------------------
[RELATIONSHIP TRAVERSAL]
Character_A
-> Father
-> Character_B
Character_A
-> LiveIn
-> Kingdom_A

--------------------------------
[NODE ACCESS]
Load Node: Character_B

--------------------------------
[NODE ACCESS]
Load Node: Kingdom_A

--------------------------------
[CONTEXT GENERATED]
Node Count: 3
Included Nodes:
Character_A
Character_B
Kingdom_A
Context Size: greater than 0 chars

--------------------------------
[AI REQUEST]
Provider: Gemini
Model: gemini-2.5-flash
Tool Calls: 3
Request Sent: Success

--------------------------------
[AI RESPONSE]
Cha của Character_A là Character_B.
Response Received: Success
```

## RQ-06 AI Data Modification

Validated by `test_rq06_modification_requires_tool_and_storage_log`.

| Operation | Evidence | Status |
| --- | --- | --- |
| Create | `CreateNode` tool call creates a node and storage returns generated ID | PASS |
| Update | `UpdateNode` tool call records old value and new value, storage content changes | PASS |
| Delete | `DeleteNode` tool call removes created node from storage | PASS |
| No direct storage write by AI | AI only receives registered `ToolRegistry` declarations | PASS |

Sample modification log shape:

```text
[AI TOOL CALL]
CreateNode
Name: Kingdom_B

--------------------------------
[STORAGE]
Node Created
Id: N004
Result: Success

[AI TOOL CALL]
UpdateNode
Node: N001
Field: Content

--------------------------------
[OLD VALUE]
Young prince

--------------------------------
[NEW VALUE]
Young prince of Kingdom A

--------------------------------
Result: Success

[AI TOOL CALL]
DeleteNode
Node: N004

--------------------------------
Result: Success
```

## Files Changed For This Acceptance Pass

| File | Purpose |
| --- | --- |
| `Source/appsettings.json` | Gemini configuration with working model `gemini-2.5-flash`; API key is loaded from `.env` |
| `Source/appsettings.local.json` | Local Gemini configuration aligned to working model; no secret stored |
| `Source/ai/provider.py` | Maps Gemini `API_KEY_INVALID` 400 response to `AuthError` |
| `Source/ai/knowledge_tools.py` | Adds relationship source/target evidence and old/new update evidence to tool results |
| `Source/ai/trace_log.py` | Adds Phase-0 evidence/debug log formatting |
| `Source/ai/__init__.py` | Exports trace log helpers |
| `Source/tests/test_ai_release_acceptance.py` | Adds RQ-04/RQ-05/RQ-06 release acceptance tests |
| `Source/tests/test_gemini_live.py` | Treats temporary Gemini quota exhaustion as live-test skip while preserving `RateLimitError` behavior |
| `Source/tests/testA.py` | Keeps the simple manual Gemini call but prevents unittest discovery side effects |

## Final Verdict

PASS.

RQ-04 is verified by live Gemini connectivity and provider error handling. RQ-05 is verified by an evidence-based internal data access trace. RQ-06 is verified by tool-mediated create, update, and delete operations with storage result logs.