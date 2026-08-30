"""Node & Relationship access with retrieval control (RQ-03).

Enforces the Phase-0 retrieval limits: max nodes returned, max relationship
traversal depth, and a cap on total characters read. Detects circular
relationships so traversal always terminates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from knowledge_graph import KnowledgeGraph
from knowledge_graph.models import Node, Relationship


@dataclass
class RetrievalLimits:
    max_nodes: int = 30
    max_depth: int = 3
    max_total_chars: int = 100_000


@dataclass
class RelatedNode:
    node: Node
    relationship: Relationship
    direction: str  # "outbound" | "inbound"
    depth: int


@dataclass
class TraversalResult:
    related: list[RelatedNode] = field(default_factory=list)
    stopped_reason: Optional[str] = None  # None | "max_depth" | "max_nodes" | "max_chars"
    visited_circular: bool = False


class KnowledgeRetrievalService:
    def __init__(
        self, graph: KnowledgeGraph, limits: Optional[RetrievalLimits] = None
    ) -> None:
        self._graph = graph
        self.limits = limits or RetrievalLimits()

    def get_node(self, node_id: str) -> Optional[Node]:
        return self._graph.get_node(node_id)

    def get_related_nodes(
        self, node_id: str, max_depth: Optional[int] = None
    ) -> TraversalResult:
        """Breadth-first traversal of directly and transitively connected Nodes,
        bounded by the retrieval limits. Circular paths are detected via a
        visited set so the walk always terminates."""
        depth_limit = self.limits.max_depth if max_depth is None else max_depth
        result = TraversalResult()
        if self._graph.get_node(node_id) is None:
            return result

        visited: set[str] = {node_id}
        chars_read = 0
        frontier: list[tuple[str, int]] = [(node_id, 0)]

        while frontier:
            current_id, depth = frontier.pop(0)
            if depth >= depth_limit:
                if self._has_unvisited_neighbor(current_id, visited):
                    result.stopped_reason = "max_depth"
                continue

            for connected in self._graph.get_connected_nodes(current_id, "both"):
                neighbor = connected.node
                if neighbor.id in visited:
                    result.visited_circular = True
                    continue

                if len(result.related) >= self.limits.max_nodes:
                    result.stopped_reason = "max_nodes"
                    return result

                chars_read += len(neighbor.content)
                if chars_read > self.limits.max_total_chars:
                    result.stopped_reason = "max_chars"
                    return result

                visited.add(neighbor.id)
                result.related.append(
                    RelatedNode(
                        node=neighbor,
                        relationship=connected.relationship,
                        direction=connected.direction,
                        depth=depth + 1,
                    )
                )
                frontier.append((neighbor.id, depth + 1))

        return result

    def _has_unvisited_neighbor(self, node_id: str, visited: set[str]) -> bool:
        for connected in self._graph.get_connected_nodes(node_id, "both"):
            if connected.node.id not in visited:
                return True
        return False
