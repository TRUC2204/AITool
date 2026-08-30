"""Minimal, text-based Knowledge Graph storage foundation (RQ-01).

Public entry point is :class:`KnowledgeGraph`.
"""

from __future__ import annotations

from .graph import KnowledgeGraph
from .integrity import IntegrityError
from .models import Node, Relationship
from .traversal import ConnectedNode

__all__ = [
    "KnowledgeGraph",
    "Node",
    "Relationship",
    "ConnectedNode",
    "IntegrityError",
]
