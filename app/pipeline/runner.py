"""Orchestrate one project end-to-end and stream progress into the DB.

Progress budget across stages (0..1):
  download 0.05->0.15 | transcribe 0.15->0.60 | score 0.60->0.65 | render ->1.0

Also hosts `reedit_clip`, the Phase-2 single-clip re-render: it reuses the
already-downloaded source and the clip's (edited) caption lines — no re-download,
no re-transcription — so applying a caption/title edit takes seconds.
"""
from __future__ import annotations

import json
import traceback
from pathlib import Path

from .. import config, repo
from ..models import Segment, words_in_range
from . import brain, captions, dub, export, ingest, music, transcribe


def run_project(project_id: int) -> None:
    project = repo.get_project(project_id)
    if project is None:
        return
    settings = project["settings"]
    width, height = config.aspect_dims(settings.get("aspect", config.DEFAULT_ASPECT))
    reframe = settings.get("reframe", config.DEFAULT_REFRAME)
    style = captions.caption_style_from_preset(settings.get("caption_preset"))
    effects = _effects_from(settings)
    music_path = music.resolve(settings.get("music"))

    media_dir = config.MEDIA_DIR / f"proj_{project_id}"
    run_dir = config.RUNS_DIR / f"proj_{project_id}"

    # 1. Ingest -------------------------------------------------------------
    repo.set_progress(project_id, "downloading", 0.05)

    def on_download(frac: float) -> None:
        repo.set_progress(project_id, "downloading", 0.05 + 0.10 * frac)

    max_minutes = int(settings.get("max_minutes") or 0) or None
    video, _title, duration = ingest.fetch(project["source"], media_dir,
                                           max_minutes=max_minutes, on_progress=on_download,
                                           cookies=settings.get("cookies"))
    repo.update_project(project_id, video_path=str(video), duration=duration)
    repo.set_progress(project_id, "transcribing", 0.15)

    # 2. Transcribe ---------------------------------------------------------
    def on_transcribe(frac: float) -> None:
        repo.set_progress(project_id, "transcribing", 0.15 + 0.45 * frac)

    segments = transcribe.transcribe(
        video,
        device=settings.get("device", config.DEFAULT_DEVICE),
        model_size=settings.get("model", config.DEFAULT_MODEL),
        duration=duration,
        on_progress=on_transcribe,
    )
    if not segments:
        repo.update_project(project_id, status="error", stage="error",
                            error="No speech was detected in this video.")
        return

    # 3. Score --------------------------------------------------------------
    repo.set_progress(project_id, "scoring", 0.62)
    max_clips = int(settings.get("max_clips", config.DEFAULT_MAX_CLIPS))
    candidates = brain.select_clips(segments, max_clips)
    repo.clear_clips(project_id)

    # 4. Render each clip ---------------------------------------------------
    total = len(candidates) or 1
    for i, cand in enumerate(candidates):
        clip_id = repo.insert_clip(project_id, i + 1, _candidate_dict(cand))
        fc = _face_crop(Path(video), cand.start, cand.end, reframe, width, height)
        _render_one(clip_id, cand, segments, Path(video), run_dir,
                    width, height, reframe, style, effects, fc, music_path)
        repo.set_progress(project_id, "rendering", 0.65 + 0.35 * ((i + 1) / total))

    repo.set_progress(project_id, "done", 1.0, status="done")


def _effects_from(settings: dict) -> dict:
    return {"zoom": bool(settings.get("zoom")), "color": bool(settings.get("color"))}


def _face_crop(source: Path, start: float, end: float, reframe: str,
               width: int, height: int) -> dict | None:
    """Compute a face-following crop spec for reframe='face', else None."""
    if reframe != "face":
        return None
    from .ffmpeg_tools import probe_dims
    from .reframe_face import face_crop

    src_w, src_h = probe_dims(source)
    if not src_w or not src_h:
        return None
    return face_crop(source, start, end - start, src_w, src_h, width, height)


def _render_one(clip_id, cand, segments: tuple[Segment, ...], video: Path,
                run_dir: Path, width: int, height: int, reframe: str,
                style: captions.CaptionStyle, effects: dict,
                face_crop: dict | None = None, music_path: Path | None = None) -> None:
    words = words_in_range(segments, cand.start, cand.end)
    lines = captions.lines_from_words(words, cand.start)
    ass_text = captions.ass_from_lines(lines, width, height, style)

    stem = f"clip_{clip_id:02d}_s{int(cand.score)}"
    out_path = run_dir / f"{stem}.mp4"
    thumb_path: Path | None = run_dir / f"{stem}.jpg"
    duration = cand.end - cand.start

    export.render_clip(video, cand.start, duration, ass_text, out_path,
                       width, height, reframe, effects, face_crop=face_crop,
                       music_path=music_path)
    try:
        export.make_thumb(video, cand.start + duration / 2, thumb_path, width, height)
    except Exception:  # noqa: BLE001 — a missing thumbnail must not fail the clip
        thumb_path = None

    repo.update_clip(
        clip_id,
        file_path=str(out_path),
        thumb_path=str(thumb_path) if thumb_path else None,
        captions=json.dumps(captions.lines_to_json(lines)),
        status="done",
    )


def reedit_clip(clip_id: int) -> None:
    """Re-render one clip from its (edited) stored caption lines. Seconds, not minutes.

    The endpoint has already persisted the edited title/hook/captions and set the
    clip status to 'rendering'; this just rebuilds the ASS + re-runs ffmpeg.
    """
    clip = repo.get_clip(clip_id)
    if clip is None:
        return
    project = repo.get_project(clip["project_id"])
    source = project.get("video_path") if project else None
    if not source or not Path(source).exists():
        repo.update_clip(clip_id, status="error")
        return

    try:
        settings = project["settings"]
        width, height = config.aspect_dims(settings.get("aspect", config.DEFAULT_ASPECT))
        reframe = settings.get("reframe", config.DEFAULT_REFRAME)
        preset = clip.get("caption_preset") or settings.get("caption_preset")
        style = captions.caption_style_from_preset(preset)
        lines = captions.lines_from_json(clip["captions"])
        ass_text = captions.ass_from_lines(lines, width, height, style)

        out_path = Path(clip["file_path"]) if clip.get("file_path") else (
            config.RUNS_DIR / f"proj_{project['id']}" / f"clip_{clip_id:02d}.mp4"
        )
        duration = clip["end"] - clip["start"]
        dub_audio = _synthesize_dub(clip, lines, out_path)
        fc = _face_crop(Path(source), clip["start"], clip["end"], reframe, width, height)
        export.render_clip(Path(source), clip["start"], duration, ass_text, out_path,
                           width, height, reframe, _effects_from(settings), dub_audio, fc,
                           music.resolve(settings.get("music")))
        repo.update_clip(clip_id, file_path=str(out_path), status="done")
    except Exception:  # noqa: BLE001 — surface as an error status on the clip
        traceback.print_exc()
        repo.update_clip(clip_id, status="error")


def _synthesize_dub(clip: dict, lines, out_path: Path) -> Path | None:
    """If the clip has a dub voice + caption text, synthesize it to an mp3."""
    voice = (clip.get("voice") or "").strip()
    if not voice or not dub.is_valid_voice(voice):
        return None
    text = " ".join(ln.text for ln in lines).strip()
    if not text:
        return None
    return dub.synthesize(text, voice, out_path.with_suffix(".dub.mp3"))


def _candidate_dict(cand) -> dict:
    return {
        "start": cand.start, "end": cand.end, "score": cand.score,
        "title": cand.title, "hook": cand.hook, "reason": cand.reason,
        "tags": list(cand.tags),
    }
