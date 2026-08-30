"""Evidence-based debug log formatting for Phase-0 AI acceptance tests."""

from __future__ import annotations

from .agent import AgentResult, ToolCallLog


SEPARATOR = "--------------------------------"


def format_agent_debug_log(
    user_request: str,
    result: AgentResult,
    provider: str = "Gemini",
    model: str | None = None,
) -> str:
    lines: list[str] = [
        "[USER REQUEST]",
        user_request,
        "",
        SEPARATOR,
    ]
    id_titles = _collect_id_titles(result.tool_calls)
    context_node_ids: set[str] = set()
    context_node_titles: list[str] = []

    for call in result.tool_calls:
        if call.name == "SearchNode":
            _append_search(lines, call)
        elif call.name == "GetNode":
            title = _title_for(call.result.get("id"), id_titles)
            _remember_context_node(call.result.get("id"), title, context_node_ids, context_node_titles)
            _append_node_access(lines, title)
        elif call.name == "GetRelatedNodes":
            source_id = str(call.args.get("nodeId", ""))
            source_title = _title_for(source_id, id_titles)
            _append_relationship_traversal(lines, call, source_title, id_titles)
            for item in call.result.get("related", []):
                title = _title_for(item.get("id"), id_titles)
                _remember_context_node(item.get("id"), title, context_node_ids, context_node_titles)
                _append_node_access(lines, title)

    context_size = sum(
        len(str(call.result.get("context", "")))
        for call in result.tool_calls
        if call.name in ("GetNode", "GetRelatedNodes")
    )
    lines.extend(
        [
            "[CONTEXT GENERATED]",
            f"Node Count: {len(context_node_titles)}",
            "Included Nodes:",
            *context_node_titles,
            f"Context Size: {context_size} chars",
            "",
            SEPARATOR,
            "[AI REQUEST]",
            f"Provider: {provider}",
        ]
    )
    if model:
        lines.append(f"Model: {model}")
    lines.extend(
        [
            f"Tool Calls: {len(result.tool_calls)}",
            "Request Sent: Success",
            "",
            SEPARATOR,
            "[AI RESPONSE]",
            result.final_text or "",
            f"Response Received: {'Success' if result.final_text else 'Empty'}",
            f"Response Length: {len(result.final_text or '')} chars",
        ]
    )
    return "\n".join(lines)


def format_tool_call_debug_log(call: ToolCallLog) -> str:
    if call.name == "CreateNode":
        return "\n".join(
            [
                "[AI TOOL CALL]",
                "CreateNode",
                f"Name: {call.args.get('title', '')}",
                "",
                SEPARATOR,
                "[STORAGE]",
                "Node Created" if call.result.get("created") else "Node Create Failed",
                f"Id: {call.result.get('id', '')}",
                f"Result: {_success(call.ok and call.result.get('created'))}",
            ]
        )
    if call.name == "UpdateNode":
        return "\n".join(
            [
                "[AI TOOL CALL]",
                "UpdateNode",
                f"Node: {call.args.get('nodeId', '')}",
                "Field: Content",
                "",
                SEPARATOR,
                "[OLD VALUE]",
                str(call.result.get("oldContent", "")),
                "",
                SEPARATOR,
                "[NEW VALUE]",
                str(call.result.get("newContent", "")),
                "",
                SEPARATOR,
                f"Result: {_success(call.ok and call.result.get('updated'))}",
            ]
        )
    if call.name == "DeleteNode":
        return "\n".join(
            [
                "[AI TOOL CALL]",
                "DeleteNode",
                f"Node: {call.args.get('nodeId', '')}",
                "",
                SEPARATOR,
                f"Result: {_success(call.ok and call.result.get('deleted'))}",
            ]
        )
    return "\n".join(
        [
            "[AI TOOL CALL]",
            call.name,
            f"Result: {_success(call.ok)}",
        ]
    )


def _append_search(lines: list[str], call: ToolCallLog) -> None:
    lines.extend(
        [
            "[SEARCH]",
            f"Keyword: {call.args.get('query', '')}",
            "Matched Nodes:",
        ]
    )
    lines.extend(candidate.get("title", "") for candidate in call.result.get("candidates", []))
    lines.extend(["", SEPARATOR])


def _append_node_access(lines: list[str], title: str) -> None:
    lines.extend(
        [
            "[NODE ACCESS]",
            f"Load Node: {title}",
            "",
            SEPARATOR,
        ]
    )


def _append_relationship_traversal(
    lines: list[str], call: ToolCallLog, source_title: str, id_titles: dict[str, str]
) -> None:
    lines.append("[RELATIONSHIP TRAVERSAL]")
    for item in call.result.get("related", []):
        metadata = item.get("relationshipMetadata") or ["(no metadata)"]
        target_id = item.get("id")
        target_title = _title_for(target_id, id_titles)
        lines.extend([source_title, f"-> {metadata[0]}", f"-> {target_title}"])
    lines.extend(["", SEPARATOR])


def _collect_id_titles(tool_calls: list[ToolCallLog]) -> dict[str, str]:
    titles: dict[str, str] = {}
    for call in tool_calls:
        if call.name == "SearchNode":
            for candidate in call.result.get("candidates", []):
                titles[str(candidate.get("id", ""))] = str(candidate.get("title", ""))
        elif call.name == "GetNode" and call.result.get("found"):
            titles[str(call.result.get("id", ""))] = str(call.result.get("title", ""))
        elif call.name == "GetRelatedNodes":
            for item in call.result.get("related", []):
                titles[str(item.get("id", ""))] = str(item.get("title", ""))
    return titles


def _remember_context_node(
    node_id: object, title: str, known_ids: set[str], titles: list[str]
) -> None:
    key = str(node_id or title)
    if key not in known_ids:
        known_ids.add(key)
        titles.append(title)


def _title_for(node_id: object, id_titles: dict[str, str]) -> str:
    return id_titles.get(str(node_id), str(node_id or ""))


def _success(value: object) -> str:
    return "Success" if value else "Fail"