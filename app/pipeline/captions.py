"""Turn a clip's words into a burned-in ASS subtitle file.

Captions are short (1-3 words per line), timed to speech, and bottom-centered.
Emojis are stripped on purpose — this tool keeps captions text-only.

Lines are a first-class, editable unit: the first render generates them from the
transcript (`lines_from_words`), they are persisted per clip, and the Phase-2
editor edits them and re-renders via `ass_from_lines`. Both paths share the same
ASS builder so an edited clip looks identical to a freshly generated one.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from ..config import CAPTION_PRESETS, DEFAULT_CAPTION_PRESET
from ..models import Word

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF\U00002B00-\U00002BFF️‍]"
)

WORDS_PER_LINE = 3
MIN_LINE_SEC = 0.35
MAX_LINE_SEC = 1.6


@dataclass(frozen=True)
class CaptionStyle:
    font: str = "Arial"
    size_ratio: float = 0.058          # fraction of frame height
    primary: str = "&H00FFFFFF"        # white  (ASS is &HAABBGGRR)
    outline: str = "&H00000000"        # black
    bottom_margin_ratio: float = 0.16  # fraction of height from the edge
    position: str = "bottom"           # bottom | middle | top
    animation: str = "pop"             # pop | fade | none


_ALIGN = {"bottom": 2, "middle": 5, "top": 8}  # ASS numpad alignment


def _anim_prefix(animation: str) -> str:
    """Inline ASS override tag that animates each caption line's appearance."""
    if animation == "fade":
        return r"{\fad(120,80)}"
    if animation == "pop":
        return r"{\fscx70\fscy70\t(0,110,\fscx100\fscy100)}"
    return ""


def caption_style_from_preset(name: str | None) -> CaptionStyle:
    """Resolve a preset name (from config) into a concrete CaptionStyle."""
    preset = CAPTION_PRESETS.get(name or DEFAULT_CAPTION_PRESET) or CAPTION_PRESETS[DEFAULT_CAPTION_PRESET]
    return CaptionStyle(
        font=preset["font"],
        size_ratio=preset["size_ratio"],
        primary=preset["primary"],
        outline=preset["outline"],
        position=preset.get("position", "bottom"),
        animation=preset.get("animation", "pop"),
    )


@dataclass(frozen=True)
class CaptionLine:
    """One on-screen caption line, timed relative to the clip start (seconds)."""

    text: str
    start: float
    end: float


def strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()


def _fmt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:d}:{minutes:02d}:{secs:05.2f}"


def lines_from_words(words: tuple[Word, ...], clip_start: float) -> list[CaptionLine]:
    """Group words into timed caption lines relative to the clip start."""
    lines: list[CaptionLine] = []
    group: list[Word] = []

    def flush() -> None:
        if not group:
            return
        text = strip_emoji(" ".join(w.text for w in group)).upper()
        if text:
            start = max(0.0, group[0].start - clip_start)
            end = max(group[-1].end - clip_start, start + MIN_LINE_SEC)
            lines.append(CaptionLine(text=text, start=round(start, 3), end=round(end, 3)))
        group.clear()

    for word in words:
        group.append(word)
        span = group[-1].end - group[0].start
        if len(group) >= WORDS_PER_LINE or span >= MAX_LINE_SEC:
            flush()
    flush()
    return lines


def validate_lines(raw: list[dict]) -> list[CaptionLine]:
    """Coerce edited caption dicts into clean, ordered CaptionLines.

    Empty/emoji-only lines are dropped; negative or inverted times are repaired.
    """
    cleaned: list[CaptionLine] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        text = strip_emoji(str(item.get("text", ""))).strip()
        if not text:
            continue
        try:
            start = max(0.0, float(item.get("start", 0.0)))
            end = float(item.get("end", start + MIN_LINE_SEC))
        except (TypeError, ValueError):
            continue
        if end <= start:
            end = start + MIN_LINE_SEC
        cleaned.append(CaptionLine(text=text, start=round(start, 3), end=round(end, 3)))
    cleaned.sort(key=lambda ln: ln.start)
    return cleaned


def lines_to_json(lines: list[CaptionLine]) -> list[dict]:
    return [asdict(ln) for ln in lines]


def lines_from_json(raw: list[dict]) -> list[CaptionLine]:
    """Rebuild CaptionLines from stored/edited JSON (alias of validate_lines)."""
    return validate_lines(raw)


def ass_from_lines(
    lines: list[CaptionLine], width: int, height: int, style: CaptionStyle | None = None
) -> str:
    """Render a complete ASS subtitle document from explicit caption lines."""
    style = style or CaptionStyle()
    font_size = int(height * style.size_ratio)
    align = _ALIGN.get(style.position, 2)
    margin_v = 0 if style.position == "middle" else int(height * style.bottom_margin_ratio)
    outline_w = max(2, font_size // 16)
    prefix = _anim_prefix(style.animation)

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\n"
        "WrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
        "BackColour, Bold, Alignment, Outline, Shadow, MarginL, MarginR, MarginV\n"
        f"Style: Cap,{style.font},{font_size},{style.primary},{style.outline},"
        f"&H80000000,-1,{align},{outline_w},1,60,60,{margin_v}\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    events = []
    for line in lines:
        text = strip_emoji(line.text).upper().replace("\n", " ")
        if not text:
            continue
        events.append(
            f"Dialogue: 0,{_fmt_time(line.start)},{_fmt_time(line.end)},Cap,,0,0,0,,{prefix}{text}"
        )
    return header + "\n".join(events) + "\n"


def build_ass(
    words: tuple[Word, ...],
    clip_start: float,
    width: int,
    height: int,
    style: CaptionStyle | None = None,
) -> str:
    """Convenience: generate lines from words and render them to ASS."""
    return ass_from_lines(lines_from_words(words, clip_start), width, height, style)
