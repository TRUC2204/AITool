"""Chat-centric CLI (Epic 8 - Chat-Centric UI).

The whole product behind one prompt: type to talk to the AI partner; use slash
commands to review/approve/reject/commit/undo proposals, toggle Internet Mode,
inspect the context panel, view the debug trace, and export diagnostics. This is
the Phase-1 "user only needs to chat" surface.
"""

from __future__ import annotations

import argparse
import os
from typing import Optional

from ai import GeminiProvider, load_settings
from knowledge_graph import KnowledgeGraph

from .partner import AIWritingPartner

_HELP = """\
Commands (anything else is sent to the AI):
  /help                 show this help
  /review               show pending proposal (change panel)
  /approve [ids...]     approve all pending changes, or the given change ids
  /reject  [ids...]     reject all pending changes, or the given change ids
  /commit               apply approved changes to the project
  /discard              throw away the pending proposal
  /undo                 undo the last commit
  /history              list commit history
  /search <text>        search change history
  /context              show the context panel (sources, tools, memory)
  /debug                show the debug trace of the last activity
  /diag <dir>           export a diagnostic package to <dir>
  /internet on|off      toggle Internet Mode (external knowledge)
  /goal <text>          set the current session goal
  /assume <text>        add a temporary working assumption
  /promote              propose saving confirmed assumptions to the project
  /settings             show AI + limit settings
  /new [id]             start a new chat session
  /quit                 exit
"""


def build_partner(project_path: str) -> tuple[AIWritingPartner, Optional[str]]:
    settings = load_settings()
    graph = KnowledgeGraph(project_path, name=os.path.basename(project_path.rstrip("/\\")))
    provider = None
    warning = None
    if settings.ai.api_key:
        provider = GeminiProvider(settings.ai, timeout=60)
    else:
        warning = "No GEMINI_API_KEY found — chat is disabled. Management commands still work."
    partner = AIWritingPartner(graph, provider=provider, limits=settings.agent_limits)
    partner.start_session()
    partner.settings = settings
    return partner, warning


def run_chat(partner: AIWritingPartner) -> None:
    print("AI Writing Partner — type /help for commands, /quit to exit.\n")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.startswith("/"):
            if _handle_command(partner, line):
                break
            continue
        _handle_chat(partner, line)


def _handle_chat(partner: AIWritingPartner, text: str) -> None:
    if not partner.has_provider:
        print("ai> (chat disabled: no API key)\n")
        return
    try:
        turn = partner.chat(text)
    except Exception as exc:  # noqa: BLE001 - keep the REPL alive
        print(f"ai> [error] {exc}\n")
        return
    print(f"ai> {turn.answer}\n")
    if turn.has_proposal:
        print(partner.change_panel())
        print("(review with /review, then /approve and /commit)\n")


def _handle_command(partner: AIWritingPartner, line: str) -> bool:
    parts = line.split()
    cmd, args = parts[0].lower(), parts[1:]

    if cmd in ("/quit", "/exit"):
        return True
    if cmd == "/help":
        print(_HELP)
    elif cmd == "/review":
        print(partner.change_panel(), "\n")
    elif cmd == "/approve":
        count = partner.approve(args or None)
        print(f"approved {count} change(s).\n")
    elif cmd == "/reject":
        count = partner.reject(args or None)
        print(f"rejected {count} change(s).\n")
    elif cmd == "/commit":
        _do_commit(partner)
    elif cmd == "/discard":
        partner.discard_proposal()
        print("proposal discarded.\n")
    elif cmd == "/undo":
        _do_undo(partner)
    elif cmd == "/history":
        _show_history(partner)
    elif cmd == "/search":
        _search_history(partner, " ".join(args))
    elif cmd == "/context":
        print(partner.context_panel(), "\n")
    elif cmd == "/debug":
        print(partner.debug_view(), "\n")
    elif cmd == "/diag":
        target = args[0] if args else "diagnostics"
        print(f"exported diagnostics to: {partner.export_diagnostics(target)}\n")
    elif cmd == "/internet":
        _toggle_internet(partner, args)
    elif cmd == "/goal":
        partner._require_session().set_goal(" ".join(args))
        print("goal set.\n")
    elif cmd == "/assume":
        partner._require_session().add_assumption(" ".join(args))
        print("assumption noted.\n")
    elif cmd == "/promote":
        _promote(partner)
    elif cmd == "/settings":
        _show_settings(partner)
    elif cmd == "/new":
        session = partner.start_session(args[0] if args else None)
        print(f"started session {session.session_id}.\n")
    else:
        print("unknown command; type /help.\n")
    return False


def _do_commit(partner: AIWritingPartner) -> None:
    issues = partner.validate_proposal()
    blocking = [i for i in issues if i.severity == "error"]
    if blocking:
        print("cannot commit — consistency errors:")
        for issue in blocking:
            print(f"  {issue}")
        print()
        return
    record = partner.commit()
    if record is None:
        print("nothing approved to commit.\n")
        return
    print(f"committed {len(record.applied)} change(s) as {record.id}.\n")


def _do_undo(partner: AIWritingPartner) -> None:
    result = partner.undo_last()
    if result is None:
        print("nothing to undo.\n")
        return
    status = "ok" if result.ok else f"with issues: {result.issues}"
    print(f"undid {result.reversed_count} change(s) [{status}].\n")


def _show_history(partner: AIWritingPartner) -> None:
    records = partner.history_view()
    if not records:
        print("no history yet.\n")
        return
    for record in records:
        flag = " (undone)" if record.undone else ""
        print(f"  {record.id}  {record.summary or '(no summary)'}{flag}  [{len(record.applied)} change(s)]")
    print()


def _search_history(partner: AIWritingPartner, text: str) -> None:
    if not text:
        print("usage: /search <text>\n")
        return
    matches = partner.search_history(text)
    print(f"{len(matches)} match(es):")
    for record in matches:
        print(f"  {record.id}  {record.summary}")
    print()


def _toggle_internet(partner: AIWritingPartner, args: list[str]) -> None:
    if not args or args[0] not in ("on", "off"):
        print("usage: /internet on|off\n")
        return
    mode = partner.set_internet_mode(args[0] == "on")
    print(f"internet mode: {mode.value}\n")


def _promote(partner: AIWritingPartner) -> None:
    proposal = partner.promote_assumptions()
    if proposal is None:
        print("no assumptions to promote.\n")
        return
    print(partner.change_panel())
    print("(review with /approve and /commit)\n")


def _show_settings(partner: AIWritingPartner) -> None:
    settings = partner.settings
    print("[SETTINGS]")
    if settings is not None:
        print(f"  Provider:      {settings.ai.provider}")
        print(f"  Model:         {settings.ai.model}")
        print(f"  MaxInputTok:   {settings.agent_limits.max_input_tokens}")
        print(f"  MaxOutputTok:  {settings.agent_limits.max_output_tokens}")
    print(f"  Internet Mode: {partner.knowledge_mode.mode.value}")
    print(f"  Session Cost:  {partner.cost.summary()}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Writing Partner chat")
    parser.add_argument(
        "--project",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MyProject"),
        help="path to the project folder (created if missing)",
    )
    parsed = parser.parse_args()
    partner, warning = build_partner(os.path.abspath(parsed.project))
    if warning:
        print(f"[!] {warning}\n")
    run_chat(partner)


if __name__ == "__main__":
    main()
