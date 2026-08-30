"""Rebuild indexes from storage (RQ-01 item 12).

If an index file is lost, both indexes can be reconstructed by scanning all
Nodes and Relationships, without losing any data.
"""

from __future__ import annotations

from .indexes import NodeTitleIndex, RelationshipIndex
from .repositories import NodeRepository, RelationshipRepository


class RebuildIndexService:
    def __init__(
        self,
        nodes: NodeRepository,
        relationships: RelationshipRepository,
        node_title_index: NodeTitleIndex,
        relationship_index: RelationshipIndex,
    ) -> None:
        self._nodes = nodes
        self._relationships = relationships
        self._node_title_index = node_title_index
        self._relationship_index = relationship_index

    def rebuild_node_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for node in self._nodes.list():
            if node.title:
                index[node.title] = node.id
        self._node_title_index.replace_all(index)
        return index

    def rebuild_relationship_index(self) -> dict[str, set[str]]:
        index: dict[str, set[str]] = {}
        for rel in self._relationships.list():
            index.setdefault(rel.source_node_id, set()).add(rel.id)
            index.setdefault(rel.target_node_id, set()).add(rel.id)
        self._relationship_index.replace_all(index)
        return index
