"""In-process background job runner.

A single daemon thread per project runs the pipeline so the HTTP layer stays
responsive. No Redis/Celery — this is a personal, single-user tool.
"""
from __future__ import annotations

import threading
import traceback
from typing import Callable, Hashable

# task key -> running thread. Keys are either a project id (int, the Phase-1
# pipeline) or a string like "clip:5" (a Phase-2 single-clip re-render).
_active: dict[Hashable, threading.Thread] = {}
_lock = threading.Lock()


def is_running(key: Hashable) -> bool:
    with _lock:
        thread = _active.get(key)
        return thread is not None and thread.is_alive()


def start(key: Hashable, work: Callable[[Hashable], None]) -> bool:
    """Start a background task under *key*. Returns False if one already runs."""
    with _lock:
        existing = _active.get(key)
        if existing is not None and existing.is_alive():
            return False
        thread = threading.Thread(target=_run, args=(key, work), daemon=True)
        _active[key] = thread
        thread.start()
        return True


def _run(key: Hashable, work: Callable[[Hashable], None]) -> None:
    # Imported lazily to avoid a circular import at module load time.
    from . import repo

    try:
        work(key)
    except Exception as exc:  # noqa: BLE001 — surface every failure to the UI
        detail = f"{exc.__class__.__name__}: {exc}"
        traceback.print_exc()
        # Only int keys are projects; clip re-renders manage their own status.
        if isinstance(key, int):
            repo.update_project(key, status="error", stage="error", error=detail)
    finally:
        with _lock:
            _active.pop(key, None)
