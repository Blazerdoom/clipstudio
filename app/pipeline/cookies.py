"""YouTube cookie sources for yt-dlp.

Two ways to authenticate downloads so bot-gated / age-gated videos work:

* **From a browser** — yt-dlp reads the browser's cookie DB directly. On Windows
  the browser must be *closed* during download (it holds an exclusive lock on the
  cookie file). Opera GX keeps its profile in a non-default folder, so we resolve
  its path explicitly.
* **From a file** — a Netscape `cookies.txt` exported once (e.g. via a
  "Get cookies.txt" browser extension). Works even while the browser is open,
  until the cookies expire. Dropped at `data/cookies.txt`.

`cookies_args()` turns a chosen source into the yt-dlp CLI flags.
"""
from __future__ import annotations

import os
from pathlib import Path

from .. import config

# Selectable sources surfaced in the UI. "none" = no auth.
SOURCES = ["none", "file", "opera", "edge", "chrome", "brave", "firefox"]
DEFAULT_SOURCE = "none"

COOKIE_FILE = config.DATA_DIR / "cookies.txt"


def _opera_gx_profile() -> str | None:
    """Path to the Opera GX user-data dir, if it exists (non-default location)."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    path = Path(appdata) / "Opera Software" / "Opera GX Stable"
    return str(path) if (path / "Default" / "Network" / "Cookies").exists() else None


def file_available() -> bool:
    return COOKIE_FILE.exists() and COOKIE_FILE.stat().st_size > 0


def is_valid(source: str | None) -> bool:
    return (source or "none") in SOURCES


def cookies_args(source: str | None) -> list[str]:
    """yt-dlp flags for the chosen cookie source (empty list for 'none')."""
    source = (source or "none").lower()
    if source in ("", "none"):
        return []
    if source == "file":
        if not file_available():
            return []
        return ["--cookies", str(COOKIE_FILE)]
    if source == "opera":
        gx = _opera_gx_profile()
        return ["--cookies-from-browser", f"opera:{gx}" if gx else "opera"]
    # Standard Chromium/Firefox browsers yt-dlp locates on its own.
    return ["--cookies-from-browser", source]


def status() -> dict:
    """Snapshot for the UI: which sources are usable right now."""
    return {
        "sources": SOURCES,
        "file_available": file_available(),
        "opera_gx_detected": _opera_gx_profile() is not None,
    }
