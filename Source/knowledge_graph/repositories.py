"""Repositories manage the storage of Nodes and Relationships (RQ-01 items 3 & 4).

Each repository keeps an in-memory view backed by :class:`JsonFileStorage`, so
data survives a restart and the whole graph can be reloaded.
"""

from __future__ import annotations

from typing import Optional

from .models import Node, Relationship
from .persistence import JsonFileStorage


class NodeRepository:
    """CRUD storage management for Nodes."""

    def __init__(self, storage: JsonFileStorage) -> None:
        self._storage = storage
        self._nodes: dict[str, Node] = {}
        self.load()

    def load(self) -> None:
        self._nodes = {
            data["id"]: Node.from_dict(data) for data in self._storage.load_nodes()
        }

    def create(self, node: Node) -> Node:
        self._nodes[node.id] = node
        self._storage.save_node(node.id, node.to_dict())
        return node

    def get(self, node_id: str) -> Optional[Node]:
        return self._nodes.get(node_id)

    def update(self, node: Node) -> Node:
        self._nodes[node.id] = node
        self._storage.save_node(node.id, node.to_dict())
        return node

    def delete(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        del self._nodes[node_id]
        self._storage.delete_node(node_id)
        return True

    def list(self) -> list[Node]:
        return list(self._nodes.values())

    def exists(self, node_id: str) -> bool:
        return node_id in self._nodes


class RelationshipRepository:
    """CRUD storage management for Relationships."""

    def __init__(self, storage: JsonFileStorage) -> None:
        self._storage = storage
        self._relationships: dict[str, Relationship] = {}
        self.load()

    def load(self) -> None:
        self._relationships = {
            data["id"]: Relationship.from_dict(data)
            for data in self._storage.load_relationships()
        }

    def create(self, relationship: Relationship) -> Relationship:
        self._relationships[relationship.id] = relationship
        self._storage.save_relationship(relationship.id, relationship.to_dict())
        return relationship

    def get(self, relationship_id: str) -> Optional[Relationship]:
        return self._relationships.get(relationship_id)

    def update(self, relationship: Relationship) -> Relationship:
        self._relationships[relationship.id] = relationship
        self._storage.save_relationship(relationship.id, relationship.to_dict())
        return relationship

    def delete(self, relationship_id: str) -> bool:
        if relationship_id not in self._relationships:
            return False
        del self._relationships[relationship_id]
        self._storage.delete_relationship(relationship_id)
        return True

    def list(self) -> list[Relationship]:
        return list(self._relationships.values())

    def exists(self, relationship_id: str) -> bool:
        return relationship_id in self._relationships
