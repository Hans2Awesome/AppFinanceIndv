"""Category repository and seeders for the Finance API."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from ..models.domain import TransactionType


@dataclass(frozen=True)
class Category:
    id: int
    user_id: int
    type: str
    name: str
    aliases: str
    is_default: int


DEFAULT_CATEGORIES: tuple[tuple[TransactionType, str, str], ...] = (
    (TransactionType.INCOME, "Gaji", "gaji,salary"),
    (TransactionType.INCOME, "Bonus", "bonus"),
    (TransactionType.INCOME, "Freelance", "freelance,project"),
    (TransactionType.INCOME, "Bisnis", "bisnis,jualan,usaha"),
    (TransactionType.INCOME, "Hadiah", "hadiah,gift"),
    (TransactionType.INCOME, "Lainnya", "lainnya,lain"),
    (
        TransactionType.EXPENSE,
        "Makan & Minum",
        "makan,minum,kopi,sarapan,makan siang,makan malam",
    ),
    (
        TransactionType.EXPENSE,
        "Transportasi",
        "transport,transportasi,gojek,grab,bensin,parkir",
    ),
    (TransactionType.EXPENSE, "Belanja", "belanja,shopping,beli"),
    (TransactionType.EXPENSE, "Tagihan", "tagihan,listrik,air,internet,pulsa"),
    (TransactionType.EXPENSE, "Hiburan", "hiburan,nonton,game"),
    (TransactionType.EXPENSE, "Kesehatan", "kesehatan,dokter,obat"),
    (TransactionType.EXPENSE, "Pendidikan", "pendidikan,sekolah,kursus,buku"),
    (TransactionType.EXPENSE, "Lainnya", "lainnya,lain"),
    (TransactionType.INVESTMENT, "Saham", "saham,stock,bbca,bmri"),
    (
        TransactionType.INVESTMENT,
        "Crypto",
        "crypto,kripto,btc,eth,bitcoin,ethereum",
    ),
    (TransactionType.INVESTMENT, "Reksadana", "reksadana,rd"),
    (TransactionType.INVESTMENT, "Emas", "emas,gold,antam"),
    (TransactionType.INVESTMENT, "Deposito", "deposito"),
    (TransactionType.INVESTMENT, "Lainnya", "investasi,lainnya,lain"),
)


def seed_default_categories(connection: sqlite3.Connection, user_id: int) -> None:
    """Seed all default categories for one user without creating duplicates."""
    connection.executemany(
        """
        INSERT OR IGNORE INTO categories (user_id, type, name, aliases, is_default)
        VALUES (?, ?, ?, ?, 1)
        """,
        [
            (user_id, transaction_type.value, name, aliases)
            for transaction_type, name, aliases in DEFAULT_CATEGORIES
        ],
    )
    connection.commit()


def list_categories(
    connection: sqlite3.Connection,
    user_id: int,
    category_type: str | None = None,
) -> list[Category]:
    """List categories for a user, optionally filtered by type."""
    connection.row_factory = sqlite3.Row
    if category_type:
        rows = connection.execute(
            """
            SELECT id, user_id, type, name, aliases, is_default
            FROM categories
            WHERE user_id = ? AND type = ?
            ORDER BY is_default DESC, name ASC
            """,
            (user_id, category_type),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT id, user_id, type, name, aliases, is_default
            FROM categories
            WHERE user_id = ?
            ORDER BY type ASC, is_default DESC, name ASC
            """,
            (user_id,),
        ).fetchall()

    return [
        Category(
            id=r["id"],
            user_id=r["user_id"],
            type=r["type"],
            name=r["name"],
            aliases=r["aliases"],
            is_default=r["is_default"],
        )
        for r in rows
    ]


def get_category_names_map(connection: sqlite3.Connection, user_id: int) -> dict[int, str]:
    """Return a mapping of category ID -> category name for a user."""
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT id, name FROM categories WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {r["id"]: r["name"] for r in rows}


def create_category(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    type: str,
    name: str,
    aliases: str = "",
) -> Category:
    """Create a custom category for a user."""
    connection.row_factory = sqlite3.Row
    cursor = connection.execute(
        """
        INSERT INTO categories (user_id, type, name, aliases, is_default)
        VALUES (?, ?, ?, ?, 0)
        """,
        (user_id, type, name.strip(), aliases.strip()),
    )
    connection.commit()
    return Category(
        id=cursor.lastrowid,
        user_id=user_id,
        type=type,
        name=name.strip(),
        aliases=aliases.strip(),
        is_default=0,
    )


def delete_category(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    category_id: int,
) -> bool:
    """Delete a custom category."""
    cursor = connection.execute(
        "DELETE FROM categories WHERE id = ? AND user_id = ?",
        (category_id, user_id),
    )
    connection.commit()
    return cursor.rowcount > 0
