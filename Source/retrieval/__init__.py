"""Knowledge Retrieval: data discovery, controlled node access, cache & ranking.

RQ-03 (Phase 0) plus Phase-1 Epic 2 context cache and context ranking.
"""

from __future__ import annotations

from .context_cache import CacheStats, ContextCache
from .ranking import (
    dedupe_candidates,
    dedupe_context,
    rank_candidates,
    score_candidate,
)
from .retrieval_service import (
    KnowledgeRetrievalService,
    RelatedNode,
    RetrievalLimits,
    TraversalResult,
)
from .search import NodeCandidate, SearchService

__all__ = [
    "SearchService",
    "NodeCandidate",
    "KnowledgeRetrievalService",
    "RetrievalLimits",
    "RelatedNode",
    "TraversalResult",
    "ContextCache",
    "CacheStats",
    "rank_candidates",
    "score_candidate",
    "dedupe_candidates",
    "dedupe_context",
]
