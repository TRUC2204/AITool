"""Graph traversal (RQ-01 item 7).

Lets you walk from one Node to its directly connected Nodes, following
relationships either outbound (A -> B) or inbound (B <- A).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .indexes import RelationshipIndex
from .models import Node, Relationship
from .repositories import NodeRepository, RelationshipRepository

Direction = Literal["outbound", "inbound", "both"]


@dataclass
class ConnectedNode:
    """A Node reached by traversing one Relationship."""

    node: Node
    relationship: Relationship
    direction: Literal["outbound", "inbound"]


class GraphTraversalService:
    def __init__(
        self,
        nodes: NodeRepository,
        relationships: RelationshipRepository,
        relationship_index: RelationshipIndex,
    ) -> None:
        self._nodes = nodes
        self._relationships = relationships
        self._index = relationship_index

    def get_connected_nodes(
        self, node_id: str, direction: Direction = "both"
    ) -> list[ConnectedNode]:
        """Return Nodes directly connected to ``node_id``.

        * ``outbound``: node is the source (A -> B).
        * ``inbound``: node is the target (B <- A).
        * ``both``: either side.
        """
        results: list[ConnectedNode] = []
        for rel_id in self._index.get_relationships_of_node(node_id):
            rel = self._relationships.get(rel_id)
            if rel is None:
                continue
            if rel.source_node_id == node_id and direction in ("outbound", "both"):
                other = self._nodes.get(rel.target_node_id)
                if other is not None:
                    results.append(ConnectedNode(other, rel, "outbound"))
            if rel.target_node_id == node_id and direction in ("inbound", "both"):
                other = self._nodes.get(rel.source_node_id)
                if other is not None:
                    results.append(ConnectedNode(other, rel, "inbound"))
        return results
