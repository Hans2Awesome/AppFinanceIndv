"""Tests for transactions and quick input API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_tx_api.sqlite3")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123456789")

    from backend.app.main import app
    from backend.app.database.connection import connect
    from backend.app.database.schema import init_db

    conn = connect(db_file)
    init_db(conn)
    conn.close()

    with TestClient(app) as client:
        # Register user
        reg = client.post(
            "/api/auth/register",
            json={"email": "tx_user@example.com", "password": "password123", "first_name": "Tester"},
        )
        token = reg.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client


def test_quick_input_preview_and_confirm(auth_client):
    # Preview
    preview_res = auth_client.post(
        "/api/transactions/quick-input",
        json={"text": "makan siang 35000 warteg"},
    )
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert preview["is_valid"] is True
    assert preview["type"] == "expense"
    assert preview["amount"] == 35000
    assert preview["category_name"] == "Makan & Minum"
    assert "warteg" in preview["note"]

    # Confirm
    confirm_res = auth_client.post(
        "/api/transactions/quick-input/confirm",
        json={"text": "makan siang 35000 warteg"},
    )
    assert confirm_res.status_code == 201
    saved = confirm_res.json()
    assert saved["amount"] == 35000
    assert saved["type"] == "expense"


def test_manual_transaction_crud(auth_client):
    # Create
    create_res = auth_client.post(
        "/api/transactions",
        json={
            "type": "income",
            "category_name": "Gaji",
            "amount": 10000000,
            "note": "Gaji bulanan",
            "transaction_date": "2026-05-30",
        },
    )
    assert create_res.status_code == 201
    tx_id = create_res.json()["id"]

    # Read list
    list_res = auth_client.get("/api/transactions")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # Read detail
    detail_res = auth_client.get(f"/api/transactions/{tx_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["amount"] == 10000000

    # Update
    update_res = auth_client.put(
        f"/api/transactions/{tx_id}",
        json={"amount": 12000000, "note": "Gaji + bonus"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["amount"] == 12000000

    # Delete
    del_res = auth_client.delete(f"/api/transactions/{tx_id}")
    assert del_res.status_code == 204

    # Verify deleted
    detail_res2 = auth_client.get(f"/api/transactions/{tx_id}")
    assert detail_res2.status_code == 404
