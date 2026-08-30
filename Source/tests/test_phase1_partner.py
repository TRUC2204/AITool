"""Phase-1 end-to-end acceptance tests (Definition of Done).

Offline: a scripted in-process provider drives the agent loop so the full
chat -> ground -> propose -> review -> commit -> undo workflow is verified
without the network. Maps to Epic 9 Testing (E2E, proposal, undo, long session).
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_graph import KnowledgeGraph  # noqa: E402
from ai import TokenUsage  # noqa: E402
from ai.provider import FunctionCall, IAIProvider, ProviderResponse  # noqa: E402
from grounding import KnowledgeMode  # noqa: E402
from app import AIWritingPartner  # noqa: E402


class ScriptedProvider(IAIProvider):
    """Returns a fixed sequence of responses; clamps to the last (a text stop)."""

    def __init__(self, responses: list[ProviderResponse]) -> None:
        self._responses = responses
        self.calls = 0

    def generate(
        self,
        contents: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        max_output_tokens: Optional[int] = None,
    ) -> ProviderResponse:
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


def _calls(*calls: FunctionCall) -> ProviderResponse:
    return ProviderResponse(function_calls=list(calls), usage=TokenUsage(12, 6))


def _text(text: Optional[str]) -> ProviderResponse:
    return ProviderResponse(text=text, usage=TokenUsage(9, 5))


def _fc(name: str, **args: Any) -> FunctionCall:
    return FunctionCall(name=name, args=args)


class PartnerTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.kg = KnowledgeGraph(os.path.join(self._tmp.name, "proj"), name="World")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _partner(self, responses: list[ProviderResponse]) -> AIWritingPartner:
        partner = AIWritingPartner(self.kg, provider=ScriptedProvider(responses))
        partner.start_session("S001")
        return partner


class GroundingAcceptance(PartnerTestBase):
    def test_answer_is_grounded_and_cites_sources(self) -> None:
        luffy = self.kg.create_node("Luffy", "Captain of the crew")
        partner = self._partner(
            [_calls(_fc("GetNode", nodeId=luffy.id)), _text("Luffy is the captain.")]
        )
        turn = partner.chat("Who is Luffy?")
        self.assertFalse(turn.no_evidence)
        self.assertIn("Sources:", turn.answer)
        self.assertTrue(any(s.id == luffy.id for s in turn.sources))

    def test_no_evidence_found_when_nothing_read(self) -> None:
        partner = self._partner([_text(None)])
        turn = partner.chat("Tell me about a character that does not exist")
        self.assertTrue(turn.no_evidence)
        self.assertIn("No internal information", turn.answer)

    def test_internet_mode_default_off_and_toggles(self) -> None:
        partner = self._partner([_text("ok")])
        self.assertEqual(partner.knowledge_mode.mode, KnowledgeMode.INTERNAL_ONLY)
        partner.set_internet_mode(True)
        self.assertEqual(partner.knowledge_mode.mode, KnowledgeMode.EXTERNAL_ALLOWED)
        self.assertIn("EXTERNAL", partner.knowledge_mode.directive())


class ProposalAcceptance(PartnerTestBase):
    def test_ai_proposes_but_does_not_write(self) -> None:
        partner = self._partner(
            [
                _calls(_fc("ProposeCreateNode", title="Nami", content="Navigator", reason="add crew")),
                _text("I propose adding Nami."),
            ]
        )
        turn = partner.chat("Add Nami")
        self.assertTrue(turn.has_proposal)
        # Draft-before-commit: nothing written yet.
        self.assertEqual(self.kg.list_nodes(), [])

    def test_review_approve_commit_writes(self) -> None:
        partner = self._partner(
            [
                _calls(_fc("ProposeCreateNode", title="Nami", content="Navigator", reason="crew")),
                _text("Proposed."),
            ]
        )
        partner.chat("Add Nami")
        self.assertIn("Nami", partner.change_panel())
        self.assertEqual(partner.approve(), 1)
        record = partner.commit()
        self.assertIsNotNone(record)
        self.assertEqual([n.title for n in self.kg.list_nodes()], ["Nami"])

    def test_partial_approval(self) -> None:
        partner = self._partner(
            [
                _calls(
                    _fc("ProposeCreateNode", title="Nami", content="Navigator"),
                    _fc("ProposeCreateNode", title="Usopp", content="Sniper"),
                ),
                _text("Proposed two."),
            ]
        )
        partner.chat("Add Nami and Usopp")
        proposal = partner.active_proposal()
        assert proposal is not None
        # Approve only the first, reject the second.
        first, second = proposal.changes[0].id, proposal.changes[1].id
        self.assertEqual(partner.approve([first]), 1)
        self.assertEqual(partner.reject([second]), 1)
        partner.commit()
        self.assertEqual([n.title for n in self.kg.list_nodes()], ["Nami"])

    def test_multi_change_proposal_with_refs(self) -> None:
        partner = self._partner(
            [
                _calls(
                    _fc("ProposeCreateNode", title="Nami", content="Navigator", ref="@nami"),
                    _fc("ProposeCreateNode", title="Sunny", content="Ship", ref="@ship"),
                    _fc("ProposeLinkNodes", sourceRef="@nami", targetRef="@ship", metadata=["sails"]),
                ),
                _text("Proposed crew + ship."),
            ]
        )
        partner.chat("Add Nami and the ship, and link them")
        partner.approve()
        record = partner.commit()
        assert record is not None
        self.assertEqual(len(self.kg.list_nodes()), 2)
        self.assertEqual(len(self.kg.list_relationships()), 1)

    def test_consistency_blocks_bad_commit(self) -> None:
        partner = self._partner(
            [_calls(_fc("ProposeUpdateNode", nodeId="N999", content="x")), _text("Proposed.")]
        )
        partner.chat("Update a missing node")
        issues = partner.validate_proposal()
        self.assertTrue(any(i.severity == "error" for i in issues))


class UndoAcceptance(PartnerTestBase):
    def test_undo_last_commit_restores_state(self) -> None:
        partner = self._partner(
            [
                _calls(_fc("ProposeCreateNode", title="Nami", content="Navigator")),
                _text("Proposed."),
            ]
        )
        partner.chat("Add Nami")
        partner.approve()
        partner.commit()
        self.assertEqual(len(self.kg.list_nodes()), 1)
        result = partner.undo_last()
        assert result is not None
        self.assertTrue(result.ok)
        self.assertEqual(self.kg.list_nodes(), [])

    def test_undo_update_restores_old_content(self) -> None:
        node = self.kg.create_node("Zoro", "Swordsman")
        partner = self._partner(
            [
                _calls(_fc("ProposeUpdateNode", nodeId=node.id, content="First mate", reason="promote")),
                _text("Proposed."),
            ]
        )
        partner.chat("Promote Zoro")
        partner.approve()
        partner.commit()
        self.assertEqual(self.kg.get_node(node.id).content, "First mate")
        partner.undo_last()
        self.assertEqual(self.kg.get_node(node.id).content, "Swordsman")


class ObservabilityAcceptance(PartnerTestBase):
    def test_debug_view_and_diagnostics_export(self) -> None:
        luffy = self.kg.create_node("Luffy", "Captain")
        partner = self._partner(
            [_calls(_fc("GetNode", nodeId=luffy.id)), _text("Answer.")]
        )
        partner.chat("Who is Luffy?")
        debug = partner.debug_view()
        self.assertIn("DECISION FLOW", debug)
        self.assertIn("TOKEN USAGE", debug)
        out = os.path.join(self._tmp.name, "diag")
        partner.export_diagnostics(out)
        self.assertTrue(os.path.exists(os.path.join(out, "package.json")))
        self.assertTrue(os.path.exists(os.path.join(out, "events.jsonl")))

    def test_context_panel_lists_sources_and_tools(self) -> None:
        luffy = self.kg.create_node("Luffy", "Captain")
        partner = self._partner(
            [_calls(_fc("GetNode", nodeId=luffy.id)), _text("Answer.")]
        )
        partner.chat("Who is Luffy?")
        panel = partner.context_panel()
        self.assertIn("GetNode", panel)
        self.assertIn("Luffy", panel)


class SessionAcceptance(PartnerTestBase):
    def test_long_chat_session_accumulates_state(self) -> None:
        # Alternate read/answer turns many times; must stay stable.
        node = self.kg.create_node("Luffy", "Captain")
        responses: list[ProviderResponse] = []
        for _ in range(12):
            responses.append(_calls(_fc("GetNode", nodeId=node.id)))
            responses.append(_text("Captain."))
        partner = self._partner(responses)
        for i in range(12):
            partner.chat(f"question {i}")
        working = partner.current
        assert working is not None
        # 12 user + 12 assistant messages.
        self.assertEqual(len(working.messages), 24)
        self.assertGreater(partner.cost.total_tokens, 0)

    def test_history_search(self) -> None:
        partner = self._partner(
            [
                _calls(_fc("ProposeCreateNode", title="Nami", content="Navigator")),
                _text("Proposed."),
            ]
        )
        partner.chat("Add Nami")
        partner.approve()
        partner.commit()
        self.assertEqual(len(partner.history_view()), 1)
        self.assertTrue(partner.search_history("Nami"))


class CliImportAcceptance(unittest.TestCase):
    def test_chat_cli_imports(self) -> None:
        import app.chat_cli as cli  # noqa: F401

        self.assertTrue(hasattr(cli, "main"))
        self.assertTrue(hasattr(cli, "run_chat"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
