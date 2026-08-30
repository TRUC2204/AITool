"""AI cost tracking & prompt optimization (Epic 2 - Token Optimization).

Estimates the monetary cost of token usage and offers light prompt-shrinking
helpers so requests stay within the token budget (FR-19 Token Efficiency).
Rates are configurable; the defaults are zero so nothing is implied about
pricing until the user sets them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .token_control import TokenUsage


@dataclass
class CostRates:
    """USD per 1,000 tokens. Defaults to 0 (unknown/free tier)."""

    input_per_1k: float = 0.0
    output_per_1k: float = 0.0

    def cost_of(self, usage: TokenUsage) -> float:
        return (
            usage.input_tokens / 1000.0 * self.input_per_1k
            + usage.output_tokens / 1000.0 * self.output_per_1k
        )


class CostTracker:
    """Accumulates token usage and its estimated cost across a session."""

    def __init__(self, rates: CostRates | None = None) -> None:
        self.rates = rates or CostRates()
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_cost = 0.0
        self.calls = 0

    def add(self, usage: TokenUsage) -> float:
        self.calls += 1
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        cost = self.rates.cost_of(usage)
        self.total_cost += cost
        return cost

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def summary(self) -> dict[str, float | int]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 6),
        }


_WS = re.compile(r"[ \t]+")
_BLANK = re.compile(r"\n{3,}")


def optimize_prompt(text: str) -> str:
    """Collapse redundant whitespace/blank lines to save input tokens."""
    if not text:
        return text
    lines = [_WS.sub(" ", line).rstrip() for line in text.splitlines()]
    return _BLANK.sub("\n\n", "\n".join(lines)).strip()
