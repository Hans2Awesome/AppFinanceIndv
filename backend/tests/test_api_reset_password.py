"""Tests for ``POST /api/auth/reset-password``.

Contract:

- ``{request_id, code, new_password}`` -> ``{message}`` with no tokens
- wrong, expired, used, or unknown request -> ``400``
- the guess counter is persisted and the request dies after five failures
- a request is single use
- a successful reset revokes every existing session
"""

from __future__ import annotations

import pytest

from backend.tests.account_security_helpers import (
    bearer,
    build_client,
    fetch_reset_requests,
    register,
    request_password_reset,
    set_reset_expiry,
)


def test_random_request_id_never_runs_bcrypt(client, monkeypatch):
    import backend.app.routes.account_security as module

    def reject_hash(_password):
        raise AssertionError("Unknown recovery request must not run bcrypt")

    monkeypatch.setattr(module, "hash_password", reject_hash)
    response = client.post(
        "/api/auth/reset-password",
        json={"request_id": "unknown-request", "code": "123456", "new_password": "password456"},
    )
    assert response.status_code == 400

@pytest.fixture
def client(tmp_path, monkeypatch):
    with build_client(tmp_path, monkeypatch) as test_client:
        yield test_client


def _reset(client, request_id, code, new_password="newpassword123"):
    return client.post(
        "/api/auth/reset-password",
        json={"request_id": request_id, "code": code, "new_password": new_password},
    )


def _wrong_code(code):
    return "000000" if code != "000000" else "111111"


# --- Happy path ------------------------------------------------------------


def test_reset_password_returns_only_a_message(client, monkeypatch):
    register(client)
    request_id, code, _ = request_password_reset(client, monkeypatch)

    response = _reset(client, request_id, code)

    assert response.status_code == 200
    assert set(response.json()) == {"message"}
    assert "access_token" not in response.json()
    assert "refresh_token" not in response.json()


def test_reset_password_sets_the_new_password_and_revokes_every_session(client, monkeypatch):
    tokens = register(client)
    second_session = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    ).json()
    request_id, code, _ = request_password_reset(client, monkeypatch)

    assert _reset(client, request_id, code, new_password="rotated123").status_code == 200

    # Both previously issued session pairs are dead.
    assert client.get("/api/auth/me", headers=bearer(tokens)).status_code == 401
    assert (
        client.post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/refresh", json={"refresh_token": second_session["refresh_token"]}
        ).status_code
        == 401
    )

    assert (
        client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "rotated123"},
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


# --- One use ---------------------------------------------------------------


def test_reset_password_request_is_single_use(client, monkeypatch):
    register(client)
    request_id, code, _ = request_password_reset(client, monkeypatch)

    assert _reset(client, request_id, code).status_code == 200
    assert fetch_reset_requests(request_id) == []
    assert _reset(client, request_id, code).status_code == 400


# --- Rejections ------------------------------------------------------------


def test_reset_password_rejects_unknown_request_id(client):
    register(client)

    response = _reset(client, "does-not-exist", "123456")

    assert response.status_code == 400


def test_reset_password_wrong_code_is_rejected_and_persists_attempt(client, monkeypatch):
    register(client)
    request_id, code, _ = request_password_reset(client, monkeypatch)

    response = _reset(client, request_id, _wrong_code(code))

    assert response.status_code == 400
    rows = fetch_reset_requests(request_id)
    assert len(rows) == 1
    assert rows[0]["attempts"] == 1


def test_reset_password_dies_after_five_wrong_guesses(client, monkeypatch):
    register(client)
    request_id, code, _ = request_password_reset(client, monkeypatch)
    wrong = _wrong_code(code)

    for _ in range(5):
        assert _reset(client, request_id, wrong).status_code == 400

    rows = fetch_reset_requests(request_id)
    assert not rows or rows[0]["attempts"] >= 5
    # Even the real code is refused once the request is spent.
    assert _reset(client, request_id, code).status_code == 400


def test_reset_password_rejects_expired_code(client, monkeypatch):
    register(client)
    request_id, code, _ = request_password_reset(client, monkeypatch)
    set_reset_expiry(request_id, 0)

    assert _reset(client, request_id, code).status_code == 400


def test_reset_password_rejects_short_new_password(client, monkeypatch):
    register(client)
    request_id, code, _ = request_password_reset(client, monkeypatch)

    assert _reset(client, request_id, code, new_password="short").status_code == 422


def test_reset_password_rejects_new_password_over_72_bytes(client, monkeypatch):
    register(client)
    request_id, code, _ = request_password_reset(client, monkeypatch)

    assert _reset(client, request_id, code, new_password="a" * 73).status_code == 422
