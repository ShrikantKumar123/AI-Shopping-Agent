"""SQLite-backed persistent conversation memory for the AI Shopping Agent."""

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from setup_db import DB_PATH


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_memory() -> None:
    """Create conversation tables without changing existing store tables."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New chat',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id)
                    REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation
            ON conversation_messages(conversation_id, id);
            """
        )


def create_conversation(title: str = "New chat") -> str:
    """Create and return a unique conversation ID."""
    conversation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        conn.execute(
            """INSERT INTO conversations (id, title, created_at, updated_at)
               VALUES (?, ?, ?, ?)""",
            (conversation_id, title, now, now),
        )

    return conversation_id


def save_message(conversation_id: str, role: str, content: str) -> None:
    """Persist one user or assistant message and update conversation metadata."""
    if role not in {"user", "assistant"}:
        raise ValueError("role must be 'user' or 'assistant'")
    if not isinstance(content, str):
        raise TypeError("content must be a string")

    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        conversation = conn.execute(
            "SELECT id, title FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()

        if conversation is None:
            raise ValueError("Conversation does not exist")

        conn.execute(
            """INSERT INTO conversation_messages
               (conversation_id, role, content, created_at)
               VALUES (?, ?, ?, ?)""",
            (conversation_id, role, content, now),
        )

        # Use the first user message as the conversation title.
        if role == "user" and conversation["title"] == "New chat":
            title = " ".join(content.split())[:60] or "New chat"
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, conversation_id),
            )
        else:
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )


def get_messages(conversation_id: str) -> list[dict]:
    """Return conversation messages in chronological order."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT role, content
               FROM conversation_messages
               WHERE conversation_id = ?
               ORDER BY id ASC""",
            (conversation_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def list_conversations(limit: int = 30) -> list[dict]:
    """Return recent conversations that contain at least one message."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT c.id, c.title, c.created_at, c.updated_at
               FROM conversations c
               WHERE EXISTS (
                   SELECT 1 FROM conversation_messages m
                   WHERE m.conversation_id = c.id
               )
               ORDER BY c.updated_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def delete_conversation(conversation_id: str) -> None:
    """Delete a conversation and its messages."""
    with _connect() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
