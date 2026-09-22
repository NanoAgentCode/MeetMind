"""Estimate prompt size and select older turns for conversation compaction."""

from math import ceil

from .models import ChatTurn


def estimate_tokens(text: str) -> int:
    """Conservative cross-provider estimate: non-ASCII chars count as one token."""
    return ceil(sum(1 if ord(char) > 127 else 0.25 for char in text))


def prompt_tokens(instruction: str, question: str, history: list[ChatTurn], summary: str) -> int:
    parts = [instruction, question, summary, *(turn.content for turn in history)]
    return estimate_tokens("\n".join(parts)) + len(history) * 8 + 32


def plan_compaction(instruction: str, question: str, history: list[ChatTurn], summary: str,
                    context_window_tokens: int) -> int:
    """Return the number of oldest turns to summarize at the 80% threshold."""
    if prompt_tokens(instruction, question, history, summary) < int(context_window_tokens * 0.8):
        return 0
    return min(len(history), max(2, len(history) - 4)) if history else 0


def truncate_to_tokens(text: str, limit: int) -> str:
    used = 0.0
    for index, char in enumerate(text):
        used += 1 if ord(char) > 127 else 0.25
        if ceil(used) > limit:
            return text[:index]
    return text
