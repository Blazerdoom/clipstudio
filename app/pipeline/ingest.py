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

from ..errors import UserError
from . import cookies as cookie_src
from .ffmpeg_tools import probe_duration

ProgressFn = Callable[[float], None]

_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
_PCT_RE = re.compile(r"\[download\]\s+([0-9.]+)%")
# Prefer <=720p mp4 for fast, reasonably-sized downloads.
_FORMAT = "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b[ext=mp4]/b"


def is_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


def fetch(source: str, out_dir: Path, max_minutes: int | None = None,
          on_progress: ProgressFn | None = None,
          cookies: str | None = None) -> tuple[Path, str, float]:
    """Resolve *source* to a local video file.

    Returns (video_path, title, duration_seconds). For URLs, only the first
    *max_minutes* are downloaded when given. *cookies* names an auth source
    (see `pipeline.cookies`) for bot-gated videos.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if is_url(source):
        video = _download(source, out_dir, max_minutes, on_progress, cookies)
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
              on_progress: ProgressFn | None, cookies: str | None = None) -> Path:
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
    cmd += cookie_src.cookies_args(cookies)
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
        raise UserError(_friendly_error(detail, cookies))
    if filepath and Path(filepath).exists():
        return Path(filepath)
    candidates = sorted(out_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise UserError("The download finished but produced no video file. Try again, "
                        "or paste a local video file path instead.")
    return candidates[-1]


def _friendly_error(detail: str, cookies: str | None) -> str:
    """Turn a raw yt-dlp failure into an actionable, non-technical message."""
    low = detail.lower()
    using_cookies = bool(cookie_src.cookies_args(cookies))

    if "could not copy" in low and "cookie" in low:
        return ("Couldn't read your browser's cookies because the browser is open and "
                "locking them. Fully close Opera GX, then generate again — or set "
                "'YouTube login' to 'Cookie file' after exporting a cookies.txt.")
    if "sign in to confirm" in low or "not a bot" in low or "confirm you" in low:
        if using_cookies:
            return ("YouTube still wants sign-in for this video even with your cookies. "
                    "Make sure you're logged in to YouTube in that browser and the cookies "
                    "are fresh, or try a different video.")
        return ("YouTube wants you signed in to prove you're not a bot. Open 'Advanced "
                "options' and set 'YouTube login' to your browser (Opera GX must be "
                "closed while generating), or to 'Cookie file' after exporting cookies.txt. "
                "You can also paste a local video file path instead.")
    if "429" in low or "too many requests" in low:
        return ("YouTube rate-limited this connection (too many requests, usually from "
                "repeated downloads of the same video). Wait ~15-30 minutes and try again, "
                "try a different video, or paste a local video file path.")
    if "private video" in low or "video unavailable" in low or "members-only" in low:
        return "This video is private, unavailable, or members-only, so it can't be downloaded."
    if "unsupported url" in low or "is not a valid url" in low:
        return "That doesn't look like a supported video URL. Paste a YouTube link or a local file path."
    return f"Download failed. Details from yt-dlp:\n{detail}"
