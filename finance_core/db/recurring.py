"""Recurring transaction schedules and the runner that materializes them."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date

from finance_core.recurring import next_after
from finance_core.timezones import today_in

from .connection import transaction
from .transactions import create_transaction

logger = logging.getLogger(__name__)

MAX_OCCURRENCES_PER_RUN = 1000

_SELECT = """
    SELECT r.id, r.user_id, r.type, r.category_id, c.name AS category_name,
           r.amount, r.note, r.asset_name, r.frequency, r.day_of_week,
           r.day_of_month, r.start_date, r.next_run_date, r.last_run_date,
           r.is_active, r.created_at, r.updated_at
    FROM recurring_transactions r
    LEFT JOIN categories c ON c.id = r.category_id
"""


@dataclass(frozen=True)
class RecurringTransaction:
    """A schedule that creates one transaction per due date."""

    id: int
    user_id: int
    type: str
    category_id: int | None
    amount: int
    note: str | None
    asset_name: str | None
    frequency: str
    day_of_week: int | None
    day_of_month: int | None
    start_date: str
    next_run_date: str
    last_run_date: str | None
    is_active: int
    category_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class RecurringRun:
    """One generated occurrence, returned so callers can log or assert."""

    recurring_id: int
    transaction_id: int
    due_date: str


def _row_to_recurring(row: sqlite3.Row) -> RecurringTransaction:
    keys = row.keys()
    return RecurringTransaction(
        id=row["id"],
        user_id=row["user_id"],
        type=row["type"],
        category_id=row["category_id"],
        amount=row["amount"],
        note=row["note"],
        asset_name=row["asset_name"],
        frequency=row["frequency"],
        day_of_week=row["day_of_week"],
        day_of_month=row["day_of_month"],
        start_date=row["start_date"],
        next_run_date=row["next_run_date"],
        last_run_date=row["last_run_date"],
        is_active=row["is_active"],
        category_name=row["category_name"] if "category_name" in keys else None,
        created_at=row["created_at"] if "created_at" in keys else None,
        updated_at=row["updated_at"] if "updated_at" in keys else None,
    )


def create_recurring(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    type: str,
    category_id: int | None,
    amount: int,
    note: str | None,
    asset_name: str | None,
    frequency: str,
    day_of_week: int | None,
    day_of_month: int | None,
    start_date: str,
    next_run_date: str,
    is_active: bool = True,
) -> RecurringTransaction:
    """Insert one schedule and return it."""

    cursor = connection.execute(
        """
        INSERT INTO recurring_transactions (
            user_id, type, category_id, amount, note, asset_name, frequency,
            day_of_week, day_of_month, start_date, next_run_date, is_active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            type,
            category_id,
            amount,
            note,
            asset_name,
            frequency,
            day_of_week,
            day_of_month,
            start_date,
            next_run_date,
            1 if is_active else 0,
        ),
    )
    recurring = get_recurring(
        connection,
        user_id=user_id,
        recurring_id=int(cursor.lastrowid),
    )
    if recurring is None:
        raise RuntimeError("Failed to create recurring transaction")
    return recurring


def get_recurring(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    recurring_id: int,
) -> RecurringTransaction | None:
    """Fetch one owned schedule."""

    row = connection.execute(
        _SELECT + " WHERE r.id = ? AND r.user_id = ?",
        (recurring_id, user_id),
    ).fetchone()
    return None if row is None else _row_to_recurring(row)


def list_recurring(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    active_only: bool = False,
) -> list[RecurringTransaction]:
    """List schedules, soonest due first."""

    query = _SELECT + " WHERE r.user_id = ?"
    params: list = [user_id]
    if active_only:
        query += " AND r.is_active = 1"
    query += " ORDER BY r.is_active DESC, r.next_run_date ASC, r.id ASC"

    rows = connection.execute(query, tuple(params)).fetchall()
    return [_row_to_recurring(row) for row in rows]


