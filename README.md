# ClipStudio

Turn one long video into a set of **ranked, captioned vertical clips** for
TikTok / Reels / YouTube Shorts — **100% local, no accounts, no API bills.**

Paste a YouTube link (or point it at a video file on your PC), and ClipStudio:

1. **Downloads** the video (`yt-dlp`)
2. **Transcribes** it with word-level timing (`faster-whisper`, GPU or CPU)
3. **Ranks** the best self-contained moments with a local scoring brain
   — no external AI; every clip gets a 0–100 score and a plain reason why
4. **Renders** each pick as a vertical clip with burned-in captions (`ffmpeg`)

Then you tweak clips in the browser: fix captions, restyle them, add a voice
dub, drop in background music, or auto-reframe onto the speaker's face.

---

## Quick start

You need two things installed once:

- **Python 3.10+** — <https://python.org> (on Windows, tick *Add Python to PATH*)
- **ffmpeg** — `winget install Gyan.FFmpeg` (Windows) · `brew install ffmpeg` (macOS) · `apt install ffmpeg` (Linux)

Then, from the project folder:

- **Windows:** double-click **`run.bat`**
- **macOS / Linux:** `chmod +x run.sh && ./run.sh`

The first run creates a virtual environment, installs the Python packages
(a few minutes), and opens your browser at **http://127.0.0.1:8790**. Paste a
link, hit **Generate clips**, and download the ones you like.

> First transcription also downloads the Whisper model once (~150 MB for
> `base`). First face-reframe downloads a ~230 KB face model. Both are one-time.

## Set up on another PC

```bash
git clone https://github.com/Blazerdoom/clipstudio.git
cd clipstudio
# Windows:  double-click run.bat     (or:  run.bat  in a terminal)
# mac/linux: ./run.sh
```

That's it — `run.bat` / `run.sh` handle the virtual environment and
dependencies automatically. Only Python + ffmpeg need to be preinstalled.

---

## Features

| Feature | What it does |
|---|---|
| **Ranked clips** | A local scoring brain picks the best moments, each with a virality score + reason |
| **Burned captions** | Word-timed captions, text-only (no emoji) |
| **Caption editor** | Fix wrong words/timing, edit title & hook, re-render one clip in seconds |
| **Caption styles** | Presets: Clean White, Bold Yellow, Mint Pop, Top Center, Minimal (pop/fade animation) |
| **Auto-reframe** | `fit` (blurred bg), `crop` (center), or **`face`** (tracks the speaker with MediaPipe) |
| **Effects** | Tighter-zoom framing + color/saturation boost |
| **Voice dub** | Free AI voices via `edge-tts` (needs internet, no key) |
| **Background music** | Drop a track in `music/`, it's looped quietly under the audio |
| **1-click YouTube** | Optional upload — see [YOUTUBE-SETUP.md](YOUTUBE-SETUP.md) (needs your Google credentials) |

### Options (UI → *Advanced*)

| Option | Choices | Notes |
|--------|---------|-------|
| **Device** | `auto` / `cuda` / `cpu` | `auto` uses your GPU if available, else CPU |
| **Whisper model** | `tiny` → `large-v3` | Bigger = better captions, slower. `base` is a good default |
| **Max clips** | 1–40 | How many clips to keep |
| **Aspect** | 9:16 / 4:5 / 1:1 / 16:9 | Output shape |
| **Reframe** | fit / crop / face | `face` follows the speaker |
| **Caption style** | 5 presets | Font, color, position, animation |
| **Zoom / Color** | on/off | Punchier framing + color pop |
| **Background music** | your tracks | From the `music/` folder |

---

## Requirements

Installed automatically by `run.bat` / `run.sh` (see `requirements.txt`):
`fastapi`, `uvicorn`, `yt-dlp`, `faster-whisper`, `edge-tts`, `mediapipe`.

Run `python doctor.py` any time to check what's OK or missing.

Optional (only for YouTube upload):
`google-api-python-client google-auth-oauthlib google-auth-httplib2` + your own
`client_secret.json` — see [YOUTUBE-SETUP.md](YOUTUBE-SETUP.md).

## Tests

```bash
python -m pytest tests/ -q
```

## Project layout

See [CODEMAP.md](CODEMAP.md) for a one-line-per-file map of the codebase.

## License

MIT — see [LICENSE](LICENSE).
