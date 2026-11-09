"""API contract for transaction history, partial edits, and read-only cash rows."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.tests import test_api_transactions as _api_transactions

auth_client = _api_transactions.auth_client

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


@pytest.fixture(name="client")
def client_fixture(auth_client):
    return auth_client


def _create_transaction(
    client,
    *,
    amount: int = 25_000,
    note: str | None = "kopi",
    asset_name: str | None = "BCA",
    transaction_date: str = "2026-11-02",
    category_name: str | None = "Makan & Minum",
):
    payload = {
        "type": "expense",
        "amount": amount,
        "note": note,
        "asset_name": asset_name,
        "transaction_date": transaction_date,
    }
    if category_name is not None:
        payload["category_name"] = category_name
    response = client.post("/api/transactions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _history(client, **params):
    response = client.get("/api/transactions/history", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _register(client, email: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "first_name": "Other"},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_update_history_contract_and_editability_flags(client) -> None:
    created = _create_transaction(client)
    assert created["can_edit"] is True
    assert created["can_delete"] is True

    updated = client.put(
        f"/api/transactions/{created['id']}",
        json={
            "amount": 30_000,
            "note": "kopi sore",
            "asset_name": "Mandiri",
            "transaction_date": "2026-11-03",
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["amount"] == 30_000
    assert body["note"] == "kopi sore"
    assert body["asset_name"] == "Mandiri"
    assert body["transaction_date"] == "2026-11-03"
    assert body["type"] == "expense"
    assert body["can_edit"] is True
    assert body["can_delete"] is True

    history = _history(client, transaction_id=created["id"])
    assert len(history) == 1
    entry = history[0]
    assert set(entry) == HISTORY_KEYS
    assert entry["transaction_id"] == created["id"]
    assert entry["action"] == "update"
    assert entry["source"] == "api"
    assert entry["reason"] == "direct"
    assert "user_id" not in entry
    assert set(entry["before"]) == SNAPSHOT_KEYS
    assert set(entry["after"]) == SNAPSHOT_KEYS
    assert entry["before"]["amount"] == 25_000
    assert entry["before"]["note"] == "kopi"
    assert entry["after"]["amount"] == 30_000
    assert entry["after"]["note"] == "kopi sore"
    created_at = datetime.fromisoformat(entry["created_at"])
    assert created_at.utcoffset() == timedelta(0)

    assert _history(client) == history
    # The static /history route must not shadow the dynamic id route.
    detail = client.get(f"/api/transactions/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["amount"] == 30_000


def test_omitted_fields_stay_and_explicit_null_clears_nullable_fields(client) -> None:
    created = _create_transaction(client)

    cleared = client.put(
        f"/api/transactions/{created['id']}",
        json={"category_id": None, "note": None, "asset_name": None},
    )
    assert cleared.status_code == 200, cleared.text
    body = cleared.json()
    assert body["category_id"] is None
    assert body["category_name"] is None
    assert body["note"] is None
    assert body["asset_name"] is None
    assert body["amount"] == 25_000
    assert body["transaction_date"] == "2026-11-02"
    assert body["type"] == "expense"

    amount_only = client.put(
        f"/api/transactions/{created['id']}", json={"amount": 42_000}
    )
    assert amount_only.status_code == 200, amount_only.text
    body = amount_only.json()
    assert body["amount"] == 42_000
    assert body["category_id"] is None
    assert body["note"] is None
    assert body["asset_name"] is None
    assert body["transaction_date"] == "2026-11-02"

    for payload in ({"amount": None}, {"transaction_date": None}):
        rejected = client.put(f"/api/transactions/{created['id']}", json=payload)
        assert rejected.status_code == 422, rejected.text

    history = _history(client, transaction_id=created["id"])
    assert len(history) == 2
    assert history[0]["after"]["amount"] == 42_000
    assert history[0]["after"]["note"] is None
    assert history[1]["before"]["note"] == "kopi"
    assert history[1]["after"]["note"] is None
    assert history[1]["after"]["category_id"] is None


def test_update_rejects_unknown_immutable_and_out_of_range_fields(client) -> None:
    created = _create_transaction(client)
    invalid_payloads = [
        {"type": "income"},
        {"source": "telegram"},
        {"reason": "debt_sync"},
        {"user_id": 999},
        {"unknown_field": 1},
        {"amount": 0},
        {"amount": -1},
        {"transaction_date": "not-a-date"},
        {"note": "x" * 501},
        {"asset_name": "x" * 81},
    ]

    for payload in invalid_payloads:
        response = client.put(f"/api/transactions/{created['id']}", json=payload)
        assert response.status_code == 422, (payload, response.text)

    detail = client.get(f"/api/transactions/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["type"] == "expense"
    assert detail.json()["amount"] == 25_000
    assert _history(client, transaction_id=created["id"]) == []


def test_delete_records_history_and_removes_row_from_ledger_and_reports(client) -> None:
    created = _create_transaction(client, amount=25_000)
    before = client.get("/api/reports/daily", params={"target_date": "2026-11-02"})
    assert before.status_code == 200, before.text
    assert before.json()["total_expense"] == 25_000

    deleted = client.delete(f"/api/transactions/{created['id']}")
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/api/transactions/{created['id']}").status_code == 404
    assert client.get("/api/transactions").json() == []

    after = client.get("/api/reports/daily", params={"target_date": "2026-11-02"})
    assert after.status_code == 200, after.text
    assert after.json()["total_expense"] == 0

    history = _history(client, transaction_id=created["id"])
    assert len(history) == 1
    entry = history[0]
    assert set(entry) == HISTORY_KEYS
    assert entry["action"] == "delete"
    assert entry["source"] == "api"
    assert entry["reason"] == "direct"
    assert entry["after"] is None
    assert entry["before"]["amount"] == 25_000

    assert client.delete(f"/api/transactions/{created['id']}").status_code == 404
    assert len(_history(client, transaction_id=created["id"])) == 1


def test_history_paging_filter_and_query_validation(client) -> None:
    created = _create_transaction(client)
    for amount in (26_000, 27_000, 28_000, 29_000):
        response = client.put(
            f"/api/transactions/{created['id']}", json={"amount": amount}
        )
        assert response.status_code == 200, response.text

    all_entries = _history(client, transaction_id=created["id"])
    assert len(all_entries) == 4
    assert [entry["id"] for entry in all_entries] == sorted(
        (entry["id"] for entry in all_entries), reverse=True
    )

    assert _history(client, transaction_id=created["id"], limit=2, offset=0) == (
        all_entries[:2]
    )
    assert _history(client, transaction_id=created["id"], limit=2, offset=2) == (
        all_entries[2:]
    )
    assert _history(client, transaction_id=999_999) == []

    for params in (
        {"limit": 0},
        {"limit": 201},
        {"offset": -1},
        {"transaction_id": 0},
        {"transaction_id": "history"},
    ):
        response = client.get("/api/transactions/history", params=params)
        assert response.status_code == 422, (params, response.text)

    # No audit mutation endpoint exists: the path is rejected, never applied.
    assert client.delete("/api/transactions/history").status_code in {405, 422}
    assert (
        client.put("/api/transactions/history", json={"action": "delete"}).status_code
        in {405, 422}
    )
    assert client.put(
        f"/api/transactions/history/{all_entries[0]['id']}", json={}
    ).status_code == 404


def test_history_and_transaction_ownership_isolation_including_deleted(client) -> None:
    owner_token = client.headers["Authorization"]
    created = _create_transaction(client)
    assert (
        client.put(
            f"/api/transactions/{created['id']}", json={"amount": 30_000}
        ).status_code
        == 200
    )

    other_token = _register(client, "other-history@example.com")
    client.headers.update({"Authorization": f"Bearer {other_token}"})

    assert _history(client) == []
    assert _history(client, transaction_id=created["id"]) == []
    assert client.get(f"/api/transactions/{created['id']}").status_code == 404
    assert (
        client.put(f"/api/transactions/{created['id']}", json={"amount": 1}).status_code
        == 404
    )
    assert client.delete(f"/api/transactions/{created['id']}").status_code == 404

    client.headers.update({"Authorization": owner_token})
    detail = client.get(f"/api/transactions/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["amount"] == 30_000
    assert len(_history(client, transaction_id=created["id"])) == 1

    assert client.delete(f"/api/transactions/{created['id']}").status_code == 204
    client.headers.update({"Authorization": f"Bearer {other_token}"})
    assert _history(client) == []
    assert _history(client, transaction_id=created["id"]) == []

    client.headers.update({"Authorization": owner_token})
    assert len(_history(client, transaction_id=created["id"])) == 2


def test_category_must_belong_to_the_transaction_owner(client) -> None:
    owner_token = client.headers["Authorization"]
    created = _create_transaction(client)

    other_token = _register(client, "category-owner@example.com")
    client.headers.update({"Authorization": f"Bearer {other_token}"})
    foreign_category = client.post(
        "/api/categories",
        json={"type": "expense", "name": "Rahasia B"},
    )
    assert foreign_category.status_code == 201, foreign_category.text

    client.headers.update({"Authorization": owner_token})
    rejected = client.put(
        f"/api/transactions/{created['id']}",
        json={"category_id": foreign_category.json()["id"]},
    )
    assert rejected.status_code == 400, rejected.text
    assert _history(client, transaction_id=created["id"]) == []

    own_category = client.post(
        "/api/categories",
        json={"type": "expense", "name": "Rahasia A"},
    )
    assert own_category.status_code == 201, own_category.text
    accepted = client.put(
        f"/api/transactions/{created['id']}",
        json={"category_id": own_category.json()["id"]},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["category_id"] == own_category.json()["id"]

    history = _history(client, transaction_id=created["id"])
    assert len(history) == 1
    assert history[0]["after"]["category_name"] == "Rahasia A"


def test_debt_cash_rows_are_locked_with_history_and_system_reasons(client) -> None:
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
        json={"amount": 40_000, "payment_date": "2026-11-03"},
    )
    assert payment.status_code == 201, payment.text

    transactions = client.get("/api/transactions", params={"limit": 50}).json()
    assert len(transactions) == 2
    assert {item["can_edit"] for item in transactions} == {False}
    assert {item["can_delete"] for item in transactions} == {False}
    opening = next(item for item in transactions if item["type"] == "income")
    payment_cash = next(item for item in transactions if item["type"] == "expense")

    for item in transactions:
        edited = client.put(
            f"/api/transactions/{item['id']}", json={"amount": 1}
        )
        assert edited.status_code == 409, edited.text
        removed = client.delete(f"/api/transactions/{item['id']}")
        assert removed.status_code == 409, removed.text

    payments = client.get(f"/api/debts/{debt_id}/payments")
    assert payments.status_code == 200, payments.text
    [payment_row] = payments.json()
    removed_payment = client.delete(
        f"/api/debts/{debt_id}/payments/{payment_row['id']}"
    )
    assert removed_payment.status_code == 204, removed_payment.text

    payment_history = _history(client, transaction_id=payment_cash["id"])
    assert len(payment_history) == 1
    assert payment_history[0]["action"] == "delete"
    assert payment_history[0]["source"] == "system"
    assert payment_history[0]["reason"] == "payment_delete"
    assert payment_history[0]["after"] is None
    assert payment_history[0]["before"]["source_key"].startswith("debt_payment:")

    assert client.delete(f"/api/debts/{debt_id}").status_code == 204
    assert client.get("/api/transactions").json() == []

    opening_history = _history(client, transaction_id=opening["id"])
    assert len(opening_history) == 1
    assert opening_history[0]["action"] == "delete"
    assert opening_history[0]["source"] == "system"
    assert opening_history[0]["reason"] == "debt_delete"
    assert opening_history[0]["before"]["source_key"].startswith("debt:")

    all_history = _history(client)
    assert len(all_history) == 2
    assert {(entry["action"], entry["source"]) for entry in all_history} == {
        ("delete", "system")
    }
    assert {entry["reason"] for entry in all_history} == {
        "payment_delete",
        "debt_delete",
    }
