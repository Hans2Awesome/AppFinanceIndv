"""Security and input-validation tests for the FastAPI backend."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "test-secret-key-1234567890123456789012")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "security.sqlite3"))

    from backend.app.main import app

    with TestClient(app) as test_client:
        yield test_client


def _register(client: TestClient, email: str = "user@example.com") -> dict:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "timezone": "Asia/Jakarta"},
    )
    assert response.status_code == 201
    return response.json()


def test_register_returns_access_and_refresh_tokens(client: TestClient) -> None:
    data = _register(client)

    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_refresh_token_returns_new_token_pair(client: TestClient) -> None:
    data = _register(client)

    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": data["refresh_token"]},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_refresh_token_is_rejected_as_bearer_token(client: TestClient) -> None:
    data = _register(client)

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['refresh_token']}"},
    )

    assert response.status_code == 401


def test_access_token_is_rejected_by_refresh_endpoint(client: TestClient) -> None:
    data = _register(client)

    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": data["access_token"]},
    )

    assert response.status_code == 401


def test_login_is_throttled_after_repeated_failures(client: TestClient) -> None:
    _register(client, "throttled@example.com")

    for _ in range(5):
        failure = client.post(
            "/api/auth/login",
            json={"email": "throttled@example.com", "password": "wrong-password"},
        )
        assert failure.status_code == 401

    blocked = client.post(
        "/api/auth/login",
        json={"email": "throttled@example.com", "password": "password123"},
    )

    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "900"


def test_successful_login_resets_throttle_counter(client: TestClient) -> None:
    _register(client, "reset@example.com")

    for _ in range(4):
        client.post(
            "/api/auth/login",
            json={"email": "reset@example.com", "password": "wrong-password"},
        )

    success = client.post(
        "/api/auth/login",
        json={"email": "reset@example.com", "password": "password123"},
    )
    assert success.status_code == 200

    failure = client.post(
        "/api/auth/login",
        json={"email": "reset@example.com", "password": "wrong-password"},
    )
    assert failure.status_code == 401


def test_invalid_transaction_date_returns_422(client: TestClient) -> None:
    data = _register(client)

    response = client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "amount": 1000,
            "transaction_date": "30-05-2026",
        },
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )

    assert response.status_code == 422


def test_invalid_report_date_returns_422(client: TestClient) -> None:
    data = _register(client)

    response = client.get(
        "/api/reports/daily?target_date=not-a-date",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )

    assert response.status_code == 422


def test_short_password_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )

    assert response.status_code == 422


def test_daily_report_uses_user_timezone_not_server_clock(tmp_path, monkeypatch) -> None:
    """A user far east of UTC must see their local date, not UTC's."""

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "tz.sqlite3"))
    from backend.app.main import app

    with TestClient(app) as test_client:
        registered = test_client.post(
            "/api/auth/register",
            json={
                "email": "tz@example.com",
                "password": "password123",
                "timezone": "Pacific/Kiritimati",
            },
        ).json()
        headers = {"Authorization": f"Bearer {registered['access_token']}"}

        today = test_client.get("/api/reports/daily", headers=headers).json()

        from finance_core.timezones import today_in

        assert today["start_date"] == today_in("Pacific/Kiritimati").isoformat()
        assert today["end_date"] == today["start_date"]

def test_logout_revokes_access_and_refresh_tokens(client: TestClient) -> None:
    tokens = _register(client, email="logout@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    assert client.post("/api/auth/logout", headers=headers).status_code == 204

    assert client.get("/api/auth/me", headers=headers).status_code == 401
    refresh = client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 401


def test_password_longer_than_bcrypt_limit_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "long@example.com", "password": "a" * 80},
    )

    assert response.status_code == 422


def test_transaction_rejects_category_owned_by_another_user(client: TestClient) -> None:
    first = _register(client, email="one@example.com")
    second = _register(client, email="two@example.com")
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}

    category = client.post(
        "/api/categories",
        headers=second_headers,
        json={"type": "expense", "name": "Rahasia"},
    )
    assert category.status_code == 201

    response = client.post(
        "/api/transactions",
        headers=first_headers,
        json={
            "type": "expense",
            "amount": 1000,
            "category_id": category.json()["id"],
            "transaction_date": "2026-05-30",
        },
    )
    assert response.status_code == 400
