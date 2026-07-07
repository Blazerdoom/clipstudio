"""Face-tracking auto-reframe.

Samples the clip, finds the main face per sample with MediaPipe's BlazeFace
detector, and builds a smoothed, clamped horizontal crop path. `export` then
crops a target-aspect window that follows the face and scales it up.

MediaPipe + its model are optional: if the package is missing or no face is
found, `face_crop()` returns None and the caller falls back to a center crop.
The ~230 KB model is downloaded once and cached under data/models/.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

from .. import config

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)
_MODEL_PATH = config.DATA_DIR / "models" / "blaze_face.tflite"

MAX_SAMPLES = 20
SMOOTH_WINDOW = 3


def _ensure_model() -> Path:
    if not _MODEL_PATH.exists():
        _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, _MODEL_PATH)  # noqa: S310 — fixed https URL
    return _MODEL_PATH


def _detector():
    from mediapipe.tasks import python as mpp
    from mediapipe.tasks.python import vision

    opts = vision.FaceDetectorOptions(
        base_options=mpp.BaseOptions(model_asset_path=str(_ensure_model())),
        running_mode=vision.RunningMode.IMAGE,
    )
    return vision.FaceDetector.create_from_options(opts)


def _sample_centers(source: Path, start: float, duration: float) -> list[tuple[float, float]] | None:
    """Return [(clip_time, face_cx_fraction)] samples, or None if no faces."""
    import cv2
    import mediapipe as mp

    step = max(0.5, duration / MAX_SAMPLES)
    detector = _detector()
    cap = cv2.VideoCapture(str(source))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1

    samples: list[tuple[float, float]] = []
    last_fraction = 0.5
    found_any = False
    t = 0.0
    while t <= duration + 1e-6:
        cap.set(cv2.CAP_PROP_POS_MSEC, (start + t) * 1000.0)
        ok, frame = cap.read()
        if ok:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            detections = detector.detect(image).detections
            if detections:
                box = max(detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)
                last_fraction = (box.bounding_box.origin_x + box.bounding_box.width / 2) / width
                found_any = True
        samples.append((round(t, 2), last_fraction))
        t += step

    cap.release()
    return samples if found_any else None


def _smooth(values: list[float]) -> list[float]:
    if len(values) < 2:
        return values
    out: list[float] = []
    half = SMOOTH_WINDOW // 2
    for i in range(len(values)):
        lo, hi = max(0, i - half), min(len(values), i + half + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


def _x_expression(samples: list[tuple[float, float]], src_w: int, crop_w: int) -> str:
    """Build a piecewise-linear ffmpeg crop-x expression over clip time `t`."""
    max_x = max(0, src_w - crop_w)
    times = [t for t, _ in samples]
    raw = [frac * src_w - crop_w / 2 for _, frac in samples]
    xs = [int(min(max_x, max(0, round(v)))) for v in _smooth(raw)]

    expr = str(xs[-1])
    for i in range(len(times) - 2, -1, -1):
        t0, t1 = times[i], times[i + 1]
        x0, x1 = xs[i], xs[i + 1]
        dt = max(0.01, t1 - t0)
        seg = f"({x0}+({x1 - x0})*(t-{t0})/{dt:.2f})"
        expr = f"if(lt(t,{t1:.2f}),{seg},{expr})"
    return expr


def face_crop(source: Path, start: float, duration: float,
              src_w: int, src_h: int, target_w: int, target_h: int) -> dict | None:
    """Compute a face-following crop spec, or None to fall back to center crop."""
    crop_w = round(src_h * target_w / target_h)
    if crop_w >= src_w:  # source not wide enough to crop horizontally
        return None
    try:
        samples = _sample_centers(source, start, duration)
    except Exception:  # noqa: BLE001 — missing dep / decode issue → fall back
        return None
    if not samples:
        return None
    crop_w -= crop_w % 2  # keep even for yuv420p
    return {"crop_w": crop_w, "crop_h": src_h - (src_h % 2),
            "x_expr": _x_expression(samples, src_w, crop_w)}
