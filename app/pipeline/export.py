"""Render one clip with ffmpeg: cut, reframe to vertical, effects, burn captions.

The ASS file is written next to the output and referenced by bare filename
with ffmpeg's working directory set to that folder — this sidesteps the
Windows path-escaping quirks of the `ass` filter.

Optional effects (all pure ffmpeg, no extra deps):
  - zoom:  a tighter 1.08x center framing (punchier than the full frame)
  - color: a saturation/contrast boost for more "pop"

Note: ffmpeg's `crop` evaluates its width/height once, so a *time-animated*
zoom isn't possible there without the fragile `zoompan` filter — a constant
tighter crop is used instead, which is robust across all inputs.
"""
from __future__ import annotations

from pathlib import Path

from .ffmpeg_tools import ffmpeg_path, run


def _reframe_base(width: int, height: int, mode: str, face_crop: dict | None = None) -> str:
    """Reframe chain that produces the [v0] label (no captions yet)."""
    if face_crop is not None:
        # Follow the tracked face: crop a target-aspect window whose x moves
        # with `t`, then scale up to the output size.
        return (
            f"[0:v]crop={face_crop['crop_w']}:{face_crop['crop_h']}:"
            f"x='{face_crop['x_expr']}':y=0,scale={width}:{height}[v0]"
        )
    if mode == "crop":
        return (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}[v0]"
        )
    # "fit" — subject fully visible over a blurred, filled background
    return (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},gblur=sigma=20[bgb];"
        f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2[v0]"
    )


def _effects_segment(inp: str, out: str, width: int, height: int,
                     color: bool, zoom: bool) -> str | None:
    """Optional filter segment applied between reframe and caption burn."""
    filters: list[str] = []
    if zoom:
        # Constant 1.08x center crop → tighter, punchier framing. crop centers
        # by default; scale back to the target size so downstream stays WxH.
        filters.append(f"crop=iw/1.08:ih/1.08,scale={width}:{height}")
    if color:
        filters.append("eq=saturation=1.25:contrast=1.06:brightness=0.01")
    if not filters:
        return None
    return f"[{inp}]" + ",".join(filters) + f"[{out}]"


def _build_filtergraph(width: int, height: int, reframe: str, ass_name: str,
                       effects: dict | None, face_crop: dict | None = None) -> str:
    color = bool(effects and effects.get("color"))
    zoom = bool(effects and effects.get("zoom"))
    parts = [_reframe_base(width, height, reframe, face_crop)]
    last = "v0"
    segment = _effects_segment("v0", "vfx", width, height, color, zoom)
    if segment:
        parts.append(segment)
        last = "vfx"
    parts.append(f"[{last}]ass={ass_name}[v]")
    return ";".join(parts)


def render_clip(
    source: Path,
    start: float,
    duration: float,
    ass_text: str,
    out_path: Path,
    width: int,
    height: int,
    reframe: str = "fit",
    effects: dict | None = None,
    dub_audio: Path | None = None,
    face_crop: dict | None = None,
    music_path: Path | None = None,
    music_volume: float = 0.18,
) -> Path:
    """Cut [start, start+duration], reframe, apply effects, burn captions.

    If *dub_audio* is given, it replaces the clip's audio (trimmed/padded to
    exactly *duration*); otherwise the original audio is kept. If *music_path*
    is given, it is looped quietly under the audio. If *face_crop* is given, the
    reframe follows the tracked face instead of center-cropping.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ass_name = out_path.stem + ".ass"
    ass_path = out_path.parent / ass_name
    ass_path.write_text(ass_text, encoding="utf-8")

    filtergraph = _build_filtergraph(width, height, reframe, ass_name, effects, face_crop)
    # Inputs must be absolute: ffmpeg runs from out_path.parent (for the bare
    # ASS filename), so a relative input path would resolve against that dir.
    cmd = ["-ss", f"{start:.3f}", "-i", str(Path(source).resolve())]
    idx = 1
    dub_idx = mus_idx = None
    if dub_audio is not None:
        cmd += ["-i", str(Path(dub_audio).resolve())]
        dub_idx = idx
        idx += 1
    if music_path is not None:
        cmd += ["-i", str(Path(music_path).resolve())]
        mus_idx = idx
        idx += 1

    audio_suffix, audio_map = _audio_plan(dub_idx, mus_idx, duration, music_volume)
    filtergraph += audio_suffix

    cmd = [
        ffmpeg_path(), "-y", *cmd,
        "-filter_complex", filtergraph,
        "-map", "[v]", *audio_map,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-t", f"{duration:.3f}",  # bound OUTPUT length (must sit before the output file)
        "-movflags", "+faststart",
        out_path.name,
    ]
    run_in(cmd, cwd=out_path.parent)
    return out_path


def _audio_plan(dub_idx: int | None, mus_idx: int | None,
                duration: float, music_volume: float) -> tuple[str, list[str]]:
    """Build the audio filter suffix + output map for dub/music combinations."""
    suffix = ""
    if dub_idx is not None:
        suffix += f";[{dub_idx}:a]atrim=0:{duration:.3f},apad=whole_dur={duration:.3f}[aout]"
        primary = "[aout]"
    else:
        primary = "[0:a]"

    if mus_idx is not None:
        # Loop the track and duck it under the primary audio.
        suffix += (
            f";[{mus_idx}:a]aloop=loop=-1:size=2000000000,volume={music_volume}[mus]"
            f";{primary}[mus]amix=inputs=2:duration=first:normalize=0[amixed]"
        )
        return suffix, ["-map", "[amixed]"]
    if dub_idx is not None:
        return suffix, ["-map", "[aout]"]
    return suffix, ["-map", "0:a?"]


def make_thumb(source: Path, at: float, out_path: Path, width: int, height: int) -> Path:
    """Grab a single center-cropped frame as a JPEG thumbnail."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tw, th = width // 3, height // 3
    vf = f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}"
    cmd = [
        ffmpeg_path(), "-y",
        "-ss", f"{at:.3f}", "-i", str(source),
        "-frames:v", "1", "-vf", vf,
        str(out_path),
    ]
    run(cmd)
    return out_path


def run_in(cmd: list[str], cwd: Path) -> None:
    """Run an ffmpeg command from *cwd* (needed for the bare ASS filename)."""
    import subprocess

    from .ffmpeg_tools import FfmpegError

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-12:])
        raise FfmpegError(f"ffmpeg render failed (exit {result.returncode}):\n{tail}")
