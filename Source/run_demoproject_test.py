"""DemoProject use-case test harness (Phase 1).

Runs the full set of "chat with the AI" use cases against the DemoProject data
and logs every result (input, AI answer, sources, tool calls, proposal, commit,
undo, PASS/FAIL). The DemoProject is copied to a throwaway folder first, so the
original data is never modified or deleted; the harness verifies that at the end.

    py -3 run_demoproject_test.py                 # deterministic (scripted AI)
    py -3 run_demoproject_test.py --live          # real Gemini chat
    py -3 run_demoproject_test.py --live --log ../Document/P1/Test/log.txt

Exit code is 0 only if every functional check passes.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from ai import GeminiProvider, TokenUsage, load_settings
from ai.provider import AIProviderError, FunctionCall, IAIProvider, ProviderResponse
from app import AIWritingPartner, ChatTurn
from changes import create_node_change, create_relationship_change, update_node_change
from knowledge_graph import KnowledgeGraph

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.join(HERE, "DemoProject")


# -- logging -----------------------------------------------------------------
class Logger:
    def __init__(self, path: Optional[str]) -> None:
        # Windows consoles default to a legacy code page; force UTF-8 so the
        # Vietnamese project data prints without a UnicodeEncodeError.
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001 - older/redirected streams
                pass
        self._fh = open(path, "w", encoding="utf-8") if path else None
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results: list[tuple[str, str]] = []

    def line(self, text: str = "") -> None:
        try:
            print(text)
        except UnicodeEncodeError:
            print(text.encode("ascii", "replace").decode("ascii"))
        if self._fh:
            self._fh.write(text + "\n")
            self._fh.flush()

    def section(self, title: str) -> None:
        self.line("\n" + "=" * 70)
        self.line(title)
        self.line("=" * 70)

    def check(self, name: str, condition: bool, detail: str = "") -> bool:
        status = "PASS" if condition else "FAIL"
        self.line(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
        self.results.append((name, status))
        if condition:
            self.passed += 1
        else:
            self.failed += 1
        return condition

    def skip(self, name: str, reason: str = "") -> None:
        self.line(f"  [SKIP] {name}" + (f" — {reason}" if reason else ""))
        self.results.append((name, "SKIP"))
        self.skipped += 1

    def summary(self) -> None:
        self.section("SUMMARY")
        for name, status in self.results:
            self.line(f"  {status}  {name}")
        self.line("")
        self.line(f"  TOTAL: {self.passed} passed, {self.failed} failed, {self.skipped} skipped")

    def close(self) -> None:
        if self._fh:
            self._fh.close()


# -- scripted provider (deterministic mode) ----------------------------------
class DemoScriptedProvider(IAIProvider):
    """Replays a per-turn script of tool calls / text, using real DemoProject ids."""

    def __init__(self) -> None:
        self.script: list[ProviderResponse] = []
        self.i = 0

    def load(self, responses: list[ProviderResponse]) -> None:
        self.script = responses
        self.i = 0

    def generate(
        self,
        contents: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        max_output_tokens: Optional[int] = None,
    ) -> ProviderResponse:
        if not self.script:
            return _text("(no scripted response)")
        resp = self.script[min(self.i, len(self.script) - 1)]
        self.i += 1
        return resp


def _fc(name: str, **args: Any) -> FunctionCall:
    return FunctionCall(name=name, args=args)


def _calls(*calls: FunctionCall) -> ProviderResponse:
    return ProviderResponse(function_calls=list(calls), usage=TokenUsage(14, 7))


def _text(text: Optional[str]) -> ProviderResponse:
    return ProviderResponse(text=text, usage=TokenUsage(10, 6))


# -- harness setup -----------------------------------------------------------
@dataclass
class Harness:
    partner: AIWritingPartner
    scripted: Optional[DemoScriptedProvider]
    graph: KnowledgeGraph
    workdir: str
    live: bool
    log: Optional["Logger"] = None

    def say(self, msg: str, script: Optional[list[ProviderResponse]] = None) -> ChatTurn:
        if self.scripted is not None and script is not None:
            self.scripted.load(script)
        try:
            return self.partner.chat(msg)
        except AIProviderError as exc:  # rate limit / auth / timeout in live mode
            if self.log is not None:
                self.log.line(f"  [provider error] {type(exc).__name__}: {str(exc)[:120]}")
            return ChatTurn(answer=f"[provider unavailable: {type(exc).__name__}]",
                            stop_reason="provider_error")

    def newest_node_id(self) -> Optional[str]:
        nodes = self.graph.list_nodes()
        return sorted(nodes, key=lambda n: n.id)[-1].id if nodes else None


def provider_failed(turn: ChatTurn) -> bool:
    return turn.stop_reason == "provider_error"


def build_harness(live: bool, model: Optional[str] = None) -> Harness:
    workdir = tempfile.mkdtemp(prefix="demo_test_")
    project = os.path.join(workdir, "DemoProject")
    shutil.copytree(DEMO, project)  # work on a copy; original untouched

    settings = load_settings()
    if model:
        settings.ai.model = model
    scripted: Optional[DemoScriptedProvider] = None
    if live and settings.ai.api_key:
        provider: IAIProvider = GeminiProvider(settings.ai, timeout=60)
    else:
        scripted = DemoScriptedProvider()
        provider = scripted

    graph = KnowledgeGraph(project)
    partner = AIWritingPartner(graph, provider=provider, limits=settings.agent_limits)
    partner.start_session("demo-test")
    return Harness(partner, scripted, graph, workdir, live and scripted is None)


# -- original-data integrity (pure file reads, no mutation) ------------------
def signature(demo_path: str) -> dict[str, Any]:
    nodes = {}
    for path in sorted(glob.glob(os.path.join(demo_path, "nodes", "*.json"))):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        nodes[data["id"]] = (data["title"], data["content"])
    rels = {}
    for path in sorted(glob.glob(os.path.join(demo_path, "relationships", "*.json"))):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        rels[data["id"]] = (data["source_node_id"], data["target_node_id"])
    return {"nodes": nodes, "relationships": rels}


# -- scenarios ---------------------------------------------------------------
def scenario_find_existing(h: Harness, log: Logger) -> None:
    log.section("UC1 — Find information about an existing character (grounded)")
    turn = h.say(
        "Luffy là ai? Cậu ấy có những đồng đội nào trong băng?",
        script=[
            _calls(_fc("GetNode", nodeId="N001"), _fc("GetRelatedNodes", nodeId="N001")),
            _text("Luffy là thuyền trưởng băng Mũ Rơm; đồng đội gồm Zoro, Nami, Sanji."),
        ],
    )
    log.line(f"  user> Luffy là ai? Cậu ấy có những đồng đội nào?")
    log.line(f"  ai>   {turn.answer}")
    if provider_failed(turn):
        log.skip("UC1 grounded answer", "live provider unavailable (rate limit)")
        return
    log.check("answer is grounded in internal data", not turn.no_evidence)
    log.check("sources are cited", len(turn.sources) > 0,
              f"{[s.id for s in turn.sources]}")
    log.check("read at least one node/relationship tool", any(
        c.name in ("GetNode", "GetRelatedNodes", "SearchNode") for c in turn.tool_calls))


def scenario_no_evidence(h: Harness, log: Logger) -> None:
    log.section("UC2 — Ask about something not in the project (internal-first)")
    turn = h.say(
        "Kể cho tôi tiểu sử nhân vật Naruto Uzumaki trong dự án này.",
        script=[_calls(_fc("SearchNode", query="Naruto")), _text(None)],
    )
    log.line(f"  user> Kể tiểu sử Naruto Uzumaki trong dự án này.")
    log.line(f"  ai>   {turn.answer}")
    if provider_failed(turn):
        log.skip("UC2 no-evidence handling", "live provider unavailable (rate limit)")
        return
    if h.live:
        log.check("did not fabricate (no internal evidence)", not turn.sources or turn.no_evidence,
                  "live model answer logged above")
    else:
        log.check("flagged as no-evidence-found", turn.no_evidence)
        log.check("returned the No-Evidence message", "No internal information" in turn.answer)


def scenario_brainstorm(h: Harness, log: Logger) -> None:
    log.section("UC3 — Brainstorm an idea for a NEW character (discussion, no write)")
    turn = h.say(
        "Gợi ý một thành viên mới cho băng Mũ Rơm, phù hợp với thế giới hiện có. "
        "Chỉ thảo luận ý tưởng, chưa cần tạo.",
        script=[
            _calls(_fc("GetRelatedNodes", nodeId="N001")),
            _text("Gợi ý: một nhà khảo cổ học đi tìm lịch sử thế giới, hợp với hành trình "
                  "của băng. (Đây là ý tưởng để thảo luận, mình chưa tạo gì cả.)"),
        ],
    )
    log.line(f"  ai>   {turn.answer}")
    if provider_failed(turn):
        log.skip("UC3 brainstorm (no write)", "live provider unavailable (rate limit)")
        return
    log.check("brainstorm produced no write proposal yet", not turn.has_proposal)


def scenario_discuss(h: Harness, log: Logger) -> None:
    log.section("UC4 — Discuss / refine the idea further (multi-turn)")
    before = len(h.partner.current.messages)
    before_nodes = len(h.graph.list_nodes())
    turn = h.say(
        "Ý tưởng nhà khảo cổ hay đấy. Cho cô ấy một mối liên hệ trong quá khứ với Shanks.",
        script=[_text("Được, có thể để cô ấy từng gặp Shanks khi còn nhỏ và được ông giúp đỡ.")],
    )
    log.line(f"  ai>   {turn.answer}")
    if provider_failed(turn):
        log.skip("UC4 multi-turn discussion", "live provider unavailable (rate limit)")
        return
    log.check("conversation state grew (multi-turn memory)",
              len(h.partner.current.messages) > before)
    # The AI may stage an idea, but draft-before-commit means nothing is written
    # without approval — the graph must be unchanged after a discussion turn.
    log.check("no data written without approval (draft-before-commit)",
              len(h.graph.list_nodes()) == before_nodes)
    h.partner.discard_proposal()  # clear any staged idea before the explicit create


def scenario_create_node(h: Harness, log: Logger) -> None:
    log.section("UC5 — Agree to CREATE the new character (draft -> approve -> commit)")
    h.partner.discard_proposal()  # start from a clean slate
    nodes_before = len(h.graph.list_nodes())
    turn = h.say(
        "Ok, tạo nhân vật mới: Robin, nhà khảo cổ học, thành viên băng Mũ Rơm.",
        script=[
            _calls(_fc("ProposeCreateNode", title="Robin",
                       content="Nhà khảo cổ học của băng Mũ Rơm, đi tìm lịch sử bị lãng quên.",
                       reason="Thành viên mới theo thảo luận", ref="@robin")),
            _text("Mình đã đề xuất tạo Robin. Bạn xem và duyệt nhé."),
        ],
    )
    log.line(f"  ai>   {turn.answer}")
    if not h.partner.active_proposal() or h.partner.active_proposal().is_empty:
        # Fallback so the commit pipeline is still exercised in live mode.
        log.line("  (AI did not stage a change; staging Robin directly to test the pipeline)")
        h.partner._require_session().set_active_proposal(None)
        prop = h.partner._new_proposal(h.partner.current)
        prop.add(create_node_change("Robin",
                 "Nhà khảo cổ học của băng Mũ Rơm.", reason="fallback"))
        h.partner.current.set_active_proposal(prop)
    log.line(h.partner.change_panel())
    issues = h.partner.validate_proposal()
    log.check("proposal has no blocking consistency errors",
              not any(i.severity == "error" for i in issues), str([str(i) for i in issues]))
    approved = h.partner.approve()
    record = h.partner.commit()
    log.check("draft-before-commit: change approved then committed",
              record is not None and approved > 0)
    log.check("a new character node was created after commit",
              len(h.graph.list_nodes()) > nodes_before)


def scenario_create_link(h: Harness, log: Logger) -> None:
    log.section("UC6 — Create a LINK between the new character and Luffy")
    h.partner.discard_proposal()  # start from a clean slate
    robin = h.graph.find_node_by_title("Robin")
    robin_id = robin.id if robin else h.newest_node_id()
    rel_before = len(h.graph.list_relationships())
    turn = h.say(
        f"Liên kết Robin (id {robin_id}) với Luffy (id N001) là đồng đội.",
        script=[
            _calls(_fc("ProposeLinkNodes", sourceRef=robin_id, targetRef="N001",
                       metadata=["đồng đội"], reason="Robin là thành viên băng")),
            _text("Đã đề xuất liên kết Robin với Luffy."),
        ],
    )
    log.line(f"  ai>   {turn.answer}")
    if not h.partner.active_proposal() or h.partner.active_proposal().is_empty:
        log.line("  (AI did not stage a link; staging directly to test the pipeline)")
        prop = h.partner._new_proposal(h.partner.current)
        prop.add(create_relationship_change(robin_id, "N001", ["đồng đội"], reason="fallback"))
        h.partner.current.set_active_proposal(prop)
    log.line(h.partner.change_panel())
    h.partner.approve()
    record = h.partner.commit()
    log.check("relationship committed", record is not None)
    log.check("relationship count increased",
              len(h.graph.list_relationships()) > rel_before)


def scenario_update_node(h: Harness, log: Logger) -> None:
    log.section("UC7 — Update an existing character's description")
    h.partner.discard_proposal()  # start from a clean slate
    original = h.graph.get_node("N002").content
    turn = h.say(
        "Cập nhật mô tả của Zoro thành: 'Kiếm sĩ ba kiếm, quyết trở thành kiếm sĩ mạnh nhất thế giới.'",
        script=[
            _calls(_fc("ProposeUpdateNode", nodeId="N002",
                       content="Kiếm sĩ ba kiếm, quyết trở thành kiếm sĩ mạnh nhất thế giới.",
                       reason="Bổ sung chi tiết mục tiêu")),
            _text("Đã đề xuất cập nhật mô tả của Zoro."),
        ],
    )
    log.line(f"  ai>   {turn.answer}")
    if not h.partner.active_proposal() or h.partner.active_proposal().is_empty:
        log.line("  (AI did not stage an update; staging directly to test the pipeline)")
        prop = h.partner._new_proposal(h.partner.current)
        prop.add(update_node_change("N002",
                 content="Kiếm sĩ ba kiếm, quyết trở thành kiếm sĩ mạnh nhất thế giới.",
                 reason="fallback"))
        h.partner.current.set_active_proposal(prop)
    h.partner.approve()
    h.partner.commit()
    h._zoro_original = original  # remembered for the undo scenario
    log.check("Zoro description changed after commit",
              h.graph.get_node("N002").content != original)


def scenario_consistency(h: Harness, log: Logger) -> None:
    log.section("UC8 — Consistency / conflict detection (duplicate character)")
    h.partner.discard_proposal()  # start from a clean slate
    turn = h.say(
        "Tạo thêm một nhân vật tên Luffy nữa.",
        script=[
            _calls(_fc("ProposeCreateNode", title="Luffy",
                       content="Một Luffy khác.", reason="test trùng tên")),
            _text("Mình đã đề xuất, nhưng lưu ý tên này có thể trùng."),
        ],
    )
    log.line(f"  ai>   {turn.answer}")
    if not h.partner.active_proposal() or h.partner.active_proposal().is_empty:
        log.line("  (staging a duplicate 'Luffy' directly to test consistency detection)")
        prop = h.partner._new_proposal(h.partner.current)
        prop.add(create_node_change("Luffy", "Một Luffy khác.", reason="fallback dup"))
        h.partner.current.set_active_proposal(prop)
    issues = h.partner.validate_proposal()
    log.line(f"  consistency issues: {[str(i) for i in issues]}")
    has_dupe_warning = any(
        getattr(i, "code", "") in ("duplicate_title", "similar_title") for i in issues)
    log.check("duplicate title detected before commit", has_dupe_warning)
    node_count_before = len(h.graph.list_nodes())
    h.partner.reject()
    h.partner.discard_proposal()
    log.check("duplicate not committed (rejected/discarded)",
              len(h.graph.list_nodes()) == node_count_before)


def scenario_undo(h: Harness, log: Logger) -> None:
    log.section("UC9 — Undo the last change (restore previous state)")
    zoro_before_undo = h.graph.get_node("N002").content
    result = h.partner.undo_last()
    log.line(f"  undo result: ok={getattr(result, 'ok', None)} "
             f"reversed={getattr(result, 'reversed_count', None)}")
    restored = h.graph.get_node("N002").content
    log.check("undo reported success", result is not None and result.ok)
    log.check("Zoro description restored by undo",
              restored == getattr(h, "_zoro_original", zoro_before_undo))


def scenario_internet_mode(h: Harness, log: Logger) -> None:
    log.section("UC10 — Internet Mode toggle (external knowledge, opt-in)")
    log.check("internet mode is OFF by default (internal-only)",
              not h.partner.knowledge_mode.is_external_allowed)
    h.partner.set_internet_mode(True)
    turn = h.say(
        "Trong thần thoại Hy Lạp, ai là thần cai quản biển cả?",
        script=[_text("[EXTERNAL] Theo thần thoại Hy Lạp, Poseidon là thần biển.")],
    )
    log.line(f"  ai>   {turn.answer}")
    log.check("internet mode enabled on request",
              h.partner.knowledge_mode.is_external_allowed)
    h.partner.set_internet_mode(False)
    log.check("internet mode toggled back off",
              not h.partner.knowledge_mode.is_external_allowed)


def scenario_memory_promotion(h: Harness, log: Logger) -> None:
    log.section("UC11 — Memory promotion (save a confirmed fact to the project)")
    h.partner._require_session().add_assumption(
        "Băng Mũ Rơm từng có con tàu Going Merry trước tàu Sunny.")
    proposal = h.partner.promote_assumptions()
    log.check("promotion produced a proposal", proposal is not None)
    if proposal:
        log.line(h.partner.change_panel())
        h.partner.approve()
        record = h.partner.commit()
        log.check("promoted fact written after approval", record is not None)


def scenario_observability(h: Harness, log: Logger) -> None:
    log.section("UC12 — Observability: debug view, cost, diagnostics export")
    debug = h.partner.debug_view()
    log.line(debug[:600] + ("..." if len(debug) > 600 else ""))
    log.check("debug view has decision flow + token usage",
              "DECISION FLOW" in debug and "TOKEN USAGE" in debug)
    log.check("token/cost tracked", h.partner.cost.total_tokens > 0,
              str(h.partner.cost.summary()))
    diag_dir = os.path.join(h.workdir, "diagnostics")
    h.partner.export_diagnostics(diag_dir)
    log.check("diagnostic package exported",
              os.path.exists(os.path.join(diag_dir, "package.json")))
    log.line(f"  diagnostics at: {diag_dir}")
    log.line(f"  history: {[r.id + ' ' + r.summary for r in h.partner.history_view()]}")


def scenario_integrity(h: Harness, log: Logger, before: dict[str, Any]) -> None:
    log.section("UC13 — Original DemoProject data integrity (must be untouched)")
    after = signature(DEMO)
    log.check("original node count unchanged by this test",
              len(after["nodes"]) == len(before["nodes"]),
              f"{len(before['nodes'])} nodes: {[t for t, _ in after['nodes'].values()]}")
    log.check("original relationship count unchanged by this test",
              len(after["relationships"]) == len(before["relationships"]))
    log.check("original data byte-for-byte unchanged", after == before)


# -- driver ------------------------------------------------------------------
def run(live: bool, log_path: Optional[str], model: Optional[str] = None) -> int:
    log = Logger(log_path)
    settings = load_settings()
    active_model = model or settings.ai.model
    mode = f"LIVE (real Gemini: {active_model})" if live and settings.ai.api_key else "SCRIPTED (deterministic)"
    log.line(f"Phase 1 — DemoProject Use-Case Test")
    log.line(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    log.line(f"Mode: {mode}")
    log.line(f"DemoProject: {DEMO}")

    before = signature(DEMO)  # snapshot original before anything runs
    h = build_harness(live, model)
    h.log = log
    log.line(f"Working copy: {h.workdir}")

    scenarios = [
        scenario_find_existing,
        scenario_no_evidence,
        scenario_brainstorm,
        scenario_discuss,
        scenario_create_node,
        scenario_create_link,
        scenario_update_node,
        scenario_consistency,
        scenario_undo,
        scenario_internet_mode,
        scenario_memory_promotion,
        scenario_observability,
    ]
    try:
        for scenario in scenarios:
            try:
                scenario(h, log)
            except Exception as exc:  # noqa: BLE001 - keep the suite running
                log.check(f"{scenario.__name__} completed without crash", False,
                          f"{type(exc).__name__}: {str(exc)[:120]}")
        scenario_integrity(h, log, before)
    finally:
        shutil.rmtree(h.workdir, ignore_errors=True)

    log.summary()
    log.close()
    return 0 if log.failed == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="DemoProject use-case test harness")
    parser.add_argument("--live", action="store_true", help="use the real Gemini model")
    parser.add_argument("--model", default=None, help="override the model for this run")
    parser.add_argument("--log", default=None, help="write the log to this path")
    parsed = parser.parse_args()
    sys.exit(run(parsed.live, parsed.log, parsed.model))


if __name__ == "__main__":
    main()
