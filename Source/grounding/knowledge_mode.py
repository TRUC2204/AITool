"""Knowledge mode control (Epic 4 - Internal First / External Knowledge Mode).

The system defaults to INTERNAL_ONLY: the AI may only ground answers in project
data. The user must explicitly opt into EXTERNAL_ALLOWED (Internet Mode) before
the AI may use the model's own background knowledge, and any such content must
be marked as external.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from observability import EventLog, EventType


class KnowledgeMode(str, Enum):
    INTERNAL_ONLY = "internal_only"
    EXTERNAL_ALLOWED = "external_allowed"


_INTERNAL_DIRECTIVE = (
    "KNOWLEDGE MODE: INTERNAL ONLY.\n"
    "- Answer ONLY from data returned by the project tools (SearchNode, GetNode, "
    "GetRelatedNodes).\n"
    "- Do NOT use your own background knowledge to fill gaps.\n"
    "- If the tools return no relevant data, reply exactly that no internal "
    "information was found and stop; never invent facts about this world."
)

_EXTERNAL_DIRECTIVE = (
    "KNOWLEDGE MODE: EXTERNAL ALLOWED (Internet Mode ON).\n"
    "- Prefer internal project data first; only use outside/background knowledge "
    "when the project has no answer.\n"
    "- Clearly mark any statement that comes from outside the project with the "
    "prefix '[EXTERNAL]'."
)


class KnowledgeModeController:
    """Holds the active knowledge mode and produces the grounding directive."""

    def __init__(
        self,
        mode: KnowledgeMode = KnowledgeMode.INTERNAL_ONLY,
        event_log: Optional[EventLog] = None,
    ) -> None:
        self._mode = mode
        self._event_log = event_log

    @property
    def mode(self) -> KnowledgeMode:
        return self._mode

    @property
    def is_external_allowed(self) -> bool:
        return self._mode == KnowledgeMode.EXTERNAL_ALLOWED

    def set_mode(self, mode: KnowledgeMode, session_id: Optional[str] = None) -> None:
        self._mode = mode
        if self._event_log is not None:
            self._event_log.emit(
                EventType.KNOWLEDGE_MODE,
                f"knowledge mode set to {mode.value}",
                session_id=session_id,
                mode=mode.value,
            )

    def enable_external(self, session_id: Optional[str] = None) -> None:
        self.set_mode(KnowledgeMode.EXTERNAL_ALLOWED, session_id)

    def disable_external(self, session_id: Optional[str] = None) -> None:
        self.set_mode(KnowledgeMode.INTERNAL_ONLY, session_id)

    def toggle(self, session_id: Optional[str] = None) -> KnowledgeMode:
        self.set_mode(
            KnowledgeMode.INTERNAL_ONLY
            if self.is_external_allowed
            else KnowledgeMode.EXTERNAL_ALLOWED,
            session_id,
        )
        return self._mode

    def directive(self) -> str:
        return (
            _EXTERNAL_DIRECTIVE
            if self.is_external_allowed
            else _INTERNAL_DIRECTIVE
        )
