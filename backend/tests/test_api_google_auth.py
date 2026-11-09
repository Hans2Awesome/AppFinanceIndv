"""API tests for the Google sign-in and linking routes.

The verifier boundary (``backend.app.routes.auth.verify_google_id_token``) is
monkeypatched, so no token is ever sent to Google. Route ownership logic,
database effects and rate limiting run for real against a throwaway SQLite file.
"""

from __future__ import annotations

import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.google import GoogleTokenError, GoogleUnavailable


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "google_auth.sqlite3")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-0123456789abcdef")
    monkeypatch.setenv("GOOGLE_WEB_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    # Keep proxy-header handling out of the picture so every request is loopback.
    monkeypatch.delenv("TRUSTED_PROXIES", raising=False)

    from backend.app.main import app

    with TestClient(app) as test_client:
        yield test_client


def _fake_verifier(subject="sub-1", email="new@example.com", first_name="Andi"):
    def verify(_raw_token):
        from backend.app.auth.google import VerifiedGoogleIdentity

        return VerifiedGoogleIdentity(subject=subject, email=email, first_name=first_name)

    return verify


def _patch(monkeypatch, behaviour):
    """Install a verifier stub; exceptions are the stub's own return style."""

    import backend.app.routes.auth as auth_module

    monkeypatch.setattr(auth_module, "verify_google_id_token", behaviour)


def _register(client, email="person@example.com", password="password123"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "first_name": "Person"},
    )
    assert response.status_code == 201
    return response.json()


def _count_users(db_file):
    connection = sqlite3.connect(db_file)
    try:
        return connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        connection.close()


