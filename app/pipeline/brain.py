"""The local "virality brain": rank self-contained moments, no external AI.

Given the transcript segments, it forms candidate windows, scores each on
measurable signals, then greedily picks the top non-overlapping clips. Every
clip carries a 0-100 score, a plain-English reason, a title, a hook and tags.
"""
from __future__ import annotations

import re

from ..config import IDEAL_CLIP_SEC, MAX_CLIP_SEC, MIN_CLIP_SEC
from ..models import ClipCandidate, Segment
from . import wordbanks

_WORD_RE = re.compile(r"[a-z0-9']+")
_NUM_RE = re.compile(r"\b\d+([.,]\d+)?\b")


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def build_candidates(
    segments: tuple[Segment, ...], min_sec: float, max_sec: float
) -> list[tuple[float, float, str]]:
    """Form (start, end, text) windows by merging consecutive segments."""
    windows: list[tuple[float, float, str]] = []
    count = len(segments)
    for i in range(count):
        parts: list[str] = []
        for j in range(i, count):
            parts.append(segments[j].text)
            start, end = segments[i].start, segments[j].end
            span = end - start
            if span < min_sec:
                continue
            if span > max_sec:
                break
            windows.append((start, end, " ".join(parts).strip()))
    return windows


def _length_bonus(duration: float) -> float:
    """Peak reward near IDEAL_CLIP_SEC, tapering toward the min/max bounds."""
    spread = max(IDEAL_CLIP_SEC - MIN_CLIP_SEC, MAX_CLIP_SEC - IDEAL_CLIP_SEC)
    closeness = 1.0 - min(1.0, abs(duration - IDEAL_CLIP_SEC) / spread)
    return round(12.0 * closeness, 2)


def score_window(text: str, duration: float) -> tuple[float, str]:
    """Return a 0-100 score and a human-readable reason for a window."""
    tokens = _tokens(text)
    if not tokens:
        return 0.0, "no speech"

    reasons: list[str] = []
    score = 40.0

    if tokens[0] in wordbanks.HOOK_WORDS or tokens[:1] == ["what"]:
        score += 12
        reasons.append("strong opener")
    if "?" in text:
        score += 9
        reasons.append("asks a question")
    if _NUM_RE.search(text):
        score += 7
        reasons.append("concrete numbers")

    emotion = sum(1 for t in tokens if t in wordbanks.EMOTION_WORDS)
    if emotion:
        score += min(14, emotion * 5)
        reasons.append("emotional punch")

    value = sum(1 for t in tokens if t in wordbanks.VALUE_WORDS)
    if value:
        score += min(8, value * 3)
        reasons.append("delivers a payoff")

    unique_ratio = len(set(tokens)) / len(tokens)
    score += round(8 * unique_ratio, 2)

    length = _length_bonus(duration)
    score += length
    if length > 8:
        reasons.append("ideal length")

    if text.rstrip()[-1:] in ".!?":
        score += 4
        reasons.append("ends cleanly")

    final = max(0.0, min(100.0, round(score, 1)))
    return final, ", ".join(reasons) if reasons else "steady moment"


def make_title(text: str) -> str:
    """Pick the most information-dense sentence, trimmed to a headline."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return "Untitled clip"
    best = max(sentences, key=lambda s: len(set(_tokens(s))))
    title = re.sub(r"\s+", " ", best).strip(" .")
    if len(title) > 64:
        title = title[:61].rstrip() + "..."
    return title[:1].upper() + title[1:]


def make_hook(text: str) -> str:
    """Take the opening clause as the on-screen hook line."""
    first = re.split(r"(?<=[.!?])\s+", text.strip())[0]
    words = first.split()
    hook = " ".join(words[:9]).strip(" ,.")
    return hook[:1].upper() + hook[1:] if hook else ""


def make_tags(text: str, limit: int = 4) -> tuple[str, ...]:
    """Most frequent non-stopword tokens as content tags."""
    counts: dict[str, int] = {}
    for token in _tokens(text):
        if token in wordbanks.STOPWORDS or len(token) < 3:
            continue
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts, key=lambda t: (-counts[t], t))
    return tuple(ranked[:limit])


def _overlaps(a: tuple[float, float], picked: list[ClipCandidate]) -> bool:
    for clip in picked:
        if a[0] < clip.end and clip.start < a[1]:
            return True
    return False


def select_clips(
    segments: tuple[Segment, ...],
    max_clips: int,
    min_sec: float = MIN_CLIP_SEC,
    max_sec: float = MAX_CLIP_SEC,
) -> list[ClipCandidate]:
    """Score every window and greedily pick the top non-overlapping clips."""
    windows = build_candidates(segments, min_sec, max_sec)
    scored: list[ClipCandidate] = []
    for start, end, text in windows:
        score, reason = score_window(text, end - start)
        scored.append(
            ClipCandidate(
                start=round(start, 3),
                end=round(end, 3),
                score=score,
                title=make_title(text),
                hook=make_hook(text),
                reason=reason,
                tags=make_tags(text),
                text=text,
            )
        )

    scored.sort(key=lambda c: c.score, reverse=True)
    picked: list[ClipCandidate] = []
    for candidate in scored:
        if len(picked) >= max_clips:
            break
        if not _overlaps((candidate.start, candidate.end), picked):
            picked.append(candidate)

    picked.sort(key=lambda c: c.start)
    return picked
