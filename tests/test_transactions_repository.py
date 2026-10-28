"""Tests for Bot04 transaction repository."""

from __future__ import annotations

import sqlite3

from finance_core.db.categories import seed_default_categories
from finance_core.db.connection import connect
from finance_core.db.migrations import init_db
from finance_core.db.transactions import (
    Transaction,
    count_transactions_by_type,
    create_transaction,
    delete_transaction,
    list_transactions,
    list_transactions_by_type,
    update_transaction,
)
from finance_core.db.users import get_or_create_user


def setup_connection() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_db(connection)
    return connection


def setup_user_with_categories(
    connection: sqlite3.Connection,
    telegram_user_id: int,
) -> tuple[int, int]:
    user = get_or_create_user(connection, telegram_user_id=telegram_user_id)
    seed_default_categories(connection, user.id)
    category_id = connection.execute(
        """
        SELECT id FROM categories
        WHERE user_id = ? AND type = 'expense' AND name = 'Makan & Minum'
        """,
        (user.id,),
    ).fetchone()[0]
    return user.id, category_id


def test_create_transaction_persists_and_returns_transaction() -> None:
    connection = setup_connection()
    user_id, category_id = setup_user_with_categories(connection, 796529359)

    transaction = create_transaction(
        connection,
        user_id=user_id,
        type="expense",
        category_id=category_id,
        amount=25000,
        note="kopi pagi",
        asset_name=None,
        transaction_date="2026-05-30",
    )

    assert transaction == Transaction(
        id=1,
        user_id=user_id,
        type="expense",
        category_id=category_id,
        amount=25000,
        note="kopi pagi",
        asset_name=None,
        transaction_date="2026-05-30",
        category_name="Makan & Minum",
    )
    row_count = connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert row_count == 1


def test_list_transactions_filters_by_user_and_date_range() -> None:
    connection = setup_connection()
    first_user_id, first_category_id = setup_user_with_categories(connection, 1)
    second_user_id, second_category_id = setup_user_with_categories(connection, 2)
    expected = create_transaction(
        connection,
        user_id=first_user_id,
        type="expense",
        category_id=first_category_id,
        amount=10000,
        note="inside range",
        asset_name=None,
        transaction_date="2026-05-15",
    )
    create_transaction(
        connection,
        user_id=first_user_id,
        type="expense",
        category_id=first_category_id,
        amount=20000,
        note="outside range",
        asset_name=None,
        transaction_date="2026-06-01",
    )
    create_transaction(
        connection,
        user_id=second_user_id,
        type="expense",
        category_id=second_category_id,
        amount=30000,
        note="other user",
        asset_name=None,
        transaction_date="2026-05-15",
    )

    transactions = list_transactions(
        connection,
        user_id=first_user_id,
        start_date="2026-05-01",
        end_date="2026-05-31",
    )

    assert transactions == [expected]


def test_list_transactions_by_type_filters_user_type_orders_newest_and_paginates() -> None:
    connection = setup_connection()
    user_id, category_id = setup_user_with_categories(connection, 1)
    other_user_id, other_category_id = setup_user_with_categories(connection, 2)

    expected_page_one: list[Transaction] = []
    expected_page_two: list[Transaction] = []
    for index in range(12):
        transaction = create_transaction(
            connection,
            user_id=user_id,
            type="income",
            category_id=None,
            amount=100_000 + index,
            note=f"income {index}",
            asset_name=None,
            transaction_date=f"2026-05-{index + 1:02d}",
        )
        if index >= 2:
            expected_page_one.append(transaction)
        else:
            expected_page_two.append(transaction)

    same_day_older = create_transaction(
        connection,
        user_id=user_id,
        type="income",
        category_id=None,
        amount=50_000,
        note="same day older id",
        asset_name=None,
        transaction_date="2026-05-12",
    )
    same_day_newer = create_transaction(
        connection,
        user_id=user_id,
        type="income",
        category_id=None,
        amount=60_000,
        note="same day newer id",
        asset_name=None,
        transaction_date="2026-05-12",
    )
    create_transaction(
        connection,
        user_id=user_id,
        type="expense",
        category_id=category_id,
        amount=25_000,
        note="wrong type",
        asset_name=None,
        transaction_date="2026-05-13",
    )
    create_transaction(
        connection,
        user_id=user_id,
        type="investment",
        category_id=None,
        amount=75_000,
        note="wrong type investment",
        asset_name="BTC",
        transaction_date="2026-05-14",
    )
    create_transaction(
        connection,
        user_id=other_user_id,
        type="income",
        category_id=other_category_id,
        amount=999_000,
        note="other user",
        asset_name=None,
        transaction_date="2026-05-15",
    )

    page_one = list_transactions_by_type(
        connection,
        user_id=user_id,
        transaction_type="income",
        limit=10,
        offset=0,
    )
    page_two = list_transactions_by_type(
        connection,
        user_id=user_id,
        transaction_type="income",
        limit=10,
        offset=10,
    )
    total = count_transactions_by_type(connection, user_id=user_id, transaction_type="income")

    assert page_one == [same_day_newer, same_day_older, *reversed(expected_page_one[-8:])]
    assert page_two == list(reversed(expected_page_two + expected_page_one[:2]))
    assert total == 14