def _category_count(db_file, user_id):
    connection = sqlite3.connect(db_file)
    try:
        return connection.execute(
            "SELECT COUNT(*) FROM categories WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    finally:
        connection.close()


# --- POST /api/auth/google -------------------------------------------------


def test_new_subject_creates_user_with_categories_and_one_token(client, monkeypatch):
    _patch(monkeypatch, _fake_verifier(subject="sub-new", email="fresh@example.com"))

    response = client.post("/api/auth/google", json={"id_token": "good"})

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["email"] == "fresh@example.com"
    assert body["user"]["google_linked"] is True
    assert body["user"]["has_password"] is False
    assert _count_users(os.environ["DATABASE_PATH"]) == 1
    assert _category_count(os.environ["DATABASE_PATH"], body["user"]["id"]) > 0


def test_repeat_subject_returns_same_user(client, monkeypatch):
    _patch(monkeypatch, _fake_verifier(subject="sub-same", email="same@example.com"))

    first = client.post("/api/auth/google", json={"id_token": "good"}).json()
    second = client.post("/api/auth/google", json={"id_token": "good"}).json()

    assert first["user"]["id"] == second["user"]["id"]
    assert _count_users(os.environ["DATABASE_PATH"]) == 1


def test_verified_email_colliding_with_password_account_is_conflict(client, monkeypatch):
    _register(client, email="taken@example.com")
    _patch(monkeypatch, _fake_verifier(subject="sub-collide", email="taken@example.com"))

    response = client.post("/api/auth/google", json={"id_token": "good"})

    assert response.status_code == 409
    # The existing password account is untouched; no second row is created.
    assert _count_users(os.environ["DATABASE_PATH"]) == 1


def test_invalid_token_is_unauthorized(client, monkeypatch):
    def invalid(_raw_token):
        raise GoogleTokenError("bad")

    _patch(monkeypatch, invalid)

    response = client.post("/api/auth/google", json={"id_token": "bad"})

    assert response.status_code == 401
    assert _count_users(os.environ["DATABASE_PATH"]) == 0


def test_unavailable_config_is_service_unavailable(client, monkeypatch):
    def unavailable(_raw_token):
        raise GoogleUnavailable("not configured")

    _patch(monkeypatch, unavailable)

    response = client.post("/api/auth/google", json={"id_token": "any"})

    assert response.status_code == 503


def test_response_never_exposes_google_sub(client, monkeypatch):
    _patch(monkeypatch, _fake_verifier(subject="secret-subject", email="hidden@example.com"))

    text = client.post("/api/auth/google", json={"id_token": "good"}).text

    assert "secret-subject" not in text
    assert "google_sub" not in text


# --- POST /api/auth/google/link -------------------------------------------


def test_link_requires_bearer_session(client, monkeypatch):
    _patch(monkeypatch, _fake_verifier(subject="sub-x", email="x@example.com"))

    response = client.post(
        "/api/auth/google/link",
        json={"id_token": "good", "password": "password123"},
    )

    assert response.status_code == 401


def test_link_with_wrong_password_is_unauthorized(client, monkeypatch):
    registered = _register(client, email="wrongpw@example.com")
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    _patch(monkeypatch, _fake_verifier(subject="sub-w", email="wrongpw@example.com"))

    response = client.post(
        "/api/auth/google/link",
        json={"id_token": "good", "password": "not-the-password"},
        headers=headers,
    )

    assert response.status_code == 401


def test_link_happy_path_marks_account_google_linked(client, monkeypatch):
    registered = _register(client, email="link@example.com")
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    _patch(monkeypatch, _fake_verifier(subject="sub-link", email="link@example.com"))

    response = client.post(
        "/api/auth/google/link",
        json={"id_token": "good", "password": "password123"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["google_linked"] is True
    assert client.get("/api/auth/me", headers=headers).json()["google_linked"] is True


def test_link_email_mismatch_is_conflict(client, monkeypatch):
    registered = _register(client, email="account@example.com")
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    _patch(monkeypatch, _fake_verifier(subject="sub-mismatch", email="other@example.com"))

    response = client.post(
        "/api/auth/google/link",
        json={"id_token": "good", "password": "password123"},
        headers=headers,
    )

    assert response.status_code == 409


def test_link_subject_owned_by_another_account_is_conflict(client, monkeypatch):
    first = _register(client, email="first@example.com")
    second = _register(client, email="second@example.com")
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    _patch(monkeypatch, _fake_verifier(subject="shared-sub", email="first@example.com"))

    owned = client.post(
        "/api/auth/google/link",
        json={"id_token": "good", "password": "password123"},
        headers=first_headers,
    )
    assert owned.status_code == 200

    # A second account whose Google email matches cannot steal the subject.
    _patch(monkeypatch, _fake_verifier(subject="shared-sub", email="second@example.com"))
    response = client.post(
        "/api/auth/google/link",
        json={"id_token": "good", "password": "password123"},
        headers=second_headers,
    )

    assert response.status_code == 409


def test_link_is_idempotent_for_same_subject(client, monkeypatch):
    registered = _register(client, email="idem@example.com")
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    _patch(monkeypatch, _fake_verifier(subject="sub-idem", email="idem@example.com"))
    payload = {"id_token": "good", "password": "password123"}

    first = client.post("/api/auth/google/link", json=payload, headers=headers)
    second = client.post("/api/auth/google/link", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["google_linked"] is True


def test_link_rejects_account_without_password(client, monkeypatch):
    _patch(monkeypatch, _fake_verifier(subject="sub-g", email="googleuser@example.com"))
    signed_in = client.post("/api/auth/google", json={"id_token": "good"}).json()
    headers = {"Authorization": f"Bearer {signed_in['access_token']}"}

    response = client.post(
        "/api/auth/google/link",
        json={"id_token": "good", "password": "password123"},
        headers=headers,
    )

    assert response.status_code == 409


def test_google_created_user_can_sign_in_again(client, monkeypatch):
    _patch(monkeypatch, _fake_verifier(subject="sub-return", email="return@example.com"))

    created = client.post("/api/auth/google", json={"id_token": "good"}).json()
    again = client.post("/api/auth/google", json={"id_token": "good"})

    assert again.status_code == 200
    assert again.json()["user"]["id"] == created["user"]["id"]


# --- Rate limiting ---------------------------------------------------------


def _set_max_attempts(monkeypatch, limiter, attempts):
    monkeypatch.setattr(limiter, "_max_attempts", attempts)


def test_google_login_rate_limited_with_retry_after(client, monkeypatch):
    from backend.app.auth.rate_limit import google_login_limiter

    _set_max_attempts(monkeypatch, google_login_limiter, 2)

    def invalid(_raw_token):
        raise GoogleTokenError("bad")

    _patch(monkeypatch, invalid)

    for _ in range(2):
        assert client.post("/api/auth/google", json={"id_token": "bad"}).status_code == 401

    blocked = client.post("/api/auth/google", json={"id_token": "bad"})

    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "900"


def test_google_login_failures_counted_before_verification(client, monkeypatch):
    """A failure is recorded even when the verifier later reports 503."""

    from backend.app.auth.rate_limit import google_login_limiter

    _set_max_attempts(monkeypatch, google_login_limiter, 2)

    def unavailable(_raw_token):
        raise GoogleUnavailable("down")

    _patch(monkeypatch, unavailable)

    for _ in range(2):
        assert client.post("/api/auth/google", json={"id_token": "any"}).status_code == 503

    blocked = client.post("/api/auth/google", json={"id_token": "any"})
    assert blocked.status_code == 429


def test_google_link_rate_limited_with_retry_after(client, monkeypatch):
    from backend.app.auth.rate_limit import google_link_limiter

    _set_max_attempts(monkeypatch, google_link_limiter, 2)

    registered = _register(client, email="limited@example.com")
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    _patch(monkeypatch, _fake_verifier(subject="sub-l", email="limited@example.com"))

    for _ in range(2):
        response = client.post(
            "/api/auth/google/link",
            json={"id_token": "good", "password": "wrong-password"},
            headers=headers,
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/auth/google/link",
        json={"id_token": "good", "password": "password123"},
        headers=headers,
    )

    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "900"
