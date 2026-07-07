"""Thin wrappers around ffmpeg / ffprobe.

Every subprocess call goes through here so error handling and the "is ffmpeg
installed?" check live in one place.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class FfmpegError(RuntimeError):
    """Raised when ffmpeg/ffprobe is missing or a render fails."""


def ffmpeg_path() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise FfmpegError("ffmpeg not found on PATH. Install it (winget install Gyan.FFmpeg).")
    return path


def ffprobe_path() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise FfmpegError("ffprobe not found on PATH. Install ffmpeg (it ships ffprobe).")
    return path


def is_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def probe_duration(video: Path) -> float:
    """Return the media duration in seconds (0.0 if it cannot be determined)."""
    cmd = [
        ffprobe_path(), "-v", "quiet", "-print_format", "json",
        "-show_format", str(video),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return 0.0
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return 0.0


def probe_dims(video: Path) -> tuple[int, int]:
    """Return (width, height) of the first video stream, or (0, 0)."""
    cmd = [
        ffprobe_path(), "-v", "quiet", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-print_format", "json", str(video),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return (0, 0)
    try:
        stream = json.loads(result.stdout)["streams"][0]
        return (int(stream["width"]), int(stream["height"]))
    except (KeyError, IndexError, ValueError, json.JSONDecodeError):
        return (0, 0)


def run(cmd: list[str]) -> None:
    """Run an ffmpeg command, raising FfmpegError with stderr tail on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-12:])
        raise FfmpegError(f"ffmpeg failed (exit {result.returncode}):\n{tail}")
