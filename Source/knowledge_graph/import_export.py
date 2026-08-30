"""Import / Export for backups (RQ-01 item 11).

Exports the whole graph to plain lists of dicts (easy to dump as JSON) and
imports them back, restoring Nodes and Relationships.
"""

from __future__ import annotations

from typing import Any

from .models import Node, Relationship
from .repositories import NodeRepository, RelationshipRepository


class ImportExportService:
    def __init__(
        self, nodes: NodeRepository, relationships: RelationshipRepository
    ) -> None:
        self._nodes = nodes
        self._relationships = relationships

    def export_nodes(self) -> list[dict[str, Any]]:
        return [node.to_dict() for node in self._nodes.list()]

    def export_relationships(self) -> list[dict[str, Any]]:
        return [rel.to_dict() for rel in self._relationships.list()]

    def import_nodes(self, data: list[dict[str, Any]]) -> int:
        count = 0
        for item in data:
            self._nodes.create(Node.from_dict(item))
            count += 1
        return count

    def import_relationships(self, data: list[dict[str, Any]]) -> int:
        count = 0
        for item in data:
            self._relationships.create(Relationship.from_dict(item))
            count += 1
        return count
