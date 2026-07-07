"""ClipStudio application entrypoint.

Run with:  python -m app.main
Serves the UI at http://127.0.0.1:8790 and the JSON API under /api.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, db
from .api import clips, projects, settings, youtube

app = FastAPI(title=config.APP_NAME, version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


app.include_router(projects.router)
app.include_router(clips.router)
app.include_router(settings.router)
app.include_router(youtube.router)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "index.html")


def _mount_static() -> None:
    config.ensure_dirs()
    # Rendered clips + thumbnails, served for inline preview/download.
    app.mount("/runs", StaticFiles(directory=str(config.RUNS_DIR)), name="runs")
    # The single-page UI assets.
    app.mount("/", StaticFiles(directory=str(config.STATIC_DIR), html=True), name="static")


_mount_static()


def main() -> None:
    import uvicorn

    db.init_db()
    print(f"\n  {config.APP_NAME} running at http://{config.HOST}:{config.PORT}\n")
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()
