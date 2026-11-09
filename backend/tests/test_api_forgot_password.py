"""Tests for ``POST /api/auth/forgot-password``.

Contract:

- ``{email}`` -> ``{message, request_id, expires_in: 600}``
- identical shape for an existing password user, an unknown email, and a
  Google-only account
- only an account with a password triggers an e-mail
- the code is delivered by ``send_password_reset_email`` and never returned
- missing ``SMTP_HOST`` or ``SMTP_FROM`` is ``503`` for every email
- a delivery failure invalidates the request and still answers generically
- a second request invalidates the first
"""

from __future__ import annotations

import json
import logging

import pytest

from backend.tests.account_security_helpers import (
    build_client,
    capture_reset_email,
    create_google_only_user,
    fetch_reset_requests,
    register,
    reset_request_count,
)

GENERIC_KEYS = {"message", "request_id", "expires_in"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    with build_client(tmp_path, monkeypatch) as test_client:
        yield test_client


@pytest.fixture
def client_without_smtp(tmp_path, monkeypatch):
    with build_client(tmp_path, monkeypatch, smtp=False) as test_client:
        yield test_client


def _forgot(client, email):
    return client.post("/api/auth/forgot-password", json={"email": email})


# --- Generic response ------------------------------------------------------


def test_existing_password_user_gets_request_id_and_sends_email(client, monkeypatch):
    tokens = register(client)
    recorder = capture_reset_email(monkeypatch)

    response = _forgot(client, "user@example.com")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == GENERIC_KEYS
    assert body["expires_in"] == 600
    assert body["message"]
    assert isinstance(body["request_id"], str) and body["request_id"]

    assert len(recorder.calls) == 1
    assert recorder.emails == ["user@example.com"]
    rows = fetch_reset_requests(body["request_id"])
    assert len(rows) == 1
    assert rows[0]["user_id"] == tokens["user"]["id"]


def test_unknown_email_returns_same_shape_without_storing_a_request(client, monkeypatch):
    recorder = capture_reset_email(monkeypatch)

    response = _forgot(client, "ghost@example.com")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == GENERIC_KEYS
    assert body["expires_in"] == 600
    assert recorder.calls == []
    assert fetch_reset_requests(body["request_id"]) == []
    assert reset_request_count() == 0


def test_google_only_account_gets_same_shape_without_sending_email(client, monkeypatch):
    create_google_only_user(google_sub="sub-forgot", email="google@example.com")
    recorder = capture_reset_email(monkeypatch)

    response = _forgot(client, "google@example.com")

    assert response.status_code == 200
    assert set(response.json()) == GENERIC_KEYS
    assert recorder.calls == []
    assert reset_request_count() == 0


def test_message_is_identical_for_known_and_unknown_email(client, monkeypatch):
    register(client)
    capture_reset_email(monkeypatch)

    known = _forgot(client, "user@example.com").json()
    unknown = _forgot(client, "ghost@example.com").json()

    assert known["message"] == unknown["message"]


# --- Code secrecy ----------------------------------------------------------


def test_code_is_never_returned_and_not_stored_in_plaintext(client, monkeypatch):
    register(client)
    recorder = capture_reset_email(monkeypatch)

    response = _forgot(client, "user@example.com")
    body = response.json()
    code = recorder.codes[0]

    assert code
    assert "code" not in body
    assert code not in body["message"]
    stored = fetch_reset_requests(body["request_id"])[0]["code_hash"]
    assert stored
    assert stored != code
    assert code not in str(stored)


def test_code_is_not_written_to_logs(client, monkeypatch, caplog):
    register(client)
    recorder = capture_reset_email(monkeypatch)

    with caplog.at_level(logging.DEBUG):
        _forgot(client, "user@example.com")

    assert recorder.codes
    assert recorder.codes[0] not in caplog.text


# --- Resend invalidation ---------------------------------------------------


def test_resend_replaces_the_previous_request(client, monkeypatch):
    tokens = register(client)
    recorder = capture_reset_email(monkeypatch)

    first = _forgot(client, "user@example.com").json()
    first_code = recorder.codes[-1]
    second = _forgot(client, "user@example.com").json()

    assert second["request_id"] != first["request_id"]
    assert reset_request_count(tokens["user"]["id"]) == 1
    assert fetch_reset_requests(first["request_id"]) == []

    # The superseded code no longer resets anything.
    stale = client.post(
        "/api/auth/reset-password",
        json={
            "request_id": first["request_id"],
            "code": first_code,
            "new_password": "newpassword123",
        },
    )
    assert stale.status_code == 400


# --- SMTP configuration ----------------------------------------------------


def test_missing_smtp_host_is_503_for_every_email(client_without_smtp):
    register(client_without_smtp)

    assert _forgot(client_without_smtp, "user@example.com").status_code == 503
    assert _forgot(client_without_smtp, "ghost@example.com").status_code == 503
    assert reset_request_count() == 0


def test_missing_smtp_from_is_503(client, monkeypatch):
    monkeypatch.delenv("SMTP_FROM", raising=False)
    register(client)

    assert _forgot(client, "user@example.com").status_code == 503


def test_delivery_failure_invalidates_request_and_stays_generic(client, monkeypatch):
    register(client)

    import backend.app.routes.account_security as module

    def failing_sender(*_args, **_kwargs):
        raise RuntimeError("smtp is down")

    monkeypatch.setattr(module, "send_password_reset_email", failing_sender)

    response = _forgot(client, "user@example.com")

    assert response.status_code == 200
    assert set(response.json()) == GENERIC_KEYS
    assert "smtp is down" not in json.dumps(response.json())
    assert reset_request_count() == 0


# --- Throttling ------------------------------------------------------------


def test_forgot_password_email_limiter_blocks_the_fourth_request(client, monkeypatch):
    register(client)
    capture_reset_email(monkeypatch)

    for _ in range(3):
        assert _forgot(client, "user@example.com").status_code == 200

    blocked = _forgot(client, "user@example.com")

    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") == "900"
