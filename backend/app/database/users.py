"""User repository for the Finance API."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from .categories import seed_default_categories


@dataclass(frozen=True)
class AppUser:
    """An application user persisted in SQLite."""

    id: int
    email: str | None
    password_hash: str | None
    first_name: str | None
    username: str | None
    telegram_user_id: int | None
    timezone: str
    currency: str
    created_at: str | None = None


def _row_to_app_user(row: sqlite3.Row) -> AppUser:
    return AppUser(
        id=row["id"],
        email=row["email"] if "email" in row.keys() else None,
        password_hash=row["password_hash"] if "password_hash" in row.keys() else None,
        first_name=row["first_name"],
        username=row["username"],
        telegram_user_id=row["telegram_user_id"],
        timezone=row["timezone"],
        currency=row["currency"],
        created_at=row["created_at"] if "created_at" in row.keys() else None,
    )


def get_user_by_email(connection: sqlite3.Connection, email: str) -> AppUser | None:
    """Fetch user by email."""
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """
        SELECT id, email, password_hash, first_name, username, telegram_user_id, timezone, currency, created_at
        FROM users
        WHERE email = ?
        """,
        (email.strip().lower(),),
    ).fetchone()
    if row is None:
        return None
    return _row_to_app_user(row)


def get_user_by_id(connection: sqlite3.Connection, user_id: int) -> AppUser | None:
    """Fetch user by id."""
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """
        SELECT id, email, password_hash, first_name, username, telegram_user_id, timezone, currency, created_at
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_app_user(row)


def create_mobile_user(
    connection: sqlite3.Connection,
    *,
    email: str,
    password_hash: str,
    first_name: str | None = None,
    timezone: str = "Asia/Jakarta",
    currency: str = "IDR",
) -> AppUser:
    """Create a new mobile user and seed their default categories."""
    connection.row_factory = sqlite3.Row
    cursor = connection.execute(
        """
        INSERT INTO users (email, password_hash, first_name, timezone, currency)
        VALUES (?, ?, ?, ?, ?)
        """,
        (email.strip().lower(), password_hash, first_name, timezone, currency),
    )
    user_id = cursor.lastrowid
    connection.commit()

    # Seed standard categories for this new user
    seed_default_categories(connection, user_id)

    user = get_user_by_id(connection, user_id)
    if user is None:
        raise RuntimeError("Failed to create mobile user")
    return user
