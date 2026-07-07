"""Central configuration: paths, defaults, and constants.

No secrets live here. All values are safe defaults; override the network
binding via the CLIPSTUDIO_HOST / CLIPSTUDIO_PORT environment variables.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "ClipStudio"

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
DATA_DIR = ROOT / "data"
MEDIA_DIR = DATA_DIR / "media"      # downloaded source videos
RUNS_DIR = DATA_DIR / "runs"        # rendered clips, grouped per project
DB_PATH = DATA_DIR / "clipstudio.db"

# --- Network ---------------------------------------------------------------
HOST = os.environ.get("CLIPSTUDIO_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLIPSTUDIO_PORT", "8790"))

# --- Pipeline defaults -----------------------------------------------------
DEFAULT_DEVICE = "auto"             # auto | cuda | cpu
DEFAULT_MODEL = "base"              # tiny | base | small | medium | large-v3
DEFAULT_MAX_CLIPS = 10
DEFAULT_ASPECT = "9:16"
DEFAULT_REFRAME = "fit"             # fit (blurred bg) | crop (center-crop)

MIN_CLIP_SEC = 12.0
MAX_CLIP_SEC = 60.0
IDEAL_CLIP_SEC = 30.0

# --- Option catalogues (surfaced in the UI) --------------------------------
WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]
DEVICES = ["auto", "cuda", "cpu"]
REFRAMES = ["fit", "crop", "face"]
ASPECTS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}

# Caption look-and-feel presets. Colors are ASS format &HAABBGGRR (blue-green-red).
# position ∈ {bottom, middle, top}; animation ∈ {pop, fade, none}.
DEFAULT_CAPTION_PRESET = "clean_white"
CAPTION_PRESETS: dict[str, dict] = {
    "clean_white": {"label": "Clean White", "font": "Arial", "size_ratio": 0.058,
                    "primary": "&H00FFFFFF", "outline": "&H00000000",
                    "position": "bottom", "animation": "pop"},
    "bold_yellow": {"label": "Bold Yellow", "font": "Impact", "size_ratio": 0.066,
                    "primary": "&H0000FFFF", "outline": "&H00000000",
                    "position": "bottom", "animation": "pop"},
    "mint_pop": {"label": "Mint Pop", "font": "Arial", "size_ratio": 0.060,
                 "primary": "&H00D9FF66", "outline": "&H00000000",
                 "position": "bottom", "animation": "pop"},
    "top_center": {"label": "Top Center", "font": "Arial", "size_ratio": 0.056,
                   "primary": "&H00FFFFFF", "outline": "&H00000000",
                   "position": "top", "animation": "fade"},
    "minimal": {"label": "Minimal (no animation)", "font": "Arial", "size_ratio": 0.054,
                "primary": "&H00FFFFFF", "outline": "&H00000000",
                "position": "bottom", "animation": "none"},
}
CAPTION_PRESET_NAMES = list(CAPTION_PRESETS)


def aspect_dims(aspect: str) -> tuple[int, int]:
    """Return (width, height) for an aspect key, defaulting to 9:16."""
    return ASPECTS.get(aspect, ASPECTS[DEFAULT_ASPECT])


def ensure_dirs() -> None:
    """Create the runtime data directories if they do not exist yet."""
    for directory in (DATA_DIR, MEDIA_DIR, RUNS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
