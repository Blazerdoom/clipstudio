"""Helpers for turning stored absolute media paths into safe served URLs."""
from __future__ import annotations

from pathlib import Path

from .. import config


def to_url(file_path: str | None) -> str | None:
    """Map an absolute path under RUNS_DIR to its /runs/... URL, else None."""
    if not file_path:
        return None
    try:
        rel = Path(file_path).resolve().relative_to(config.RUNS_DIR.resolve())
    except (ValueError, OSError):
        return None
    return "/runs/" + rel.as_posix()


def clip_with_urls(clip: dict) -> dict:
    """Attach browser-facing URLs to a clip record."""
    return {**clip, "url": to_url(clip.get("file_path")), "thumb_url": to_url(clip.get("thumb_path"))}
