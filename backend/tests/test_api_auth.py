"""Tests for authentication API endpoints."""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_api.sqlite3")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123456789")

    from backend.app.main import app
    from backend.app.database.connection import connect
    from backend.app.database.schema import init_db

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
