"""Indexes for fast lookup (RQ-01 items 5 & 6).

* :class:`NodeTitleIndex` maps a title to a Node id so we never scan all Nodes.
* :class:`RelationshipIndex` maps a Node id to the Relationship ids that touch
  it, so traceability does not require a full database scan.
"""

from __future__ import annotations

from typing import Optional

from .persistence import JsonFileStorage


class NodeTitleIndex:
    """title -> node_id lookup."""

    def __init__(self, storage: JsonFileStorage) -> None:
        self._storage = storage
        self._index: dict[str, str] = storage.load_node_title_index()

    def add(self, title: str, node_id: str) -> None:
        self._index[title] = node_id
        self._persist()

    def remove(self, title: str) -> None:
        if title in self._index:
            del self._index[title]
            self._persist()

    def find_node_by_title(self, title: str) -> Optional[str]:
        return self._index.get(title)

    def replace_all(self, index: dict[str, str]) -> None:
        self._index = dict(index)
        self._persist()

    def as_dict(self) -> dict[str, str]:
        return dict(self._index)

    def _persist(self) -> None:
        self._storage.save_node_title_index(self._index)


class RelationshipIndex:
    """node_id -> [relationship_id, ...] lookup."""

    def __init__(self, storage: JsonFileStorage) -> None:
        self._storage = storage
        raw = storage.load_relationship_index()
        self._index: dict[str, set[str]] = {k: set(v) for k, v in raw.items()}

    def add(self, node_id: str, relationship_id: str) -> None:
        self._index.setdefault(node_id, set()).add(relationship_id)
        self._persist()

    def remove(self, node_id: str, relationship_id: str) -> None:
        bucket = self._index.get(node_id)
        if not bucket:
            return
        bucket.discard(relationship_id)
        if not bucket:
            del self._index[node_id]
        self._persist()

    def get_relationships_of_node(self, node_id: str) -> list[str]:
        return sorted(self._index.get(node_id, set()))

    def replace_all(self, index: dict[str, set[str]]) -> None:
        self._index = {k: set(v) for k, v in index.items()}
        self._persist()

    def _persist(self) -> None:
        self._storage.save_relationship_index(
            {k: sorted(v) for k, v in self._index.items()}
        )
