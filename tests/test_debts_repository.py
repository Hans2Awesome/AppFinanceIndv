"""Tests for debt repository row locking, cash sync, and payment deletion."""

from __future__ import annotations

import sqlite3

from finance_core.db.connection import connect
from finance_core.db.debts import (
    create_debt,
    create_debt_payment,
    delete_debt_payment,
    get_debt_by_id,
    sync_derived_debt_transaction,
)
from finance_core.db.migrations import init_db
from finance_core.db.transactions import create_transaction


def setup_connection() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_db(connection)
    connection.execute(
        "INSERT INTO users (telegram_user_id, first_name) VALUES (1, 'Budi')"
    )
    return connection


def test_get_debt_by_id_for_update_is_ignored_on_sqlite() -> None:
    connection = setup_connection()
    debt = create_debt(
        connection,
        user_id=1,
        type="debt",
        person_name="Andi",
        total_amount=100_000,
        cash_synced=True,
    )

    found = get_debt_by_id(
        connection, user_id=1, debt_id=debt.id, for_update=True
    )
    assert found is not None
    assert found.id == debt.id


def test_sync_derived_debt_transaction_updates_cash_amount() -> None:
    connection = setup_connection()
    debt = create_debt(
        connection,
        user_id=1,
        type="debt",
        person_name="Andi",
        total_amount=100_000,
        cash_synced=True,
    )
    create_transaction(
        connection,
        user_id=1,
        type="income",
        category_id=None,
        amount=debt.total_amount,
        note="Pinjaman",
        asset_name=None,
        transaction_date="2026-01-01",
        source_key=f"debt:1:{debt.id}",
    )

    sync_derived_debt_transaction(
        connection, user_id=1, debt_id=debt.id, amount=50_000
    )

    row = connection.execute(
        "SELECT amount FROM transactions WHERE source_key = ?",
        (f"debt:1:{debt.id}",),
    ).fetchone()
    assert row["amount"] == 50_000


def test_delete_debt_payment_removes_cash_row_and_reduces_paid_amount() -> None:
    connection = setup_connection()
    debt = create_debt(
        connection,
        user_id=1,
        type="debt",
        person_name="Andi",
        total_amount=100_000,
        cash_synced=True,
    )
    payment = create_debt_payment(
        connection,
        debt_id=debt.id,
        user_id=1,
        amount=40_000,
        payment_date="2026-01-02",
    )
    create_transaction(
        connection,
        user_id=1,
        type="expense",
        category_id=None,
        amount=payment.amount,
        note="Bayar hutang",
        asset_name=None,
        transaction_date="2026-01-02",
        source_key=f"debt_payment:1:{payment.id}",
    )

    deleted = delete_debt_payment(
        connection, user_id=1, debt_id=debt.id, payment_id=payment.id
    )
    assert deleted is not None
    assert deleted.id == payment.id

    updated = get_debt_by_id(connection, user_id=1, debt_id=debt.id)
    assert updated is not None
    assert updated.paid_amount == 0
    assert updated.status == "active"

    cash_count = connection.execute(
        "SELECT COUNT(*) FROM transactions WHERE source_key = ?",
        (f"debt_payment:1:{payment.id}",),
    ).fetchone()[0]
    assert cash_count == 0


def test_delete_debt_payment_reverts_settled_status() -> None:
    connection = setup_connection()
    debt = create_debt(
        connection,
        user_id=1,
        type="debt",
        person_name="Andi",
        total_amount=50_000,
        cash_synced=False,
    )
    payment = create_debt_payment(
        connection,
        debt_id=debt.id,
        user_id=1,
        amount=50_000,
        payment_date="2026-01-02",
    )
    settled = get_debt_by_id(connection, user_id=1, debt_id=debt.id)
    assert settled is not None and settled.status == "settled"

    delete_debt_payment(
        connection, user_id=1, debt_id=debt.id, payment_id=payment.id
    )

    reverted = get_debt_by_id(connection, user_id=1, debt_id=debt.id)
    assert reverted is not None
    assert reverted.paid_amount == 0
    assert reverted.status == "active"