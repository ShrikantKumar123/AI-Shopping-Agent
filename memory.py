
"""SQLite-backed, user-specific conversation memory."""

import os
import sqlite3
import uuid

from datetime import datetime, timezone

from setup_db import DB_PATH


# --------------------------------------------------
# Database connection
# --------------------------------------------------

def _connect() -> sqlite3.Connection:
    """Create a database connection."""

    db_directory = os.path.dirname(DB_PATH)

    if db_directory:
        os.makedirs(db_directory, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


# --------------------------------------------------
# Validation
# --------------------------------------------------

def _validate_user_id(user_id: int) -> None:
    """Validate the authenticated user's ID."""

    if (
        not isinstance(user_id, int)
        or isinstance(user_id, bool)
        or user_id <= 0
    ):
        raise ValueError("A valid user_id is required.")


def _ensure_owned_conversation(
    conn: sqlite3.Connection,
    conversation_id: str,
    user_id: int,
):
    """Verify that a conversation belongs to the specified user."""

    conversation = conn.execute(
        """
        SELECT id, title
        FROM conversations
        WHERE id = ? AND user_id = ?
        """,
        (conversation_id, user_id),
    ).fetchone()

    if conversation is None:
        raise ValueError(
            "Conversation not found or you do not have access to it."
        )

    return conversation


# --------------------------------------------------
# Initialize tables and migrate existing database
# --------------------------------------------------

def initialize_memory() -> None:
    """Create conversation tables and add user ownership."""

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
                role TEXT NOT NULL
                    CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,

                FOREIGN KEY (conversation_id)
                    REFERENCES conversations(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
                idx_conversation_messages_conversation
            ON conversation_messages(conversation_id, id);
            """
        )

        # Migrate existing conversations.
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(conversations)"
            ).fetchall()
        }

        if "user_id" not in columns:
            conn.execute(
                "ALTER TABLE conversations ADD COLUMN user_id INTEGER"
            )

        # Index conversations by owner.
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
            ON conversations(user_id, updated_at DESC)
            """
        )


# --------------------------------------------------
# Create conversation
# --------------------------------------------------

def create_conversation(
    user_id: int,
    title: str = "New chat",
) -> str:
    """Create a conversation for a specific user."""

    _validate_user_id(user_id)

    if not isinstance(title, str) or not title.strip():
        title = "New chat"

    conversation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:

        conn.execute(
            """
            INSERT INTO conversations (
                id,
                title,
                created_at,
                updated_at,
                user_id
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                title.strip(),
                now,
                now,
                user_id,
            ),
        )

    return conversation_id


# --------------------------------------------------
# Save message
# --------------------------------------------------

def save_message(
    conversation_id: str,
    user_id: int,
    role: str,
    content: str,
) -> None:
    """Save a message only if the conversation belongs to the user."""

    _validate_user_id(user_id)

    if not conversation_id:
        raise ValueError("conversation_id is required.")

    if role not in {"user", "assistant"}:
        raise ValueError("role must be 'user' or 'assistant'.")

    if not isinstance(content, str):
        raise TypeError("content must be a string.")

    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:

        conversation = _ensure_owned_conversation(
            conn,
            conversation_id,
            user_id,
        )

        conn.execute(
            """
            INSERT INTO conversation_messages (
                conversation_id,
                role,
                content,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                conversation_id,
                role,
                content,
                now,
            ),
        )

        # Set the title using the first user message.
        if role == "user" and conversation["title"] == "New chat":

            title = " ".join(content.split())[:60] or "New chat"

            conn.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    title,
                    now,
                    conversation_id,
                    user_id,
                ),
            )

        else:

            conn.execute(
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    now,
                    conversation_id,
                    user_id,
                ),
            )


# --------------------------------------------------
# Get messages
# --------------------------------------------------

def get_messages(
    conversation_id: str,
    user_id: int,
) -> list[dict]:
    """Retrieve messages from the user's own conversation."""

    _validate_user_id(user_id)

    with _connect() as conn:

        _ensure_owned_conversation(
            conn,
            conversation_id,
            user_id,
        )

        rows = conn.execute(
            """
            SELECT m.role, m.content
            FROM conversation_messages m
            INNER JOIN conversations c
                ON c.id = m.conversation_id
            WHERE c.id = ? AND c.user_id = ?
            ORDER BY m.id ASC
            """,
            (
                conversation_id,
                user_id,
            ),
        ).fetchall()

    return [dict(row) for row in rows]


# --------------------------------------------------
# List conversations
# --------------------------------------------------

def list_conversations(
    user_id: int,
    limit: int = 30,
) -> list[dict]:
    """List recent conversations belonging to a user."""

    _validate_user_id(user_id)

    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise ValueError("limit must be a positive integer.")

    with _connect() as conn:

        rows = conn.execute(
            """
            SELECT
                c.id,
                c.title,
                c.created_at,
                c.updated_at
            FROM conversations c
            WHERE c.user_id = ?
              AND EXISTS (
                  SELECT 1
                  FROM conversation_messages m
                  WHERE m.conversation_id = c.id
              )
            ORDER BY c.updated_at DESC
            LIMIT ?
            """,
            (
                user_id,
                limit,
            ),
        ).fetchall()

    return [dict(row) for row in rows]


# --------------------------------------------------
# Delete conversation
# --------------------------------------------------

def delete_conversation(
    conversation_id: str,
    user_id: int,
) -> None:
    """Delete a conversation only if it belongs to the user."""

    _validate_user_id(user_id)

    with _connect() as conn:

        _ensure_owned_conversation(
            conn,
            conversation_id,
            user_id,
        )

        conn.execute(
            """
            DELETE FROM conversations
            WHERE id = ? AND user_id = ?
            """,
            (
                conversation_id,
                user_id,
            ),
        )
