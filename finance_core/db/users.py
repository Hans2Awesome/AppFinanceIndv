"""User repository shared by the API and the Telegram bot."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .categories import seed_default_categories
from .connection import transaction


@dataclass(frozen=True)
class AppUser:
    """An application user persisted in SQLite.

    Mobile users are identified by ``email``, Telegram users by
    ``telegram_user_id``. Both columns are unique but nullable.
    """

    id: int
    email: str | None = None
    password_hash: str | None = None
    first_name: str | None = None
    username: str | None = None
    telegram_user_id: int | None = None
    timezone: str = "Asia/Jakarta"
    currency: str = "IDR"
    token_version: int = 0
    created_at: str | None = None


# Alias kept for the Telegram bot's existing imports and tests.
User = AppUser

_USER_COLUMNS = (
    "id, email, password_hash, first_name, username, "
    "telegram_user_id, timezone, currency, token_version, created_at"
)


def _row_to_user(row: sqlite3.Row) -> AppUser:
    keys = row.keys()
    return AppUser(
        id=row["id"],
        email=row["email"] if "email" in keys else None,
        password_hash=row["password_hash"] if "password_hash" in keys else None,
        first_name=row["first_name"],
        username=row["username"],
        telegram_user_id=row["telegram_user_id"],
        timezone=row["timezone"],
        currency=row["currency"],
        token_version=row["token_version"] if "token_version" in keys else 0,
        created_at=row["created_at"] if "created_at" in keys else None,
    )


def get_user_by_id(connection: sqlite3.Connection, user_id: int) -> AppUser | None:
    """Fetch a user by primary key."""

    row = connection.execute(
        f"SELECT {_USER_COLUMNS} FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return None if row is None else _row_to_user(row)


def get_user_by_email(connection: sqlite3.Connection, email: str) -> AppUser | None:
    """Fetch a mobile user by email."""

    row = connection.execute(
        f"SELECT {_USER_COLUMNS} FROM users WHERE email = ?",
        (email.strip().lower(),),
    ).fetchone()
    return None if row is None else _row_to_user(row)


def get_user_by_telegram_id(
    connection: sqlite3.Connection,
    telegram_user_id: int,
) -> AppUser | None:
    """Fetch a Telegram user by their Telegram ID."""

    row = connection.execute(
        f"SELECT {_USER_COLUMNS} FROM users WHERE telegram_user_id = ?",
        (telegram_user_id,),
    ).fetchone()
    return None if row is None else _row_to_user(row)


def create_mobile_user(
    connection: sqlite3.Connection,
    *,
    email: str,
    password_hash: str,
    first_name: str | None = None,
    timezone: str = "Asia/Jakarta",
    currency: str = "IDR",
) -> AppUser:
    """Create a mobile user and seed their default categories."""

    with transaction(connection):
        cursor = connection.execute(
            """
            INSERT INTO users (email, password_hash, first_name, timezone, currency)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email.strip().lower(), password_hash, first_name, timezone, currency),
        )

        user_id = cursor.lastrowid
        seed_default_categories(connection, user_id)

    user = get_user_by_id(connection, user_id)
    if user is None:
        raise RuntimeError("Failed to create mobile user")
    return user


def get_or_create_user(
    connection: sqlite3.Connection,
    *,
    telegram_user_id: int,
    first_name: str | None = None,
    username: str | None = None,
    timezone: str = "Asia/Jakarta",
    currency: str = "IDR",
) -> AppUser:
    """Return the existing Telegram user or create it once."""

    existing_user = get_user_by_telegram_id(connection, telegram_user_id)
    if existing_user is not None:
        return existing_user

    connection.execute(
        """
        INSERT INTO users (telegram_user_id, first_name, username, timezone, currency)
        VALUES (?, ?, ?, ?, ?)
        """,
        (telegram_user_id, first_name, username, timezone, currency),
    )

    created_user = get_user_by_telegram_id(connection, telegram_user_id)
    if created_user is None:
        raise RuntimeError("Failed to create user")
    return created_user


def update_user_profile(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    first_name: str | None = None,
    timezone: str | None = None,
    currency: str | None = None,
) -> AppUser | None:
    """Update the editable profile fields of one user."""

    current = get_user_by_id(connection, user_id)
    if current is None:
        return None

    connection.execute(
        """
        UPDATE users
        SET first_name = ?, timezone = ?, currency = ?
        WHERE id = ?
        """,
        (
            first_name if first_name is not None else current.first_name,
            timezone if timezone is not None else current.timezone,
            currency if currency is not None else current.currency,
            user_id,
        ),
    )
    return get_user_by_id(connection, user_id)


