"""
SQLite-backed conversation history for JARVIS.

Stores chat sessions and messages persistently.
"""

import sqlite3
import json
import uuid
import datetime
from pathlib import Path

from jarvis.core.logging import get_logger

logger = get_logger("jarvis.chat.history")

# Store db in the same config dir as other JARVIS data
DB_PATH = Path.home() / ".jarvis" / "chat.db"


def _get_conn() -> sqlite3.Connection:
    """Get a database connection, initializing the schema if necessary."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Initialize schema
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        )
    ''')
    # Trigger to update session updated_at
    conn.execute('''
        CREATE TRIGGER IF NOT EXISTS update_session_timestamp
        AFTER INSERT ON messages
        BEGIN
            UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = NEW.session_id;
        END;
    ''')
    conn.commit()
    return conn


def get_or_create_session(session_id: str | None = None) -> str:
    """Ensure a session exists and return its ID."""
    sid = session_id or str(uuid.uuid4())[:12]
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (session_id, title) VALUES (?, ?)",
            (sid, f"Chat {sid}")
        )
        conn.commit()
    return sid


def get_session_history(session_id: str, limit: int = 40) -> list[dict[str, str]]:
    """Get the recent history for a session."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        
    # Return in chronological order
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def add_messages(session_id: str, messages: list[dict[str, str]]):
    """Append messages to a session's history."""
    with _get_conn() as conn:
        for msg in messages:
            conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, msg.get("role", "user"), msg.get("content", ""))
            )
        conn.commit()


def list_sessions(limit: int = 50) -> list[dict]:
    """List recent sessions."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT session_id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_session(session_id: str):
    """Delete a session and all its messages."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()


__all__ = ["get_or_create_session", "get_session_history", "add_messages", "list_sessions", "delete_session"]
