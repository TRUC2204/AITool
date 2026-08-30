"""Commit engine (Epic 6 - Commit System / Mapping proposal -> graph op).

Applies the approved changes of a proposal to the knowledge graph in order,
resolving temporary ``@ref`` handles to real node ids, capturing before/after
snapshots for undo, and recording a reversible :class:`CommitRecord`.
"""

from __future__ import annotations

from typing import Any, Optional

from knowledge_graph import KnowledgeGraph

from observability import ErrorCategory, ErrorTracker, EventLog, EventType
from .history import AppliedChange, ChangeHistory, CommitRecord
from .proposal import Change, ChangeStatus, ChangeType, Proposal


class CommitEngine:
    def __init__(
        self,
        graph: KnowledgeGraph,
        history: ChangeHistory,
        event_log: Optional[EventLog] = None,
        error_tracker: Optional[ErrorTracker] = None,
    ) -> None:
        self._graph = graph
        self._history = history
        self._event_log = event_log
        self._errors = error_tracker

    def commit(
        self, proposal: Proposal, session_id: Optional[str] = None
    ) -> CommitRecord:
        """Apply every APPROVED change; skip and log any that fail."""
        record = CommitRecord(
            id=self._history.next_id(),
            proposal_id=proposal.id,
            session_id=session_id or proposal.session_id,
            summary=proposal.summary or proposal.reason_summary(),
        )
        ref_map: dict[str, str] = {}

        for change in proposal.approved():
            try:
                applied = self._apply(change, ref_map)
            except Exception as exc:  # noqa: BLE001 - per-change isolation
                if self._errors is not None:
                    self._errors.capture(
                        exc,
                        ErrorCategory.COMMIT,
                        context={"change_id": change.id, "type": change.change_type.value},
                        session_id=session_id,
                    )
                continue
            change.status = ChangeStatus.COMMITTED
            record.applied.append(applied)

        if record.applied:
            self._history.append(record)
            proposal.status = ChangeStatus.COMMITTED
            if self._event_log is not None:
                self._event_log.emit(
                    EventType.COMMIT,
                    f"committed {len(record.applied)} change(s) from {proposal.id}",
                    session_id=session_id,
                    commit_id=record.id,
                    proposal_id=proposal.id,
                    change_count=len(record.applied),
                )
        return record

    def _apply(self, change: Change, ref_map: dict[str, str]) -> AppliedChange:
        kind = change.change_type
        if kind == ChangeType.CREATE_NODE:
            node = self._graph.create_node(
                title=change.title or "", content=change.content or ""
            )
            if change.ref:
                ref_map[change.ref] = node.id
            change.after = node.to_dict()
            return AppliedChange(change.id, kind, node.id, after=node.to_dict())

        if kind == ChangeType.UPDATE_NODE:
            before = self._graph.get_node(str(change.target_id))
            if before is None:
                raise ValueError(f"node not found: {change.target_id}")
            before_dict = before.to_dict()
            node = self._graph.update_node(
                str(change.target_id), title=change.title, content=change.content
            )
            change.before = before_dict
            change.after = node.to_dict() if node else None
            return AppliedChange(
                change.id, kind, str(change.target_id), before=before_dict,
                after=change.after,
            )

        if kind == ChangeType.DELETE_NODE:
            before = self._graph.get_node(str(change.target_id))
            if before is None:
                raise ValueError(f"node not found: {change.target_id}")
            related = [
                rel.to_dict()
                for rel in self._graph.get_relationships_of_node(str(change.target_id))
            ]
            before_dict = before.to_dict()
            self._graph.delete_node(str(change.target_id))
            change.before = before_dict
            return AppliedChange(
                change.id, kind, str(change.target_id), before=before_dict,
                related_before=related,
            )

        if kind == ChangeType.CREATE_RELATIONSHIP:
            source = self._resolve(change.source_ref, ref_map)
            target = self._resolve(change.target_ref, ref_map)
            rel = self._graph.create_relationship(
                source, target, metadata=change.metadata or []
            )
            change.after = rel.to_dict()
            return AppliedChange(change.id, kind, rel.id, after=rel.to_dict())

        if kind == ChangeType.UPDATE_RELATIONSHIP:
            before = self._graph.get_relationship(str(change.target_id))
            if before is None:
                raise ValueError(f"relationship not found: {change.target_id}")
            before_dict = before.to_dict()
            rel = self._graph.update_relationship(
                str(change.target_id), metadata=change.metadata or []
            )
            change.before = before_dict
            change.after = rel.to_dict() if rel else None
            return AppliedChange(
                change.id, kind, str(change.target_id), before=before_dict,
                after=change.after,
            )

        # DELETE_RELATIONSHIP
        before = self._graph.get_relationship(str(change.target_id))
        if before is None:
            raise ValueError(f"relationship not found: {change.target_id}")
        before_dict = before.to_dict()
        self._graph.delete_relationship(str(change.target_id))
        change.before = before_dict
        return AppliedChange(change.id, kind, str(change.target_id), before=before_dict)

    @staticmethod
    def _resolve(ref: Optional[str], ref_map: dict[str, str]) -> str:
        if ref is None:
            raise ValueError("relationship endpoint is missing")
        if ref.startswith("@"):
            resolved = ref_map.get(ref)
            if resolved is None:
                raise ValueError(f"unresolved reference: {ref}")
            return resolved
        return ref
