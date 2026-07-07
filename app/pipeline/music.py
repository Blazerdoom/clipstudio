"""Background-music track discovery.

Users drop audio files into the top-level `music/` folder (next to run.bat);
they then appear in the create form's music picker. `export` loops the chosen
track quietly under the clip's audio.
"""
from __future__ import annotations

from pathlib import Path

from .. import config

MUSIC_DIR = config.ROOT / "music"
_SUFFIXES = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}


def list_tracks() -> list[dict]:
    """Return [{name, label}] for every audio file in the music folder."""
    if not MUSIC_DIR.exists():
        return []
    tracks = [
        {"name": p.name, "label": p.stem}
        for p in sorted(MUSIC_DIR.iterdir())
        if p.is_file() and p.suffix.lower() in _SUFFIXES
    ]
    return tracks


def resolve(name: str | None) -> Path | None:
    """Map a chosen track name to a path inside the music folder (or None)."""
    if not name:
        return None
    candidate = (MUSIC_DIR / name).resolve()
    # Never escape the music folder.
    if MUSIC_DIR.resolve() not in candidate.parents or not candidate.exists():
        return None
    return candidate


def is_valid(name: str | None) -> bool:
    return not name or resolve(name) is not None
