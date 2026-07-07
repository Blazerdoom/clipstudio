"""Immutable value objects passed through the pipeline.

Everything here is frozen — pipeline stages return *new* objects rather than
mutating inputs, which keeps the data flow easy to reason about and test.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Word:
    """A single transcribed word with absolute timestamps (seconds)."""

    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Segment:
    """A transcript segment (roughly a sentence) with its words."""

    text: str
    start: float
    end: float
    words: tuple[Word, ...]


@dataclass(frozen=True)
class ClipCandidate:
    """A scored, self-contained moment selected as a potential clip."""

    start: float
    end: float
    score: float
    title: str
    hook: str
    reason: str
    tags: tuple[str, ...]
    text: str

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)


def words_in_range(segments: tuple[Segment, ...], start: float, end: float) -> tuple[Word, ...]:
    """Collect every word whose midpoint falls inside [start, end]."""
    collected: list[Word] = []
    for segment in segments:
        for word in segment.words:
            mid = (word.start + word.end) / 2.0
            if start <= mid <= end:
                collected.append(word)
    return tuple(collected)
