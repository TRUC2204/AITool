"""Observability & Debugging (Epic 10).

Runtime logging, centralized error tracking, debug views and diagnostic
package export. Every other Phase-1 subsystem emits structured events here so
that when the system misbehaves the root cause can be reconstructed from the
log alone.
"""

from __future__ import annotations

from .diagnostics import DiagnosticPackage
from .debug_view import (
    render_context_build,
    render_decision_flow,
    render_full_debug,
    render_retrieval_path,
    render_token_usage,
    render_tool_sequence,
)
from .errors import CapturedError, ErrorCategory, ErrorTracker
from .events import Event, EventLog, EventType

__all__ = [
    "Event",
    "EventLog",
    "EventType",
    "CapturedError",
    "ErrorCategory",
    "ErrorTracker",
    "render_tool_sequence",
    "render_retrieval_path",
    "render_context_build",
    "render_token_usage",
    "render_decision_flow",
    "render_full_debug",
    "DiagnosticPackage",
]
