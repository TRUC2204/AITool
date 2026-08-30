"""Undo & restore (Epic 7 - Undo / Restore).

Reverses committed changes using the before/after snapshots stored in the
:class:`ChangeHistory`. Supports undoing a single commit, the most recent
commit, or every commit from a proposal, and verifies the graph state after a
rollback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from knowledge_graph import KnowledgeGraph

from observability import EventLog, EventType
from .history import AppliedChange, ChangeHistory, CommitRecord
from .proposal import ChangeType


@dataclass
class UndoResult:
    record_id: str
    reversed_count: int
    ok: bool
    issues: list[str] = field(default_factory=list)


class UndoManager:
    def __init__(
        self,
        graph: KnowledgeGraph,
        history: ChangeHistory,
        event_log: Optional[EventLog] = None,
    ) -> None:
        self._graph = graph
        self._history = history
        self._event_log = event_log

    def undo_last(self) -> Optional[UndoResult]:
        record = self._history.last(active_only=True)
        if record is None:
            return None
        return self.undo_record(record.id)

    def undo_record(self, record_id: str) -> UndoResult:
        record = self._history.get(record_id)
        if record is None:
            return UndoResult(record_id, 0, False, [f"no such commit: {record_id}"])
        if record.undone:
            return UndoResult(record_id, 0, False, [f"already undone: {record_id}"])

        issues: list[str] = []
        # Reverse in the opposite order they were applied.
        for applied in reversed(record.applied):
            issues.extend(self._reverse(applied))

        record.undone = True
        issues.extend(self.verify_after(record))
        result = UndoResult(record_id, len(record.applied), not issues, issues)
        if self._event_log is not None:
            self._event_log.emit(
                EventType.UNDO,
                f"undid commit {record_id} ({result.reversed_count} change(s))",
                session_id=record.session_id,
                commit_id=record_id,
                ok=result.ok,
                issues=issues,
            )
        return result

    def undo_proposal(self, proposal_id: str) -> list[UndoResult]:
        records = [r for r in self._history.by_proposal(proposal_id) if not r.undone]
        return [self.undo_record(r.id) for r in reversed(records)]

    def _reverse(self, applied: AppliedChange) -> list[str]:
        issues: list[str] = []
        kind = applied.change_type

        if kind == ChangeType.CREATE_NODE and applied.after:
            self._graph.delete_node(applied.after["id"])

        elif kind == ChangeType.UPDATE_NODE and applied.before:
            self._graph.update_node(
                applied.before["id"],
                title=applied.before.get("title"),
                content=applied.before.get("content"),
            )

        elif kind == ChangeType.DELETE_NODE and applied.before:
            node_id = applied.before["id"]
            if self._graph.get_node(node_id) is None:
                self._graph.create_node(
                    title=applied.before.get("title", ""),
                    content=applied.before.get("content", ""),
                    node_id=node_id,
                )
            for rel in applied.related_before:
                issues.extend(self._restore_relationship(rel))

        elif kind == ChangeType.CREATE_RELATIONSHIP and applied.after:
            self._graph.delete_relationship(applied.after["id"])

        elif kind == ChangeType.UPDATE_RELATIONSHIP and applied.before:
            self._graph.update_relationship(
                applied.before["id"], metadata=applied.before.get("metadata", [])
            )

        elif kind == ChangeType.DELETE_RELATIONSHIP and applied.before:
            issues.extend(self._restore_relationship(applied.before))

        return issues

    def _restore_relationship(self, rel: dict) -> list[str]:
        if self._graph.get_relationship(rel["id"]) is not None:
            return []
        source, target = rel["source_node_id"], rel["target_node_id"]
        if self._graph.get_node(source) is None or self._graph.get_node(target) is None:
            return [f"cannot restore relationship {rel['id']}: endpoint missing"]
        self._graph.create_relationship(
            source, target, metadata=rel.get("metadata", []), relationship_id=rel["id"]
        )
        return []

    def verify_after(self, record: CommitRecord) -> list[str]:
        """Confirm the graph matches the expected post-undo state (FR-12)."""
        issues: list[str] = []
        for applied in record.applied:
            kind = applied.change_type
            if kind == ChangeType.CREATE_NODE and applied.after:
                if self._graph.get_node(applied.after["id"]) is not None:
                    issues.append(f"node {applied.after['id']} should be removed")
            elif kind == ChangeType.DELETE_NODE and applied.before:
                if self._graph.get_node(applied.before["id"]) is None:
                    issues.append(f"node {applied.before['id']} should be restored")
            elif kind == ChangeType.CREATE_RELATIONSHIP and applied.after:
                if self._graph.get_relationship(applied.after["id"]) is not None:
                    issues.append(f"relationship {applied.after['id']} should be removed")
        return issues
