"""Account security writes, composed inside caller-owned transactions.

All security mutations lock the user row first. Recovery consumption, password
rotation, and deletion therefore serialize for both SQLite and PostgreSQL.
"""

from __future__ import annotations

import hmac
from typing import Any

from .connection import is_postgres
from .users import AppUser, get_user_by_id


def lock_user(connection: Any, user_id: int) -> AppUser | None:
    """Acquire a write lock before reading security-sensitive user state."""

    if is_postgres(connection):
        connection.execute("SELECT id FROM users WHERE id = ? FOR UPDATE", (user_id,)).fetchone()
    else:
        connection.execute("UPDATE users SET token_version = token_version WHERE id = ?", (user_id,))
    return get_user_by_id(connection, user_id)


def replace_password(connection: Any, user_id: int, password_hash: str) -> AppUser | None:
    """Rotate the hash and session version, invalidating outstanding resets."""

    connection.execute(
        "UPDATE users SET password_hash = ?, token_version = token_version + 1 WHERE id = ?",
        (password_hash, user_id),
    )
    connection.execute("DELETE FROM password_reset_requests WHERE user_id = ?", (user_id,))
    return get_user_by_id(connection, user_id)


def create_reset_request(
    connection: Any, user: AppUser, request_id: str, code_hash: str, expires_at: int
) -> None:
    """Keep only the latest recovery challenge for the already-locked user."""

    connection.execute("DELETE FROM password_reset_requests WHERE user_id = ?", (user.id,))
    connection.execute(
        """INSERT INTO password_reset_requests
           (request_id, user_id, code_hash, expires_at, attempts, token_version)
           VALUES (?, ?, ?, ?, 0, ?)""",
        (request_id, user.id, code_hash, expires_at, user.token_version),
    )


def get_reset_request(connection: Any, request_id: str) -> Any:
    return connection.execute(
        "SELECT * FROM password_reset_requests WHERE request_id = ?", (request_id,)
    ).fetchone()


def consume_reset_request(
    connection: Any, request_id: str, code_hash: str, password_hash: str | None, now: int
) -> bool:
    """Consume atomically, persisting wrong-guess budgets even on rejection."""

    initial = get_reset_request(connection, request_id)
    if initial is None:
        return False
    user = lock_user(connection, initial["user_id"])
    row = get_reset_request(connection, request_id)
    if (
        user is None
        or row is None
        or not user.has_password
        or row["expires_at"] <= now
        or row["attempts"] >= 5
        or row["token_version"] != user.token_version
    ):
        return False
    connection.execute(
        "UPDATE password_reset_requests SET attempts = attempts + 1 WHERE request_id = ?",
        (request_id,),
    )
    if not hmac.compare_digest(row["code_hash"], code_hash):
        return False
    if password_hash is None:
        return False
    replace_password(connection, user.id, password_hash)
    return True
