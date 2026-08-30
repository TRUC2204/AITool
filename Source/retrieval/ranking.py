"""Context ranking & de-duplication (Epic 2 - Context Optimization).

Ranks search candidates by relevance to the query and removes duplicate or
redundant material so the assistant sends the smallest useful context to the
model (supports FR-06 Context Minimization and FR-19 Token Efficiency).
"""

from __future__ import annotations

from retrieval.search import NodeCandidate


def score_candidate(candidate: NodeCandidate, query: str) -> float:
    """Higher is more relevant. Title matches beat content/metadata matches."""
    q = query.strip().lower()
    if not q:
        return 0.0
    title = candidate.title.lower()
    snippet = candidate.snippet.lower()
    score = 0.0
    if title == q:
        score += 100.0
    elif title.startswith(q):
        score += 60.0
    elif q in title:
        score += 40.0
    if q in snippet:
        score += 10.0
    if candidate.matched_on.startswith("title"):
        score += 5.0
    # Shorter titles that still match are usually the more specific hit.
    score += max(0.0, 5.0 - len(title) / 20.0)
    return score


def dedupe_candidates(candidates: list[NodeCandidate]) -> list[NodeCandidate]:
    seen: set[str] = set()
    unique: list[NodeCandidate] = []
    for candidate in candidates:
        if candidate.id in seen:
            continue
        seen.add(candidate.id)
        unique.append(candidate)
    return unique


def rank_candidates(
    candidates: list[NodeCandidate], query: str, limit: int | None = None
) -> list[NodeCandidate]:
    unique = dedupe_candidates(candidates)
    ranked = sorted(unique, key=lambda c: score_candidate(c, query), reverse=True)
    return ranked[:limit] if limit else ranked


def dedupe_context(parts: list[str]) -> list[str]:
    """Drop empty and exactly-repeated context blocks, preserving order."""
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        key = part.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(part)
    return unique
