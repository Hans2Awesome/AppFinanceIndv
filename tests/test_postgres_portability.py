"""Portability checks that run the same repositories and API on PostgreSQL.

These tests need a real PostgreSQL server. Point ``POSTGRES_TEST_URL`` at a
database the test user may create schemas in, for example:

    POSTGRES_TEST_URL=postgresql://postgres:postgres@127.0.0.1:5432/postgres

Each test gets its own schema, so parallel runs and repeated runs never see
each other's rows. Without the variable the module is skipped and the SQLite
suite remains the default.
"""

from __future__ import annotations

import os
import uuid
from datetime import date
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

POSTGRES_URL = os.getenv("POSTGRES_TEST_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="POSTGRES_TEST_URL is not set; PostgreSQL portability tests skipped",
)


@pytest.fixture
def postgres_url():
    psycopg = pytest.importorskip("psycopg")

    schema = f"t_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(POSTGRES_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')

    separator = "&" if "?" in POSTGRES_URL else "?"
    url = f"{POSTGRES_URL}{separator}options={quote(f'-c search_path={schema}')}"

    try:
        yield url
    finally:
        from finance_core.db.connection import close_pools

        close_pools()
        with psycopg.connect(POSTGRES_URL, autocommit=True) as connection:
            connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


@pytest.fixture
def pg_client(postgres_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", postgres_url)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-1234567890123456789012")
    monkeypatch.setenv("RECURRING_SCHEDULER_ENABLED", "0")

    from backend.app.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            json={
                "email": "pg_user@example.com",
                "password": "password123",
                "first_name": "Postgres",
            },
        )
        assert response.status_code == 201, response.text
        client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
        yield client


def test_postgres_schema_reaches_current_version(postgres_url):
    from finance_core.db.connection import connect_url
    from finance_core.db.migrations import current_version, run_migrations

    connection = connect_url(postgres_url)
    try:
        assert run_migrations(connection) == 7
        assert run_migrations(connection) == 7
        assert current_version(connection) == 7
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        assert [row[0] for row in versions] == [1, 2, 3, 4, 5, 6, 7]
    finally:
        connection.close()


def test_postgres_api_round_trip(pg_client):
    created = pg_client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "category_name": "Makan & Minum",
            "amount": 25000,
            "note": "Kopi",
            "transaction_date": "2026-11-02",
        },
    )
    assert created.status_code == 201, created.text
    transaction = created.json()
    assert transaction["category_name"] == "Makan & Minum"

    listed = pg_client.get("/api/transactions", params={"limit": 10})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [transaction["id"]]

    report = pg_client.get("/api/reports/daily", params={"target_date": "2026-11-02"})
    assert report.status_code == 200, report.text
    assert report.json()["total_expense"] == 25000


def test_postgres_debt_cash_sync_and_settlement(pg_client):
    debt = pg_client.post(
        "/api/debts",
        json={
            "type": "debt",
            "person_name": "Budi",
            "total_amount": 500000,
            "sync_cash": True,
        },
    ).json()

    payment = pg_client.post(
        f"/api/debts/{debt['id']}/payments",
        json={"amount": 200000, "payment_date": "2026-11-01"},
    )
    assert payment.status_code == 201, payment.text

    settled = pg_client.put(f"/api/debts/{debt['id']}", json={"status": "settled"})
    assert settled.status_code == 200, settled.text
    record = settled.json()
    assert record["paid_amount"] == record["total_amount"] == 500000
    assert record["cash_synced"] is True

    payments = pg_client.get(f"/api/debts/{debt['id']}/payments").json()
    assert [item["amount"] for item in payments] == [300000, 200000]

    transactions = pg_client.get("/api/transactions", params={"limit": 50}).json()
    assert len(transactions) == 3
    assert sum(item["amount"] for item in transactions if item["type"] == "expense") == 500000

    summary = pg_client.get("/api/debts/summary").json()
    assert summary["total_debt_remaining"] == 0


