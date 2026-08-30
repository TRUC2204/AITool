"""Context Assembly (RQ-05): build AI-readable context from Nodes and
Relationships and merge them into a single text block."""

from __future__ import annotations

from knowledge_graph.models import Node, Relationship


def build_node_context(node: Node) -> str:
    return (
        f"[Node {node.id}] {node.title}\n"
        f"{node.content}\n"
        f"(version {node.version})"
    )


def build_relationship_context(relationship: Relationship, linked: Node | None) -> str:
    meta = ", ".join(relationship.metadata) if relationship.metadata else "(no metadata)"
    target = f"{linked.id} {linked.title}" if linked else relationship.target_node_id
    return (
        f"[Relationship {relationship.id}] "
        f"{relationship.source_node_id} -> {target} :: {meta}"
    )


def merge_context(parts: list[str]) -> str:
    return "\n\n".join(part for part in parts if part.strip())
