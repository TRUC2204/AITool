"""Debug views (Epic 10 - Debug View).

Renders human-readable slices of the event stream: the tool-call sequence, the
retrieval path, the context that was built, token usage, and the AI decision
flow. These are pure functions over an :class:`EventLog` so they can be shown
in the chat app or bundled into a diagnostic package.
"""

from __future__ import annotations

from typing import Optional

from .events import EventLog, EventType

_SEP = "-" * 40


def render_tool_sequence(log: EventLog, session_id: Optional[str] = None) -> str:
    events = log.events(event_type=EventType.TOOL_CALL, session_id=session_id)
    if not events:
        return "[TOOL CALL SEQUENCE]\n(no tool calls)"
    lines = ["[TOOL CALL SEQUENCE]"]
    for event in events:
        status = "ok" if event.data.get("ok", True) else "FAIL"
        iteration = event.data.get("iteration", "-")
        args = event.data.get("args", {})
        lines.append(f"  #{event.seq} it{iteration} {event.message} [{status}] {args}")
    return "\n".join(lines)


def render_retrieval_path(log: EventLog, session_id: Optional[str] = None) -> str:
    events = log.events(event_type=EventType.RETRIEVAL, session_id=session_id)
    if not events:
        return "[RETRIEVAL PATH]\n(no retrieval)"
    lines = ["[RETRIEVAL PATH]"]
    for event in events:
        kind = event.data.get("kind", "?")
        count = event.data.get("count")
        cached = " (cache hit)" if event.data.get("cache_hit") else ""
        suffix = f" -> {count} result(s)" if count is not None else ""
        lines.append(f"  {kind}: {event.message}{suffix}{cached}")
    return "\n".join(lines)


def render_context_build(log: EventLog, session_id: Optional[str] = None) -> str:
    events = log.events(event_type=EventType.CONTEXT_BUILD, session_id=session_id)
    if not events:
        return "[CONTEXT BUILD]\n(no context assembled)"
    lines = ["[CONTEXT BUILD]"]
    for event in events:
        node_count = event.data.get("node_count", 0)
        char_size = event.data.get("char_size", 0)
        titles = event.data.get("node_titles", [])
        lines.append(f"  nodes={node_count} chars={char_size}")
        for title in titles:
            lines.append(f"    - {title}")
    return "\n".join(lines)


def render_token_usage(log: EventLog, session_id: Optional[str] = None) -> str:
    events = log.events(event_type=EventType.AI_RESPONSE, session_id=session_id)
    total_in = sum(int(e.data.get("input_tokens", 0)) for e in events)
    total_out = sum(int(e.data.get("output_tokens", 0)) for e in events)
    total_cost = sum(float(e.data.get("cost", 0.0)) for e in events)
    lines = [
        "[TOKEN USAGE]",
        f"  ai calls: {len(events)}",
        f"  input tokens:  {total_in}",
        f"  output tokens: {total_out}",
        f"  total tokens:  {total_in + total_out}",
        f"  est. cost:     ${total_cost:.6f}",
    ]
    return "\n".join(lines)


def render_decision_flow(log: EventLog, session_id: Optional[str] = None) -> str:
    wanted = {
        EventType.AI_REQUEST,
        EventType.DECISION,
        EventType.TOOL_CALL,
        EventType.RETRIEVAL,
        EventType.PROPOSAL_CREATED,
        EventType.AI_RESPONSE,
    }
    events = [e for e in log.events(session_id=session_id) if e.type in wanted]
    if not events:
        return "[DECISION FLOW]\n(no activity)"
    lines = ["[DECISION FLOW]"]
    for event in events:
        lines.append(f"  {event.type.value}: {event.message}")
    return "\n".join(lines)


def render_full_debug(log: EventLog, session_id: Optional[str] = None) -> str:
    return f"\n{_SEP}\n".join(
        [
            render_decision_flow(log, session_id),
            render_retrieval_path(log, session_id),
            render_tool_sequence(log, session_id),
            render_context_build(log, session_id),
            render_token_usage(log, session_id),
        ]
    )
