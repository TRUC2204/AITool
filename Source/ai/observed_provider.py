"""Observed AI provider (Epic 10 - Runtime Logging for AI, Epic 2 - cost).

A decorator around any :class:`IAIProvider` that emits AI_REQUEST / AI_RESPONSE
events and feeds token usage into a :class:`CostTracker`, without the agent loop
needing to know about observability.
"""

from __future__ import annotations

from typing import Any, Optional

from observability import ErrorCategory, ErrorTracker, EventLog, EventType
from .cost import CostTracker
from .provider import IAIProvider, ProviderResponse


class ObservedProvider(IAIProvider):
    def __init__(
        self,
        inner: IAIProvider,
        event_log: EventLog,
        cost_tracker: CostTracker,
        error_tracker: Optional[ErrorTracker] = None,
        session_id: Optional[str] = None,
    ) -> None:
        self._inner = inner
        self._log = event_log
        self._cost = cost_tracker
        self._errors = error_tracker
        self._session_id = session_id

    def generate(
        self,
        contents: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        max_output_tokens: Optional[int] = None,
    ) -> ProviderResponse:
        self._log.emit(
            EventType.AI_REQUEST,
            "generate request sent",
            session_id=self._session_id,
            turns=len(contents),
            tool_count=len(tools or []),
        )
        try:
            response = self._inner.generate(contents, tools, max_output_tokens)
        except Exception as exc:  # noqa: BLE001 - log then re-raise
            if self._errors is not None:
                self._errors.capture(
                    exc, ErrorCategory.AI, session_id=self._session_id
                )
            raise

        cost = self._cost.add(response.usage)
        self._log.emit(
            EventType.AI_RESPONSE,
            "generate response received",
            session_id=self._session_id,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost=cost,
            has_tool_calls=response.has_tool_calls,
            finish_reason=response.finish_reason,
        )
        return response
