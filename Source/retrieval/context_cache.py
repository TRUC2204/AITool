"""Context cache (Epic 2 - Context Cache).

An in-session LRU cache for retrieval results so the same search or node load is
not repeated while the underlying data is unchanged. A monotonic revision is
bumped whenever the graph is mutated (commit/undo), which invalidates every
stale entry automatically. Hit/miss counts are tracked for observability.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    invalidations: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class ContextCache:
    def __init__(self, max_entries: int = 128) -> None:
        self._max = max_entries
        self._revision = 0
        self._store: "OrderedDict[str, tuple[int, Any]]" = OrderedDict()
        self.stats = CacheStats()

    @property
    def revision(self) -> int:
        return self._revision

    def bump_revision(self) -> None:
        """Invalidate the whole cache after a data change."""
        self._revision += 1
        self.stats.invalidations += 1

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None or entry[0] != self._revision:
            if entry is not None:
                del self._store[key]  # drop stale entry
            self.stats.misses += 1
            return None
        self._store.move_to_end(key)
        self.stats.hits += 1
        return entry[1]

    def put(self, key: str, value: Any) -> None:
        self._store[key] = (self._revision, value)
        self._store.move_to_end(key)
        while len(self._store) > self._max:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