def test_update_transaction_changes_only_owned_transaction_fields() -> None:
    connection = setup_connection()
    user_id, category_id = setup_user_with_categories(connection, 1)
    other_user_id, other_category_id = setup_user_with_categories(connection, 2)
    transaction = create_transaction(
        connection,
        user_id=user_id,
        type="expense",
        category_id=category_id,
        amount=10000,
        note="old note",
        asset_name=None,
        transaction_date="2026-05-15",
    )
    other_transaction = create_transaction(
        connection,
        user_id=other_user_id,
        type="expense",
        category_id=other_category_id,
        amount=99999,
        note="do not touch",
        asset_name=None,
        transaction_date="2026-05-15",
    )

    updated = update_transaction(
        connection,
        user_id=user_id,
        transaction_id=transaction.id,
        amount=15000,
        category_id=category_id,
        transaction_date="2026-05-16",
        note="updated note",
    )
    blocked_update = update_transaction(
        connection,
        user_id=user_id,
        transaction_id=other_transaction.id,
        amount=1,
        category_id=category_id,
        transaction_date="2026-05-17",
        note="leak attempt",
    )

    assert updated == Transaction(
        id=transaction.id,
        user_id=user_id,
        type="expense",
        category_id=category_id,
        amount=15000,
        note="updated note",
        asset_name=None,
        transaction_date="2026-05-16",
        category_name="Makan & Minum",
    )
    assert blocked_update is None


def test_delete_transaction_removes_only_owned_transaction() -> None:
    connection = setup_connection()
    user_id, category_id = setup_user_with_categories(connection, 1)
    other_user_id, other_category_id = setup_user_with_categories(connection, 2)
    transaction = create_transaction(
        connection,
        user_id=user_id,
        type="expense",
        category_id=category_id,
        amount=10000,
        note="delete me",
        asset_name=None,
        transaction_date="2026-05-15",
    )
    other_transaction = create_transaction(
        connection,
        user_id=other_user_id,
        type="expense",
        category_id=other_category_id,
        amount=20000,
        note="keep me",
        asset_name=None,
        transaction_date="2026-05-15",
    )

    assert delete_transaction(connection, user_id=user_id, transaction_id=other_transaction.id) is False
    assert delete_transaction(connection, user_id=user_id, transaction_id=transaction.id) is True

    assert list_transactions(
        connection,
        user_id=user_id,
        start_date="2026-05-01",
        end_date="2026-05-31",
    ) == []
    assert list_transactions(
        connection,
        user_id=other_user_id,
        start_date="2026-05-01",
        end_date="2026-05-31",
    ) == [other_transaction]


def test_repository_writes_are_rolled_back_without_a_commit(tmp_path) -> None:
    from finance_core.db.connection import connect, transaction
    from finance_core.db.migrations import init_db
    from finance_core.db.transactions import create_transaction, list_transactions
    from finance_core.db.users import get_or_create_user

    path = str(tmp_path / "unit-of-work.sqlite3")
    connection = connect(path)
    init_db(connection)
    user = get_or_create_user(connection, telegram_user_id=123)
    connection.commit()

    create_transaction(
        connection,
        user_id=user.id,
        type="expense",
        category_id=None,
        amount=1000,
        note=None,
        asset_name=None,
        transaction_date="2026-05-30",
    )
    connection.rollback()
    assert list_transactions(connection, user_id=user.id) == []

    with transaction(connection):
        create_transaction(
            connection,
            user_id=user.id,
            type="expense",
            category_id=None,
            amount=1000,
            note=None,
            asset_name=None,
            transaction_date="2026-05-30",
        )

    assert len(list_transactions(connection, user_id=user.id)) == 1
    connection.close()


def test_transaction_context_manager_rolls_back_on_exception(tmp_path) -> None:
    import pytest

    from finance_core.db.connection import connect, transaction
    from finance_core.db.migrations import init_db
    from finance_core.db.transactions import create_transaction, list_transactions
    from finance_core.db.users import get_or_create_user

    connection = connect(str(tmp_path / "rollback.sqlite3"))
    init_db(connection)
    user = get_or_create_user(connection, telegram_user_id=456)

    with pytest.raises(RuntimeError):
        with transaction(connection):
            create_transaction(
                connection,
                user_id=user.id,
                type="expense",
                category_id=None,
                amount=1000,
                note=None,
                asset_name=None,
                transaction_date="2026-05-30",
            )
            raise RuntimeError("boom")

    assert list_transactions(connection, user_id=user.id) == []
    connection.close()
