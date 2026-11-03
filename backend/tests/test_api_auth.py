"""Tests for authentication API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_api.sqlite3")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-1234567890123456789012")

    from backend.app.main import app
    from finance_core.db.connection import connect
    from finance_core.db.migrations import init_db

    conn = connect(db_file)
    init_db(conn)
    conn.close()

    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client):
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "online"


def test_register_and_login(client):
    # 1. Register
    reg_res = client.post(
        "/api/auth/register",
        json={
            "email": "user@example.com",
            "password": "password123",
            "first_name": "Hans",
        },
    )
    assert reg_res.status_code == 201
    data = reg_res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "user@example.com"
    token = data["access_token"]

    # 2. Get profile with Bearer token
    me_res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["first_name"] == "Hans"

    # 3. Login
    login_res = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()


def test_duplicate_registration_fails(client):
    payload = {"email": "dup@example.com", "password": "password123"}
    res1 = client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/auth/register", json=payload)
    assert res2.status_code == 400
    assert "Email sudah terdaftar" in res2.json()["detail"]


def test_telegram_link_token_returns_rotating_six_digit_code(client):
    registered = client.post(
        "/api/auth/register",
        json={"email": "link@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    first = client.post("/api/auth/telegram-link-token", headers=headers)
    assert first.status_code == 201
    first_body = first.json()
    assert len(first_body["code"]) == 6 and first_body["code"].isdigit()
    assert first_body["expires_in_minutes"] == 10

    # Kode baru membatalkan kode lama.
    second = client.post("/api/auth/telegram-link-token", headers=headers)
    assert second.status_code == 201
    assert second.json()["code"] != first_body["code"]

    import os

    from finance_core.db.connection import open_database
    from finance_core.db.users import consume_telegram_link_code

    connection = open_database(os.environ["DATABASE_PATH"])
    try:
        assert consume_telegram_link_code(connection, code=first_body["code"]) is None
        assert consume_telegram_link_code(
            connection, code=second.json()["code"]
        ) == registered.json()["user"]["id"]
    finally:
        connection.close()


def test_profile_reports_telegram_link_state(client):
    registered = client.post(
        "/api/auth/register",
        json={"email": "state@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["telegram_linked"] is False


def test_telegram_link_can_be_removed_without_losing_data(client):
    registered = client.post(
        "/api/auth/register",
        json={"email": "unlink@example.com", "password": "password123"},
    )
    user_id = registered.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "category_name": "Makan & Minum",
            "amount": 15000,
            "transaction_date": "2026-11-02",
        },
        headers=headers,
    )

    import os

    from finance_core.db.connection import open_database
    from finance_core.db.users import link_telegram_account

    connection = open_database(os.environ["DATABASE_PATH"])
    try:
        link_telegram_account(connection, user_id=user_id, telegram_user_id=31337)
        connection.commit()
    finally:
        connection.close()

    assert client.get("/api/auth/me", headers=headers).json()["telegram_linked"] is True

    removed = client.delete("/api/auth/telegram-link", headers=headers)
    assert removed.status_code == 200
    assert removed.json() == {"telegram_linked": False}

    me = client.get("/api/auth/me", headers=headers).json()
    assert me["telegram_linked"] is False

    listed = client.get("/api/transactions", headers=headers).json()
    assert len(listed) == 1
