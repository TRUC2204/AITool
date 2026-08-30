"""Token Control (RQ-04): input estimation, budget, context truncation,
output control and a usage monitor.

Token counts before a call are heuristic estimates (~4 chars/token). Actual
input/output/total usage comes from the provider's ``usageMetadata``.
"""

from __future__ import annotations

from dataclasses import dataclass

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Rough token estimate used for pre-flight budgeting."""
    if not text:
        return 0
    return max(1, (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN)


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class UsageMonitor:
    """Accumulates token usage across an agent run."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, usage: TokenUsage) -> None:
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens

    def snapshot(self) -> TokenUsage:
        return TokenUsage(self.input_tokens, self.output_tokens)


class InputTokenControl:
    """Estimates input size and truncates context to fit the input budget."""

    def __init__(self, max_input_tokens: int) -> None:
        self.max_input_tokens = max_input_tokens

    def exceeds_budget(self, text: str) -> bool:
        return estimate_tokens(text) > self.max_input_tokens

    def truncate_to_budget(self, text: str) -> str:
        """Trim from the front (oldest context) so the newest content is kept."""
        if not self.exceeds_budget(text):
            return text
        max_chars = self.max_input_tokens * _CHARS_PER_TOKEN
        return text[-max_chars:]

    def truncate_segments(self, segments: list[str]) -> tuple[list[str], bool]:
        """Keep the most recent segments that fit the budget.

        Returns the kept segments and whether any were dropped.
        """
        kept: list[str] = []
        used = 0
        trimmed = False
        for segment in reversed(segments):
            cost = estimate_tokens(segment)
            if used + cost > self.max_input_tokens:
                trimmed = True
                break
            kept.append(segment)
            used += cost
        kept.reverse()
        return kept, trimmed


class OutputTokenControl:
    """Caps response length via MaxOutputTokens."""

    def __init__(self, max_output_tokens: int) -> None:
        self.max_output_tokens = max_output_tokens

    def clamp(self, requested: int | None) -> int:
        if requested is None:
            return self.max_output_tokens
        return min(requested, self.max_output_tokens)
