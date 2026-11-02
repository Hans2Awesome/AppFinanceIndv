"""Tests for cash synchronization on debts and receivables."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def cash_client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_debt_cash.sqlite3")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-1234567890123456789012")
    monkeypatch.setenv("RECURRING_SCHEDULER_ENABLED", "0")

    from backend.app.main import app
    from finance_core.db.connection import connect
    from finance_core.db.migrations import init_db

    conn = connect(db_file)
    init_db(conn)
    conn.close()

    with TestClient(app) as client:
        reg = client.post(
            "/api/auth/register",
            json={
                "email": "cash_user@example.com",
                "password": "password123",
                "first_name": "Cash",
            },
        )
        token = reg.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client


def _transactions(client: TestClient) -> list[dict]:
    res = client.get("/api/transactions", params={"limit": 50})
    assert res.status_code == 200, res.text
    return res.json()


def test_debt_with_cash_sync_adds_cash_on_creation_and_payment(cash_client):
    created = cash_client.post(
        "/api/debts",
        json={
            "type": "debt",
            "person_name": "Budi",
            "total_amount": 500000,
            "sync_cash": True,
        },
    )
    assert created.status_code == 201, created.text
    debt = created.json()
    assert debt["cash_synced"] is True

    [opening] = _transactions(cash_client)
    assert opening["type"] == "income"
    assert opening["amount"] == 500000
    assert opening["note"] == "Pinjaman dari Budi"
    assert opening["category_name"] == "Lainnya"

    payment = cash_client.post(
        f"/api/debts/{debt['id']}/payments",
        json={"amount": 200000, "payment_date": "2026-11-02"},
    )
    assert payment.status_code == 201, payment.text

    transactions = _transactions(cash_client)
    assert len(transactions) == 2
    repayment = next(item for item in transactions if item["type"] == "expense")
    assert repayment["amount"] == 200000
    assert repayment["note"] == "Bayar hutang ke Budi"
    assert repayment["category_name"] == "Lainnya"


def test_receivable_with_cash_sync_reverses_the_direction(cash_client):
    created = cash_client.post(
        "/api/debts",
        json={
            "type": "receivable",
            "person_name": "Ani",
            "total_amount": 300000,
            "sync_cash": True,
        },
    )
    assert created.status_code == 201, created.text
    debt = created.json()

    [opening] = _transactions(cash_client)
    assert opening["type"] == "expense"
    assert opening["note"] == "Piutang ke Ani"

    payment = cash_client.post(
        f"/api/debts/{debt['id']}/payments",
        json={"amount": 300000, "payment_date": "2026-11-02"},
    )
    assert payment.status_code == 201, payment.text

    received = next(
        item for item in _transactions(cash_client) if item["type"] == "income"
    )
    assert received["amount"] == 300000
    assert received["note"] == "Terima piutang dari Ani"


def test_debt_without_cash_sync_never_touches_the_ledger(cash_client):
    created = cash_client.post(
        "/api/debts",
        json={
            "type": "debt",
            "person_name": "Sasa",
            "total_amount": 100000,
        },
    )
    assert created.status_code == 201, created.text
    debt = created.json()
    assert debt["cash_synced"] is False

    payment = cash_client.post(
        f"/api/debts/{debt['id']}/payments",
        json={"amount": 50000, "payment_date": "2026-11-02"},
    )
    assert payment.status_code == 201, payment.text

    assert _transactions(cash_client) == []


def test_overpayment_is_rejected_without_a_cash_row(cash_client):
    created = cash_client.post(
        "/api/debts",
        json={
            "type": "debt",
            "person_name": "Budi",
            "total_amount": 100000,
            "sync_cash": True,
        },
    ).json()

    payment = cash_client.post(
        f"/api/debts/{created['id']}/payments",
        json={"amount": 150000, "payment_date": "2026-11-02"},
    )

    assert payment.status_code == 400
    assert len(_transactions(cash_client)) == 1


def test_mark_settled_records_remaining_payment_and_cash(cash_client):
    created = cash_client.post(
        "/api/debts",
        json={
            "type": "debt",
            "person_name": "Budi",
            "total_amount": 500000,
            "sync_cash": True,
        },
    ).json()

    cash_client.post(
        f"/api/debts/{created['id']}/payments",
        json={"amount": 200000, "payment_date": "2026-11-01"},
    )

    settled = cash_client.put(f"/api/debts/{created['id']}", json={"status": "settled"})
    assert settled.status_code == 200, settled.text
    debt = settled.json()
    assert debt["status"] == "settled"
    assert debt["paid_amount"] == 500000

    payments = cash_client.get(f"/api/debts/{created['id']}/payments").json()
    assert [item["amount"] for item in payments] == [300000, 200000]
    assert payments[0]["note"] == "Pelunasan"

    transactions = _transactions(cash_client)
    settlement = next(
        item for item in transactions if item["note"].startswith("Bayar hutang ke Budi: Pelunasan")
    )
    assert settlement["type"] == "expense"
    assert settlement["amount"] == 300000

    spending = sum(
        item["amount"] for item in transactions if item["type"] == "expense"
    )
    assert spending == 500000


def test_mark_settled_receivable_adds_the_remaining_cash(cash_client):
    created = cash_client.post(
        "/api/debts",
        json={
            "type": "receivable",
            "person_name": "Ani",
            "total_amount": 300000,
            "sync_cash": True,
        },
    ).json()

    settled = cash_client.put(f"/api/debts/{created['id']}", json={"status": "settled"})
    assert settled.status_code == 200, settled.text
    assert settled.json()["paid_amount"] == 300000

    transactions = _transactions(cash_client)
    incoming = [item for item in transactions if item["type"] == "income"]
    assert len(incoming) == 1
    assert incoming[0]["amount"] == 300000
    assert incoming[0]["note"].startswith("Terima piutang dari Ani")


def test_mark_settled_without_cash_sync_keeps_the_ledger_untouched(cash_client):
    created = cash_client.post(
        "/api/debts",
        json={"type": "debt", "person_name": "Sasa", "total_amount": 100000},
    ).json()

    settled = cash_client.put(f"/api/debts/{created['id']}", json={"status": "settled"})
    assert settled.status_code == 200, settled.text
    assert settled.json()["paid_amount"] == 100000
    assert settled.json()["cash_synced"] is False

    payments = cash_client.get(f"/api/debts/{created['id']}/payments").json()
    assert [item["amount"] for item in payments] == [100000]
    assert _transactions(cash_client) == []


def test_settling_twice_does_not_duplicate_the_payment(cash_client):
    created = cash_client.post(
        "/api/debts",
        json={
            "type": "debt",
            "person_name": "Budi",
            "total_amount": 100000,
            "sync_cash": True,
        },
    ).json()

    first = cash_client.put(f"/api/debts/{created['id']}", json={"status": "settled"})
    second = cash_client.put(f"/api/debts/{created['id']}", json={"status": "settled"})
    assert first.status_code == 200 and second.status_code == 200

    payments = cash_client.get(f"/api/debts/{created['id']}/payments").json()
    assert [item["amount"] for item in payments] == [100000]
    assert len(_transactions(cash_client)) == 2