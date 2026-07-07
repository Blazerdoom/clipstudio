"""YouTube upload endpoints (optional; gated behind credentials)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config, jobs, repo
from ..pipeline import youtube

router = APIRouter(prefix="/api/youtube", tags=["youtube"])

_PRIVACY = {"private", "unlisted", "public"}


class UploadBody(BaseModel):
    clip_id: int
    privacy: str = "private"


@router.get("/status")
def get_status() -> dict:
    return youtube.status()


@router.post("/connect")
def connect() -> dict:
    st = youtube.status()
    if not st["libs"]:
        raise HTTPException(409, "Google client libraries are not installed. See YOUTUBE-SETUP.md.")
    if not st["configured"]:
        raise HTTPException(409, "client_secret.json is missing. See YOUTUBE-SETUP.md.")
    # Runs the interactive browser-consent flow in the background.
    jobs.start("yt:connect", lambda _k: youtube.connect())
    return {"ok": True, "message": "A browser window will open for Google sign-in."}


@router.get("/upload_status")
def upload_status(clip_id: int) -> dict:
    return youtube.get_upload_status(clip_id)


@router.post("/upload")
def upload(body: UploadBody) -> dict:
    if body.privacy not in _PRIVACY:
        raise HTTPException(422, f"privacy must be one of {sorted(_PRIVACY)}")
    st = youtube.status()
    if not st["ready"]:
        raise HTTPException(409, "YouTube is not set up. See YOUTUBE-SETUP.md.")
    if not st["authed"]:
        raise HTTPException(409, "Not connected to YouTube yet. Click Connect first.")

    clip = repo.get_clip(body.clip_id)
    if clip is None:
        raise HTTPException(404, "Clip not found")
    path = Path(clip.get("file_path") or "")
    if not path.exists() or config.RUNS_DIR.resolve() not in path.resolve().parents:
        raise HTTPException(404, "Clip file not found.")
    if jobs.is_running(f"yt:{body.clip_id}"):
        raise HTTPException(409, "This clip is already uploading.")

    title = clip.get("title") or f"Clip {body.clip_id}"
    tags = clip.get("tags") or []
    jobs.start(
        f"yt:{body.clip_id}",
        lambda _k: youtube.upload(body.clip_id, path, title, tags=tags, privacy=body.privacy),
    )
    return {"ok": True, "clip_id": body.clip_id, "state": "uploading"}
