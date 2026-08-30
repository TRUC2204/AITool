"""Knowledge tools exposed to the AI (RQ-05 read + RQ-06 modify).

Security: the agent only ever touches the graph through these tools; it never
reads the storage files directly.
"""

from __future__ import annotations

from typing import Any, Optional

from knowledge_graph import KnowledgeGraph

from .context_assembly import (
    build_node_context,
    build_relationship_context,
    merge_context,
)
from .tools import ToolRegistry, ToolSpec
from retrieval import KnowledgeRetrievalService, RetrievalLimits, SearchService

_STRING = {"type": "string"}


def build_knowledge_tools(
    graph: KnowledgeGraph, limits: Optional[RetrievalLimits] = None
) -> ToolRegistry:
    search = SearchService(graph)
    retrieval = KnowledgeRetrievalService(graph, limits)
    registry = ToolRegistry()

    # -- RQ-05 read tools ---------------------------------------------------
    def _search_node(args: dict[str, Any]) -> dict[str, Any]:
        query = args["query"]
        by = args.get("by", "keyword")
        if by == "title":
            hits = search.search_by_title(query)
        elif by == "metadata":
            hits = search.search_by_metadata(query)
        else:
            hits = search.search_by_keyword(query)
        return {
            "count": len(hits),
            "candidates": [
                {"id": c.id, "title": c.title, "snippet": c.snippet} for c in hits
            ],
        }

    def _get_node(args: dict[str, Any]) -> dict[str, Any]:
        node = retrieval.get_node(args["nodeId"])
        if node is None:
            return {"found": False}
        return {
            "found": True,
            "id": node.id,
            "title": node.title,
            "content": node.content,
            "version": node.version,
            "context": build_node_context(node),
        }

    def _get_related_nodes(args: dict[str, Any]) -> dict[str, Any]:
        node_id = args["nodeId"]
        depth = args.get("maxDepth")
        result = retrieval.get_related_nodes(node_id, depth)
        contexts = []
        related = []
        for item in result.related:
            related.append(
                {
                    "id": item.node.id,
                    "title": item.node.title,
                    "direction": item.direction,
                    "depth": item.depth,
                    "relationshipId": item.relationship.id,
                    "sourceNodeId": item.relationship.source_node_id,
                    "targetNodeId": item.relationship.target_node_id,
                    "relationshipMetadata": item.relationship.metadata,
                }
            )
            contexts.append(
                build_relationship_context(item.relationship, item.node)
            )
        return {
            "count": len(related),
            "related": related,
            "stoppedReason": result.stopped_reason,
            "circularDetected": result.visited_circular,
            "context": merge_context(contexts),
        }

    # -- RQ-06 modification tools ------------------------------------------
    def _create_node(args: dict[str, Any]) -> dict[str, Any]:
        node = graph.create_node(
            title=args["title"], content=args.get("content", "")
        )
        return {"created": True, "id": node.id, "title": node.title}

    def _update_node(args: dict[str, Any]) -> dict[str, Any]:
        before = graph.get_node(args["nodeId"])
        node = graph.update_node(
            args["nodeId"],
            title=args.get("title"),
            content=args.get("content"),
        )
        if node is None:
            return {"updated": False, "reason": "node_not_found"}
        return {
            "updated": True,
            "id": node.id,
            "version": node.version,
            "oldTitle": before.title if before else None,
            "newTitle": node.title,
            "oldContent": before.content if before else None,
            "newContent": node.content,
        }

    def _delete_node(args: dict[str, Any]) -> dict[str, Any]:
        ok = graph.delete_node(args["nodeId"])
        return {"deleted": ok, "id": args["nodeId"], "reason": None if ok else "node_not_found"}

    registry.register(
        ToolSpec(
            name="SearchNode",
            description="Search nodes by keyword, title, or metadata. Returns candidate nodes.",
            parameters={
                "type": "object",
                "properties": {
                    "query": _STRING,
                    "by": {"type": "string", "enum": ["keyword", "title", "metadata"]},
                },
                "required": ["query"],
            },
            handler=_search_node,
            required=["query"],
        )
    )
    registry.register(
        ToolSpec(
            name="GetNode",
            description="Load a single node's full content and metadata by id.",
            parameters={
                "type": "object",
                "properties": {"nodeId": _STRING},
                "required": ["nodeId"],
            },
            handler=_get_node,
            required=["nodeId"],
        )
    )
    registry.register(
        ToolSpec(
            name="GetRelatedNodes",
            description="Load nodes related to a node, bounded by depth and limits.",
            parameters={
                "type": "object",
                "properties": {
                    "nodeId": _STRING,
                    "maxDepth": {"type": "integer"},
                },
                "required": ["nodeId"],
            },
            handler=_get_related_nodes,
            required=["nodeId"],
        )
    )
    registry.register(
        ToolSpec(
            name="CreateNode",
            description="Create a new node with a title and optional content.",
            parameters={
                "type": "object",
                "properties": {"title": _STRING, "content": _STRING},
                "required": ["title"],
            },
            handler=_create_node,
            required=["title"],
        )
    )
    registry.register(
        ToolSpec(
            name="UpdateNode",
            description="Update an existing node's title and/or content.",
            parameters={
                "type": "object",
                "properties": {
                    "nodeId": _STRING,
                    "title": _STRING,
                    "content": _STRING,
                },
                "required": ["nodeId"],
            },
            handler=_update_node,
            required=["nodeId"],
        )
    )
    registry.register(
        ToolSpec(
            name="DeleteNode",
            description="Delete a node and its relationships by id.",
            parameters={
                "type": "object",
                "properties": {"nodeId": _STRING},
                "required": ["nodeId"],
            },
            handler=_delete_node,
            required=["nodeId"],
        )
    )
    return registry
