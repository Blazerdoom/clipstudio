"""Settings + environment endpoints (global defaults, doctor info)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from .. import config, db
from ..pipeline import cookies, music
from ..pipeline.dub import VOICES as DUB_VOICES
from ..pipeline.ffmpeg_tools import is_available as ffmpeg_available

router = APIRouter(prefix="/api", tags=["settings"])


class SettingsPatch(BaseModel):
    device: str | None = None
    model: str | None = None
    max_clips: int | None = None
    max_minutes: int | None = None
    aspect: str | None = None
    reframe: str | None = None
    caption_preset: str | None = None
    zoom: bool | None = None
    color: bool | None = None
    music: str | None = None
    cookies: str | None = None


@router.get("/settings")
def get_settings() -> dict:
    return db.get_settings()


@router.put("/settings")
def update_settings(patch: SettingsPatch) -> dict:
    values = {k: v for k, v in patch.model_dump().items() if v is not None}
    return db.save_settings(values)


def _cuda_devices() -> int:
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count())
    except Exception:  # noqa: BLE001 — treat any probe failure as "no GPU"
        return 0


@router.get("/music")
def list_music() -> list[dict]:
    return music.list_tracks()


@router.get("/cookies")
def cookies_status() -> dict:
    return cookies.status()


@router.get("/env")
def get_env() -> dict:
    cuda = _cuda_devices()
    return {
        "app": config.APP_NAME,
        "ffmpeg": ffmpeg_available(),
        "cuda_devices": cuda,
        "gpu_available": cuda > 0,
        "devices": config.DEVICES,
        "models": config.WHISPER_MODELS,
        "aspects": list(config.ASPECTS.keys()),
        "reframes": config.REFRAMES,
        "caption_presets": [
            {"name": name, "label": preset["label"]}
            for name, preset in config.CAPTION_PRESETS.items()
        ],
        "dub_voices": DUB_VOICES,
        "cookie_sources": cookies.SOURCES,
        "cookies_status": cookies.status(),
    }
