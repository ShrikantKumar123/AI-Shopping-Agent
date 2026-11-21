
"""User authentication for the AI Shopping Agent."""

import hashlib
import hmac
import os
import sqlite3

from setup_db import DB_PATH


ITERATIONS = 600_000


def _connect():
    """Create a database connection."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_auth():
    """Create the users table if it does not exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def _hash_password(password, salt):
    """Generate a secure password hash."""
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        ITERATIONS
    )

    return password_hash.hex()


def register_user(name, email, password):
    """Register a new user."""

    name = name.strip() if isinstance(name, str) else ""
    email = email.strip().lower() if isinstance(email, str) else ""

    if not name:
        return {"success": False, "message": "Name is required."}

    if not email or "@" not in email:
        return {"success": False, "message": "Enter a valid email address."}

    if not isinstance(password, str) or len(password) < 8:
        return {
            "success": False,
            "message": "Password must contain at least 8 characters."
        }

    salt = os.urandom(16).hex()
    password_hash = _hash_password(password, salt)

    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (name, email, password_hash, salt)
                VALUES (?, ?, ?, ?)
                """,
                (name, email, password_hash, salt)
            )

            user_id = cursor.lastrowid

        return {
            "success": True,
            "message": "Account created successfully.",
            "user": {
                "id": user_id,
                "name": name,
                "email": email
            }
        }

    except sqlite3.IntegrityError:
        return {
            "success": False,
            "message": "An account with this email already exists."
        }


def authenticate_user(email, password):
    """Verify user credentials and return the user."""

    email = email.strip().lower() if isinstance(email, str) else ""

    if not email or not isinstance(password, str) or not password:
        return {"success": False, "message": "Invalid email or password."}

    with _connect() as conn:
        user = conn.execute(
            """
            SELECT id, name, email, password_hash, salt
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

    if user is None:
        return {"success": False, "message": "Invalid email or password."}

    entered_hash = _hash_password(password, user["salt"])

    if not hmac.compare_digest(entered_hash, user["password_hash"]):
        return {"success": False, "message": "Invalid email or password."}

    return {
        "success": True,
        "message": "Login successful.",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }
    }
