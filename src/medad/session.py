"""Session persistence: SQLite checkpointer + last-session tracking."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


def open_checkpointer(state_dir: Path) -> SqliteSaver:
    state_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(state_dir / "sessions.db", check_same_thread=False)
    return SqliteSaver(conn)


def new_thread_id() -> str:
    return uuid.uuid4().hex


def _marker(state_dir: Path) -> Path:
    return state_dir / "last_session"


def save_last_thread_id(state_dir: Path, thread_id: str) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    _marker(state_dir).write_text(thread_id)


def load_last_thread_id(state_dir: Path) -> str | None:
    marker = _marker(state_dir)
    if marker.is_file():
        value = marker.read_text().strip()
        return value or None
    return None
