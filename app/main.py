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


def _lan_ip() -> str | None:
    """Best-effort LAN IPv4 of this machine (no traffic actually sent)."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))  # picks the interface with a default route
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def main() -> None:
    import uvicorn

    db.init_db()
    print(f"\n  {config.APP_NAME} running")
    print(f"    This PC:        http://127.0.0.1:{config.PORT}")
    if config.HOST in ("0.0.0.0", "::"):
        lan = _lan_ip()
        if lan:
            print(f"    Other devices:  http://{lan}:{config.PORT}  (same Wi-Fi/network)")
        print("    Binding to all interfaces — anyone on your network can reach it.")
    print()
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()
