"""Diagnostic package (Epic 10 - Diagnostic Package).

Bundles the event stream, captured errors, debug views and AI execution history
into a single exportable package so a failing session can be reproduced.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .debug_view import render_full_debug
from .errors import ErrorTracker
from .events import EventLog, EventType


@dataclass
class DiagnosticPackage:
    event_log: EventLog
    error_tracker: ErrorTracker

    def build(self, session_id: Optional[str] = None) -> dict[str, Any]:
        events = self.event_log.events(session_id=session_id)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "summary": {
                "events": len(events),
                "errors": len(self.error_tracker.errors()),
                "ai_calls": len(
                    self.event_log.events(
                        event_type=EventType.AI_RESPONSE, session_id=session_id
                    )
                ),
                "commits": len(
                    self.event_log.events(
                        event_type=EventType.COMMIT, session_id=session_id
                    )
                ),
            },
            "events": [event.to_dict() for event in events],
            "errors": [error.to_dict() for error in self.error_tracker.errors()],
            "execution_history": self._execution_history(session_id),
            "debug_view": render_full_debug(self.event_log, session_id),
        }

    def _execution_history(self, session_id: Optional[str]) -> list[dict[str, Any]]:
        history_types = {
            EventType.AI_REQUEST,
            EventType.TOOL_CALL,
            EventType.PROPOSAL_CREATED,
            EventType.COMMIT,
            EventType.UNDO,
            EventType.AI_RESPONSE,
        }
        return [
            event.to_dict()
            for event in self.event_log.events(session_id=session_id)
            if event.type in history_types
        ]

    def to_json(self, session_id: Optional[str] = None) -> str:
        return json.dumps(
            self.build(session_id), ensure_ascii=False, indent=2, default=str
        )

    def export(self, directory: str, session_id: Optional[str] = None) -> str:
        """Write the package to ``directory`` and return its path."""
        os.makedirs(directory, exist_ok=True)
        package = self.build(session_id)

        with open(os.path.join(directory, "package.json"), "w", encoding="utf-8") as fh:
            json.dump(package, fh, ensure_ascii=False, indent=2, default=str)
        self.event_log.write_jsonl(os.path.join(directory, "events.jsonl"))
        with open(os.path.join(directory, "errors.json"), "w", encoding="utf-8") as fh:
            json.dump(package["errors"], fh, ensure_ascii=False, indent=2, default=str)
        with open(os.path.join(directory, "debug.txt"), "w", encoding="utf-8") as fh:
            fh.write(package["debug_view"])
        return directory
