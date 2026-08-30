"""Working memory (Epic 3 - Working Memory / FR-16).

Volatile state for the current chat session: the message history, the current
goal, the topic under discussion, a rolling discussion summary, temporary
assumptions, and the proposal being built. Cleared when the session ends.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from changes import Proposal


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system"
    text: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkingMemory:
    """Per-session scratch space (FR-16). Not persisted to the graph."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.messages: list[Message] = []
        self.current_goal: Optional[str] = None
        self.topic: Optional[str] = None
        self.discussion_summary: str = ""
        self.assumptions: list[str] = []
        self.active_proposal: Optional[Proposal] = None

    # -- conversation state ------------------------------------------------
    def add_message(self, role: str, text: str) -> Message:
        message = Message(role=role, text=text)
        self.messages.append(message)
        return message

    def recent_messages(self, limit: int = 10) -> list[Message]:
        return self.messages[-limit:]

    def history_text(self, limit: int = 10) -> str:
        return "\n".join(f"{m.role}: {m.text}" for m in self.recent_messages(limit))

    # -- goal / topic / summary -------------------------------------------
    def set_goal(self, goal: str) -> None:
        self.current_goal = goal

    def set_topic(self, topic: str) -> None:
        self.topic = topic

    def set_summary(self, summary: str) -> None:
        self.discussion_summary = summary

    # -- temporary assumptions --------------------------------------------
    def add_assumption(self, assumption: str) -> None:
        if assumption and assumption not in self.assumptions:
            self.assumptions.append(assumption)

    def clear_assumptions(self) -> None:
        self.assumptions.clear()

    # -- proposal under construction --------------------------------------
    def set_active_proposal(self, proposal: Optional[Proposal]) -> None:
        self.active_proposal = proposal

    def clear_proposal(self) -> None:
        self.active_proposal = None

    def snapshot(self) -> dict[str, Any]:
        """A compact view for the context panel and diagnostics."""
        return {
            "session_id": self.session_id,
            "goal": self.current_goal,
            "topic": self.topic,
            "summary": self.discussion_summary,
            "assumptions": list(self.assumptions),
            "message_count": len(self.messages),
            "active_proposal": self.active_proposal.id if self.active_proposal else None,
        }
