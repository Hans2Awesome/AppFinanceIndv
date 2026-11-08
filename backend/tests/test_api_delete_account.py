"""Tests for ``DELETE /api/auth/account``.

Contract:

- authenticated; body ``{confirmation: "DELETE", password?, id_token?}``
- ``204`` on success, ``422`` for a missing or wrong confirmation
- a password is required even when the account is Google-linked
- a Google-only account proves identity with an id token whose subject matches
  the stored Google subject, and whose ``issued_at`` (when present) is at most
  five minutes old; stale or mismatched tokens are ``401``
- deletion cascades every live row for that user and leaves other users alone
- previously issued access and refresh tokens stop working
"""

from __future__ import annotations

import time

import pytest

from backend.tests.account_security_helpers import (
    access_token_for,
    bearer,
    build_client,
    create_google_only_user,
    google_identity,
    link_google_to_user,
    patch_delete_verifier,
    register,
    table_count,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    with build_client(tmp_path, monkeypatch) as test_client:
        yield test_client


def _delete(client, tokens, **body):
    payload = {"confirmation": "DELETE", **body}
    return client.request("DELETE", "/api/auth/account", json=payload, headers=bearer(tokens))


# --- Password account ------------------------------------------------------


def test_delete_password_account_returns_204_and_revokes_tokens(client):
    tokens = register(client)

    response = _delete(client, tokens, password="password123")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/api/auth/me", headers=bearer(tokens)).status_code == 401
    assert (
        client.post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    assert table_count("users", "id = ?", (tokens["user"]["id"],)) == 0


def test_delete_password_account_requires_password(client):
    tokens = register(client)

    response = _delete(client, tokens)

    assert response.status_code in (401, 422)
    assert client.get("/api/auth/me", headers=bearer(tokens)).status_code == 200


def test_delete_password_account_with_wrong_password_is_unauthorized(client):
    tokens = register(client)

    response = _delete(client, tokens, password="not-the-password")

    assert response.status_code == 401
    assert client.get("/api/auth/me", headers=bearer(tokens)).status_code == 200


def test_delete_requires_authentication(client):
    register(client)

    response = client.request(
        "DELETE",
        "/api/auth/account",
        json={"confirmation": "DELETE", "password": "password123"},
    )

    assert response.status_code == 401


# --- Confirmation ----------------------------------------------------------


def test_delete_rejects_missing_confirmation(client):
    tokens = register(client)

    response = client.request(
        "DELETE",
        "/api/auth/account",
        json={"password": "password123"},
        headers=bearer(tokens),
    )

    assert response.status_code == 422


def test_delete_rejects_wrong_confirmation(client):
    tokens = register(client)

    response = _delete(client, tokens, confirmation="delete", password="password123")

    assert response.status_code == 422


# --- Cascade ---------------------------------------------------------------


def test_delete_cascades_all_live_rows_and_spares_other_user(client):
    victim = register(client, email="victim@example.com")
    other = register(client, email="other@example.com")
    victim_id = victim["user"]["id"]
    other_id = other["user"]["id"]

    created = client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "category_name": "Makan & Minum",
            "amount": 15000,
            "transaction_date": "2026-11-02",
        },
        headers=bearer(victim),
    )
    assert created.status_code == 201, created.text
    debt = client.post(
        "/api/debts",
        json={"type": "debt", "person_name": "Budi", "total_amount": 500000},
        headers=bearer(victim),
    )
    assert debt.status_code == 201, debt.text
    other_tx = client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "category_name": "Transportasi",
            "amount": 20000,
            "transaction_date": "2026-11-02",
        },
        headers=bearer(other),
    )
    assert other_tx.status_code == 201, other_tx.text

    assert _delete(client, victim, password="password123").status_code == 204

    assert table_count("users", "id = ?", (victim_id,)) == 0
    for table in (
        "categories",
        "transactions",
        "debts",
        "recurring_transactions",
        "password_reset_requests",
    ):
        assert table_count(table, "user_id = ?", (victim_id,)) == 0, table

    # The other user is untouched and still authenticated.
    assert table_count("users", "id = ?", (other_id,)) == 1
    assert table_count("transactions", "user_id = ?", (other_id,)) == 1
    assert table_count("categories", "user_id = ?", (other_id,)) >= 1
    assert client.get("/api/auth/me", headers=bearer(other)).status_code == 200


# --- Google-only account ---------------------------------------------------


