"""Phase-1 core unit tests: changes, memory, grounding, retrieval-ext, observability."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_graph import KnowledgeGraph  # noqa: E402
from changes import (  # noqa: E402
    ChangeHistory,
    ChangeStatus,
    CommitEngine,
    Proposal,
    UndoManager,
    create_node_change,
    create_relationship_change,
    delete_node_change,
    update_node_change,
)
from grounding import (  # noqa: E402
    EvidenceTracker,
    KnowledgeMode,
    KnowledgeModeController,
    SourceKind,
)
from memory import (  # noqa: E402
    ConsistencyChecker,
    LongTermMemory,
    MemoryPromotion,
    WorkingMemory,
)
from observability import (  # noqa: E402
    DiagnosticPackage,
    ErrorCategory,
    ErrorTracker,
    EventLog,
    EventType,
    render_full_debug,
)
from retrieval import ContextCache, NodeCandidate, dedupe_candidates, rank_candidates  # noqa: E402


class ChangesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.kg = KnowledgeGraph(os.path.join(self._tmp.name, "p"), name="T")
        self.history = ChangeHistory()
        self.engine = CommitEngine(self.kg, self.history)
        self.undo = UndoManager(self.kg, self.history)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _approved(self, proposal: Proposal) -> None:
        for change in proposal.changes:
            change.status = ChangeStatus.APPROVED

    def test_commit_resolves_refs(self) -> None:
        proposal = Proposal(id="P1")
        proposal.add(create_node_change("A", ref="@a"))
        proposal.add(create_node_change("B", ref="@b"))
        proposal.add(create_relationship_change("@a", "@b", ["link"]))
        self._approved(proposal)
        record = self.engine.commit(proposal)
        self.assertEqual(len(record.applied), 3)
        self.assertEqual(len(self.kg.list_relationships()), 1)

    def test_only_approved_changes_commit(self) -> None:
        proposal = Proposal(id="P1")
        c1 = proposal.add(create_node_change("A"))
        proposal.add(create_node_change("B"))
        c1.status = ChangeStatus.APPROVED  # only A approved
        record = self.engine.commit(proposal)
        self.assertEqual(len(record.applied), 1)
        self.assertEqual([n.title for n in self.kg.list_nodes()], ["A"])

    def test_delete_node_undo_restores_relationships(self) -> None:
        a = self.kg.create_node("A")
        b = self.kg.create_node("B")
        self.kg.create_relationship(a.id, b.id, ["link"])
        proposal = Proposal(id="P1")
        proposal.add(delete_node_change(a.id))
        self._approved(proposal)
        record = self.engine.commit(proposal)
        self.assertIsNone(self.kg.get_node(a.id))
        self.assertEqual(len(self.kg.list_relationships()), 0)
        result = self.undo.undo_record(record.id)
        self.assertTrue(result.ok)
        self.assertIsNotNone(self.kg.get_node(a.id))
        self.assertEqual(len(self.kg.list_relationships()), 1)

    def test_history_grouping_and_search(self) -> None:
        proposal = Proposal(id="P1", session_id="S1", summary="add hero")
        proposal.add(create_node_change("Hero", "the chosen one"))
        self._approved(proposal)
        self.engine.commit(proposal, session_id="S1")
        self.assertEqual(len(self.history.by_session("S1")), 1)
        self.assertEqual(len(self.history.by_proposal("P1")), 1)
        self.assertTrue(self.history.search("chosen"))

    def test_proposal_render_groups_changes(self) -> None:
        proposal = Proposal(id="P1", summary="mix")
        proposal.add(create_node_change("A"))
        proposal.add(update_node_change("N001", content="x"))
        rendered = proposal.render()
        self.assertIn("Added:", rendered)
        self.assertIn("Modified:", rendered)


class GroundingTests(unittest.TestCase):
    def test_knowledge_mode_default_and_toggle(self) -> None:
        log = EventLog()
        controller = KnowledgeModeController(event_log=log)
        self.assertEqual(controller.mode, KnowledgeMode.INTERNAL_ONLY)
        self.assertIn("INTERNAL ONLY", controller.directive())
        controller.toggle()
        self.assertTrue(controller.is_external_allowed)
        self.assertIn("EXTERNAL", controller.directive())
        self.assertTrue(log.events(event_type=EventType.KNOWLEDGE_MODE))

    def test_evidence_tracker_dedupes_and_attributes(self) -> None:
        tracker = EvidenceTracker()
        tracker.record_node("N001", "Luffy")
        tracker.record_node("N001", "Luffy")  # dup
        tracker.record_relationship("R001", "crew")
        self.assertEqual(len(tracker.sources(SourceKind.NODE)), 1)
        self.assertTrue(tracker.has_internal_evidence)
        self.assertIn("Node N001", tracker.render_attribution())

    def test_evidence_empty_is_no_evidence(self) -> None:
        tracker = EvidenceTracker()
        self.assertFalse(tracker.has_internal_evidence)
        self.assertTrue(tracker.is_empty)


class MemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.kg = KnowledgeGraph(os.path.join(self._tmp.name, "p"), name="T")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_working_memory_tracks_session_state(self) -> None:
        wm = WorkingMemory("S1")
        wm.add_message("user", "hi")
        wm.set_goal("build a villain")
        wm.add_assumption("The villain fears fire")
        wm.add_assumption("The villain fears fire")  # dup ignored
        snap = wm.snapshot()
        self.assertEqual(snap["goal"], "build a villain")
        self.assertEqual(len(wm.assumptions), 1)
        self.assertEqual(snap["message_count"], 1)

    def test_consistency_detects_duplicate_titles(self) -> None:
        self.kg.create_node("Luffy", "a")
        self.kg.create_node("Luffy", "b")
        checker = ConsistencyChecker(self.kg)
        self.assertEqual(len(checker.find_duplicate_titles()), 1)
        issues = checker.check_new_node("Luffy")
        self.assertTrue(any(i.code == "duplicate_title" for i in issues))

    def test_long_term_memory_retrieve(self) -> None:
        self.kg.create_node("Dragon", "a fearsome beast")
        ltm = LongTermMemory(self.kg)
        hits = ltm.retrieve("dragon")
        self.assertTrue(any(h.title == "Dragon" for h in hits))

    def test_memory_promotion_builds_proposal(self) -> None:
        wm = WorkingMemory("S1")
        wm.add_assumption("The kingdom has three moons")
        promotion = MemoryPromotion()
        candidates = promotion.candidates_from_assumptions(wm)
        proposal = promotion.build_proposal(candidates, "S1-P1", "S1")
        self.assertEqual(len(proposal.changes), 1)
        self.assertIn("three moons", proposal.changes[0].content)


class RetrievalExtTests(unittest.TestCase):
    def test_context_cache_hit_miss_and_invalidation(self) -> None:
        cache = ContextCache()
        self.assertIsNone(cache.get("k"))  # miss
        cache.put("k", [1, 2, 3])
        self.assertEqual(cache.get("k"), [1, 2, 3])  # hit
        cache.bump_revision()
        self.assertIsNone(cache.get("k"))  # invalidated
        self.assertEqual(cache.stats.hits, 1)
        self.assertEqual(cache.stats.misses, 2)

    def test_ranking_prefers_exact_title(self) -> None:
        candidates = [
            NodeCandidate("N1", "Luffy Junior", "x", "title"),
            NodeCandidate("N2", "Luffy", "x", "title"),
        ]
        ranked = rank_candidates(candidates, "Luffy")
        self.assertEqual(ranked[0].id, "N2")

    def test_dedupe_candidates(self) -> None:
        candidates = [
            NodeCandidate("N1", "A", "x", "title"),
            NodeCandidate("N1", "A", "x", "title"),
        ]
        self.assertEqual(len(dedupe_candidates(candidates)), 1)


class ObservabilityTests(unittest.TestCase):
    def test_event_log_emit_filter_and_jsonl(self) -> None:
        log = EventLog()
        log.emit(EventType.TOOL_CALL, "GetNode", session_id="S1", ok=True)
        log.emit(EventType.AI_RESPONSE, "resp", session_id="S1", input_tokens=5)
        self.assertEqual(len(log.events(event_type=EventType.TOOL_CALL)), 1)
        self.assertEqual(len(log.events(session_id="S1")), 2)
        self.assertIn("GetNode", log.to_jsonl())

    def test_error_tracker_capture_and_guard(self) -> None:
        log = EventLog()
        tracker = ErrorTracker(log)
        try:
            with tracker.guard(ErrorCategory.TOOL, context={"tool": "X"}):
                raise ValueError("boom")
        except ValueError:
            pass
        self.assertEqual(len(tracker.errors()), 1)
        self.assertEqual(tracker.last().category, ErrorCategory.TOOL)
        self.assertTrue(log.events(event_type=EventType.ERROR))

    def test_debug_view_and_diagnostic_package(self) -> None:
        log = EventLog()
        tracker = ErrorTracker(log)
        log.emit(EventType.AI_REQUEST, "req", session_id="S1")
        log.emit(EventType.TOOL_CALL, "GetNode", session_id="S1", ok=True, iteration=1, args={})
        log.emit(EventType.AI_RESPONSE, "resp", session_id="S1", input_tokens=10, output_tokens=3, cost=0.0)
        self.assertIn("DECISION FLOW", render_full_debug(log, "S1"))
        package = DiagnosticPackage(log, tracker).build("S1")
        self.assertEqual(package["summary"]["ai_calls"], 1)
        self.assertIn("events", package)


if __name__ == "__main__":
    unittest.main(verbosity=2)