def update_recurring(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    recurring_id: int,
    type: str,
    category_id: int | None,
    amount: int,
    note: str | None,
    asset_name: str | None,
    frequency: str,
    day_of_week: int | None,
    day_of_month: int | None,
    start_date: str,
    next_run_date: str,
    is_active: bool,
) -> RecurringTransaction | None:
    """Replace every editable field of an owned schedule."""

    if get_recurring(connection, user_id=user_id, recurring_id=recurring_id) is None:
        return None

    connection.execute(
        """
        UPDATE recurring_transactions
        SET type = ?, category_id = ?, amount = ?, note = ?, asset_name = ?,
            frequency = ?, day_of_week = ?, day_of_month = ?, start_date = ?,
            next_run_date = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        (
            type,
            category_id,
            amount,
            note,
            asset_name,
            frequency,
            day_of_week,
            day_of_month,
            start_date,
            next_run_date,
            1 if is_active else 0,
            recurring_id,
            user_id,
        ),
    )
    return get_recurring(connection, user_id=user_id, recurring_id=recurring_id)


def delete_recurring(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    recurring_id: int,
) -> bool:
    """Delete one owned schedule. Generated transactions stay in place."""

    cursor = connection.execute(
        "DELETE FROM recurring_transactions WHERE id = ? AND user_id = ?",
        (recurring_id, user_id),
    )
    return cursor.rowcount > 0


def run_due_recurring(
    connection: sqlite3.Connection,
    *,
    today_by_timezone=today_in,
) -> list[RecurringRun]:
    """Create every missed occurrence up to each user's local today.

    Each schedule is processed inside its own SQLite transaction, so a crash
    cannot leave a generated transaction without advancing ``next_run_date``.
    The unique ``transactions.source_key`` index is the second guard against
    duplicates if two processes ever run at the same time.
    """

    rows = connection.execute(
        """
        SELECT r.id, r.user_id, r.type, r.category_id, r.amount, r.note,
               r.asset_name, r.frequency, r.day_of_week, r.day_of_month,
               r.start_date, r.next_run_date, r.last_run_date, r.is_active,
               u.timezone
        FROM recurring_transactions r
        JOIN users u ON u.id = r.user_id
        WHERE r.is_active = 1
        ORDER BY r.next_run_date ASC, r.id ASC
        """
    ).fetchall()

    runs: list[RecurringRun] = []

    for row in rows:
        due = date.fromisoformat(row["next_run_date"])
        today = today_by_timezone(row["timezone"])
        if due > today:
            continue

        processed_for_schedule = 0
        schedule_runs: list[RecurringRun] = []
        try:
            with transaction(connection):
                while due <= today and processed_for_schedule < MAX_OCCURRENCES_PER_RUN:
                    processed_for_schedule += 1
                    source_key = f"recurring:{row['user_id']}:{row['id']}:{due.isoformat()}"
                    exists = connection.execute(
                        "SELECT 1 FROM transactions WHERE source_key = ?",
                        (source_key,),
                    ).fetchone()

                    if exists is None:
                        created = create_transaction(
                            connection,
                            user_id=row["user_id"],
                            type=row["type"],
                            category_id=row["category_id"],
                            amount=row["amount"],
                            note=row["note"],
                            asset_name=row["asset_name"],
                            transaction_date=due.isoformat(),
                            source_key=source_key,
                        )
                        schedule_runs.append(
                            RecurringRun(
                                recurring_id=row["id"],
                                transaction_id=created.id,
                                due_date=due.isoformat(),
                            )
                        )
                    following = next_after(
                        due,
                        row["frequency"],
                        row["day_of_week"],
                        row["day_of_month"],
                    )
                    connection.execute(
                        """
                        UPDATE recurring_transactions
                        SET next_run_date = ?, last_run_date = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (following.isoformat(), due.isoformat(), row["id"]),
                    )
                    due = following
        except sqlite3.IntegrityError:
            logger.exception("Recurring schedule %s skipped after an integrity error", row["id"])
        else:
            runs.extend(schedule_runs)

        if processed_for_schedule >= MAX_OCCURRENCES_PER_RUN and due <= today:
            logger.warning(
                "Recurring schedule %s hit the per-run cap; remaining occurrences wait for the next tick",
                row["id"],
            )

    return runs