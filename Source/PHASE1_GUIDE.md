# Phase 1 — AI Writing Partner Guide

Phase 1 turns the Phase-0 storage foundation into a **chat-centric AI writing
partner**. You talk to one assistant; it grounds every answer in your project,
proposes changes before writing, and lets you review, approve, reject and undo.
The Knowledge Graph is the assistant's memory — you never edit it by hand.

## Setup Instructions

1. Python 3.10+ (standard library only, no external packages).
2. Put your Gemini key in `Source/.env`:

   ```text
   GEMINI_API_KEY=your_key_here
   ```

   Without a key the chat is disabled, but every management command still works.
3. Optionally tune `Source/appsettings.json` (model, token limits, agent limits).

## Running

```powershell
# from the Source/ folder
py -3 chat.py --project ./MyProject      # start chatting (folder is created if missing)
py -3 -m unittest tests.test_phase1_core tests.test_phase1_partner -v   # acceptance tests
```

## User Guide — the chat surface

Type normally to talk to the assistant. Slash commands drive the workflow:

| Command | Purpose |
| --- | --- |
| `/review` | show the pending proposal (change panel) |
| `/approve [ids...]` | approve all pending changes, or specific change ids |
| `/reject [ids...]` | reject all pending changes, or specific change ids |
| `/commit` | apply approved changes to the project |
| `/discard` | throw away the pending proposal |
| `/undo` | undo the last commit (restores previous state) |
| `/history`, `/search <text>` | list / search change history |
| `/context` | context panel: sources used, tools called, session memory |
| `/debug` | decision flow, retrieval path, tool sequence, token usage |
| `/diag <dir>` | export a diagnostic package for a failing session |
| `/internet on\|off` | toggle Internet Mode (external knowledge) |
| `/goal`, `/assume`, `/promote` | set goal, note an assumption, promote facts to memory |
| `/settings`, `/new [id]`, `/quit` | settings, new session, exit |

### The core workflow (draft before commit)

1. Ask the assistant to change the world ("add a navigator named Nami").
2. It stages a **proposal** — nothing is written yet.
3. `/review` to see exactly what will be added / modified / deleted, with reasons.
4. `/approve` (all or specific ids) then `/commit`. You can `/reject` parts.
5. Made a mistake? `/undo` reverses the last commit.

## AI Usage Guide

- **Internal first.** By default the assistant answers only from your project.
  If it finds nothing it says so ("No internal information was found") instead of
  inventing facts.
- **Sources are cited.** Every grounded answer lists the nodes/relationships it
  used. `/context` shows the same evidence plus the tools it called.
- **Internet Mode is opt-in.** `/internet on` lets it use outside knowledge;
  such content is marked `[EXTERNAL]`. Project data still takes priority.
- **It plans its own retrieval.** You don't point it at nodes; it searches,
  expands context and traverses relationships on its own.
- **Brainstorming.** Ask it to find gaps (`FindContentGaps`), check consistency
  (`CheckConsistency`), or develop characters/events/settings; it grounds ideas
  in what already exists.

## Known Limitations

- Storage is JSON files: fine for a personal project, not for concurrent multi-
  user writing or very large worlds.
- Undo restores content/relationships faithfully; version numbers and timestamps
  on restored items are refreshed rather than byte-for-byte preserved.
- "Streaming" responses are delivered per turn, not token-by-token.
- Consistency/conflict detection is structural (duplicate titles, dangling
  links, missing targets), not deep semantic contradiction analysis.
- Cost estimates depend on the rates you configure; defaults are zero.
- Internet Mode relies on the model's own knowledge; there is no live web fetch.
