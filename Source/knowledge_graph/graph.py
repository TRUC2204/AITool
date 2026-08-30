"""KnowledgeGraph facade: the public API for RQ-01 Data Storage Foundation.

Wires together the repositories, indexes, validation, traversal, versioning,
import/export and rebuild services around a single Project (JSON file storage).
Versioning (item 9): every update bumps the ``version`` field; only the current
version is tracked.
"""

from __future__ import annotations

from typing import Any, Optional

from .import_export import ImportExportService
from .indexes import NodeTitleIndex, RelationshipIndex
from .integrity import IntegrityValidator
from .models import Node, Relationship, utc_now
from .persistence import JsonFileStorage
from .rebuild_index import RebuildIndexService
from .repositories import NodeRepository, RelationshipRepository
from .traversal import ConnectedNode, Direction, GraphTraversalService


class KnowledgeGraph:
    """A minimal, text-based Knowledge Graph stored in a Project directory."""

    def __init__(self, project_path: str, name: Optional[str] = None) -> None:
        self.storage = JsonFileStorage(project_path)
        self._meta = self.storage.read_project(
            {
                "name": name or "Untitled Project",
                "node_counter": 0,
                "relationship_counter": 0,
                "created_at": utc_now(),
            }
        )
        if name is not None:
            self._meta["name"] = name
        self.storage.write_project(self._meta)

        self.nodes = NodeRepository(self.storage)
        self.relationships = RelationshipRepository(self.storage)
        self.node_index = NodeTitleIndex(self.storage)
        self.relationship_index = RelationshipIndex(self.storage)
        self.integrity = IntegrityValidator(self.nodes, self.relationships)
        self.traversal = GraphTraversalService(
            self.nodes, self.relationships, self.relationship_index
        )
        self.import_export = ImportExportService(self.nodes, self.relationships)
        self.rebuild = RebuildIndexService(
            self.nodes, self.relationships, self.node_index, self.relationship_index
        )

    # -- id generation -----------------------------------------------------
    def _next_node_id(self) -> str:
        self._meta["node_counter"] += 1
        self.storage.write_project(self._meta)
        return f"N{self._meta['node_counter']:03d}"

    def _next_relationship_id(self) -> str:
        self._meta["relationship_counter"] += 1
        self.storage.write_project(self._meta)
        return f"R{self._meta['relationship_counter']:03d}"

    # -- Node CRUD ---------------------------------------------------------
    def create_node(
        self, title: str = "", content: str = "", node_id: Optional[str] = None
    ) -> Node:
        node_id = node_id or self._next_node_id()
        self.integrity.ensure_unique_node_id(node_id)
        node = Node(id=node_id, title=title, content=content)
        self.nodes.create(node)
        if title:
            self.node_index.add(title, node.id)
        return node

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def update_node(
        self,
        node_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
    ) -> Optional[Node]:
        node = self.nodes.get(node_id)
        if node is None:
            return None
        if title is not None and title != node.title:
            self.node_index.remove(node.title)
            node.title = title
            self.node_index.add(title, node.id)
        if content is not None:
            node.content = content
        node.version += 1
        node.updated_at = utc_now()
        return self.nodes.update(node)

    def delete_node(self, node_id: str) -> bool:
        node = self.nodes.get(node_id)
        if node is None:
            return False
        # Remove relationships attached to this node to keep the graph valid.
        for rel_id in self.relationship_index.get_relationships_of_node(node_id):
            self.delete_relationship(rel_id)
        if node.title:
            self.node_index.remove(node.title)
        return self.nodes.delete(node_id)

    def list_nodes(self) -> list[Node]:
        return self.nodes.list()

    def find_node_by_title(self, title: str) -> Optional[Node]:
        node_id = self.node_index.find_node_by_title(title)
        return self.nodes.get(node_id) if node_id else None

    # -- Relationship CRUD -------------------------------------------------
    def create_relationship(
        self,
        source_node_id: str,
        target_node_id: str,
        metadata: Optional[list[str]] = None,
        relationship_id: Optional[str] = None,
    ) -> Relationship:
        relationship_id = relationship_id or self._next_relationship_id()
        self.integrity.ensure_unique_relationship_id(relationship_id)
        self.integrity.ensure_endpoints_exist(source_node_id, target_node_id)
        relationship = Relationship(
            id=relationship_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            metadata=list(metadata or []),
        )
        self.relationships.create(relationship)
        self.relationship_index.add(source_node_id, relationship.id)
        self.relationship_index.add(target_node_id, relationship.id)
        return relationship

    def get_relationship(self, relationship_id: str) -> Optional[Relationship]:
        return self.relationships.get(relationship_id)

    def update_relationship(
        self, relationship_id: str, metadata: Optional[list[str]] = None
    ) -> Optional[Relationship]:
        relationship = self.relationships.get(relationship_id)
        if relationship is None:
            return None
        if metadata is not None:
            relationship.metadata = list(metadata)
        relationship.version += 1
        relationship.updated_at = utc_now()
        return self.relationships.update(relationship)

    def delete_relationship(self, relationship_id: str) -> bool:
        relationship = self.relationships.get(relationship_id)
        if relationship is None:
            return False
        self.relationship_index.remove(relationship.source_node_id, relationship_id)
        self.relationship_index.remove(relationship.target_node_id, relationship_id)
        return self.relationships.delete(relationship_id)

    def list_relationships(self) -> list[Relationship]:
        return self.relationships.list()

    # -- Graph -------------------------------------------------------------
    def get_relationships_of_node(self, node_id: str) -> list[Relationship]:
        return [
            rel
            for rel_id in self.relationship_index.get_relationships_of_node(node_id)
            if (rel := self.relationships.get(rel_id)) is not None
        ]

    def get_connected_nodes(
        self, node_id: str, direction: Direction = "both"
    ) -> list[ConnectedNode]:
        return self.traversal.get_connected_nodes(node_id, direction)

    # -- Import / Export ---------------------------------------------------
    def export_nodes(self) -> list[dict[str, Any]]:
        return self.import_export.export_nodes()

    def export_relationships(self) -> list[dict[str, Any]]:
        return self.import_export.export_relationships()

    def import_nodes(self, data: list[dict[str, Any]]) -> int:
        count = self.import_export.import_nodes(data)
        self.rebuild_node_index()
        return count

    def import_relationships(self, data: list[dict[str, Any]]) -> int:
        count = self.import_export.import_relationships(data)
        self.rebuild_relationship_index()
        return count

    # -- Rebuild indexes ---------------------------------------------------
    def rebuild_node_index(self) -> dict[str, str]:
        return self.rebuild.rebuild_node_index()

    def rebuild_relationship_index(self) -> dict[str, set[str]]:
        return self.rebuild.rebuild_relationship_index()
