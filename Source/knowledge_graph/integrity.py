"""Integrity validation to keep the graph from breaking (RQ-01 item 10).

Guarantees:
* No two Nodes / Relationships share the same id.
* A Relationship never points at a Node that does not exist.
"""

from __future__ import annotations

from .repositories import NodeRepository, RelationshipRepository


class IntegrityError(Exception):
    """Raised when an operation would corrupt the graph."""


class IntegrityValidator:
    def __init__(
        self, nodes: NodeRepository, relationships: RelationshipRepository
    ) -> None:
        self._nodes = nodes
        self._relationships = relationships

    def ensure_unique_node_id(self, node_id: str) -> None:
        if self._nodes.exists(node_id):
            raise IntegrityError(f"Duplicate node id: {node_id}")

    def ensure_unique_relationship_id(self, relationship_id: str) -> None:
        if self._relationships.exists(relationship_id):
            raise IntegrityError(f"Duplicate relationship id: {relationship_id}")

    def ensure_endpoints_exist(self, source_node_id: str, target_node_id: str) -> None:
        if not self._nodes.exists(source_node_id):
            raise IntegrityError(f"Source node does not exist: {source_node_id}")
        if not self._nodes.exists(target_node_id):
            raise IntegrityError(f"Target node does not exist: {target_node_id}")
