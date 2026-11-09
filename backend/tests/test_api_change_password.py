"""Tests for ``POST /api/auth/change-password``.

Contract:

- authenticated password user only; ``{current_password, new_password}``
- returns a fresh ``TokenResponse``
- Google-only account is ``409``, wrong current password is ``401``
- new password: at least 8 characters, at most 72 UTF-8 bytes
- revokes the caller's old access and refresh tokens and pending reset codes
"""

from __future__ import annotations

import pytest

from backend.tests.account_security_helpers import (
    access_token_for,
    bearer,
    build_client,
    capture_reset_email,
    create_google_only_user,
    register,
    reset_request_count,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    with build_client(tmp_path, monkeypatch) as test_client:
        yield test_client


def _change(client, tokens, current="password123", new="newpassword123"):
    return client.post(
        "/api/auth/change-password",
        json={"current_password": current, "new_password": new},
        headers=bearer(tokens),
    )


# --- Happy path ------------------------------------------------------------


def test_change_password_returns_new_tokens_and_user(client):
    tokens = register(client)

    response = _change(client, tokens)

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["email"] == "user@example.com"
    assert body["token_type"] == "bearer"
    assert client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    ).status_code == 200


def test_change_password_revokes_old_access_and_refresh_tokens(client):
    tokens = register(client)

    rotated = _change(client, tokens).json()

    assert client.get("/api/auth/me", headers=bearer(tokens)).status_code == 401
    assert (
        client.post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/refresh", json={"refresh_token": rotated["refresh_token"]}
        ).status_code
        == 200
    )


def test_change_password_makes_new_password_effective(client):
    tokens = register(client)

    assert _change(client, tokens, new="brandnew123").status_code == 200

    assert (
        client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "brandnew123"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        ).status_code
        == 401
    )


# --- Rejections ------------------------------------------------------------


def test_change_password_requires_authentication(client):
    register(client)

    response = client.post(
        "/api/auth/change-password",
        json={"current_password": "password123", "new_password": "newpassword123"},
    )

    assert response.status_code == 401


def test_change_password_with_wrong_current_password_is_unauthorized(client):
    tokens = register(client)

    response = _change(client, tokens, current="not-the-password")

    assert response.status_code == 401
    # The stored password is untouched.
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        ).status_code
        == 200
    )


def test_change_password_on_google_only_account_is_conflict(client):
    user = create_google_only_user(google_sub="sub-no-password", email="google@example.com")
    headers = {"Authorization": f"Bearer {access_token_for(user)}"}

    response = client.post(
        "/api/auth/change-password",
        json={"current_password": "whatever", "new_password": "newpassword123"},
        headers=headers,
    )

    assert response.status_code == 409


# --- New-password validation ----------------------------------------------


def test_change_password_rejects_new_password_shorter_than_eight(client):
    tokens = register(client)

    assert _change(client, tokens, new="seven77").status_code == 422


def test_change_password_rejects_new_password_over_72_bytes(client):
    tokens = register(client)

    assert _change(client, tokens, new="a" * 73).status_code == 422


def test_change_password_accepts_new_password_of_exactly_72_bytes(client):
    tokens = register(client)

    assert _change(client, tokens, new="a" * 72).status_code == 200


def test_change_password_measures_utf8_bytes_not_characters(client):
    # 40 x 2-byte characters = 80 bytes, under the 128-character field cap but
    # over bcrypt's 72-byte limit.
    tokens = register(client)

    assert _change(client, tokens, new="\u00e9" * 40).status_code == 422


def test_change_password_accepts_multibyte_password_at_byte_boundary(client):
    # 36 x 2-byte characters = exactly 72 bytes.
    tokens = register(client)

    assert _change(client, tokens, new="\u00e9" * 36).status_code == 200


# --- Reset-code revocation -------------------------------------------------


def test_change_password_revokes_pending_reset_codes(client, monkeypatch):
    owner = register(client, email="owner@example.com")
    other = register(client, email="other@example.com")

    capture_reset_email(monkeypatch)
    owner_reset = client.post(
        "/api/auth/forgot-password", json={"email": "owner@example.com"}
    )
    other_reset = client.post(
        "/api/auth/forgot-password", json={"email": "other@example.com"}
    )
    assert owner_reset.status_code == 200
    assert other_reset.status_code == 200
    owner_id = owner["user"]["id"]
    other_id = other["user"]["id"]
    assert reset_request_count(owner_id) == 1
    assert reset_request_count(other_id) == 1

    assert _change(client, owner).status_code == 200

    # The owner's pending reset request is gone; the other user's is untouched.
    assert reset_request_count(owner_id) == 0
    assert reset_request_count(other_id) == 1

    stale = client.post(
        "/api/auth/reset-password",
        json={
            "request_id": owner_reset.json()["request_id"],
            "code": "000000",
            "new_password": "newpassword123",
        },
    )
    assert stale.status_code == 400
