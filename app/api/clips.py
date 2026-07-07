"""Clip endpoints: download one clip, or a ZIP of all clips in a project."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from .. import config, jobs, repo
from ..pipeline import captions, dub, runner

router = APIRouter(prefix="/api", tags=["clips"])


def _safe_clip_path(file_path: str | None) -> Path:
    """Return an existing path guaranteed to sit under RUNS_DIR."""
    if not file_path:
        raise HTTPException(404, "Clip has no rendered file yet.")
    path = Path(file_path).resolve()
    runs_root = config.RUNS_DIR.resolve()
    if runs_root not in path.parents or not path.exists():
        raise HTTPException(404, "Clip file not found.")
    return path


class CaptionLineIn(BaseModel):
    text: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)


class ReeditBody(BaseModel):
    title: str | None = None
    hook: str | None = None
    caption_preset: str | None = None
    voice: str | None = None
    captions: list[CaptionLineIn] = Field(default_factory=list)


@router.post("/clips/{clip_id}/reedit")
def reedit_clip(clip_id: int, body: ReeditBody) -> dict:
    """Apply edited title/hook/captions/style and re-render just this clip."""
    clip = repo.get_clip(clip_id)
    if clip is None:
        raise HTTPException(404, "Clip not found")
    if jobs.is_running(f"clip:{clip_id}"):
        raise HTTPException(409, "A re-render is already running for this clip.")

    project = repo.get_project(clip["project_id"])
    source = project.get("video_path") if project else None
    if not source or not Path(source).exists():
        raise HTTPException(409, "Source video is no longer available; can't re-render.")

    if body.caption_preset is not None and body.caption_preset not in config.CAPTION_PRESETS:
        raise HTTPException(422, f"caption_preset must be one of {config.CAPTION_PRESET_NAMES}")
    if body.voice is not None and not dub.is_valid_voice(body.voice):
        raise HTTPException(422, "voice is not a recognised option")

    lines = captions.validate_lines([ln.model_dump() for ln in body.captions])
    fields = {"captions": json.dumps(captions.lines_to_json(lines)), "status": "rendering"}
    if body.title is not None:
        fields["title"] = body.title.strip()[:200]
    if body.hook is not None:
        fields["hook"] = body.hook.strip()[:200]
    if body.caption_preset is not None:
        fields["caption_preset"] = body.caption_preset
    if body.voice is not None:
        fields["voice"] = body.voice
    repo.update_clip(clip_id, **fields)

    jobs.start(f"clip:{clip_id}", lambda _key: runner.reedit_clip(clip_id))
    return {"ok": True, "clip_id": clip_id, "status": "rendering"}


@router.get("/clips/{clip_id}/download")
def download_clip(clip_id: int) -> FileResponse:
    clip = repo.get_clip(clip_id)
    if clip is None:
        raise HTTPException(404, "Clip not found")
    path = _safe_clip_path(clip.get("file_path"))
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@router.get("/projects/{project_id}/download_all")
def download_all(project_id: int) -> StreamingResponse:
    project = repo.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    clips = [c for c in repo.list_clips(project_id) if c.get("file_path")]
    if not clips:
        raise HTTPException(404, "No rendered clips to download yet.")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for clip in clips:
            path = Path(clip["file_path"])
            if path.exists():
                archive.write(path, arcname=path.name)
    buffer.seek(0)

    safe_name = "".join(c for c in project["name"] if c.isalnum() or c in "-_") or "clips"
    headers = {"Content-Disposition": f'attachment; filename="{safe_name}_clips.zip"'}
    return StreamingResponse(buffer, media_type="application/zip", headers=headers)
