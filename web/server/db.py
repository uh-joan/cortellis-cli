"""SQLite persistence for conversations and messages."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path.home() / ".cortellis" / "web.db"


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            workspace_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conv_id TEXT NOT NULL REFERENCES conversations(id),
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conv_id, created_at);
    """)
    conn.commit()
    conn.close()


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_conversation(workspace_path: str, title: str = "New conversation") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    cid = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations VALUES (?,?,?,?,?)",
            (cid, title, workspace_path, now, now),
        )
    return {"id": cid, "title": title, "workspace_path": workspace_path, "created_at": now, "updated_at": now}


def list_conversations(workspace_path: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE workspace_path=? ORDER BY updated_at DESC",
            (workspace_path,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(conv_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
    return dict(row) if row else None


def rename_conversation(conv_id: str, title: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE conversations SET title=? WHERE id=?", (title, conv_id))


def delete_conversation(conv_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE conv_id=?", (conv_id,))
        conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,))


def add_message(conv_id: str, role: str, content: str, metadata: dict | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    mid = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages VALUES (?,?,?,?,?,?)",
            (mid, conv_id, role, content, json.dumps(metadata or {}), now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at=? WHERE id=?",
            (now, conv_id),
        )
    return {"id": mid, "conv_id": conv_id, "role": role, "content": content, "created_at": now}


def list_messages(conv_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE conv_id=? ORDER BY created_at ASC",
            (conv_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_history(conv_id: str, limit: int = 5) -> list:
    """Return last N Q/A pairs for context injection."""
    msgs = list_messages(conv_id)
    pairs = []
    i = 0
    while i < len(msgs):
        if msgs[i]["role"] == "user":
            q = msgs[i]["content"]
            a = msgs[i + 1]["content"] if i + 1 < len(msgs) and msgs[i + 1]["role"] == "assistant" else ""
            pairs.append({"q": q[:300], "a": a[:600]})
            i += 2
        else:
            i += 1
    return pairs[-limit:]
