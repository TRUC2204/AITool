"""Phase-1 live demo: the AI Writing Partner against Source/DemoProject.

Shows the Definition-of-Done flow end to end with a real Gemini call:

    py -3 seed_demo.py           # once, to create DemoProject
    py -3 run_partner_demo.py    # grounded answer -> proposal -> commit -> undo

Needs a network that allows HTTPS to the Gemini API and a key in Source/.env.
"""

from __future__ import annotations

import os

from ai import GeminiProvider, load_settings
from app import AIWritingPartner
from knowledge_graph import KnowledgeGraph

PROJECT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DemoProject")


def main() -> None:
    settings = load_settings()
    if not settings.ai.api_key:
        raise SystemExit("No API key. Set GEMINI_API_KEY in Source/.env.")

    graph = KnowledgeGraph(PROJECT_PATH)
    provider = GeminiProvider(settings.ai, timeout=60)
    partner = AIWritingPartner(graph, provider=provider, limits=settings.agent_limits)
    partner.start_session("demo")

    # 1. Grounded question — the assistant retrieves and cites project data.
    turn = partner.chat("Who is Luffy and who are his crew mates?")
    print(f"\nQ1 answer:\n{turn.answer}\n")
    print(partner.context_panel())

    # 2. Ask for a change — staged as a proposal, not written.
    turn = partner.chat("Add a new crew member named Nami, a navigator, and link her to Luffy.")
    print(f"\nQ2 answer:\n{turn.answer}\n")
    print(partner.change_panel())

    # 3. Review -> approve -> commit.
    partner.approve()
    record = partner.commit()
    if record:
        print(f"\nCommitted {len(record.applied)} change(s) as {record.id}.")

    # 4. Undo to prove reversibility.
    result = partner.undo_last()
    if result:
        print(f"Undo ok={result.ok} ({result.reversed_count} change(s) reversed).")

    print("\n" + partner.debug_view())


if __name__ == "__main__":
    main()
