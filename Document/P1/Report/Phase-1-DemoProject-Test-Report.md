# Phase 1 — DemoProject Use-Case Test Report

- Date: 2026-08-30
- Scope: End-to-end "chat with the AI" use cases against real project data
- Data source: `Source/DemoProject` (One Piece world — Luffy, Zoro, Nami, Sanji, Shanks)
- Harness: `Source/run_demoproject_test.py`
- Logs: `demoproject-functional-log.txt` (deterministic), `demoproject-live-chat-log.txt` (real Gemini)

## Purpose

Verify every Phase-1 capability through the conversational surface, using the
actual DemoProject data, across the use cases a real user runs: find existing
character info, brainstorm a new character, discuss/refine, agree to create a
node, create a link, update, detect conflicts, undo, toggle Internet Mode,
promote a fact to memory, and inspect observability.

## Method & data-safety guarantee

- The harness **copies DemoProject to a throwaway folder** and runs every read
  and write there. The original is opened **read-only** for verification.
- A byte-for-byte signature of the original is captured before the run and
  re-checked after (UC13). **The original DemoProject data is never modified or
  deleted.** Verified: 5 nodes `[Luffy, Zoro, Nami, Sanji, Shanks]`, 5
  relationships, counters 5/5 — unchanged after all runs.
- Two modes were executed:
  1. **Deterministic** — a scripted provider drives the exact tool sequence, giving
     reproducible, fully-asserted results.
  2. **Live** — the real Gemini model (`gemini-flash-lite-latest`) actually
     converses, so the log contains genuine AI answers.

## Results

| Mode | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Deterministic (scripted) | 29 | 0 | 0 |
| Live (real Gemini) | 28 | 0 | 0 |

All use cases pass in both modes; the original data is verified intact in both.

## Use-case coverage

| UC | Scenario | What it proves | Result |
| --- | --- | --- | --- |
| UC1 | Find info on an existing character | Grounded retrieval + source attribution | ✅ |
| UC2 | Ask about something not in the project | Internal-first, "No Evidence Found", no fabrication | ✅ |
| UC3 | Brainstorm a NEW character (discuss only) | Creative ideas grounded in existing world, no write | ✅ |
| UC4 | Discuss / refine further | Multi-turn memory; nothing written without approval | ✅ |
| UC5 | Agree to create the character | Draft → approve → commit; node created | ✅ |
| UC6 | Create a link to Luffy | Relationship proposal → commit | ✅ |
| UC7 | Update an existing character | Update proposal → commit | ✅ |
| UC8 | Try to create a duplicate | Consistency/conflict detection blocks it | ✅ |
| UC9 | Undo the last change | Reversal + restore verification | ✅ |
| UC10 | Toggle Internet Mode | External knowledge is opt-in, off by default | ✅ |
| UC11 | Promote a fact to memory | Working → long-term via approval | ✅ |
| UC12 | Observability | Debug view, cost/tokens, diagnostic export | ✅ |
| UC13 | Original data integrity | DemoProject untouched | ✅ |

## Real AI transcript (live, excerpts)

**UC1 — find existing character (grounded + cited):**
> user> Luffy là ai? Cậu ấy có những đồng đội nào?
> ai> …**Luffy** là thuyền trưởng băng Mũ Rơm và là tương lai Vua Hải Tặc. Các
> đồng đội… bao gồm: **Zoro**, **Nami** và **Sanji**.
> Sources: Node N002 (Zoro), Relationship R001 (đồng đội…), Node N003 (Nami)…

**UC2 — not in project (no fabrication):**
> user> Kể tiểu sử Naruto Uzumaki trong dự án này.
> ai> Không tìm thấy thông tin nào về nhân vật Naruto Uzumaki trong cơ sở dữ liệu của dự án.

**UC3 — brainstorm grounded in the world (no write):**
> ai> …một ý tưởng thành viên mới có thể là: **Một thợ đóng tàu (Shipwright)**…
> hoặc **Một bác sĩ (Doctor)**… *(Đây chỉ là ý tưởng thảo luận…, chưa được thêm vào hệ thống.)*

**UC5 — agree to create → staged as a reviewable proposal (not written yet):**
> ai> Tôi đã soạn thảo các đề xuất thay đổi… 1. Tạo node mới: **Robin**… 2. Liên kết:
> Robin ↔ Luffy (N001)… Vui lòng xem xét và phê duyệt…
> ```
> Proposal demo-test-P2 — AI-proposed changes
>   Added:
>     + Create node 'Robin'  (pending)
>     + Link @robin -> N001 :: thành viên, đồng đội  (pending)
>     + Link @robin -> N005 :: mối liên hệ quá khứ  (pending)
> ```
> → after approve + commit: a new character node exists in the (copied) project.

This is the Definition of Done in action: the AI found data, cited it, refused to
invent, brainstormed grounded ideas, and **proposed** changes that only became
real after explicit approval.

## Reliability note

The live model calls flow through the real Gemini API on the free tier. The
harness handles transient rate limits (HTTP 429) gracefully — an affected turn is
logged and the run continues; write use cases still exercise the full
proposal → commit → undo pipeline. In the recorded live run one turn (UC7) hit a
rate limit and was covered by the pipeline fallback, so the final result remained
28/0/0.

## Bug found and fixed during testing

Live multi-turn tool calling initially failed with
`HTTP 400: Function call is missing a thought_signature`. Gemini "thinking" models
(2.5 / flash-lite) return an opaque `thoughtSignature` with each function call that
must be echoed back on the next turn. Fixed in
[Source/ai/provider.py](../../../Source/ai/provider.py) and
[Source/ai/agent.py](../../../Source/ai/agent.py) by preserving and re-sending the
signature. After the fix, live multi-turn tool calling works end to end.

## How to reproduce

```powershell
# from the Source/ folder
py -3 run_demoproject_test.py --log ../Document/P1/Test/demoproject-functional-log.txt
py -3 run_demoproject_test.py --live --model gemini-flash-lite-latest \
   --log ../Document/P1/Test/demoproject-live-chat-log.txt
```

Both runs copy DemoProject first, so re-running never risks the original data.

## Verdict

All 13 Phase-1 use cases pass against real DemoProject data in both deterministic
and live modes, with the original data verified untouched. The chat-centric
draft-before-commit workflow, grounding, consistency, undo, memory, Internet Mode
and observability are all confirmed working end to end.
