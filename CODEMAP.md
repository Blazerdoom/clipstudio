# ClipStudio — CODEMAP

> **Read this first.** This is the token-cheap map of the project. Read it at the
> start of a session instead of re-scanning every file. Update it when structure
> changes (new module, new endpoint, new data-flow stage) — not for line edits.

## What it is
Fully-local Vizard.ai clone: one long video → ranked, captioned vertical clips.
No accounts, no API bills, no LLM — the clip-picking "brain" is local heuristics.
FastAPI backend + static UI (no Node build). SQLite + local files. Runs at
http://127.0.0.1:8790 via `run.bat`.

## Data flow (one request, end to end)
```
UI (app.js) POST /api/projects
  → repo.create_project()               # row in SQLite, status=queued
  → jobs.start(runner.run_project)      # background daemon thread
      runner.run_project:
        ingest.fetch()      # yt-dlp URL  OR local file → (video, title, duration)
        transcribe.transcribe()          # faster-whisper, device+model → Segments
        brain.select_clips()             # score windows → top non-overlapping clips
        for each clip:
          captions.build_ass()           # words → ASS subtitle text (emoji-stripped)
          export.render_clip()           # ffmpeg cut + vertical reframe + burn captions
          export.make_thumb()            # 1-frame jpg
          repo.update_clip(file_path,…)
  UI polls GET /api/projects/{id} every 1.5s → renders progress + clip grid
```
Progress budget: download .05→.15 · transcribe .15→.60 · score →.65 · render →1.0

## File map (one line each)
| File | Responsibility | Key names |
|---|---|---|
| `app/main.py` | FastAPI app; startup init_db; mount `/runs` + static; serve index | `app`, `main()` |
| `app/config.py` | paths, defaults, option catalogues | `WHISPER_MODELS`, `DEVICES`, `ASPECTS`, `CAPTION_PRESETS`, `aspect_dims()`, `ensure_dirs()` |
| `app/models.py` | immutable pipeline value objects | `Word`, `Segment`, `ClipCandidate`, `words_in_range()` |
| `app/db.py` | SQLite schema + connection + global settings | `init_db()`, `connect()`, `get_settings()`, `save_settings()` |
| `app/repo.py` | project/clip CRUD | `create_project`, `get_project`, `set_progress`, `insert_clip`, `update_clip` |
| `app/jobs.py` | in-process background job runner (1 thread/project) | `start()`, `is_running()` |
| `app/pipeline/ingest.py` | acquire source; friendly yt-dlp errors | `fetch(...,cookies)`, `is_url()`, `_friendly_error()` |
| `app/pipeline/cookies.py` | YouTube auth sources for yt-dlp | `SOURCES`, `cookies_args()`, `status()`, `_opera_gx_profile()`, `COOKIE_FILE` |
| `app/errors.py` | user-facing exception (shown verbatim) | `UserError` |
| `app/pipeline/transcribe.py` | speech→text, GPU/CPU + model choice | `transcribe()` |
| `app/pipeline/brain.py` | local virality scoring + titles/hooks/tags | `select_clips()`, `score_window()`, `make_title/hook/tags` |
| `app/pipeline/wordbanks.py` | lexical signal sets (data only) | `HOOK_WORDS`, `EMOTION_WORDS`, `STOPWORDS` |
| `app/pipeline/captions.py` | words → ASS subtitles (no emoji), style presets | `build_ass()`, `ass_from_lines()`, `caption_style_from_preset()`, `strip_emoji()`, `CaptionStyle` (font/color/`position`/`animation`) |
| `app/pipeline/export.py` | ffmpeg render: reframe + effects + dub + caption burn | `render_clip(...,effects,dub_audio,face_crop)`, `make_thumb()` |
| `app/pipeline/reframe_face.py` | face-tracking auto-reframe (MediaPipe BlazeFace) | `face_crop()` → `{crop_w,crop_h,x_expr}` (None → fallback) |
| `app/pipeline/dub.py` | free voice dub (edge-tts) | `VOICES`, `synthesize()`, `is_valid_voice()` |
| `app/pipeline/youtube.py` | optional 1-click upload (gated on user creds) | `status()`, `connect()`, `upload()` |
| `app/pipeline/ffmpeg_tools.py` | ffmpeg/ffprobe wrappers | `probe_duration()`, `probe_dims()`, `run()`, `is_available()` |
| `app/pipeline/runner.py` | orchestrate a job, write progress; single-clip re-edit | `run_project()`, `reedit_clip()`, `_face_crop()`, `_synthesize_dub()` |
| `app/api/projects.py` | create/list/get/delete projects | `router` (`/api/projects`) |
| `app/api/clips.py` | reedit / download one clip / zip all | `router` (`/api/clips`, `/api/projects/{id}/download_all`) |
| `app/api/settings.py` | global settings + env/doctor info | `router` (`/api/settings`, `/api/env`) |
| `app/api/youtube.py` | upload endpoints (gated) | `router` (`/api/youtube/*`) |
| `app/api/media.py` | stored path → served `/runs/...` url | `to_url()`, `clip_with_urls()` |
| `app/static/{index.html,styles.css,app.js}` | single-page UI (vanilla JS, poll-based) | — |
| `doctor.py` | env checker (python/ffmpeg/deps/GPU) | `main()` |

