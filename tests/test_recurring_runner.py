"""Tests for the recurring runner that materializes missed occurrences."""

from __future__ import annotations

from datetime import date

from finance_core.db.connection import connect
from finance_core.db.migrations import run_migrations
from finance_core.db.recurring import create_recurring, list_recurring, run_due_recurring
from finance_core.db.transactions import list_transactions
from finance_core.db.users import create_mobile_user


def _seed(tmp_path, *, frequency: str, next_run_date: str, day_of_week=None, day_of_month=None):
    connection = connect(str(tmp_path / "runner.sqlite3"))
    run_migrations(connection)
    user = create_mobile_user(
        connection,
        email="runner@example.com",
        password_hash="not-used-in-this-test",
    )
    schedule = create_recurring(
        connection,
        user_id=user.id,
        type="expense",
        category_id=None,
        amount=15000,
        note="Kopi langganan",
        asset_name=None,
        frequency=frequency,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        start_date="2026-01-01",
        next_run_date=next_run_date,
    )
    return connection, user, schedule


def test_weekly_catch_up_fills_every_missed_occurrence(tmp_path):
    connection, user, schedule = _seed(
        tmp_path,
        frequency="weekly",
        day_of_week=0,
        next_run_date="2026-01-05",
    )
    try:
        runs = run_due_recurring(
            connection,
            today_by_timezone=lambda timezone: date(2026, 1, 26),
        )

        assert [run.due_date for run in runs] == [
            "2026-01-05",
            "2026-01-12",
            "2026-01-19",
            "2026-01-26",
        ]
        transactions = list_transactions(connection, user_id=user.id)
        assert len(transactions) == 4
        assert {transaction.transaction_date for transaction in transactions} == {
            "2026-01-05",
            "2026-01-12",
            "2026-01-19",
            "2026-01-26",
        }

        [updated] = list_recurring(connection, user_id=user.id)
        assert updated.next_run_date == "2026-02-02"
        assert updated.last_run_date == "2026-01-26"
    finally:
        connection.close()
    assert schedule.id


def test_monthly_catch_up_clamps_short_months(tmp_path):
    connection, user, _ = _seed(
        tmp_path,
        frequency="monthly",
        day_of_month=31,
        next_run_date="2026-01-31",
    )
    try:
        runs = run_due_recurring(
            connection,
            today_by_timezone=lambda timezone: date(2026, 4, 30),
        )

        assert [run.due_date for run in runs] == [
            "2026-01-31",
            "2026-02-28",
            "2026-03-31",
            "2026-04-30",
        ]
        [updated] = list_recurring(connection, user_id=user.id)
        assert updated.next_run_date == "2026-05-31"
    finally:
        connection.close()


def test_second_run_is_idempotent(tmp_path):
    connection, user, _ = _seed(
        tmp_path,
        frequency="weekly",
        day_of_week=0,
        next_run_date="2026-01-05",
    )
    try:
        def today(timezone):
            return date(2026, 1, 26)

        first = run_due_recurring(connection, today_by_timezone=today)
        second = run_due_recurring(connection, today_by_timezone=today)

        assert len(first) == 4
        assert second == []
        assert len(list_transactions(connection, user_id=user.id)) == 4
    finally:
        connection.close()


def test_future_schedule_is_untouched(tmp_path):
    connection, user, _ = _seed(
        tmp_path,
        frequency="weekly",
        day_of_week=0,
        next_run_date="2026-02-02",
    )
    try:
        runs = run_due_recurring(
            connection,
            today_by_timezone=lambda timezone: date(2026, 1, 26),
        )

        assert runs == []
        assert list_transactions(connection, user_id=user.id) == []
        [updated] = list_recurring(connection, user_id=user.id)
        assert updated.next_run_date == "2026-02-02"
    finally:
        connection.close()