def _fresh_google_token(monkeypatch, *, subject, email="google@example.com", issued_at=None):
    identity = google_identity(subject, email, issued_at=issued_at)
    patch_delete_verifier(monkeypatch, lambda _raw_token: identity)


def test_delete_google_only_with_fresh_token_succeeds(client, monkeypatch):
    user = create_google_only_user(google_sub="sub-del-fresh", email="google@example.com")
    token = access_token_for(user)
    _fresh_google_token(
        monkeypatch, subject="sub-del-fresh", issued_at=int(time.time())
    )

    response = client.request(
        "DELETE",
        "/api/auth/account",
        json={"confirmation": "DELETE", "id_token": "fresh"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_delete_google_only_without_issued_at_is_rejected(client, monkeypatch):
    """A Google proof must carry an ``issued_at``; a bare subject is not enough.

    The freshness bound is only meaningful when the token says when it was
    minted, so a missing timestamp is treated as unverifiable and refused.
    """

    user = create_google_only_user(google_sub="sub-del-none", email="google@example.com")
    token = access_token_for(user)
    _fresh_google_token(monkeypatch, subject="sub-del-none", issued_at=None)

    response = client.request(
        "DELETE",
        "/api/auth/account",
        json={"confirmation": "DELETE", "id_token": "opaque"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_delete_google_only_accepts_fresh_token_within_five_minutes(client, monkeypatch):
    user = create_google_only_user(google_sub="sub-del-bound", email="google@example.com")
    token = access_token_for(user)
    # Just inside the five-minute window (margin for test execution time).
    _fresh_google_token(
        monkeypatch, subject="sub-del-bound", issued_at=int(time.time()) - 290
    )

    response = client.request(
        "DELETE",
        "/api/auth/account",
        json={"confirmation": "DELETE", "id_token": "recent"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204


def test_delete_google_only_with_future_issued_at_is_rejected(client, monkeypatch):
    """A token minted well in the future is not a valid freshness proof."""

    user = create_google_only_user(google_sub="sub-del-future", email="google@example.com")
    token = access_token_for(user)
    _fresh_google_token(
        monkeypatch, subject="sub-del-future", issued_at=int(time.time()) + 120
    )

    response = client.request(
        "DELETE",
        "/api/auth/account",
        json={"confirmation": "DELETE", "id_token": "from-the-future"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_delete_google_only_allows_small_clock_skew(client, monkeypatch):
    """Up to 60 seconds of future drift is tolerated, matching the verifier."""

    user = create_google_only_user(google_sub="sub-del-skew", email="google@example.com")
    token = access_token_for(user)
    _fresh_google_token(
        monkeypatch, subject="sub-del-skew", issued_at=int(time.time()) + 30
    )

    response = client.request(
        "DELETE",
        "/api/auth/account",
        json={"confirmation": "DELETE", "id_token": "skewed"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204


def test_delete_google_only_with_stale_token_is_unauthorized(client, monkeypatch):
    user = create_google_only_user(google_sub="sub-del-stale", email="google@example.com")
    token = access_token_for(user)
    _fresh_google_token(
        monkeypatch, subject="sub-del-stale", issued_at=int(time.time()) - 600
    )

    response = client.request(
        "DELETE",
        "/api/auth/account",
        json={"confirmation": "DELETE", "id_token": "old"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_delete_google_only_with_mismatched_subject_is_unauthorized(client, monkeypatch):
    user = create_google_only_user(google_sub="sub-del-owner", email="google@example.com")
    token = access_token_for(user)
    _fresh_google_token(
        monkeypatch, subject="sub-del-attacker", issued_at=int(time.time())
    )

    response = client.request(
        "DELETE",
        "/api/auth/account",
        json={"confirmation": "DELETE", "id_token": "someone-else"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_delete_google_linked_password_account_still_requires_password(client, monkeypatch):
    tokens = register(client, email="linked@example.com")
    link_google_to_user(tokens["user"]["id"], "sub-linked")
    _fresh_google_token(monkeypatch, subject="sub-linked", email="linked@example.com", issued_at=int(time.time()))

    refused = _delete(client, tokens, id_token="fresh")
    assert refused.status_code in (401, 422)
    assert client.get("/api/auth/me", headers=bearer(tokens)).status_code == 200

    accepted = _delete(client, tokens, password="password123", id_token="fresh")
    assert accepted.status_code == 204
