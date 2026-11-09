"""SQLite writers must acquire the write lock before reading audit snapshots."""

from __future__ import annotations

import threading

from finance_core.db.categories import create_category
from finance_core.db.connection import connect
from finance_core.db.migrations import run_migrations
from finance_core.db.transactions import (
    create_transaction,
    delete_transaction,
    list_transaction_history,
    update_transaction,
)
from finance_core.db.users import create_mobile_user, get_or_create_user, link_telegram_account


def test_sqlite_second_writer_snapshots_latest_committed_value(tmp_path):
    path = str(tmp_path / "concurrent.sqlite3")
    first = connect(path)
    run_migrations(first)
    owner = create_mobile_user(first, email="sqlite-lock@example.com", password_hash="unused")
    item = create_transaction(
        first, user_id=owner.id, type="expense", category_id=None, amount=100,
        note=None, asset_name=None, transaction_date="2026-11-09",
    )
    first.commit()
    update_transaction(first, user_id=owner.id, transaction_id=item.id, amount=200, source="api")

    attempted_write = threading.Event()
    read_snapshot = threading.Event()
    finished = threading.Event()
    errors = []

    def second_writer():
        second = connect(path)
        try:
            def trace(sql):
                if sql.lstrip().startswith("UPDATE transactions"):
                    attempted_write.set()
                if "SELECT t.id, t.user_id" in sql:
                    read_snapshot.set()

            second.set_trace_callback(trace)
            update_transaction(
                second, user_id=owner.id, transaction_id=item.id, amount=300, source="telegram",
            )
            second.commit()
        except BaseException as error:
            errors.append(error)
        finally:
            second.close()
            finished.set()

    worker = threading.Thread(target=second_writer)
    worker.start()
    try:
        assert attempted_write.wait(5), "second writer never attempted its lock"
        assert not read_snapshot.wait(0.2), "snapshot read before obtaining SQLite write lock"
        assert not finished.is_set()
    finally:
        first.commit()
        worker.join(10)

    try:
        assert not worker.is_alive()
        assert errors == []
        history = list_transaction_history(first, user_id=owner.id, transaction_id=item.id)
        assert [entry["before"]["amount"] for entry in history] == [200, 100]
        assert [entry["after"]["amount"] for entry in history] == [300, 200]
        assert [entry["source"] for entry in history] == ["telegram", "api"]
    finally:
        first.close()


def test_deleted_history_survives_category_removal_and_telegram_merge(tmp_path):
    connection = connect(str(tmp_path / "retention.sqlite3"))
    try:
        run_migrations(connection)
        bot = get_or_create_user(connection, telegram_user_id=123456, first_name="Bot")
        owner = create_mobile_user(
            connection, email="retention@example.com", password_hash="unused",
        )
        category = create_category(connection, user_id=bot.id, type="expense", name="Historical category")
        item = create_transaction(
            connection, user_id=bot.id, type="expense", category_id=category.id, amount=100,
            note="Snapshot remains", asset_name=None, transaction_date="2026-11-09",
        )
        delete_transaction(
            connection, user_id=bot.id, transaction_id=item.id, source="telegram",
        )
        connection.execute("DELETE FROM categories WHERE id = ?", (category.id,))
        link_telegram_account(connection, user_id=owner.id, telegram_user_id=123456)
        connection.commit()

        history = list_transaction_history(connection, user_id=owner.id, transaction_id=item.id)
        assert len(history) == 1
        assert history[0]["before"]["category_name"] == category.name
        assert history[0]["before"]["note"] == "Snapshot remains"
        assert history[0]["after"] is None
        assert list_transaction_history(connection, user_id=bot.id) == []
    finally:
        connection.close()
