"""Data Discovery: search Nodes by keyword / title / metadata (RQ-03).

Returns lightweight candidate lists; the caller loads full content via the
retrieval service.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledge_graph import KnowledgeGraph
from knowledge_graph.models import Node


@dataclass
class NodeCandidate:
    """A search hit: enough to decide whether to load the full Node."""

    id: str
    title: str
    snippet: str
    matched_on: str  # "title" | "content" | "metadata"


class SearchService:
    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def search_by_title(self, keyword: str, limit: int = 30) -> list[NodeCandidate]:
        key = keyword.strip().lower()
        hits = [n for n in self._graph.list_nodes() if key in n.title.lower()]
        return self._to_candidates(hits, "title", limit)

    def search_by_keyword(self, keyword: str, limit: int = 30) -> list[NodeCandidate]:
        """Match keyword in title or content."""
        key = keyword.strip().lower()
        hits: list[Node] = []
        for node in self._graph.list_nodes():
            if key in node.title.lower():
                hits.append(node)
            elif key in node.content.lower():
                hits.append(node)
        matched = "title/content"
        return self._to_candidates(hits, matched, limit)

    def search_by_metadata(self, keyword: str, limit: int = 30) -> list[NodeCandidate]:
        """Match keyword inside relationship metadata, returning the Nodes those
        relationships connect."""
        key = keyword.strip().lower()
        node_ids: set[str] = set()
        for rel in self._graph.list_relationships():
            if any(key in meta.lower() for meta in rel.metadata):
                node_ids.add(rel.source_node_id)
                node_ids.add(rel.target_node_id)
        hits = [n for n in (self._graph.get_node(i) for i in node_ids) if n]
        return self._to_candidates(hits, "metadata", limit)

    @staticmethod
    def _to_candidates(
        nodes: list[Node], matched_on: str, limit: int
    ) -> list[NodeCandidate]:
        candidates = [
            NodeCandidate(
                id=node.id,
                title=node.title,
                snippet=node.content[:120],
                matched_on=matched_on,
            )
            for node in nodes[: max(0, limit)]
        ]
        return candidates
