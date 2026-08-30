"""Memory promotion (Epic 3 - Memory Promotion / FR-18).

Not everything said in a chat belongs in long-term memory. Promotion turns
selected working-memory facts into a reviewable proposal; nothing is written to
the graph until the user approves it, keeping the draft-before-commit guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from changes import Proposal, create_node_change

from .working_memory import WorkingMemory


@dataclass
class PromotionCandidate:
    title: str
    content: str
    source: str  # "assumption" | "discussion" | "explicit"
    reason: str = ""


class MemoryPromotion:
    """Builds promotion proposals from working memory (never auto-writes)."""

    def candidates_from_assumptions(
        self, working_memory: WorkingMemory
    ) -> list[PromotionCandidate]:
        return [
            PromotionCandidate(
                title=self._title_of(assumption),
                content=assumption,
                source="assumption",
                reason="Confirmed during this session",
            )
            for assumption in working_memory.assumptions
        ]

    def build_proposal(
        self,
        candidates: list[PromotionCandidate],
        proposal_id: str,
        session_id: Optional[str] = None,
    ) -> Proposal:
        proposal = Proposal(
            id=proposal_id,
            session_id=session_id,
            summary="Promote working-memory facts to long-term memory",
        )
        for candidate in candidates:
            proposal.add(
                create_node_change(
                    title=candidate.title,
                    content=candidate.content,
                    reason=candidate.reason or f"Promoted from {candidate.source}",
                )
            )
        return proposal

    @staticmethod
    def _title_of(text: str, max_len: int = 60) -> str:
        first_line = text.strip().splitlines()[0] if text.strip() else "Untitled"
        return first_line[:max_len].rstrip()
