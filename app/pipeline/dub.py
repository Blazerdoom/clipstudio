"""Free, local-ish AI voice dubbing via edge-tts (Microsoft neural voices).

No API key. Needs an internet connection at synthesis time. The dub reads the
clip's caption text in the chosen voice; `export.render_clip` then swaps it in
as the clip's audio track (trimmed/padded to the clip length).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

# Curated small voice list surfaced in the editor. Empty id = no dub.
VOICES: list[dict] = [
    {"id": "", "label": "None (keep original audio)"},
    {"id": "en-US-GuyNeural", "label": "Guy — US male"},
    {"id": "en-US-AriaNeural", "label": "Aria — US female"},
    {"id": "en-US-AndrewNeural", "label": "Andrew — US male"},
    {"id": "en-GB-RyanNeural", "label": "Ryan — UK male"},
    {"id": "en-AU-NatashaNeural", "label": "Natasha — AU female"},
]
VOICE_IDS = {v["id"] for v in VOICES}


def is_valid_voice(voice: str | None) -> bool:
    return (voice or "") in VOICE_IDS


def synthesize(text: str, voice: str, out_path: Path) -> Path:
    """Synthesize *text* to an mp3 at *out_path* using edge-tts. Blocking."""
    import edge_tts  # imported lazily so the app runs without the optional dep

    out_path.parent.mkdir(parents=True, exist_ok=True)

    async def _run() -> None:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(out_path))

    asyncio.run(_run())
    if not out_path.exists() or out_path.stat().st_size < 512:
        raise RuntimeError("Voice synthesis produced no audio (check your connection).")
    return out_path
