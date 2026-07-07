"""Source acquisition: download a URL with yt-dlp, or use a local file.

For long videos, only the first `max_minutes` are downloaded (yt-dlp
`--download-sections`), so a 4-hour stream becomes a short job instead of a
20 GB one. Download progress is streamed back via `on_progress`.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .ffmpeg_tools import probe_duration

ProgressFn = Callable[[float], None]

_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
_PCT_RE = re.compile(r"\[download\]\s+([0-9.]+)%")
# Prefer <=720p mp4 for fast, reasonably-sized downloads.
_FORMAT = "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b[ext=mp4]/b"


def is_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


def fetch(source: str, out_dir: Path, max_minutes: int | None = None,
          on_progress: ProgressFn | None = None) -> tuple[Path, str, float]:
    """Resolve *source* to a local video file.

    Returns (video_path, title, duration_seconds). For URLs, only the first
    *max_minutes* are downloaded when given.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if is_url(source):
        video = _download(source, out_dir, max_minutes, on_progress)
    else:
        video = _local(source)
    return video, video.stem, probe_duration(video)


def _local(source: str) -> Path:
    path = Path(source).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Local file not found: {source}")
    if path.suffix.lower() not in _VIDEO_SUFFIXES:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    return path


def _download(url: str, out_dir: Path, max_minutes: int | None,
              on_progress: ProgressFn | None) -> Path:
    """Download the first <=max_minutes at <=720p, streaming progress."""
    template = str(out_dir / "%(id)s.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", _FORMAT,
        "--merge-output-format", "mp4",
        "--no-playlist", "--newline",
        "-o", template,
        "--print", "after_move:filepath",
    ]
    if max_minutes and max_minutes > 0:
        cmd += ["--download-sections", f"*0-{int(max_minutes) * 60}"]
    cmd.append(url)

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)
    filepath: str | None = None
    tail: list[str] = []
    for line in proc.stdout or []:
        match = _PCT_RE.search(line)
        if match and on_progress:
            try:
                on_progress(min(1.0, float(match.group(1)) / 100.0))
            except ValueError:
                pass
        clean = line.strip()
        if clean and not clean.startswith("[") and clean.lower().endswith(".mp4"):
            filepath = clean
        tail.append(clean)
    proc.wait()

    if proc.returncode != 0:
        detail = "\n".join(t for t in tail[-8:] if t)
        raise RuntimeError(f"yt-dlp failed:\n{detail}")
    if filepath and Path(filepath).exists():
        return Path(filepath)
    candidates = sorted(out_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise RuntimeError("yt-dlp reported success but no video file was produced.")
    return candidates[-1]
