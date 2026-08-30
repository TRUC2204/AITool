"""Evidence & source attribution (Epic 4 - Source Attribution / No Evidence).

Tracks every internal node and relationship the AI actually read while forming
an answer so the assistant can cite its sources, and detects the
"no internal evidence found" condition that INTERNAL_ONLY mode must honour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

NO_EVIDENCE_MESSAGE = (
    "No internal information was found in this project for your request. "
    "I won't guess. Enable Internet Mode if you want me to use outside knowledge, "
    "or add the information to the project first."
)


class SourceKind(str, Enum):
    NODE = "node"
    RELATIONSHIP = "relationship"
    EXTERNAL = "external"


@dataclass(frozen=True)
class SourceRef:
    kind: SourceKind
    id: str
    title: str = ""
    snippet: str = ""

    def label(self) -> str:
        if self.kind == SourceKind.EXTERNAL:
            return f"[EXTERNAL] {self.title or self.id}"
        prefix = "Node" if self.kind == SourceKind.NODE else "Relationship"
        name = self.title or self.id
        return f"{prefix} {self.id} ({name})" if self.title else f"{prefix} {self.id}"


class EvidenceTracker:
    """Accumulates the sources used to answer a single request."""

    def __init__(self) -> None:
        self._sources: dict[tuple[SourceKind, str], SourceRef] = {}

    def record_node(self, node_id: str, title: str = "", snippet: str = "") -> None:
        self._add(SourceRef(SourceKind.NODE, node_id, title, snippet))

    def record_relationship(
        self, relationship_id: str, title: str = "", snippet: str = ""
    ) -> None:
        self._add(SourceRef(SourceKind.RELATIONSHIP, relationship_id, title, snippet))

    def record_external(self, label: str) -> None:
        self._add(SourceRef(SourceKind.EXTERNAL, label, label))

    def _add(self, source: SourceRef) -> None:
        self._sources.setdefault((source.kind, source.id), source)

    def sources(self, kind: Optional[SourceKind] = None) -> list[SourceRef]:
        items = list(self._sources.values())
        if kind is not None:
            items = [s for s in items if s.kind == kind]
        return items

    @property
    def has_internal_evidence(self) -> bool:
        return any(
            s.kind in (SourceKind.NODE, SourceKind.RELATIONSHIP)
            for s in self._sources.values()
        )

    @property
    def is_empty(self) -> bool:
        return not self._sources

    def render_attribution(self) -> str:
        if not self._sources:
            return "Sources: (none)"
        lines = ["Sources:"]
        lines.extend(f"  - {source.label()}" for source in self.sources())
        return "\n".join(lines)


@dataclass
class GroundingResult:
    """Outcome of a grounded answer: the text plus its evidence."""

    text: str
    evidence: EvidenceTracker = field(default_factory=EvidenceTracker)
    no_evidence: bool = False

    def with_attribution(self) -> str:
        if self.no_evidence:
            return self.text
        return f"{self.text}\n\n{self.evidence.render_attribution()}"
