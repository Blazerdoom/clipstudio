"""Optional one-click YouTube upload.

UNVERIFIED IN THIS BUILD — it needs credentials only you can create:

  1. pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
  2. Create a Google Cloud OAuth **Desktop app** client and download its
     client_secret.json into the ClipStudio project root.

See YOUTUBE-SETUP.md. Everything is gated behind `status()` so the app runs
fine without any of it — the UI just hides the upload button until it's ready.
"""
from __future__ import annotations

import threading
from pathlib import Path

from .. import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET = config.ROOT / "client_secret.json"
TOKEN_PATH = config.DATA_DIR / "youtube_token.json"

# clip_id -> {"state": queued|uploading|done|error, "url"|"error": ...}
_uploads: dict[int, dict] = {}
_lock = threading.Lock()


def libs_installed() -> bool:
    try:
        import googleapiclient  # noqa: F401
        import google_auth_oauthlib  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def status() -> dict:
    configured = CLIENT_SECRET.exists()
    libs = libs_installed()
    return {
        "libs": libs,
        "configured": configured,
        "authed": TOKEN_PATH.exists(),
        "ready": libs and configured,
    }


def connect() -> None:
    """Interactive OAuth: opens a browser for consent and saves the token."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")


def _service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    return build("youtube", "v3", credentials=creds)


def get_upload_status(clip_id: int) -> dict:
    with _lock:
        return dict(_uploads.get(clip_id, {"state": "idle"}))


def _set(clip_id: int, **fields) -> None:
    with _lock:
        _uploads[clip_id] = {**_uploads.get(clip_id, {}), **fields}


def upload(clip_id: int, video: Path, title: str, description: str = "",
           tags: list[str] | None = None, category_id: str = "22",
           privacy: str = "private") -> None:
    """Resumable-upload one clip; progress is tracked in `_uploads`."""
    from googleapiclient.http import MediaFileUpload

    _set(clip_id, state="uploading", progress=0.0)
    try:
        body = {
            "snippet": {"title": title[:100], "description": description,
                        "tags": tags or [], "categoryId": category_id},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(str(video), chunksize=-1, resumable=True, mimetype="video/mp4")
        request = _service().videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _progress, response = request.next_chunk()
        _set(clip_id, state="done", url=f"https://youtu.be/{response['id']}")
    except Exception as exc:  # noqa: BLE001 — surface to the UI
        _set(clip_id, state="error", error=f"{exc.__class__.__name__}: {exc}")
