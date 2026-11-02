"""Cash rows generated from debts must stay read-only from the ledger API."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "test-secret-key-1234567890123456789012")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "derived.sqlite3"))

    from backend.app.main import app

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/auth/register",
            json={"email": "derived@example.com", "password": "password123"},
        )
        assert response.status_code == 201, response.text
        test_client.headers.update(
            {"Authorization": f"Bearer {response.json()['access_token']}"}
        )
        yield test_client


def _create_debt_with_cash(client: TestClient) -> int:
    debt = client.post(
        "/api/debts",
        json={
            "type": "debt",
            "person_name": "Budi",
            "total_amount": 100_000,
            "sync_cash": True,
        },
    )
    assert debt.status_code == 201, debt.text
    debt_id = debt.json()["id"]

    payment = client.post(
        f"/api/debts/{debt_id}/payments",
        json={"amount": 40_000, "payment_date": "2026-11-02"},
    )
    assert payment.status_code == 201, payment.text
    return debt_id


def _cash_transaction_ids(client: TestClient) -> list[int]:
    response = client.get("/api/transactions", params={"limit": 50})
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()]


def test_derived_cash_transactions_reject_edit_and_delete(client: TestClient) -> None:
    _create_debt_with_cash(client)
    transaction_ids = _cash_transaction_ids(client)
    assert len(transaction_ids) == 2

    for transaction_id in transaction_ids:
        edited = client.put(
            f"/api/transactions/{transaction_id}", json={"amount": 1}
        )
        assert edited.status_code == 409, edited.text
        assert "utang/piutang" in edited.json()["detail"]

        deleted = client.delete(f"/api/transactions/{transaction_id}")
        assert deleted.status_code == 409, deleted.text

    # Nothing changed after the rejected calls.
    assert _cash_transaction_ids(client) == transaction_ids


def test_manual_transactions_stay_editable_and_deletable(client: TestClient) -> None:
    created = client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "category_name": "Makan & Minum",
            "amount": 25_000,
            "note": "Kopi",
            "transaction_date": "2026-11-02",
        },
    )
    assert created.status_code == 201, created.text
    transaction_id = created.json()["id"]

    edited = client.put(f"/api/transactions/{transaction_id}", json={"amount": 30_000})
    assert edited.status_code == 200, edited.text
    assert edited.json()["amount"] == 30_000

    deleted = client.delete(f"/api/transactions/{transaction_id}")
    assert deleted.status_code == 204, deleted.text


def test_deleting_a_debt_removes_its_cash_rows(client: TestClient) -> None:
    debt_id = _create_debt_with_cash(client)

    manual = client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "category_name": "Transportasi",
            "amount": 12_000,
            "note": "Parkir",
            "transaction_date": "2026-11-02",
        },
    )
    assert manual.status_code == 201, manual.text
    manual_id = manual.json()["id"]

    removed = client.delete(f"/api/debts/{debt_id}")
    assert removed.status_code == 204, removed.text

    assert _cash_transaction_ids(client) == [manual_id]