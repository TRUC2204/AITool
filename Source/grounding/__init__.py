"""Knowledge Grounding (Epic 4).

Guarantees the assistant answers from internal project data first, surfaces the
exact sources it used, refuses to invent when no internal evidence exists, and
only reaches outside the project when the user explicitly enables External /
Internet Mode.
"""

from __future__ import annotations

from .evidence import (
    NO_EVIDENCE_MESSAGE,
    EvidenceTracker,
    SourceKind,
    SourceRef,
)
from .knowledge_mode import KnowledgeMode, KnowledgeModeController

__all__ = [
    "KnowledgeMode",
    "KnowledgeModeController",
    "SourceKind",
    "SourceRef",
    "EvidenceTracker",
    "NO_EVIDENCE_MESSAGE",
]
