"""Chat-centric product shell (Epic 8 & 9).

:class:`AIWritingPartner` is the orchestrator that wires together every Phase-1
subsystem behind a single conversational surface; :mod:`app.chat_cli` is the
runnable chat interface on top of it.
"""

from __future__ import annotations

from .partner import AIWritingPartner, ChatTurn

__all__ = ["AIWritingPartner", "ChatTurn"]
