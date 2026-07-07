"""Speech-to-text via faster-whisper, with word-level timestamps.

Device resolution:
  - "auto": try CUDA (GPU) first, fall back to CPU on any load error.
  - "cuda"/"cpu": use exactly what was asked.
The model is created lazily so importing this module never loads CUDA libs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..models import Segment, Word

ProgressFn = Callable[[float], None]


def _compute_type(device: str) -> str:
    return "float16" if device == "cuda" else "int8"


def _load_model(model_size: str, device: str):
    from faster_whisper import WhisperModel  # imported lazily

    if device == "auto":
        try:
            return WhisperModel(model_size, device="cuda", compute_type="float16"), "cuda"
        except Exception:  # noqa: BLE001 — any CUDA/driver issue -> CPU fallback
            return WhisperModel(model_size, device="cpu", compute_type="int8"), "cpu"
    return WhisperModel(model_size, device=device, compute_type=_compute_type(device)), device


def transcribe(
    video: Path,
    device: str,
    model_size: str,
    duration: float = 0.0,
    on_progress: ProgressFn | None = None,
) -> tuple[Segment, ...]:
    """Transcribe *video* into immutable Segments carrying their Words."""
    model, _resolved = _load_model(model_size, device)
    raw_segments, _info = model.transcribe(
        str(video),
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
    )

    segments: list[Segment] = []
    for seg in raw_segments:
        words = tuple(
            Word(text=w.word.strip(), start=float(w.start), end=float(w.end))
            for w in (seg.words or [])
            if w.word and w.word.strip()
        )
        segments.append(
            Segment(text=seg.text.strip(), start=float(seg.start), end=float(seg.end), words=words)
        )
        if on_progress and duration > 0:
            on_progress(min(1.0, seg.end / duration))

    return tuple(segments)
