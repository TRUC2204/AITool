"""Runtime logging (Epic 10 - Runtime Logging).

A single append-only, in-memory event stream shared by the whole runtime. Every
AI request/response, tool call, retrieval, proposal, commit and undo becomes an
``Event`` so the flow can be replayed later. Events can be streamed to a JSONL
file sink for post-mortem diagnostics.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional


class EventType(str, Enum):
    AI_REQUEST = "ai_request"
    AI_RESPONSE = "ai_response"
    TOOL_CALL = "tool_call"
    RETRIEVAL = "retrieval"
    CACHE = "cache"
    CONTEXT_BUILD = "context_build"
    PROPOSAL_CREATED = "proposal_created"
    PROPOSAL_REVIEWED = "proposal_reviewed"
    COMMIT = "commit"
    UNDO = "undo"
    MEMORY_PROMOTION = "memory_promotion"
    KNOWLEDGE_MODE = "knowledge_mode"
    DECISION = "decision"
    ERROR = "error"
    SESSION = "session"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Event:
    """A single structured log record."""

    seq: int
    timestamp: str
    type: EventType
    message: str
    session_id: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        record = asdict(self)
        record["type"] = self.type.value
        return record

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class EventLog:
    """Thread-safe, append-only event stream with an optional file sink."""

    def __init__(self, sink: Optional[Callable[[Event], None]] = None) -> None:
        self._events: list[Event] = []
        self._seq = 0
        self._sink = sink
        self._lock = threading.Lock()

    def emit(
        self,
        event_type: EventType,
        message: str,
        *,
        session_id: Optional[str] = None,
        **data: Any,
    ) -> Event:
        with self._lock:
            self._seq += 1
            event = Event(
                seq=self._seq,
                timestamp=_utc_now(),
                type=event_type,
                message=message,
                session_id=session_id,
                data=data,
            )
            self._events.append(event)
        if self._sink is not None:
            self._sink(event)
        return event

    def events(
        self,
        *,
        event_type: Optional[EventType] = None,
        session_id: Optional[str] = None,
    ) -> list[Event]:
        with self._lock:
            items = list(self._events)
        if event_type is not None:
            items = [e for e in items if e.type == event_type]
        if session_id is not None:
            items = [e for e in items if e.session_id == session_id]
        return items

    def last(self, event_type: Optional[EventType] = None) -> Optional[Event]:
        matches = self.events(event_type=event_type)
        return matches[-1] if matches else None

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def to_jsonl(self) -> str:
        return "\n".join(event.to_json() for event in self.events())

    def write_jsonl(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.to_jsonl())

    def __len__(self) -> int:
        return len(self._events)


def file_sink(path: str) -> Callable[[Event], None]:
    """A sink that appends each event as a JSON line to ``path``."""

    def _write(event: Event) -> None:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(event.to_json() + "\n")

    return _write
