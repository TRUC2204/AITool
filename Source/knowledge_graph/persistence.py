"""JSON file storage for a Project (Persistence Layer, RQ-01 item 8).

Project structure on disk::

    Project/
      project.json
      nodes/
        <node-id>.json
      relationships/
        <relationship-id>.json
      indexes/
        node-title-index.json
        relationship-index.json

Each Project is an isolated world-building space; data in one Project never
affects another.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any


class JsonFileStorage:
    """Low-level read/write access to a Project directory."""

    def __init__(self, project_path: str) -> None:
        self.project_path = project_path
        self.nodes_dir = os.path.join(project_path, "nodes")
        self.relationships_dir = os.path.join(project_path, "relationships")
        self.indexes_dir = os.path.join(project_path, "indexes")
        self.project_file = os.path.join(project_path, "project.json")
        self.node_title_index_file = os.path.join(
            self.indexes_dir, "node-title-index.json"
        )
        self.relationship_index_file = os.path.join(
            self.indexes_dir, "relationship-index.json"
        )
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        for path in (self.nodes_dir, self.relationships_dir, self.indexes_dir):
            os.makedirs(path, exist_ok=True)

    # -- generic helpers ---------------------------------------------------
    @staticmethod
    def _read_json(path: str, default: Any) -> Any:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _write_json(path: str, data: Any) -> None:
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        # Atomic replace, retried because cloud-sync clients (e.g. OneDrive) can
        # briefly lock the destination. Fall back to a direct write if needed.
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt < 4:
                    time.sleep(0.1 * (attempt + 1))
                    continue
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, ensure_ascii=False, indent=2)
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
                return

    # -- project metadata --------------------------------------------------
    def read_project(self, default: dict[str, Any]) -> dict[str, Any]:
        return self._read_json(self.project_file, default)

    def write_project(self, data: dict[str, Any]) -> None:
        self._write_json(self.project_file, data)

    # -- nodes -------------------------------------------------------------
    def _node_path(self, node_id: str) -> str:
        return os.path.join(self.nodes_dir, f"{node_id}.json")

    def save_node(self, node_id: str, data: dict[str, Any]) -> None:
        self._write_json(self._node_path(node_id), data)

    def delete_node(self, node_id: str) -> None:
        path = self._node_path(node_id)
        if os.path.exists(path):
            os.remove(path)

    def load_nodes(self) -> list[dict[str, Any]]:
        return self._load_dir(self.nodes_dir)

    # -- relationships -----------------------------------------------------
    def _relationship_path(self, relationship_id: str) -> str:
        return os.path.join(self.relationships_dir, f"{relationship_id}.json")

    def save_relationship(self, relationship_id: str, data: dict[str, Any]) -> None:
        self._write_json(self._relationship_path(relationship_id), data)

    def delete_relationship(self, relationship_id: str) -> None:
        path = self._relationship_path(relationship_id)
        if os.path.exists(path):
            os.remove(path)

    def load_relationships(self) -> list[dict[str, Any]]:
        return self._load_dir(self.relationships_dir)

    @staticmethod
    def _load_dir(directory: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if not os.path.isdir(directory):
            return items
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(directory, name), "r", encoding="utf-8") as handle:
                items.append(json.load(handle))
        return items

    # -- indexes -----------------------------------------------------------
    def save_node_title_index(self, data: dict[str, str]) -> None:
        self._write_json(self.node_title_index_file, data)

    def load_node_title_index(self) -> dict[str, str]:
        return self._read_json(self.node_title_index_file, {})

    def save_relationship_index(self, data: dict[str, list[str]]) -> None:
        self._write_json(self.relationship_index_file, data)

    def load_relationship_index(self) -> dict[str, list[str]]:
        return self._read_json(self.relationship_index_file, {})
