"""Source acquisition: download a URL with yt-dlp, or use a local file."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .ffmpeg_tools import probe_duration

_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def is_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


def fetch(source: str, out_dir: Path) -> tuple[Path, str, float]:
    """Resolve *source* to a local video file.

    Returns (video_path, title, duration_seconds).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if is_url(source):
        video = _download(source, out_dir)
    else:
        video = _local(source)
    duration = probe_duration(video)
    return video, video.stem, duration


def _local(source: str) -> Path:
    path = Path(source).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Local file not found: {source}")
    if path.suffix.lower() not in _VIDEO_SUFFIXES:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    return path


def _download(url: str, out_dir: Path) -> Path:
    """Download the best <=1080p mp4 via yt-dlp, invoked as a module."""
    template = str(out_dir / "%(id)s.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "-o", template,
        "--print", "after_move:filepath",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-8:])
        raise RuntimeError(f"yt-dlp failed:\n{tail}")

    printed = [line for line in result.stdout.strip().splitlines() if line.strip()]
    if printed and Path(printed[-1]).exists():
        return Path(printed[-1])

    candidates = sorted(out_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise RuntimeError("yt-dlp reported success but no video file was produced.")
    return candidates[-1]