def test_postgres_recurring_catch_up_is_idempotent(postgres_url):
    from finance_core.db.connection import connect_url
    from finance_core.db.migrations import run_migrations
    from finance_core.db.recurring import create_recurring, list_recurring, run_due_recurring
    from finance_core.db.transactions import list_transactions
    from finance_core.db.users import create_mobile_user

    connection = connect_url(postgres_url)
    try:
        run_migrations(connection)
        user = create_mobile_user(
            connection,
            email="runner_pg@example.com",
            password_hash="not-used",
        )
        schedule = create_recurring(
            connection,
            user_id=user.id,
            type="expense",
            category_id=None,
            amount=15000,
            note="Kopi langganan",
            asset_name=None,
            frequency="weekly",
            day_of_week=0,
            day_of_month=None,
            start_date="2026-01-01",
            next_run_date="2026-01-05",
        )

        def today(timezone):
            return date(2026, 1, 26)

        first = run_due_recurring(connection, today_by_timezone=today)
        second = run_due_recurring(connection, today_by_timezone=today)

        assert [run.due_date for run in first] == [
            "2026-01-05",
            "2026-01-12",
            "2026-01-19",
            "2026-01-26",
        ]
        assert second == []
        assert len(list_transactions(connection, user_id=user.id)) == 4

        [updated] = list_recurring(connection, user_id=user.id)
        assert updated.next_run_date == "2026-02-02"
        assert updated.id == schedule.id
    finally:
        connection.close()

def test_postgres_derived_cash_rows_are_locked_and_cleaned_up(pg_client):
    debt = pg_client.post(
        "/api/debts",
        json={
            "type": "debt",
            "person_name": "Sari",
            "total_amount": 200000,
            "sync_cash": True,
        },
    ).json()
    payment = pg_client.post(
        f"/api/debts/{debt['id']}/payments",
        json={"amount": 50000, "payment_date": "2026-11-02"},
    )
    assert payment.status_code == 201, payment.text

    cash_ids = [item["id"] for item in pg_client.get("/api/transactions").json()]
    assert len(cash_ids) == 2

    for transaction_id in cash_ids:
        edited = pg_client.put(f"/api/transactions/{transaction_id}", json={"amount": 1})
        assert edited.status_code == 409, edited.text
        deleted = pg_client.delete(f"/api/transactions/{transaction_id}")
        assert deleted.status_code == 409, deleted.text

    manual = pg_client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "category_name": "Transportasi",
            "amount": 15000,
            "transaction_date": "2026-11-02",
        },
    ).json()

    removed = pg_client.delete(f"/api/debts/{debt['id']}")
    assert removed.status_code == 204, removed.text

    remaining = [item["id"] for item in pg_client.get("/api/transactions").json()]
    assert remaining == [manual["id"]]


def test_row_iterates_over_values_like_sqlite_row(postgres_url) -> None:
    """``tuple(row)`` must yield values, not column names.

    The data migration copies rows with ``[tuple(row) for row in rows]``. When
    Row inherited Mapping it iterated over keys, so the migration would have
    inserted column names as data on any non-empty table.
    """

    import sqlite3

    from finance_core.db.connection import close_pools, connect_url

    connection = connect_url(postgres_url)
    try:
        connection.execute(
            "CREATE TEMP TABLE row_parity (a INTEGER, b TEXT) ON COMMIT DROP"
        )
        connection.execute("INSERT INTO row_parity (a, b) VALUES (?, ?)", (7, "tujuh"))
        pg_row = connection.execute("SELECT a, b FROM row_parity").fetchone()
    finally:
        connection.close()
        close_pools()

    sqlite_connection = sqlite3.connect(":memory:")
    sqlite_connection.row_factory = sqlite3.Row
    sqlite_connection.execute("CREATE TABLE row_parity (a INTEGER, b TEXT)")
    sqlite_connection.execute("INSERT INTO row_parity (a, b) VALUES (7, 'tujuh')")
    lite_row = sqlite_connection.execute("SELECT a, b FROM row_parity").fetchone()
    sqlite_connection.close()

    assert tuple(pg_row) == tuple(lite_row) == (7, "tujuh")
    assert list(pg_row) == list(lite_row) == [7, "tujuh"]
    assert dict(pg_row) == dict(lite_row) == {"a": 7, "b": "tujuh"}
    assert pg_row["a"] == lite_row["a"] == 7
    assert pg_row[0] == lite_row[0] == 7
    assert pg_row[0:2] == lite_row[0:2] == (7, "tujuh")
    assert len(pg_row) == len(lite_row) == 2
    assert pg_row.keys() == lite_row.keys() == ["a", "b"]
    # sqlite3.Row membership tests values, not names.
    assert (7 in pg_row) is (7 in lite_row) is True
    assert ("a" in pg_row) is ("a" in lite_row) is False