## HTTP surface
- `POST /api/projects` — create + start job
- `GET /api/projects` · `GET /api/projects/{id}` (includes clips+progress+captions) · `DELETE /api/projects/{id}`
- `POST /api/clips/{id}/reedit` — apply edited title/hook/**style(caption_preset)**/**voice**/captions → background re-render of that one clip
- `GET /api/clips/{id}/download` · `GET /api/projects/{id}/download_all` (zip)
- `GET /api/settings` · `PUT /api/settings` · `GET /api/env` (lists devices/models/aspects/reframes/caption_presets/dub_voices)
- `GET /api/youtube/status` · `POST /api/youtube/connect` · `POST /api/youtube/upload` · `GET /api/youtube/upload_status` (all gated; 409 until client_secret.json + google libs present)
- `/runs/...` static (rendered clips + thumbs) · `/` SPA

## Render options (all wired through project settings + editor)
- **reframe**: fit | crop | **face** (MediaPipe track → animated `crop x`; falls back to fit if no face / source too narrow / mediapipe absent)
- **caption_preset**: clean_white | bold_yellow | mint_pop | top_center | minimal (font/color/position/animation). Project-level default + **per-clip override** (`clips.caption_preset`).
- **effects**: `zoom` (static 1.08x tighter crop — NOT time-animated: ffmpeg crop w/h eval once) + `color` (eq saturation/contrast). Project-level bools.
- **voice** (per-clip): edge-tts dub; synthesized from caption text, swapped as audio in `render_clip(dub_audio=)`. Needs internet.
- **music** (project): filename from top-level `music/` folder (`pipeline/music.py`), looped + ducked (~0.18 vol) under audio via `export._audio_plan`. `GET /api/music` lists tracks; None = off.
- **cookies** (project, YouTube auth): `none | file | opera | edge | chrome | brave | firefox` (`pipeline/cookies.py`). `cookies_args()` → `--cookies data/cookies.txt` (file) or `--cookies-from-browser <b>` (browser; Opera GX profile path auto-resolved). Browser DBs are OS-locked while the browser runs → user must close it (no ABE on this machine, DPAPI decrypts fine). `file` works while browser open. Surfaced in Advanced dropdown; `GET /api/cookies` + `/api/env.cookie_sources/cookies_status`.
- Clip columns added over time: `captions`, `caption_preset`, `voice` (see db.py migration list).

## Contracts / invariants
- **Immutable** pipeline objects (`models.py` frozen dataclasses).
- Caption times are **relative to clip start** (`build_ass(words, clip_start,…)`).
- Clip files live under `data/runs/proj_<id>/`; `media.to_url()` refuses paths outside `RUNS_DIR`.
- SQLite: one connection per call (thread-safe across the job thread + API).
- **No emoji in captions** (`strip_emoji` enforces it).

## Where to add things (phase → touch these)
- **Phase 2 caption/title editor — DONE.** `POST /api/clips/{id}/reedit` (`api/clips.py`) → `runner.reedit_clip()` (reuses `captions.ass_from_lines` + `export.render_clip`, no re-download/transcribe). Editable lines persist in the `clips.captions` column (JSON list of `{text,start,end}`, generated on first render by `captions.lines_from_words`). Edit modal + `openEditor/makeLineRow/applyEdit` in `app.js`; job keyed `"clip:{id}"` in `jobs.py`. UI polls while any clip `status=='rendering'`.
- **Phase 3 face-tracking reframe — DONE.** `pipeline/reframe_face.py` → `_reframe_base(...,face_crop)` in export. Model auto-downloads to `data/models/`.
- **Phase 4 effects — DONE (zoom+color+music).** In `export._effects_segment` + `export._audio_plan`. Music = drop files in `music/`, pick in Advanced.
- **Phase 5 dub — DONE.** `pipeline/dub.py` (edge-tts). Translation/B-roll still open.
- **Phase 6 publish — code built, UNVERIFIED.** `pipeline/youtube.py` + `api/youtube.py`; needs `client_secret.json` + google libs (see YOUTUBE-SETUP.md).
- **Caption style presets — DONE.** `config.CAPTION_PRESETS` (Clean White / Bold Yellow / Mint Pop / Top Center / Minimal) → `captions.caption_style_from_preset()` → `CaptionStyle` (font, color, position bottom/middle/top, animation pop/fade/none). Chosen per project in the create form's Advanced panel (`caption_preset` in project settings), applied on first render AND re-edit. To add a preset: append to `CAPTION_PRESETS` only — UI reads it from `/api/env`.
- **New Whisper option / aspect:** add to `config.py` catalogues only — UI reads them from `/api/env`.

## Run / test
- `run.bat` (Win) / `run.sh` (mac/linux) → venv + deps + open browser.
- `python -m pytest tests/ -q` (12 tests: brain, captions, models — pure, no ffmpeg/whisper).
- `python doctor.py` — environment check.
