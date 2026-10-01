"""Service layer for saving and managing transactions."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from ..database.transactions import create_transaction, Transaction
from .quick_input_parser import QuickInputResult


class TransactionServiceError(ValueError):
    """Raised when a transaction cannot be saved."""


def save_quick_input_transaction(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    preview: QuickInputResult,
) -> Transaction:
    """Save a confirmed quick-input preview as a transaction."""
    if preview.error:
        raise TransactionServiceError(preview.error)
    if (
        preview.type is None
        or preview.category_name is None
        or preview.amount is None
        or preview.transaction_date is None
    ):
        raise TransactionServiceError("Preview belum lengkap dan belum bisa disimpan.")

    category_id = find_or_create_category(
        connection,
        user_id=user_id,
        category_type=preview.type,
        category_name=preview.category_name,
    )

    return create_transaction(
        connection,
        user_id=user_id,
        type=preview.type,
        category_id=category_id,
        amount=preview.amount,
        note=preview.note or None,
        asset_name=preview.asset_name,
        transaction_date=preview.transaction_date.isoformat(),
    )


def find_or_create_category(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    category_type: str,
    category_name: str,
) -> int:
    """Find category ID by name/type or create it if not found."""
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """
        SELECT id FROM categories
        WHERE user_id = ? AND type = ? AND LOWER(name) = LOWER(?)
        """,
        (user_id, category_type, category_name),
    ).fetchone()

    if row is not None:
        return row["id"]

    cursor = connection.execute(
        """
        INSERT INTO categories (user_id, type, name, aliases, is_default)
        VALUES (?, ?, ?, '', 0)
        """,
        (user_id, category_type, category_name),
    )
    connection.commit()
    return cursor.lastrowid
