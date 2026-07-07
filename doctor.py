"""Environment checker. Run:  python doctor.py

Prints an [ OK ] / [MISS] line for each dependency and a one-line hint for
anything missing. Exits 0 even with warnings so run.bat can continue.
"""
from __future__ import annotations

import shutil
import sys


def check(label: str, ok: bool, hint: str = "") -> bool:
    tag = "[ OK ]" if ok else "[MISS]"
    line = f"  {tag}  {label}"
    if not ok and hint:
        line += f"  ->  {hint}"
    print(line)
    return ok


def _import_ok(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:  # noqa: BLE001
        return False


def _cuda_count() -> int:
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count())
    except Exception:  # noqa: BLE001
        return 0


def main() -> int:
    print("\nClipStudio environment check")
    print("-" * 40)

    py_ok = sys.version_info >= (3, 10)
    check(f"Python {sys.version.split()[0]}", py_ok, "Need Python 3.10 or newer")

    check("ffmpeg", shutil.which("ffmpeg") is not None, "winget install Gyan.FFmpeg")
    check("ffprobe", shutil.which("ffprobe") is not None, "ships with ffmpeg")

    for mod, hint in [
        ("fastapi", "pip install -r requirements.txt"),
        ("uvicorn", "pip install -r requirements.txt"),
        ("yt_dlp", "pip install yt-dlp"),
        ("faster_whisper", "pip install faster-whisper"),
    ]:
        check(mod, _import_ok(mod), hint)

    cuda = _cuda_count()
    print("-" * 40)
    if cuda > 0:
        print(f"  GPU: {cuda} CUDA device(s) available - transcription can use 'cuda'.")
    else:
        print("  GPU: none detected — transcription will run on CPU (still works).")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
