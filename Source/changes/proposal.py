"""Proposals & changes (Epic 6 - Proposal System / Change Visualization).

A :class:`Proposal` groups one or more :class:`Change` records with a reason so
the user can see exactly what will be added, modified or deleted before any of
it touches the graph. Newly created nodes can be referenced by other changes in
the same proposal through a temporary ``ref`` (e.g. ``@hero``) that the commit
engine resolves to a real id.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChangeType(str, Enum):
    CREATE_NODE = "create_node"
    UPDATE_NODE = "update_node"
    DELETE_NODE = "delete_node"
    CREATE_RELATIONSHIP = "create_relationship"
    UPDATE_RELATIONSHIP = "update_relationship"
    DELETE_RELATIONSHIP = "delete_relationship"


class ChangeStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMMITTED = "committed"


@dataclass
class Change:
    """A single proposed mutation. ``before``/``after`` are filled at commit."""

    change_type: ChangeType
    reason: str = ""
    id: str = ""
    target_id: Optional[str] = None          # node/relationship being changed
    ref: Optional[str] = None                # temp handle for a created node
    title: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[list[str]] = None
    source_ref: Optional[str] = None         # relationship source (id or @ref)
    target_ref: Optional[str] = None         # relationship target (id or @ref)
    status: ChangeStatus = ChangeStatus.PENDING
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None

    def describe(self) -> str:
        kind = self.change_type
        if kind == ChangeType.CREATE_NODE:
            return f"+ Create node '{self.title}'"
        if kind == ChangeType.UPDATE_NODE:
            fields = [f for f in ("title", "content") if getattr(self, f) is not None]
            return f"~ Update node {self.target_id} ({', '.join(fields) or 'no fields'})"
        if kind == ChangeType.DELETE_NODE:
            return f"- Delete node {self.target_id}"
        if kind == ChangeType.CREATE_RELATIONSHIP:
            meta = ", ".join(self.metadata or []) or "(no metadata)"
            return f"+ Link {self.source_ref} -> {self.target_ref} :: {meta}"
        if kind == ChangeType.UPDATE_RELATIONSHIP:
            meta = ", ".join(self.metadata or []) or "(no metadata)"
            return f"~ Update relationship {self.target_id} :: {meta}"
        return f"- Delete relationship {self.target_id}"

    def diff(self) -> str:
        """Old-vs-new view once ``before`` is known (used post-commit/preview)."""
        if self.change_type == ChangeType.UPDATE_NODE and self.before is not None:
            lines = [self.describe()]
            if self.title is not None:
                lines.append(f"    title: {self.before.get('title')!r} -> {self.title!r}")
            if self.content is not None:
                lines.append(
                    f"    content: {self.before.get('content')!r} -> {self.content!r}"
                )
            return "\n".join(lines)
        return self.describe()

    def to_dict(self) -> dict[str, Any]:
        record = asdict(self)
        record["change_type"] = self.change_type.value
        record["status"] = self.status.value
        return record


@dataclass
class Proposal:
    """An ordered, reviewable set of changes."""

    id: str
    session_id: Optional[str] = None
    summary: str = ""
    created_at: str = field(default_factory=_utc_now)
    status: ChangeStatus = ChangeStatus.PENDING
    changes: list[Change] = field(default_factory=list)
    _counter: int = 0

    def add(self, change: Change) -> Change:
        self._counter += 1
        change.id = f"{self.id}-C{self._counter}"
        self.changes.append(change)
        return change

    @property
    def is_empty(self) -> bool:
        return not self.changes

    def get(self, change_id: str) -> Optional[Change]:
        return next((c for c in self.changes if c.id == change_id), None)

    def pending(self) -> list[Change]:
        return [c for c in self.changes if c.status == ChangeStatus.PENDING]

    def approved(self) -> list[Change]:
        return [c for c in self.changes if c.status == ChangeStatus.APPROVED]

    def render(self) -> str:
        """Change visualization (FR-11): grouped add / modify / delete view."""
        if self.is_empty:
            return f"Proposal {self.id}: (no changes)"
        added = [c for c in self.changes if c.change_type.value.startswith("create")]
        modified = [c for c in self.changes if c.change_type.value.startswith("update")]
        deleted = [c for c in self.changes if c.change_type.value.startswith("delete")]

        lines = [f"Proposal {self.id} — {self.summary or 'proposed changes'}"]
        if self.reason_summary():
            lines.append(f"Reason: {self.reason_summary()}")
        for label, group in (("Added", added), ("Modified", modified), ("Deleted", deleted)):
            if not group:
                continue
            lines.append(f"  {label}:")
            for change in group:
                lines.append(f"    [{change.id}] {change.diff()}  ({change.status.value})")
        return "\n".join(lines)

    def reason_summary(self) -> str:
        reasons = [c.reason for c in self.changes if c.reason]
        # Collapse duplicates while preserving order.
        seen: list[str] = []
        for reason in reasons:
            if reason not in seen:
                seen.append(reason)
        return "; ".join(seen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "summary": self.summary,
            "created_at": self.created_at,
            "status": self.status.value,
            "changes": [c.to_dict() for c in self.changes],
        }


# -- typed change constructors ----------------------------------------------
def create_node_change(
    title: str, content: str = "", reason: str = "", ref: Optional[str] = None
) -> Change:
    return Change(
        change_type=ChangeType.CREATE_NODE,
        title=title,
        content=content,
        reason=reason,
        ref=ref,
    )


def update_node_change(
    node_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    reason: str = "",
) -> Change:
    return Change(
        change_type=ChangeType.UPDATE_NODE,
        target_id=node_id,
        title=title,
        content=content,
        reason=reason,
    )


def delete_node_change(node_id: str, reason: str = "") -> Change:
    return Change(change_type=ChangeType.DELETE_NODE, target_id=node_id, reason=reason)


def create_relationship_change(
    source_ref: str, target_ref: str, metadata: Optional[list[str]] = None, reason: str = ""
) -> Change:
    return Change(
        change_type=ChangeType.CREATE_RELATIONSHIP,
        source_ref=source_ref,
        target_ref=target_ref,
        metadata=list(metadata or []),
        reason=reason,
    )


def update_relationship_change(
    relationship_id: str, metadata: list[str], reason: str = ""
) -> Change:
    return Change(
        change_type=ChangeType.UPDATE_RELATIONSHIP,
        target_id=relationship_id,
        metadata=list(metadata),
        reason=reason,
    )


def delete_relationship_change(relationship_id: str, reason: str = "") -> Change:
    return Change(
        change_type=ChangeType.DELETE_RELATIONSHIP,
        target_id=relationship_id,
        reason=reason,
    )
