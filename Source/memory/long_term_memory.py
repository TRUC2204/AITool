"""Long-term memory (Epic 3 - Long-Term Memory + FR-22/23 consistency).

The Knowledge Graph is the long-term store. This module is the single access
layer for retrieving and validating it: natural-language-ish retrieval through
the search service, plus consistency and conflict checks that run before a
proposal is committed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from knowledge_graph import KnowledgeGraph
from retrieval import NodeCandidate, SearchService

from changes import ChangeType, Proposal


@dataclass
class ConsistencyIssue:
    severity: str  # "error" | "warning"
    code: str
    message: str
    refs: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.message}"


class ConsistencyChecker:
    """Structural consistency & conflict detection over the graph (FR-22/23)."""

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def find_duplicate_titles(self) -> list[list[str]]:
        buckets: dict[str, list[str]] = {}
        for node in self._graph.list_nodes():
            key = node.title.strip().lower()
            if key:
                buckets.setdefault(key, []).append(node.id)
        return [ids for ids in buckets.values() if len(ids) > 1]

    def find_dangling_relationships(self) -> list[str]:
        dangling: list[str] = []
        for rel in self._graph.list_relationships():
            if (
                self._graph.get_node(rel.source_node_id) is None
                or self._graph.get_node(rel.target_node_id) is None
            ):
                dangling.append(rel.id)
        return dangling

    def check_new_node(self, title: str, content: str = "") -> list[ConsistencyIssue]:
        issues: list[ConsistencyIssue] = []
        clean = title.strip()
        if not clean:
            issues.append(ConsistencyIssue("error", "empty_title", "Node title is empty"))
            return issues
        key = clean.lower()
        for node in self._graph.list_nodes():
            existing = node.title.strip().lower()
            if existing == key:
                issues.append(
                    ConsistencyIssue(
                        "warning",
                        "duplicate_title",
                        f"A node titled '{node.title}' already exists ({node.id})",
                        refs=[node.id],
                    )
                )
            elif existing and (existing in key or key in existing):
                issues.append(
                    ConsistencyIssue(
                        "warning",
                        "similar_title",
                        f"Similar to existing node '{node.title}' ({node.id})",
                        refs=[node.id],
                    )
                )
        return issues

    def check_proposal(self, proposal: Proposal) -> list[ConsistencyIssue]:
        """Validate a proposal against the current graph before commit."""
        issues: list[ConsistencyIssue] = []
        for change in proposal.changes:
            kind = change.change_type
            if kind == ChangeType.CREATE_NODE:
                issues.extend(self.check_new_node(change.title or "", change.content or ""))
            elif kind in (ChangeType.UPDATE_NODE, ChangeType.DELETE_NODE):
                if self._graph.get_node(str(change.target_id)) is None:
                    issues.append(
                        ConsistencyIssue(
                            "error",
                            "missing_node",
                            f"Target node {change.target_id} does not exist",
                            refs=[str(change.target_id)],
                        )
                    )
            elif kind in (ChangeType.UPDATE_RELATIONSHIP, ChangeType.DELETE_RELATIONSHIP):
                if self._graph.get_relationship(str(change.target_id)) is None:
                    issues.append(
                        ConsistencyIssue(
                            "error",
                            "missing_relationship",
                            f"Target relationship {change.target_id} does not exist",
                            refs=[str(change.target_id)],
                        )
                    )
            elif kind == ChangeType.CREATE_RELATIONSHIP:
                for ref in (change.source_ref, change.target_ref):
                    if ref and not ref.startswith("@") and self._graph.get_node(ref) is None:
                        issues.append(
                            ConsistencyIssue(
                                "error",
                                "missing_endpoint",
                                f"Relationship endpoint {ref} does not exist",
                                refs=[ref],
                            )
                        )
        return issues

    @staticmethod
    def has_blocking_errors(issues: list[ConsistencyIssue]) -> bool:
        return any(issue.severity == "error" for issue in issues)


class LongTermMemory:
    """Single access layer to the graph as long-term memory."""

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph
        self._search = SearchService(graph)
        self.consistency = ConsistencyChecker(graph)

    def retrieve(self, query: str, by: str = "keyword") -> list[NodeCandidate]:
        if by == "title":
            return self._search.search_by_title(query)
        if by == "metadata":
            return self._search.search_by_metadata(query)
        return self._search.search_by_keyword(query)

    def get(self, node_id: str):
        return self._graph.get_node(node_id)

    def validate_new_node(self, title: str, content: str = "") -> list[ConsistencyIssue]:
        return self.consistency.check_new_node(title, content)

    def validate_proposal(self, proposal: Proposal) -> list[ConsistencyIssue]:
        return self.consistency.check_proposal(proposal)
