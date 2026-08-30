"""Change Management + History & Undo (Epic 6 & 7).

The safety spine of Phase 1: the AI never writes to the graph directly. Every
mutation becomes a :class:`Change` inside a :class:`Proposal`; the user reviews
and approves (all or in part); the :class:`CommitEngine` applies approved
changes and records a reversible :class:`CommitRecord`; the :class:`UndoManager`
rolls changes back.
"""

from __future__ import annotations

from .commit import CommitEngine
from .history import AppliedChange, ChangeHistory, CommitRecord
from .proposal import (
    Change,
    ChangeStatus,
    ChangeType,
    Proposal,
    create_node_change,
    create_relationship_change,
    delete_node_change,
    delete_relationship_change,
    update_node_change,
    update_relationship_change,
)
from .undo import UndoManager, UndoResult

__all__ = [
    "Change",
    "ChangeType",
    "ChangeStatus",
    "Proposal",
    "create_node_change",
    "update_node_change",
    "delete_node_change",
    "create_relationship_change",
    "update_relationship_change",
    "delete_relationship_change",
    "CommitEngine",
    "CommitRecord",
    "AppliedChange",
    "ChangeHistory",
    "UndoManager",
    "UndoResult",
]