def bump_token_version(connection: sqlite3.Connection, *, user_id: int) -> AppUser | None:
    """Invalidate every token previously issued to one user."""

    with transaction(connection):
        cursor = connection.execute(
            "UPDATE users SET token_version = token_version + 1 WHERE id = ?",
            (user_id,),
        )
        if cursor.rowcount == 0:
            return None
    return get_user_by_id(connection, user_id)


def create_telegram_link_code(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    code: str,
    ttl_minutes: int = 10,
) -> str:
    """Buat kode tautan satu pakai untuk menghubungkan akun Mobile dengan Telegram."""

    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    ).strftime("%Y-%m-%d %H:%M:%S")
    connection.execute(
        """
        INSERT INTO telegram_link_codes (user_id, code, expires_at, used)
        VALUES (?, ?, ?, 0)
        """,
        (user_id, code, expires_at),
    )
    return code


def consume_telegram_link_code(
    connection: sqlite3.Connection,
    *,
    code: str,
) -> int | None:
    """Verifikasi dan konsumsi kode tautan. Mengembalikan user_id atau None jika tidak valid/kedaluwarsa."""

    row = connection.execute(
        """
        SELECT id, user_id, expires_at, used
        FROM telegram_link_codes
        WHERE code = ? AND used = 0
        """,
        (code,),
    ).fetchone()
    if row is None:
        return None
    if row["expires_at"] < datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"):
        return None
    connection.execute(
        "UPDATE telegram_link_codes SET used = 1 WHERE id = ?",
        (row["id"],),
    )
    return int(row["user_id"])


def link_telegram_account(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    telegram_user_id: int,
) -> AppUser:
    """Gabungkan identitas Telegram ke baris akun Mobile utama.

    Jika ``telegram_user_id`` sudah terdaftar pada baris bot lain (dibuat via
    ``/start``), semua transaksi, utang, kategori, dan jadwal berulang dipindahkan
    ke ``user_id`` utama, baris bot dihapus, lalu ``telegram_user_id`` diisi pada
    baris utama.
    """

    connection.row_factory = sqlite3.Row

    # Cek apakah telegram_user_id sudah digunakan oleh baris lain (biasanya bot).
    bot_user = get_user_by_telegram_id(connection, telegram_user_id)
    if bot_user is not None and bot_user.id != user_id:
        bot_id = bot_user.id

        # Petakan kategori bot ke kategori owner yang setara (type + name),
        # agar UNIQUE (user_id, type, name) tidak bentrok saat digabung.
        bot_categories = connection.execute(
            "SELECT id, type, name, aliases, is_default FROM categories WHERE user_id = ?",
            (bot_id,),
        ).fetchall()
        for category in bot_categories:
            owner_category = connection.execute(
                "SELECT id FROM categories WHERE user_id = ? AND type = ? AND name = ?",
                (user_id, category["type"], category["name"]),
            ).fetchone()
            if owner_category is None:
                cursor = connection.execute(
                    """
                    INSERT INTO categories (user_id, type, name, aliases, is_default)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        category["type"],
                        category["name"],
                        category["aliases"],
                        category["is_default"],
                    ),
                )
                new_category_id = cursor.lastrowid
            else:
                new_category_id = owner_category["id"]
            connection.execute(
                "UPDATE transactions SET category_id = ? WHERE category_id = ?",
                (new_category_id, category["id"]),
            )
            connection.execute(
                "UPDATE recurring_transactions SET category_id = ? WHERE category_id = ?",
                (new_category_id, category["id"]),
            )

        # Pindahkan semua data milik bot ke akun utama, lalu hapus kategori bot.
        connection.execute(
            "UPDATE transactions SET user_id = ? WHERE user_id = ?", (user_id, bot_id)
        )
        connection.execute(
            "UPDATE debts SET user_id = ? WHERE user_id = ?", (user_id, bot_id)
        )
        connection.execute(
            "UPDATE recurring_transactions SET user_id = ? WHERE user_id = ?",
            (user_id, bot_id),
        )
        connection.execute("DELETE FROM categories WHERE user_id = ?", (bot_id,))
        # Hapus baris bot duplikat.
        connection.execute("DELETE FROM users WHERE id = ?", (bot_id,))

    connection.execute(
        """
        UPDATE users
        SET telegram_user_id = ?
        WHERE id = ?
        """,
        (telegram_user_id, user_id),
    )
    return get_user_by_id(connection, user_id)


def get_telegram_link_code(
    connection: sqlite3.Connection,
    *,
    code: str,
) -> int | None:
    """Cek kode tautan tanpa mengonsumsi (digunakan untuk debug/tes)."""

    row = connection.execute(
        """
        SELECT user_id, expires_at, used
        FROM telegram_link_codes
        WHERE code = ?
        """,
        (code,),
    ).fetchone()
    if row is None:
        return None
    if row["used"] == 1:
        return None
    if row["expires_at"] < datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"):
        return None
    return int(row["user_id"])
