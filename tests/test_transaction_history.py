"""Transaction history, audit snapshots, and caller-owned transaction boundaries."""

from __future__ import annotations

import os
import sqlite3
import threading
import time
import uuid
from datetime import date, datetime, timedelta
from urllib.parse import quote

import pytest

from bot04.bot.handlers_transactions import (
    CALLBACK_TRANSACTION_DELETE_CONFIRM_PREFIX,
    CALLBACK_TRANSACTION_EDIT_PREFIX,
    handle_transaction_edit_text,
    handle_transactions_callback,
)
from bot04.services.pending_store import PendingConfirmationStore
from finance_core.db.connection import (
    close_pools,
    connect,
    connect_url,
    is_postgres,
)
from finance_core.db.connection import (
    transaction as db_transaction,
)
from finance_core.db.debts import (
    create_debt,
    create_debt_payment,
    delete_debt,
    delete_debt_payment,
    sync_derived_debt_transaction,
)
from finance_core.db.migrations import (
    SCHEMA_VERSION,
    current_version,
    run_migrations,
)
from finance_core.db.recurring import create_recurring, run_due_recurring
from finance_core.db.transactions import (
    create_transaction,
    delete_transaction,
    get_transaction_by_id,
    list_transaction_history,
    list_transactions,
    update_transaction,
)
from finance_core.db.users import (
    create_mobile_user,
    get_or_create_user,
    get_user_by_id,
    get_user_by_telegram_id,
    link_telegram_account,
)

POSTGRES_URL = os.getenv("POSTGRES_TEST_URL")
DIALECTS = ["sqlite"] + (["postgres"] if POSTGRES_URL else [])

HISTORY_KEYS = {
    "id",
    "transaction_id",
    "action",
    "source",
    "reason",
    "before",
    "after",
    "created_at",
}
SNAPSHOT_KEYS = {
    "id",
    "type",
    "category_id",
    "category_name",
    "amount",
    "note",
    "asset_name",
    "transaction_date",
    "source_key",
}


def _make_postgres_url(schema: str) -> str:
    separator = "&" if "?" in POSTGRES_URL else "?"
    return f"{POSTGRES_URL}{separator}options={quote(f'-c search_path={schema}')}"


