"""Project endpoints: create (kick off a job), list, detail, delete."""
from __future__ import annotations

import shutil

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import config, db, jobs, repo
from ..pipeline import ingest, music, runner
from .media import clip_with_urls

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProject(BaseModel):
    source: str = Field(..., min_length=1, description="A URL or local file path")
    name: str | None = None
    device: str | None = None
    model: str | None = None
    max_clips: int | None = Field(default=None, ge=1, le=40)
    max_minutes: int | None = Field(default=None, ge=1, le=240)
    aspect: str | None = None
    reframe: str | None = None
    caption_preset: str | None = None
    zoom: bool | None = None
    color: bool | None = None
    music: str | None = None


def _resolve_settings(body: CreateProject) -> dict:
    defaults = db.get_settings()
    chosen = {
        "device": body.device or defaults["device"],
        "model": body.model or defaults["model"],
        "max_clips": body.max_clips or defaults["max_clips"],
        "max_minutes": body.max_minutes or defaults["max_minutes"],
        "aspect": body.aspect or defaults["aspect"],
        "reframe": body.reframe or defaults["reframe"],
        "caption_preset": body.caption_preset or defaults["caption_preset"],
        "zoom": defaults["zoom"] if body.zoom is None else bool(body.zoom),
        "color": defaults["color"] if body.color is None else bool(body.color),
        "music": defaults["music"] if body.music is None else body.music,
    }
    _validate(chosen)
    return chosen


def _validate(s: dict) -> None:
    if s["device"] not in config.DEVICES:
        raise HTTPException(422, f"device must be one of {config.DEVICES}")
    if s["model"] not in config.WHISPER_MODELS:
        raise HTTPException(422, f"model must be one of {config.WHISPER_MODELS}")
    if s["aspect"] not in config.ASPECTS:
        raise HTTPException(422, f"aspect must be one of {list(config.ASPECTS)}")
    if s["reframe"] not in config.REFRAMES:
        raise HTTPException(422, f"reframe must be one of {config.REFRAMES}")
    if s["caption_preset"] not in config.CAPTION_PRESETS:
        raise HTTPException(422, f"caption_preset must be one of {config.CAPTION_PRESET_NAMES}")
    if not music.is_valid(s["music"]):
        raise HTTPException(422, "music track not found in the music/ folder")


@router.post("")
def create_project(body: CreateProject) -> dict:
    settings = _resolve_settings(body)
    source_type = "url" if ingest.is_url(body.source) else "file"
    name = body.name or _derive_name(body.source)
    project_id = repo.create_project(name, body.source, source_type, settings)
    jobs.start(project_id, runner.run_project)
    return repo.get_project(project_id)


@router.get("")
def list_projects() -> list[dict]:
    return repo.list_projects()


@router.get("/{project_id}")
def get_project(project_id: int) -> dict:
    project = repo.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    project["running"] = jobs.is_running(project_id)
    project["clips"] = [clip_with_urls(c) for c in repo.list_clips(project_id)]
    return project


@router.delete("/{project_id}")
def delete_project(project_id: int) -> dict:
    if repo.get_project(project_id) is None:
        raise HTTPException(404, "Project not found")
    if jobs.is_running(project_id):
        raise HTTPException(409, "Job still running; wait for it to finish.")
    repo.delete_project(project_id)
    for base in (config.MEDIA_DIR, config.RUNS_DIR):
        shutil.rmtree(base / f"proj_{project_id}", ignore_errors=True)
    return {"deleted": project_id}


def _derive_name(source: str) -> str:
    tail = source.rstrip("/").split("/")[-1].split("?")[0]
    return (tail or "Untitled")[:60]
