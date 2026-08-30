"""Data models for the Knowledge Graph storage foundation (RQ-01).

Only two kinds of data exist: Node and Relationship. Every content field is
plain text and no domain schema is enforced.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Node:
    """A single unit of knowledge in the graph."""

    id: str
    title: str = ""
    content: str = ""
    version: int = 1
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Node":
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            content=data.get("content", ""),
            version=int(data.get("version", 1)),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )


@dataclass
class Relationship:
    """A directed connection between two Nodes.

    ``metadata`` is a list of free-text labels, so a single relationship can
    carry several meanings at once (e.g. "vua yeu", "vua han").
    """

    id: str
    source_node_id: str
    target_node_id: str
    metadata: list[str] = field(default_factory=list)
    version: int = 1
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Relationship":
        return cls(
            id=data["id"],
            source_node_id=data["source_node_id"],
            target_node_id=data["target_node_id"],
            metadata=list(data.get("metadata", [])),
            version=int(data.get("version", 1)),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )
