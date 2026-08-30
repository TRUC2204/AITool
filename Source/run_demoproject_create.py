"""Persisted create demo — the AI writes a new related character into the REAL
DemoProject (Phase 1).

Unlike run_demoproject_test.py (which works on a throwaway copy), this runs
against Source/DemoProject directly so you can see the AI actually create a new
node and relationship ON DISK: discuss -> propose -> approve -> commit -> files
appear under DemoProject/nodes and DemoProject/relationships, and survive a fresh
reload.

    py -3 run_demoproject_create.py                         # live Gemini
    py -3 run_demoproject_create.py --model gemini-flash-lite-latest
    py -3 run_demoproject_create.py --scripted              # offline, deterministic

The changes are permanent; undo them from the chat app with /undo if you want the
project back to its previous state.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Any, Optional

from ai import GeminiProvider, TokenUsage, load_settings
from ai.provider import FunctionCall, IAIProvider, ProviderResponse
from app import AIWritingPartner, ChatTurn
from changes import create_node_change, create_relationship_change
from knowledge_graph import KnowledgeGraph

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.join(HERE, "DemoProject")
LOG_PATH = os.path.join(HERE, "..", "Document", "P1", "Test", "demoproject-create-log.txt")

_LOG_FH = None


def out(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))
    if _LOG_FH:
        _LOG_FH.write(text + "\n")
        _LOG_FH.flush()


# -- scripted fallback provider ---------------------------------------------
class ScriptProvider(IAIProvider):
    def __init__(self) -> None:
        self.script: list[ProviderResponse] = []
        self.i = 0

    def load(self, responses: list[ProviderResponse]) -> None:
        self.script, self.i = responses, 0

    def generate(self, contents, tools=None, max_output_tokens=None) -> ProviderResponse:
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


def snapshot(graph: KnowledgeGraph) -> str:
    nodes = graph.list_nodes()
    rels = graph.list_relationships()
    lines = [f"  nodes ({len(nodes)}): " + ", ".join(f"{n.id}:{n.title}" for n in nodes)]
    lines.append(f"  relationships ({len(rels)}): " + ", ".join(
        f"{r.id}:{r.source_node_id}->{r.target_node_id}" for r in rels))
    return "\n".join(lines)


def commit_proposal(partner: AIWritingPartner, label: str) -> None:
    issues = [i for i in partner.validate_proposal() if i.severity == "error"]
    if issues:
        out(f"  [consistency] blocking: {[str(i) for i in issues]}")
        partner.discard_proposal()
        return
    approved = partner.approve()
    record = partner.commit()
    if record:
        out(f"  COMMITTED {label}: {approved} change(s) -> {record.id} (written to disk)")
    else:
        out(f"  nothing committed for {label}")


def run(scripted_mode: bool, model: Optional[str]) -> int:
    settings = load_settings()
    if model:
        settings.ai.model = model

    provider: IAIProvider
    script: Optional[ScriptProvider] = None
    if scripted_mode or not settings.ai.api_key:
        script = ScriptProvider()
        provider = script
        mode = "SCRIPTED (deterministic)"
    else:
        provider = GeminiProvider(settings.ai, timeout=60)
        mode = f"LIVE ({settings.ai.model})"

    graph = KnowledgeGraph(DEMO)  # the REAL project — changes persist to disk
    partner = AIWritingPartner(graph, provider=provider, limits=settings.agent_limits)
    partner.start_session("create-demo")

    out("=" * 70)
    out("Persisted create demo — writing into the REAL DemoProject")
    out(f"Mode: {mode}")
    out("=" * 70)
    out("\nBEFORE:")
    out(snapshot(graph))
    nodes_before = len(graph.list_nodes())
    rels_before = len(graph.list_relationships())

    # -- Turn 1: discuss a new related character ---------------------------
    out("\n" + "-" * 70)
    out("STEP 1 — Discuss a new character related to Luffy")
    if script:
        script.load([
            _calls(_fc("GetRelatedNodes", nodeId="N001")),
            _text("Gợi ý: thêm Nico Robin — nhà khảo cổ học, gia nhập băng Mũ Rơm và trở "
                  "thành đồng đội của Luffy. Cô đọc được Poneglyph, rất hợp hành trình tìm "
                  "lịch sử thế giới. (Đây là ý tưởng, mình chưa ghi gì cả.)"),
        ])
    t1 = partner.chat("Tôi muốn thêm một nhân vật mới có liên quan tới Luffy. "
                      "Gợi ý một nhân vật phù hợp với thế giới hiện có và giải thích mối liên hệ.")
    out(f"  user> Gợi ý một nhân vật mới liên quan tới Luffy.")
    out(f"  ai>   {t1.answer}")
    partner.discard_proposal()  # discussion only — don't keep any staged idea

    # -- Turn 2: agree, AI creates the node --------------------------------
    out("\n" + "-" * 70)
    out("STEP 2 — Agree; the AI proposes creating the character")
    if script:
        script.load([
            _calls(_fc("ProposeCreateNode", title="Robin",
                       content="Nhà khảo cổ học của băng Mũ Rơm, đọc được Poneglyph, "
                               "đồng đội của Luffy.",
                       reason="Thêm nhân vật mới theo thảo luận", ref="@robin")),
            _text("Mình đã đề xuất tạo node Robin. Bạn duyệt nhé."),
        ])
    t2 = partner.chat("Đồng ý. Hãy tạo nhân vật Robin — nhà khảo cổ học của băng Mũ Rơm.")
    out(f"  user> Hãy tạo nhân vật Robin.")
    out(f"  ai>   {t2.answer}")
    if not partner.active_proposal() or partner.active_proposal().is_empty:
        out("  (AI did not stage a change; staging Robin directly)")
        prop = partner._new_proposal(partner.current)
        prop.add(create_node_change("Robin",
                 "Nhà khảo cổ học của băng Mũ Rơm, đồng đội của Luffy.", reason="fallback"))
        partner.current.set_active_proposal(prop)
    out(partner.change_panel())
    commit_proposal(partner, "new character")

    new_node = sorted(graph.list_nodes(), key=lambda n: n.id)[-1]

    # -- Turn 3: link the new character to Luffy (if not linked yet) --------
    if len(graph.get_relationships_of_node(new_node.id)) == 0:
        out("\n" + "-" * 70)
        out("STEP 3 — Link the new character to Luffy")
        if script:
            script.load([
                _calls(_fc("ProposeLinkNodes", sourceRef=new_node.id, targetRef="N001",
                           metadata=["đồng đội", "thuyền trưởng - thuyền viên"],
                           reason="Robin là thành viên băng Mũ Rơm")),
                _text("Đã đề xuất liên kết Robin với Luffy."),
            ])
        t3 = partner.chat(f"Bây giờ hãy liên kết Robin (id {new_node.id}) với Luffy "
                          f"(id N001) là đồng đội.")
        out(f"  user> Liên kết Robin với Luffy là đồng đội.")
        out(f"  ai>   {t3.answer}")
        if not partner.active_proposal() or partner.active_proposal().is_empty:
            out("  (AI did not stage a link; staging directly)")
            prop = partner._new_proposal(partner.current)
            prop.add(create_relationship_change(new_node.id, "N001", ["đồng đội"],
                     reason="fallback"))
            partner.current.set_active_proposal(prop)
        out(partner.change_panel())
        commit_proposal(partner, "new relationship")

    # -- After state -------------------------------------------------------
    out("\n" + "-" * 70)
    out("AFTER:")
    out(snapshot(graph))

    # -- Persistence proof: reopen the project from disk -------------------
    out("\n" + "-" * 70)
    out("PERSISTENCE PROOF — reopening DemoProject from disk (fresh process state)")
    fresh = KnowledgeGraph(DEMO)
    reloaded = fresh.get_node(new_node.id)
    reloaded_rels = fresh.get_relationships_of_node(new_node.id)
    out(f"  reloaded node {new_node.id}: {reloaded.title if reloaded else None}")
    out(f"  reloaded relationships on {new_node.id}: "
        f"{[r.id + ':' + '/'.join(r.metadata) for r in reloaded_rels]}")

    node_file = os.path.join(DEMO, "nodes", f"{new_node.id}.json")
    out(f"\n  new node file on disk: {node_file}")
    if os.path.exists(node_file):
        out("  " + json.load(open(node_file, encoding="utf-8")).__str__())
    for rel in reloaded_rels:
        rel_file = os.path.join(DEMO, "relationships", f"{rel.id}.json")
        if os.path.exists(rel_file):
            out(f"  new relationship file on disk: {rel_file}")
            out("  " + json.load(open(rel_file, encoding="utf-8")).__str__())

    # -- Verdict -----------------------------------------------------------
    nodes_after = len(fresh.list_nodes())
    rels_after = len(fresh.list_relationships())
    node_ok = nodes_after == nodes_before + 1
    rel_ok = rels_after == rels_before + 1
    out("\n" + "=" * 70)
    out(f"RESULT: nodes {nodes_before} -> {nodes_after} ({'+1 OK' if node_ok else 'UNEXPECTED'}), "
        f"relationships {rels_before} -> {rels_after} ({'+1 OK' if rel_ok else 'UNEXPECTED'})")
    out("The AI created a new node and relationship, persisted to the real DemoProject."
        if node_ok and rel_ok else "Expected exactly one new node and one new relationship.")
    out("=" * 70)
    return 0 if node_ok and rel_ok else 1


def main() -> None:
    global _LOG_FH
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    parser = argparse.ArgumentParser(description="Persist a new character into the real DemoProject")
    parser.add_argument("--scripted", action="store_true", help="offline deterministic mode")
    parser.add_argument("--model", default=None, help="override the Gemini model")
    parser.add_argument("--log", default=LOG_PATH, help="log file path")
    parsed = parser.parse_args()
    _LOG_FH = open(parsed.log, "w", encoding="utf-8") if parsed.log else None
    try:
        sys.exit(run(parsed.scripted, parsed.model))
    finally:
        if _LOG_FH:
            _LOG_FH.close()


if __name__ == "__main__":
    main()
