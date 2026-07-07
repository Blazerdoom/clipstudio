"""Data-access helpers for projects and clips.

These are thin functions over SQLite so both the API layer and the background
worker share one consistent shape for reads and writes.
"""
from __future__ import annotations

import json
from typing import Any

from .db import connect


def _project_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row)
    data["settings"] = json.loads(data.get("settings") or "{}")
    return data


def _clip_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row)
    data["tags"] = json.loads(data.get("tags") or "[]")
    data["captions"] = json.loads(data.get("captions") or "[]")
    return data


def create_project(name: str, source: str, source_type: str, settings: dict[str, Any]) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, source, source_type, settings) VALUES (?, ?, ?, ?)",
            (name, source, source_type, json.dumps(settings)),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_projects() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
    return [_project_to_dict(r) for r in rows]


def get_project(project_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _project_to_dict(row) if row else None


def update_project(project_id: int, **fields: Any) -> None:
    if not fields:
        return
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [project_id]
    with connect() as conn:
        conn.execute(f"UPDATE projects SET {columns} WHERE id = ?", values)
        conn.commit()


def set_progress(project_id: int, stage: str, progress: float, status: str = "running") -> None:
    update_project(project_id, stage=stage, progress=round(progress, 3), status=status)


def delete_project(project_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()


def list_clips(project_id: int) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM clips WHERE project_id = ? ORDER BY score DESC, idx ASC",
            (project_id,),
        ).fetchall()
    return [_clip_to_dict(r) for r in rows]


def get_clip(clip_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM clips WHERE id = ?", (clip_id,)).fetchone()
    return _clip_to_dict(row) if row else None


def clear_clips(project_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM clips WHERE project_id = ?", (project_id,))
        conn.commit()


def insert_clip(project_id: int, idx: int, candidate: dict[str, Any]) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO clips
               (project_id, idx, start, end, score, title, hook, reason, tags, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (
                project_id,
                idx,
                candidate["start"],
                candidate["end"],
                candidate["score"],
                candidate["title"],
                candidate["hook"],
                candidate["reason"],
                json.dumps(candidate["tags"]),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def update_clip(clip_id: int, **fields: Any) -> None:
    if not fields:
        return
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [clip_id]
    with connect() as conn:
        conn.execute(f"UPDATE clips SET {columns} WHERE id = ?", values)
        conn.commit()
