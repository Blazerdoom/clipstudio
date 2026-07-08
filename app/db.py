"""SQLite persistence for projects, clips, and global settings.

A fresh connection is opened per call so the API thread and background job
threads never share a connection (SQLite connections are not thread-safe).
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    source       TEXT NOT NULL,
    source_type  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued',
    stage        TEXT NOT NULL DEFAULT 'queued',
    progress     REAL NOT NULL DEFAULT 0,
    error        TEXT,
    video_path   TEXT,
    duration     REAL,
    settings     TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clips (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    idx         INTEGER NOT NULL,
    start       REAL NOT NULL,
    end         REAL NOT NULL,
    score       REAL NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    hook        TEXT NOT NULL DEFAULT '',
    reason      TEXT NOT NULL DEFAULT '',
    tags           TEXT NOT NULL DEFAULT '[]',
    captions       TEXT NOT NULL DEFAULT '[]',
    caption_preset TEXT,
    voice          TEXT,
    file_path      TEXT,
    thumb_path     TEXT,
    status         TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS settings (
    id    INTEGER PRIMARY KEY CHECK (id = 1),
    data  TEXT NOT NULL DEFAULT '{}'
);
"""

_DEFAULT_SETTINGS: dict[str, Any] = {
    "device": config.DEFAULT_DEVICE,
    "model": config.DEFAULT_MODEL,
    "max_clips": config.DEFAULT_MAX_CLIPS,
    "aspect": config.DEFAULT_ASPECT,
    "reframe": config.DEFAULT_REFRAME,
    "caption_preset": config.DEFAULT_CAPTION_PRESET,
    "zoom": False,
    "color": False,
    "music": "",
    "max_minutes": config.DEFAULT_MAX_MINUTES,
    "cookies": "none",  # YouTube auth source; see pipeline.cookies.SOURCES
}


def connect() -> sqlite3.Connection:
    """Open a connection with row access by column name and FK enforcement."""
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables and seed the single settings row."""
    config.ensure_dirs()
    with connect() as conn:
        conn.executescript(_SCHEMA)
        # Migrate DBs created before these clip columns existed.
        for ddl in (
            "ALTER TABLE clips ADD COLUMN captions TEXT NOT NULL DEFAULT '[]'",
            "ALTER TABLE clips ADD COLUMN caption_preset TEXT",
            "ALTER TABLE clips ADD COLUMN voice TEXT",
        ):
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # column already present
        conn.execute(
            "INSERT OR IGNORE INTO settings (id, data) VALUES (1, ?)",
            (json.dumps(_DEFAULT_SETTINGS),),
        )
        conn.commit()


def get_settings() -> dict[str, Any]:
    """Return global defaults, backfilling any missing keys."""
    with connect() as conn:
        row = conn.execute("SELECT data FROM settings WHERE id = 1").fetchone()
    stored = json.loads(row["data"]) if row else {}
    return {**_DEFAULT_SETTINGS, **stored}


def save_settings(values: dict[str, Any]) -> dict[str, Any]:
    """Merge and persist global defaults, returning the full settings."""
    merged = {**get_settings(), **values}
    with connect() as conn:
        conn.execute("UPDATE settings SET data = ? WHERE id = 1", (json.dumps(merged),))
        conn.commit()
    return merged
