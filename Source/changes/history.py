"""Change history (Epic 7 - Change History).

Each commit produces a :class:`CommitRecord` holding reversible
:class:`AppliedChange` snapshots (before/after). History is queryable by session
or proposal and full-text searchable, and is the source of truth the
:class:`UndoManager` reverses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .proposal import ChangeType


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AppliedChange:
    """A committed change plus the snapshots needed to reverse it."""

    change_id: str
    change_type: ChangeType
    target_id: Optional[str]
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None
    # Relationships removed as a side effect of deleting a node (for undo).
    related_before: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        record = asdict(self)
        record["change_type"] = self.change_type.value
        return record


@dataclass
class CommitRecord:
    id: str
    proposal_id: str
    session_id: Optional[str]
    summary: str
    timestamp: str = field(default_factory=_utc_now)
    applied: list[AppliedChange] = field(default_factory=list)
    undone: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposal_id": self.proposal_id,
            "session_id": self.session_id,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "undone": self.undone,
            "applied": [change.to_dict() for change in self.applied],
        }


class ChangeHistory:
    """Append-only store of commit records grouped by session and proposal."""

    def __init__(self) -> None:
        self._records: list[CommitRecord] = []
        self._counter = 0

    def next_id(self) -> str:
        self._counter += 1
        return f"H{self._counter:04d}"

    def append(self, record: CommitRecord) -> CommitRecord:
        self._records.append(record)
        return record

    def records(self, include_undone: bool = True) -> list[CommitRecord]:
        if include_undone:
            return list(self._records)
        return [r for r in self._records if not r.undone]

    def get(self, record_id: str) -> Optional[CommitRecord]:
        return next((r for r in self._records if r.id == record_id), None)

    def by_session(self, session_id: str) -> list[CommitRecord]:
        return [r for r in self._records if r.session_id == session_id]

    def by_proposal(self, proposal_id: str) -> list[CommitRecord]:
        return [r for r in self._records if r.proposal_id == proposal_id]

    def last(self, active_only: bool = True) -> Optional[CommitRecord]:
        for record in reversed(self._records):
            if not active_only or not record.undone:
                return record
        return None

    def search(self, text: str) -> list[CommitRecord]:
        key = text.strip().lower()
        if not key:
            return []
        matches: list[CommitRecord] = []
        for record in self._records:
            haystack = [record.summary]
            for change in record.applied:
                haystack.append(str(change.before or ""))
                haystack.append(str(change.after or ""))
            if any(key in part.lower() for part in haystack):
                matches.append(record)
        return matches

    def __len__(self) -> int:
        return len(self._records)
