"""Transaction repository for the Finance API."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Transaction:
    """A financial transaction persisted in SQLite."""

    id: int
    user_id: int
    type: str
    category_id: Optional[int]
    category_name: Optional[str]
    amount: int
    note: Optional[str]
    asset_name: Optional[str]
    transaction_date: str


def _row_to_transaction(row: sqlite3.Row) -> Transaction:
    return Transaction(
        id=row["id"],
        user_id=row["user_id"],
        type=row["type"],
        category_id=row["category_id"],
        category_name=row["category_name"] if "category_name" in row.keys() else None,
        amount=row["amount"],
        note=row["note"],
        asset_name=row["asset_name"],
        transaction_date=row["transaction_date"],
    )


def create_transaction(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    type: str,
    category_id: int | None,
    amount: int,
    note: str | None,
    asset_name: str | None,
    transaction_date: str,
) -> Transaction:
    """Create and return a transaction for one user."""
    connection.row_factory = sqlite3.Row
    cursor = connection.execute(
        """
        INSERT INTO transactions (
            user_id, type, category_id, amount, note, asset_name, transaction_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, type, category_id, amount, note, asset_name, transaction_date),
    )
    connection.commit()
    tx_id = cursor.lastrowid
    transaction = get_transaction_by_id(connection, user_id=user_id, transaction_id=tx_id)
    if transaction is None:
        raise RuntimeError("Failed to create transaction")
    return transaction


def get_transaction_by_id(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    transaction_id: int,
) -> Transaction | None:
    """Fetch one transaction by ID with joined category name."""
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """
        SELECT t.id, t.user_id, t.type, t.category_id, c.name AS category_name,
               t.amount, t.note, t.asset_name, t.transaction_date
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.id = ? AND t.user_id = ?
        """,
        (transaction_id, user_id),
    ).fetchone()
    if row is None:
        return None
    return _row_to_transaction(row)


def list_transactions(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    transaction_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Transaction]:
    """List user transactions with optional filters."""
    connection.row_factory = sqlite3.Row

    query = """
        SELECT t.id, t.user_id, t.type, t.category_id, c.name AS category_name,
               t.amount, t.note, t.asset_name, t.transaction_date
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.user_id = ?
    """
    params: list = [user_id]

    if start_date:
        query += " AND t.transaction_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND t.transaction_date <= ?"
        params.append(end_date)
    if transaction_type:
        query += " AND t.type = ?"
        params.append(transaction_type)

    query += " ORDER BY t.transaction_date DESC, t.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = connection.execute(query, tuple(params)).fetchall()
    return [_row_to_transaction(r) for r in rows]


def list_transactions_in_range(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    start_date: str,
    end_date: str,
) -> list[Transaction]:
    """List transactions for report aggregations in ascending order."""
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT t.id, t.user_id, t.type, t.category_id, c.name AS category_name,
               t.amount, t.note, t.asset_name, t.transaction_date
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.user_id = ? AND t.transaction_date BETWEEN ? AND ?
        ORDER BY t.transaction_date ASC, t.id ASC
        """,
        (user_id, start_date, end_date),
    ).fetchall()
    return [_row_to_transaction(r) for r in rows]


def update_transaction(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    transaction_id: int,
    amount: int | None = None,
    category_id: int | None = None,
    transaction_date: str | None = None,
    note: str | None = None,
    asset_name: str | None = None,
) -> Transaction | None:
    """Update editable fields for an owned transaction."""
    current = get_transaction_by_id(connection, user_id=user_id, transaction_id=transaction_id)
    if current is None:
        return None

    new_amount = amount if amount is not None else current.amount
    new_cat_id = category_id if category_id is not None else current.category_id
    new_date = transaction_date if transaction_date is not None else current.transaction_date
    new_note = note if note is not None else current.note
    new_asset = asset_name if asset_name is not None else current.asset_name

    connection.execute(
        """
        UPDATE transactions
        SET amount = ?, category_id = ?, transaction_date = ?, note = ?, asset_name = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        (new_amount, new_cat_id, new_date, new_note, new_asset, transaction_id, user_id),
    )
    connection.commit()
    return get_transaction_by_id(connection, user_id=user_id, transaction_id=transaction_id)


def delete_transaction(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    transaction_id: int,
) -> bool:
    """Delete one owned transaction."""
    cursor = connection.execute(
        "DELETE FROM transactions WHERE id = ? AND user_id = ?",
        (transaction_id, user_id),
    )
    connection.commit()
    return cursor.rowcount > 0
