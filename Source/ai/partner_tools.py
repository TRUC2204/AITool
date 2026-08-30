"""Phase-1 partner tools (Epic 1 Tool Framework, Epic 4 grounding, Epic 5 collab).

The single access layer the agent uses to touch the project. Read tools record
evidence, cache results and emit retrieval events; write tools never mutate the
graph — they stage changes into the active proposal (draft-before-commit,
FR-05/FR-09). Also exposes project-management and creative-collaboration tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from knowledge_graph import KnowledgeGraph
from observability import EventLog, EventType
from retrieval import (
    ContextCache,
    KnowledgeRetrievalService,
    SearchService,
    dedupe_context,
    rank_candidates,
)

from .context_assembly import (
    build_node_context,
    build_relationship_context,
    merge_context,
)
from grounding import EvidenceTracker
from memory import ConsistencyChecker
from changes import (
    Proposal,
    create_node_change,
    create_relationship_change,
    delete_node_change,
    update_node_change,
)
from .tools import ToolRegistry, ToolSpec

_STRING = {"type": "string"}
_STRING_ARRAY = {"type": "array", "items": {"type": "string"}}


@dataclass
class ToolContext:
    """Shared, per-session state the partner tools operate on."""

    graph: KnowledgeGraph
    retrieval: KnowledgeRetrievalService
    search: SearchService
    evidence: EvidenceTracker
    cache: ContextCache
    event_log: EventLog
    consistency: ConsistencyChecker
    get_active_proposal: Callable[[], Proposal]
    session_id: Optional[str] = None

    def emit_retrieval(self, kind: str, message: str, count: int, cache_hit: bool = False) -> None:
        self.event_log.emit(
            EventType.RETRIEVAL,
            message,
            session_id=self.session_id,
            kind=kind,
            count=count,
            cache_hit=cache_hit,
        )

    def emit_context(self, node_count: int, char_size: int, titles: list[str]) -> None:
        self.event_log.emit(
            EventType.CONTEXT_BUILD,
            f"assembled context from {node_count} node(s)",
            session_id=self.session_id,
            node_count=node_count,
            char_size=char_size,
            node_titles=titles,
        )


def build_partner_tools(ctx: ToolContext) -> ToolRegistry:
    registry = ToolRegistry()

    # -- read tools (evidence + cache + events) ----------------------------
    def _search_node(args: dict[str, Any]) -> dict[str, Any]:
        query = args["query"]
        by = args.get("by", "keyword")
        key = f"search:{by}:{query.strip().lower()}"
        cached = ctx.cache.get(key)
        if cached is not None:
            ctx.emit_retrieval("search", f"'{query}' (by {by})", len(cached), cache_hit=True)
            return {"count": len(cached), "candidates": cached}
        if by == "title":
            hits = ctx.search.search_by_title(query)
        elif by == "metadata":
            hits = ctx.search.search_by_metadata(query)
        else:
            hits = ctx.search.search_by_keyword(query)
        ranked = rank_candidates(hits, query)
        candidates = [{"id": c.id, "title": c.title, "snippet": c.snippet} for c in ranked]
        ctx.cache.put(key, candidates)
        ctx.emit_retrieval("search", f"'{query}' (by {by})", len(candidates))
        return {"count": len(candidates), "candidates": candidates}

    def _get_node(args: dict[str, Any]) -> dict[str, Any]:
        node = ctx.retrieval.get_node(args["nodeId"])
        if node is None:
            ctx.emit_retrieval("get", f"node {args['nodeId']}", 0)
            return {"found": False}
        ctx.evidence.record_node(node.id, node.title, node.content[:120])
        context = build_node_context(node)
        ctx.emit_retrieval("get", f"node {node.id} ({node.title})", 1)
        ctx.emit_context(1, len(context), [node.title])
        return {
            "found": True,
            "id": node.id,
            "title": node.title,
            "content": node.content,
            "version": node.version,
            "context": context,
        }

    def _get_related_nodes(args: dict[str, Any]) -> dict[str, Any]:
        node_id = args["nodeId"]
        result = ctx.retrieval.get_related_nodes(node_id, args.get("maxDepth"))
        related: list[dict[str, Any]] = []
        contexts: list[str] = []
        titles: list[str] = []
        for item in result.related:
            ctx.evidence.record_node(item.node.id, item.node.title, item.node.content[:120])
            ctx.evidence.record_relationship(
                item.relationship.id, ", ".join(item.relationship.metadata)
            )
            related.append(
                {
                    "id": item.node.id,
                    "title": item.node.title,
                    "direction": item.direction,
                    "depth": item.depth,
                    "relationshipId": item.relationship.id,
                    "relationshipMetadata": item.relationship.metadata,
                }
            )
            contexts.append(build_relationship_context(item.relationship, item.node))
            titles.append(item.node.title)
        merged = merge_context(dedupe_context(contexts))
        ctx.emit_retrieval("traverse", f"related to {node_id}", len(related))
        ctx.emit_context(len(titles), len(merged), titles)
        return {
            "count": len(related),
            "related": related,
            "stoppedReason": result.stopped_reason,
            "circularDetected": result.visited_circular,
            "context": merged,
        }

    # -- write tools (proposal only, no direct mutation) -------------------
    def _propose_create_node(args: dict[str, Any]) -> dict[str, Any]:
        proposal = ctx.get_active_proposal()
        change = proposal.add(
            create_node_change(
                title=args["title"],
                content=args.get("content", ""),
                reason=args.get("reason", ""),
                ref=args.get("ref"),
            )
        )
        ctx.event_log.emit(
            EventType.PROPOSAL_CREATED,
            f"proposed: {change.describe()}",
            session_id=ctx.session_id,
            proposal_id=proposal.id,
            change_id=change.id,
        )
        return {"proposed": True, "changeId": change.id, "summary": change.describe()}

    def _propose_update_node(args: dict[str, Any]) -> dict[str, Any]:
        proposal = ctx.get_active_proposal()
        change = proposal.add(
            update_node_change(
                node_id=args["nodeId"],
                title=args.get("title"),
                content=args.get("content"),
                reason=args.get("reason", ""),
            )
        )
        ctx.event_log.emit(
            EventType.PROPOSAL_CREATED,
            f"proposed: {change.describe()}",
            session_id=ctx.session_id,
            proposal_id=proposal.id,
            change_id=change.id,
        )
        return {"proposed": True, "changeId": change.id, "summary": change.describe()}

    def _propose_delete_node(args: dict[str, Any]) -> dict[str, Any]:
        proposal = ctx.get_active_proposal()
        change = proposal.add(
            delete_node_change(node_id=args["nodeId"], reason=args.get("reason", ""))
        )
        ctx.event_log.emit(
            EventType.PROPOSAL_CREATED,
            f"proposed: {change.describe()}",
            session_id=ctx.session_id,
            proposal_id=proposal.id,
            change_id=change.id,
        )
        return {"proposed": True, "changeId": change.id, "summary": change.describe()}

    def _propose_link_nodes(args: dict[str, Any]) -> dict[str, Any]:
        proposal = ctx.get_active_proposal()
        change = proposal.add(
            create_relationship_change(
                source_ref=args["sourceRef"],
                target_ref=args["targetRef"],
                metadata=args.get("metadata", []),
                reason=args.get("reason", ""),
            )
        )
        ctx.event_log.emit(
            EventType.PROPOSAL_CREATED,
            f"proposed: {change.describe()}",
            session_id=ctx.session_id,
            proposal_id=proposal.id,
            change_id=change.id,
        )
        return {"proposed": True, "changeId": change.id, "summary": change.describe()}

    # -- project management & collaboration tools --------------------------
    def _get_project_info(_args: dict[str, Any]) -> dict[str, Any]:
        return {
            "nodeCount": len(ctx.graph.list_nodes()),
            "relationshipCount": len(ctx.graph.list_relationships()),
        }

    def _check_consistency(_args: dict[str, Any]) -> dict[str, Any]:
        duplicates = ctx.consistency.find_duplicate_titles()
        dangling = ctx.consistency.find_dangling_relationships()
        return {
            "duplicateTitleGroups": duplicates,
            "danglingRelationships": dangling,
            "clean": not duplicates and not dangling,
        }

    def _find_content_gaps(_args: dict[str, Any]) -> dict[str, Any]:
        gaps = [
            {"id": n.id, "title": n.title, "contentLength": len(n.content)}
            for n in ctx.graph.list_nodes()
            if len(n.content.strip()) < 20
        ]
        return {"count": len(gaps), "gaps": gaps}

    _register_read_tools(registry, _search_node, _get_node, _get_related_nodes)
    _register_write_tools(
        registry,
        _propose_create_node,
        _propose_update_node,
        _propose_delete_node,
        _propose_link_nodes,
    )
    _register_support_tools(
        registry, _get_project_info, _check_consistency, _find_content_gaps
    )
    return registry


def _register_read_tools(registry, search_fn, get_fn, related_fn) -> None:
    registry.register(
        ToolSpec(
            name="SearchNode",
            description="Search project nodes by keyword, title, or metadata.",
            parameters={
                "type": "object",
                "properties": {
                    "query": _STRING,
                    "by": {"type": "string", "enum": ["keyword", "title", "metadata"]},
                },
                "required": ["query"],
            },
            handler=search_fn,
            required=["query"],
        )
    )
    registry.register(
        ToolSpec(
            name="GetNode",
            description="Load one node's full content by id. Records it as a source.",
            parameters={
                "type": "object",
                "properties": {"nodeId": _STRING},
                "required": ["nodeId"],
            },
            handler=get_fn,
            required=["nodeId"],
        )
    )
    registry.register(
        ToolSpec(
            name="GetRelatedNodes",
            description="Load nodes related to a node, bounded by depth/limits.",
            parameters={
                "type": "object",
                "properties": {"nodeId": _STRING, "maxDepth": {"type": "integer"}},
                "required": ["nodeId"],
            },
            handler=related_fn,
            required=["nodeId"],
        )
    )


def _register_write_tools(registry, create_fn, update_fn, delete_fn, link_fn) -> None:
    registry.register(
        ToolSpec(
            name="ProposeCreateNode",
            description=(
                "Propose creating a node (does NOT write yet). Give a clear reason. "
                "Set 'ref' (e.g. '@hero') to link it in the same proposal."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "title": _STRING,
                    "content": _STRING,
                    "reason": _STRING,
                    "ref": _STRING,
                },
                "required": ["title"],
            },
            handler=create_fn,
            required=["title"],
        )
    )
    registry.register(
        ToolSpec(
            name="ProposeUpdateNode",
            description="Propose updating a node's title and/or content. Give a reason.",
            parameters={
                "type": "object",
                "properties": {
                    "nodeId": _STRING,
                    "title": _STRING,
                    "content": _STRING,
                    "reason": _STRING,
                },
                "required": ["nodeId"],
            },
            handler=update_fn,
            required=["nodeId"],
        )
    )
    registry.register(
        ToolSpec(
            name="ProposeDeleteNode",
            description="Propose deleting a node. Give a reason.",
            parameters={
                "type": "object",
                "properties": {"nodeId": _STRING, "reason": _STRING},
                "required": ["nodeId"],
            },
            handler=delete_fn,
            required=["nodeId"],
        )
    )
    registry.register(
        ToolSpec(
            name="ProposeLinkNodes",
            description=(
                "Propose a relationship between two nodes. sourceRef/targetRef are "
                "node ids or '@ref' handles from ProposeCreateNode in this proposal."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "sourceRef": _STRING,
                    "targetRef": _STRING,
                    "metadata": _STRING_ARRAY,
                    "reason": _STRING,
                },
                "required": ["sourceRef", "targetRef"],
            },
            handler=link_fn,
            required=["sourceRef", "targetRef"],
        )
    )


def _register_support_tools(registry, info_fn, consistency_fn, gaps_fn) -> None:
    registry.register(
        ToolSpec(
            name="GetProjectInfo",
            description="Return counts of nodes and relationships in the project.",
            parameters={"type": "object", "properties": {}},
            handler=info_fn,
        )
    )
    registry.register(
        ToolSpec(
            name="CheckConsistency",
            description="Find duplicate node titles and dangling relationships.",
            parameters={"type": "object", "properties": {}},
            handler=consistency_fn,
        )
    )
    registry.register(
        ToolSpec(
            name="FindContentGaps",
            description="List nodes with little or no content (candidates to develop).",
            parameters={"type": "object", "properties": {}},
            handler=gaps_fn,
        )
    )