@pytest.fixture(params=DIALECTS)
def database(request, tmp_path):
    """One migrated database per test, either SQLite or an isolated PG schema."""

    if request.param == "sqlite":
        path = str(tmp_path / "history.sqlite3")
        connection = connect(path)
        try:
            run_migrations(connection)
        finally:
            connection.close()
        yield {"dialect": "sqlite", "path": path}
        return

    psycopg = pytest.importorskip("psycopg")
    schema = f"t_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(POSTGRES_URL, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{schema}"')

    url = _make_postgres_url(schema)
    connection = connect_url(url)
    try:
        run_migrations(connection)
    finally:
        connection.close()

    try:
        yield {"dialect": "postgres", "url": url, "schema": schema, "psycopg": psycopg}
    finally:
        close_pools()
        with psycopg.connect(POSTGRES_URL, autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


@pytest.fixture
def connection(database):
    connection = _open(database)
    try:
        yield connection
    finally:
        connection.close()


def _open(database):
    if database["dialect"] == "sqlite":
        return connect(database["path"])
    return connect_url(database["url"])


def _create_user(connection, email: str = "owner@example.com"):
    return create_mobile_user(connection, email=email, password_hash="test-hash")


def _category_id(connection, user_id: int, name: str = "Makan & Minum") -> int:
    row = connection.execute(
        "SELECT id FROM categories WHERE user_id = ? AND type = 'expense' AND name = ?",
        (user_id, name),
    ).fetchone()
    assert row is not None
    return int(row[0])


def _add_expense(
    connection,
    *,
    user_id: int,
    amount: int = 25_000,
    note: str | None = "kopi",
    asset_name: str | None = "BCA",
    transaction_date: str = "2026-11-02",
):
    return create_transaction(
        connection,
        user_id=user_id,
        type="expense",
        category_id=_category_id(connection, user_id),
        amount=amount,
        note=note,
        asset_name=asset_name,
        transaction_date=transaction_date,
    )


def _database_error(connection):
    if is_postgres(connection):
        import psycopg

        return psycopg.Error
    return sqlite3.IntegrityError


def test_update_history_has_exact_contract_and_snapshot_shape(connection) -> None:
    user = _create_user(connection)
    transaction = _add_expense(connection, user_id=user.id)
    transport = _category_id(connection, user.id, "Transportasi")

    updated = update_transaction(
        connection,
        user_id=user.id,
        transaction_id=transaction.id,
        amount=30_000,
        category_id=transport,
        transaction_date="2026-11-03",
        note="kopi sore",
        asset_name="Mandiri",
        source="api",
        reason="direct",
    )
    assert updated is not None

    history = list_transaction_history(
        connection, user_id=user.id, transaction_id=transaction.id
    )
    assert len(history) == 1
    entry = history[0]
    assert set(entry) == HISTORY_KEYS
    assert "user_id" not in entry
    assert entry["transaction_id"] == transaction.id
    assert entry["action"] == "update"
    assert entry["source"] == "api"
    assert entry["reason"] == "direct"

    assert set(entry["before"]) == SNAPSHOT_KEYS
    assert set(entry["after"]) == SNAPSHOT_KEYS
    assert entry["before"] == {
        "id": transaction.id,
        "type": "expense",
        "category_id": transaction.category_id,
        "category_name": "Makan & Minum",
        "amount": 25_000,
        "note": "kopi",
        "asset_name": "BCA",
        "transaction_date": "2026-11-02",
        "source_key": None,
    }
    assert entry["after"]["type"] == "expense"
    assert entry["after"]["category_id"] == transport
    assert entry["after"]["category_name"] == "Transportasi"
    assert entry["after"]["amount"] == 30_000
    assert entry["after"]["note"] == "kopi sore"
    assert entry["after"]["asset_name"] == "Mandiri"
    assert entry["after"]["transaction_date"] == "2026-11-03"

    created_at = datetime.fromisoformat(entry["created_at"])
    assert created_at.utcoffset() == timedelta(0)


def test_omitted_fields_are_kept_and_explicit_none_clears_only_nullable_fields(
    connection,
) -> None:
    user = _create_user(connection)
    transaction = _add_expense(connection, user_id=user.id)

    amount_only = update_transaction(
        connection,
        user_id=user.id,
        transaction_id=transaction.id,
        amount=40_000,
        source="api",
    )
    assert amount_only is not None
    assert amount_only.amount == 40_000
    assert amount_only.category_id == transaction.category_id
    assert amount_only.note == "kopi"
    assert amount_only.asset_name == "BCA"
    assert amount_only.transaction_date == "2026-11-02"

    cleared = update_transaction(
        connection,
        user_id=user.id,
        transaction_id=transaction.id,
        category_id=None,
        note=None,
        asset_name=None,
        source="api",
    )
    assert cleared is not None
    assert cleared.category_id is None
    assert cleared.category_name is None
    assert cleared.note is None
    assert cleared.asset_name is None
    assert cleared.amount == 40_000
    assert cleared.transaction_date == "2026-11-02"

    # ``None`` for amount or date is not a request to clear those columns; the
    # repository keeps the current value. The API schema rejects it instead.
    unchanged = update_transaction(
        connection,
        user_id=user.id,
        transaction_id=transaction.id,
        amount=None,
        transaction_date=None,
        source="api",
    )
    assert unchanged is not None
    assert unchanged.amount == 40_000
    assert unchanged.transaction_date == "2026-11-02"

    history = list_transaction_history(
        connection, user_id=user.id, transaction_id=transaction.id
    )
    assert len(history) == 2
    assert history[0]["before"]["note"] == "kopi"
    assert history[0]["after"]["note"] is None
    assert history[0]["after"]["category_id"] is None
    assert history[0]["after"]["asset_name"] is None


def test_noop_update_appends_no_history(connection) -> None:
    user = _create_user(connection)
    transaction = _add_expense(connection, user_id=user.id)

    result = update_transaction(
        connection,
        user_id=user.id,
        transaction_id=transaction.id,
        amount=None,
        source="api",
    )
    assert result == transaction

    same_values = update_transaction(
        connection,
        user_id=user.id,
        transaction_id=transaction.id,
        amount=transaction.amount,
        category_id=transaction.category_id,
        transaction_date=transaction.transaction_date,
        note=transaction.note,
        asset_name=transaction.asset_name,
        source="api",
    )
    assert same_values == transaction
    assert list_transaction_history(connection, user_id=user.id) == []


def test_delete_records_snapshot_and_history_outlives_live_row(connection) -> None:
    user = _create_user(connection)
    transaction = _add_expense(connection, user_id=user.id)

    assert delete_transaction(
        connection, user_id=user.id, transaction_id=transaction.id, source="api"
    )
    assert get_transaction_by_id(
        connection, user_id=user.id, transaction_id=transaction.id
    ) is None
    assert not delete_transaction(
        connection, user_id=user.id, transaction_id=transaction.id, source="api"
    )

    history = list_transaction_history(
        connection, user_id=user.id, transaction_id=transaction.id
    )
    assert len(history) == 1
    entry = history[0]
    assert entry["action"] == "delete"
    assert entry["source"] == "api"
    assert entry["reason"] == "direct"
    assert entry["after"] is None
    assert entry["before"]["id"] == transaction.id
    assert entry["before"]["amount"] == 25_000
    assert entry["before"]["note"] == "kopi"


def test_history_is_newest_first_and_paginates_with_transaction_filter(connection) -> None:
    user = _create_user(connection)
    first = _add_expense(connection, user_id=user.id)
    second = _add_expense(connection, user_id=user.id, note="lain")

    for amount in (26_000, 27_000, 28_000, 29_000, 30_000):
        update_transaction(
            connection,
            user_id=user.id,
            transaction_id=first.id,
            amount=amount,
            source="api",
        )
    update_transaction(
        connection, user_id=user.id, transaction_id=second.id, amount=5_000, source="api"
    )

    all_entries = list_transaction_history(connection, user_id=user.id)
    assert len(all_entries) == 6
    assert [entry["id"] for entry in all_entries] == sorted(
        (entry["id"] for entry in all_entries), reverse=True
    )

    first_entries = list_transaction_history(
        connection, user_id=user.id, transaction_id=first.id
    )
    assert len(first_entries) == 5
    assert {entry["transaction_id"] for entry in first_entries} == {first.id}

    page = list_transaction_history(
        connection, user_id=user.id, transaction_id=first.id, limit=2, offset=1
    )
    assert page == first_entries[1:3]
    assert (
        list_transaction_history(
            connection, user_id=user.id, transaction_id=first.id, limit=2, offset=9
        )
        == []
    )


def test_history_is_owner_scoped_including_deleted_rows(connection) -> None:
    owner = _create_user(connection, email="owner@example.com")
    other = _create_user(connection, email="other@example.com")
    transaction = _add_expense(connection, user_id=owner.id)

    update_transaction(
        connection,
        user_id=owner.id,
        transaction_id=transaction.id,
        amount=35_000,
        source="telegram",
    )

    assert list_transaction_history(connection, user_id=other.id) == []
    assert (
        list_transaction_history(
            connection, user_id=other.id, transaction_id=transaction.id
        )
        == []
    )
    assert (
        update_transaction(
            connection,
            user_id=other.id,
            transaction_id=transaction.id,
            amount=1,
            source="api",
        )
        is None
    )
    assert not delete_transaction(
        connection, user_id=other.id, transaction_id=transaction.id, source="api"
    )
    assert get_transaction_by_id(
        connection, user_id=owner.id, transaction_id=transaction.id
    ) is not None

    assert delete_transaction(
        connection, user_id=owner.id, transaction_id=transaction.id, source="api"
    )
    assert list_transaction_history(connection, user_id=other.id) == []
    assert len(list_transaction_history(connection, user_id=owner.id)) == 2


def test_source_and_reason_are_persisted_and_invalid_values_roll_back(connection) -> None:
    user = _create_user(connection)
    transaction = _add_expense(connection, user_id=user.id)
    removable = _add_expense(connection, user_id=user.id, note="hapus")

    update_transaction(
        connection,
        user_id=user.id,
        transaction_id=transaction.id,
        amount=31_000,
        source="telegram",
        reason="direct",
    )
    delete_transaction(
        connection, user_id=user.id, transaction_id=removable.id, source="telegram"
    )

    entries = list_transaction_history(connection, user_id=user.id)
    assert {(entry["action"], entry["source"], entry["reason"]) for entry in entries} == {
        ("update", "telegram", "direct"),
        ("delete", "telegram", "direct"),
    }

    with pytest.raises(_database_error(connection)):
        update_transaction(
            connection,
            user_id=user.id,
            transaction_id=transaction.id,
            amount=99_000,
            source="unknown-source",
        )
    assert get_transaction_by_id(
        connection, user_id=user.id, transaction_id=transaction.id
    ).amount == 31_000
    assert len(list_transaction_history(connection, user_id=user.id)) == 2


def test_audit_insert_failure_rolls_back_update_and_delete(connection) -> None:
    user = _create_user(connection)
    transaction = _add_expense(connection, user_id=user.id)

    if is_postgres(connection):
        connection.execute(
            """
            CREATE OR REPLACE FUNCTION finance_fail_audit() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'audit down';
            END;
            $$
            """
        )
        connection.execute(
            "CREATE TRIGGER trg_fail_transaction_audit BEFORE INSERT ON transaction_audit "
            "FOR EACH ROW EXECUTE FUNCTION finance_fail_audit()"
        )
    else:
        connection.execute(
            """
            CREATE TRIGGER trg_fail_transaction_audit
            BEFORE INSERT ON transaction_audit
            BEGIN SELECT RAISE(ABORT, 'audit down'); END
            """
        )

    expected = _database_error(connection)
    with pytest.raises(expected):
        update_transaction(
            connection,
            user_id=user.id,
            transaction_id=transaction.id,
            amount=90_000,
            source="api",
        )
    current = get_transaction_by_id(
        connection, user_id=user.id, transaction_id=transaction.id
    )
    assert current is not None
    assert current.amount == 25_000
    assert list_transaction_history(connection, user_id=user.id) == []

    with pytest.raises(expected):
        delete_transaction(
            connection, user_id=user.id, transaction_id=transaction.id, source="api"
        )
    assert get_transaction_by_id(
        connection, user_id=user.id, transaction_id=transaction.id
    ) is not None
    assert list_transaction_history(connection, user_id=user.id) == []

    if is_postgres(connection):
        connection.execute("DROP TRIGGER trg_fail_transaction_audit ON transaction_audit")
    else:
        connection.execute("DROP TRIGGER trg_fail_transaction_audit")
    recovered = update_transaction(
        connection,
        user_id=user.id,
        transaction_id=transaction.id,
        amount=90_000,
        source="api",
    )
    assert recovered is not None
    assert recovered.amount == 90_000
    assert len(list_transaction_history(connection, user_id=user.id)) == 1


def test_caller_rollback_reverts_mutation_and_audit_entry(connection) -> None:
    user = _create_user(connection)
    transaction = _add_expense(connection, user_id=user.id)
    connection.commit()

    with pytest.raises(RuntimeError, match="outer failure"):
        with db_transaction(connection):
            update_transaction(
                connection,
                user_id=user.id,
                transaction_id=transaction.id,
                amount=123_000,
                source="api",
            )
            delete_transaction(
                connection, user_id=user.id, transaction_id=transaction.id, source="api"
            )
            raise RuntimeError("outer failure")

    current = get_transaction_by_id(
        connection, user_id=user.id, transaction_id=transaction.id
    )
    assert current is not None
    assert current.amount == 25_000
    assert list_transaction_history(connection, user_id=user.id) == []


def test_repository_does_not_commit_until_the_caller_commits(database) -> None:
    writer = _open(database)
    observer = _open(database)
    try:
        user = _create_user(writer, email="uncommitted@example.com")
        transaction = _add_expense(writer, user_id=user.id)
        writer.commit()

        update_transaction(
            writer,
            user_id=user.id,
            transaction_id=transaction.id,
            amount=44_000,
            source="api",
        )

        observed = get_transaction_by_id(
            observer, user_id=user.id, transaction_id=transaction.id
        )
        assert observed is not None
        assert observed.amount == 25_000
        assert list_transaction_history(observer, user_id=user.id) == []

        writer.commit()

        observed = get_transaction_by_id(
            observer, user_id=user.id, transaction_id=transaction.id
        )
        assert observed is not None
        assert observed.amount == 44_000
        assert len(list_transaction_history(observer, user_id=user.id)) == 1
    finally:
        writer.close()
        observer.close()


def test_postgres_second_writer_snapshots_first_committed_update(database, connection) -> None:
    if database["dialect"] != "postgres":
        pytest.skip("row-lock concurrency regression requires PostgreSQL")

    user = _create_user(connection, email="concurrent@example.com")
    transaction = _add_expense(connection, user_id=user.id)
    connection.commit()

    first_wrote = threading.Event()
    allow_first_commit = threading.Event()
    second_started = threading.Event()
    second_finished = threading.Event()
    errors: list[BaseException] = []

    def first_writer() -> None:
        writer = connect_url(database["url"])
        try:
            with db_transaction(writer):
                update_transaction(
                    writer,
                    user_id=user.id,
                    transaction_id=transaction.id,
                    amount=200_000,
                    source="api",
                )
                first_wrote.set()
                if not allow_first_commit.wait(10):
                    raise RuntimeError("first writer was never released")
        except BaseException as error:  # pragma: no cover - surfaced below
            errors.append(error)
        finally:
            writer.close()

    def second_writer() -> None:
        writer = connect_url(database["url"])
        try:
            second_started.set()
            with db_transaction(writer):
                update_transaction(
                    writer,
                    user_id=user.id,
                    transaction_id=transaction.id,
                    amount=300_000,
                    source="api",
                )
        except BaseException as error:  # pragma: no cover - surfaced below
            errors.append(error)
        finally:
            second_finished.set()
            writer.close()

    first = threading.Thread(target=first_writer)
    second = threading.Thread(target=second_writer)
    first.start()
    try:
        assert first_wrote.wait(10), "first writer did not reach its uncommitted update"

        observer = connect_url(database["url"])
        try:
            observed = get_transaction_by_id(
                observer, user_id=user.id, transaction_id=transaction.id
            )
            assert observed is not None
            assert observed.amount == 25_000
            assert list_transaction_history(observer, user_id=user.id) == []
        finally:
            observer.close()

        second.start()
        assert second_started.wait(10)
        time.sleep(0.5)
        assert not second_finished.is_set(), "second writer did not wait for the row lock"
        allow_first_commit.set()
        first.join(10)
        second.join(10)
    finally:
        allow_first_commit.set()
        first.join(10)
        if second.is_alive():
            second.join(10)

    assert not second.is_alive()
    assert errors == []
    current = get_transaction_by_id(
        connection, user_id=user.id, transaction_id=transaction.id
    )
    assert current is not None
    assert current.amount == 300_000

    history = list_transaction_history(
        connection, user_id=user.id, transaction_id=transaction.id
    )
    assert [entry["before"]["amount"] for entry in history] == [200_000, 25_000]
    assert [entry["after"]["amount"] for entry in history] == [300_000, 200_000]


def test_account_deletion_cascades_audit_rows(connection) -> None:
    user = _create_user(connection, email="delete-me@example.com")
    transaction = _add_expense(connection, user_id=user.id)
    update_transaction(
        connection,
        user_id=user.id,
        transaction_id=transaction.id,
        amount=27_000,
        source="api",
    )
    delete_transaction(
        connection, user_id=user.id, transaction_id=transaction.id, source="api"
    )
    assert len(list_transaction_history(connection, user_id=user.id)) == 2

    with db_transaction(connection):
        connection.execute("DELETE FROM users WHERE id = ?", (user.id,))

    assert list_transaction_history(connection, user_id=user.id) == []
    count = connection.execute(
        "SELECT COUNT(*) FROM transaction_audit WHERE user_id = ?", (user.id,)
    ).fetchone()[0]
    assert int(count) == 0


def test_telegram_account_merge_moves_audit_ownership(connection) -> None:
    bot = get_or_create_user(connection, telegram_user_id=555_001, first_name="Bot")
    bot_transaction = create_transaction(
        connection,
        user_id=bot.id,
        type="expense",
        category_id=None,
        amount=10_000,
        note="dari bot",
        asset_name=None,
        transaction_date="2026-11-02",
    )
    update_transaction(
        connection,
        user_id=bot.id,
        transaction_id=bot_transaction.id,
        amount=11_000,
        source="telegram",
    )
    owner = _create_user(connection, email="merge-owner@example.com")

    with db_transaction(connection):
        linked = link_telegram_account(
            connection, user_id=owner.id, telegram_user_id=555_001
        )
    assert linked is not None
    linked_owner = get_user_by_telegram_id(connection, 555_001)
    assert linked_owner is not None
    assert linked_owner.id == owner.id
    assert get_user_by_id(connection, bot.id) is None
    assert get_user_by_id(connection, owner.id).telegram_user_id == 555_001

    moved = get_transaction_by_id(
        connection, user_id=owner.id, transaction_id=bot_transaction.id
    )
    assert moved is not None
    history = list_transaction_history(
        connection, user_id=owner.id, transaction_id=bot_transaction.id
    )
    assert len(history) == 1
    assert history[0]["source"] == "telegram"
    assert (
        connection.execute(
            "SELECT COUNT(*) FROM transaction_audit WHERE user_id = ?", (bot.id,)
        ).fetchone()[0]
        == 0
    )


def test_debt_cash_history_uses_system_source_and_explicit_reasons(connection) -> None:
    user = _create_user(connection, email="debt-history@example.com")

    with db_transaction(connection):
        debt = create_debt(
            connection,
            user_id=user.id,
            type="debt",
            person_name="Budi",
            total_amount=100_000,
            note="pinjam",
            cash_synced=True,
        )
        opening = create_transaction(
            connection,
            user_id=user.id,
            type="income",
            category_id=None,
            amount=100_000,
            note="Pinjaman dari Budi",
            asset_name=None,
            transaction_date="2026-11-02",
            source_key=f"debt:{user.id}:{debt.id}",
        )
        sync_derived_debt_transaction(
            connection, user_id=user.id, debt_id=debt.id, amount=150_000
        )
        payment = create_debt_payment(
            connection,
            debt_id=debt.id,
            user_id=user.id,
            amount=40_000,
            note="cicilan",
            payment_date="2026-11-03",
        )
        payment_cash = create_transaction(
            connection,
            user_id=user.id,
            type="expense",
            category_id=None,
            amount=40_000,
            note="Bayar hutang ke Budi",
            asset_name=None,
            transaction_date="2026-11-03",
            source_key=f"debt_payment:{user.id}:{payment.id}",
        )
        removed_payment = delete_debt_payment(
            connection, user_id=user.id, debt_id=debt.id, payment_id=payment.id
        )
        assert removed_payment is not None
        assert delete_debt(connection, user_id=user.id, debt_id=debt.id)

    assert get_transaction_by_id(
        connection, user_id=user.id, transaction_id=opening.id
    ) is None
    assert get_transaction_by_id(
        connection, user_id=user.id, transaction_id=payment_cash.id
    ) is None

    entries = list_transaction_history(connection, user_id=user.id)
    assert len(entries) == 3
    assert {entry["source"] for entry in entries} == {"system"}
    assert {entry["reason"] for entry in entries} == {
        "debt_sync",
        "debt_delete",
        "payment_delete",
    }

    opening_entries = list_transaction_history(
        connection, user_id=user.id, transaction_id=opening.id
    )
    assert [(entry["action"], entry["reason"]) for entry in opening_entries] == [
        ("delete", "debt_delete"),
        ("update", "debt_sync"),
    ]
    assert opening_entries[0]["after"] is None
    assert opening_entries[1]["before"]["amount"] == 100_000
    assert opening_entries[1]["after"]["amount"] == 150_000

    payment_entries = list_transaction_history(
        connection, user_id=user.id, transaction_id=payment_cash.id
    )
    assert len(payment_entries) == 1
    assert payment_entries[0]["action"] == "delete"
    assert payment_entries[0]["reason"] == "payment_delete"


def test_telegram_handler_keeps_note_on_amount_only_edit_and_logs_telegram_source(
    connection,
) -> None:
    user = _create_user(connection, email="telegram-history@example.com")
    transaction = _add_expense(connection, user_id=user.id)
    store = PendingConfirmationStore()
    telegram_user_id = 777_001

    handle_transactions_callback(
        f"{CALLBACK_TRANSACTION_EDIT_PREFIX}{transaction.id}",
        connection=connection,
        user_id=user.id,
        telegram_user_id=telegram_user_id,
        pending_store=store,
    )
    response = handle_transaction_edit_text(
        "30000",
        connection=connection,
        user_id=user.id,
        telegram_user_id=telegram_user_id,
        pending_store=store,
    )
    assert response is not None
    amount_only = get_transaction_by_id(
        connection, user_id=user.id, transaction_id=transaction.id
    )
    assert amount_only is not None
    assert amount_only.amount == 30_000
    assert amount_only.note == "kopi"
    assert amount_only.category_id == transaction.category_id
    assert amount_only.asset_name == "BCA"
    assert amount_only.transaction_date == "2026-11-02"

    handle_transactions_callback(
        f"{CALLBACK_TRANSACTION_EDIT_PREFIX}{transaction.id}",
        connection=connection,
        user_id=user.id,
        telegram_user_id=telegram_user_id,
        pending_store=store,
    )
    handle_transaction_edit_text(
        "35000 kopi sore",
        connection=connection,
        user_id=user.id,
        telegram_user_id=telegram_user_id,
        pending_store=store,
    )
    note_replaced = get_transaction_by_id(
        connection, user_id=user.id, transaction_id=transaction.id
    )
    assert note_replaced is not None
    assert note_replaced.amount == 35_000
    assert note_replaced.note == "kopi sore"

    deleted = handle_transactions_callback(
        f"{CALLBACK_TRANSACTION_DELETE_CONFIRM_PREFIX}{transaction.id}",
        connection=connection,
        user_id=user.id,
        telegram_user_id=telegram_user_id,
        pending_store=store,
    )
    assert deleted is not None

    history = list_transaction_history(
        connection, user_id=user.id, transaction_id=transaction.id
    )
    assert [entry["action"] for entry in history] == ["delete", "update", "update"]
    assert {entry["source"] for entry in history} == {"telegram"}
    assert history[0]["after"] is None
    assert history[2]["before"]["note"] == "kopi"
    assert history[2]["after"]["note"] == "kopi"
    assert history[1]["after"]["note"] == "kopi sore"


def test_recurring_generated_row_deletion_is_not_replayed(connection) -> None:
    user = _create_user(connection, email="recurring-history@example.com")
    schedule = create_recurring(
        connection,
        user_id=user.id,
        type="expense",
        category_id=_category_id(connection, user.id),
        amount=15_000,
        note="Kopi langganan",
        asset_name=None,
        frequency="weekly",
        day_of_week=0,
        day_of_month=None,
        start_date="2026-01-01",
        next_run_date="2026-01-05",
    )
    connection.commit()

    first_runs = run_due_recurring(
        connection, today_by_timezone=lambda timezone: date(2026, 1, 6)
    )
    assert [run.due_date for run in first_runs] == ["2026-01-05"]
    generated_id = first_runs[0].transaction_id

    with db_transaction(connection):
        assert delete_transaction(
            connection, user_id=user.id, transaction_id=generated_id, source="api"
        )

    assert (
        run_due_recurring(connection, today_by_timezone=lambda timezone: date(2026, 1, 6))
        == []
    )
    assert list_transactions(connection, user_id=user.id) == []

    later_runs = run_due_recurring(
        connection, today_by_timezone=lambda timezone: date(2026, 1, 12)
    )
    assert [run.due_date for run in later_runs] == ["2026-01-12"]
    remaining = list_transactions(connection, user_id=user.id)
    assert len(remaining) == 1
    assert remaining[0].source_key == f"recurring:{user.id}:{schedule.id}:2026-01-12"

    history = list_transaction_history(
        connection, user_id=user.id, transaction_id=generated_id
    )
    assert len(history) == 1
    assert history[0]["action"] == "delete"
    assert history[0]["source"] == "api"


def test_version_7_database_upgrades_to_8_and_remains_idempotent(tmp_path) -> None:
    path = str(tmp_path / "v7.sqlite3")
    connection = connect(path)
    try:
        assert run_migrations(connection) == SCHEMA_VERSION
        user = _create_user(connection, email="upgrade@example.com")
        transaction = _add_expense(connection, user_id=user.id)
        connection.commit()

        connection.execute("DROP TABLE transaction_audit")
        connection.execute("DELETE FROM schema_migrations WHERE version = 8")
        connection.commit()
        assert current_version(connection) == 7
    finally:
        connection.close()

    connection = connect(path)
    try:
        assert run_migrations(connection) == 8
        assert current_version(connection) == 8
        assert get_transaction_by_id(
            connection, user_id=user.id, transaction_id=transaction.id
        ) is not None

        assert run_migrations(connection) == 8
        versions = [
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
        assert versions == list(range(1, 9))

        audit_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'transaction_audit'"
        ).fetchone()
        assert audit_table is not None
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'index' AND tbl_name = 'transaction_audit'"
            ).fetchall()
        }
        assert {
            "idx_transaction_audit_owner",
            "idx_transaction_audit_transaction",
        } <= indexes
    finally:
        connection.close()
