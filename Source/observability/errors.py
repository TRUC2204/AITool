"""Centralized error tracking (Epic 10 - Error Tracking).

Captures failures from any layer (tool, AI provider, retrieval, application)
with a stack trace and reproduction context, mirrors them into the event log,
and keeps them queryable for the diagnostic package.
"""

from __future__ import annotations

import traceback
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterator, Optional

from .events import EventLog, EventType


class ErrorCategory(str, Enum):
    TOOL = "tool"
    AI = "ai"
    RETRIEVAL = "retrieval"
    COMMIT = "commit"
    APP = "app"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CapturedError:
    timestamp: str
    category: ErrorCategory
    message: str
    exception_type: str
    stack: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        record = asdict(self)
        record["category"] = self.category.value
        return record


class ErrorTracker:
    """Collects ``CapturedError`` records and echoes them to the event log."""

    def __init__(self, event_log: Optional[EventLog] = None) -> None:
        self._errors: list[CapturedError] = []
        self._event_log = event_log

    def capture(
        self,
        exc: BaseException,
        category: ErrorCategory,
        *,
        context: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> CapturedError:
        captured = CapturedError(
            timestamp=_utc_now(),
            category=category,
            message=str(exc),
            exception_type=type(exc).__name__,
            stack="".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            ),
            context=dict(context or {}),
        )
        self._errors.append(captured)
        if self._event_log is not None:
            self._event_log.emit(
                EventType.ERROR,
                f"{category.value} error: {captured.message}",
                session_id=session_id,
                exception_type=captured.exception_type,
                category=category.value,
                **captured.context,
            )
        return captured

    @contextmanager
    def guard(
        self,
        category: ErrorCategory,
        *,
        context: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
        reraise: bool = True,
    ) -> Iterator[None]:
        """Capture any exception raised in the block. Re-raises by default."""
        try:
            yield
        except Exception as exc:  # noqa: BLE001 - centralized capture point
            self.capture(exc, category, context=context, session_id=session_id)
            if reraise:
                raise

    def errors(
        self, category: Optional[ErrorCategory] = None
    ) -> list[CapturedError]:
        if category is None:
            return list(self._errors)
        return [e for e in self._errors if e.category == category]

    def last(self) -> Optional[CapturedError]:
        return self._errors[-1] if self._errors else None

    def __len__(self) -> int:
        return len(self._errors)
