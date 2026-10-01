"""SQLite schema initialization and migrations for the Finance API."""

from __future__ import annotations

import sqlite3


def init_db(connection: sqlite3.Connection) -> None:
    """Create database tables and apply migrations if needed."""

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT,
            first_name TEXT,
            username TEXT,
            timezone TEXT NOT NULL DEFAULT 'Asia/Jakarta',
            currency TEXT NOT NULL DEFAULT 'IDR',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            aliases TEXT NOT NULL DEFAULT '',
            is_default INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (user_id, type, name)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            category_id INTEGER,
            amount INTEGER NOT NULL,
            note TEXT,
            asset_name TEXT,
            transaction_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            balance INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            person_name TEXT NOT NULL,
            total_amount INTEGER NOT NULL,
            paid_amount INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS debt_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            debt_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            note TEXT,
            payment_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (debt_id) REFERENCES debts(id) ON DELETE CASCADE
        );
        """
    )

    # Check and add email & password_hash if migrating an existing users table
    cursor = connection.execute("PRAGMA table_info(users)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    if "email" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if "password_hash" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")

    connection.commit()
