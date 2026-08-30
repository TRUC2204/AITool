"""Memory Architecture (Epic 3).

Two memory layers plus the workflow that moves information between them:

* :class:`WorkingMemory` — volatile, per-session: conversation state, current
  goal, discussion summary, temporary assumptions and the proposal under
  construction.
* :class:`LongTermMemory` — the Knowledge Graph, retrieved/updated through a
  single access layer with consistency validation.
* :class:`MemoryPromotion` — turns confirmed working-memory facts into a
  reviewable proposal before anything is written to long-term memory.
"""

from __future__ import annotations

from .long_term_memory import ConsistencyChecker, ConsistencyIssue, LongTermMemory
from .promotion import MemoryPromotion, PromotionCandidate
from .working_memory import Message, WorkingMemory

__all__ = [
    "WorkingMemory",
    "Message",
    "LongTermMemory",
    "ConsistencyChecker",
    "ConsistencyIssue",
    "MemoryPromotion",
    "PromotionCandidate",
]
