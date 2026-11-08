"""Rate-limit tests for the account-security endpoints.

Contract windows (all 15 minutes):

- ``account_action_limiter`` 5 (change-password, delete account)
- ``forgot_password_limiter`` 10 per IP
- ``forgot_password_email_limiter`` 3 per email
- ``reset_password_limiter`` 30 per IP

The exact maxima are lowered through ``monkeypatch`` so a test needs a handful
of requests instead of the production count.
"""

from __future__ import annotations

import pytest

from backend.tests.account_security_helpers import bearer, build_client, register


@pytest.fixture
def client(tmp_path, monkeypatch):
    with build_client(tmp_path, monkeypatch) as test_client:
        yield test_client


def test_account_action_limiter_blocks_repeated_change_password_failures(client, monkeypatch):
    from backend.app.auth.rate_limit import account_action_limiter

    monkeypatch.setattr(account_action_limiter, "_max_attempts", 2)
    tokens = register(client)

    for _ in range(2):
        response = client.post(
            "/api/auth/change-password",
            json={"current_password": "wrong-password", "new_password": "newpassword123"},
            headers=bearer(tokens),
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong-password", "new_password": "newpassword123"},
        headers=bearer(tokens),
    )

    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") == "900"


def test_forgot_password_ip_limiter_blocks_across_emails(client, monkeypatch):
    from backend.app.auth.rate_limit import (
        forgot_password_email_limiter,
        forgot_password_limiter,
    )

    monkeypatch.setattr(forgot_password_limiter, "_max_attempts", 2)
    monkeypatch.setattr(forgot_password_email_limiter, "_max_attempts", 100)

    for index in range(2):
        response = client.post(
            "/api/auth/forgot-password",
            json={"email": f"ghost{index}@example.com"},
        )
        assert response.status_code == 200

    blocked = client.post(
        "/api/auth/forgot-password",
        json={"email": "ghost-final@example.com"},
    )

    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") == "900"


def test_forgot_password_email_limiter_blocks_one_address(client, monkeypatch):
    from backend.app.auth.rate_limit import (
        forgot_password_email_limiter,
        forgot_password_limiter,
    )

    monkeypatch.setattr(forgot_password_email_limiter, "_max_attempts", 2)
    monkeypatch.setattr(forgot_password_limiter, "_max_attempts", 100)
    register(client)

    for _ in range(2):
        assert (
            client.post(
                "/api/auth/forgot-password", json={"email": "user@example.com"}
            ).status_code
            == 200
        )

    blocked = client.post(
        "/api/auth/forgot-password", json={"email": "user@example.com"}
    )

    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") == "900"


def test_reset_password_limiter_blocks_repeated_attempts(client, monkeypatch):
    from backend.app.auth.rate_limit import reset_password_limiter

    monkeypatch.setattr(reset_password_limiter, "_max_attempts", 2)
    register(client)

    for _ in range(2):
        response = client.post(
            "/api/auth/reset-password",
            json={
                "request_id": "unknown-request",
                "code": "123456",
                "new_password": "newpassword123",
            },
        )
        assert response.status_code == 400

    blocked = client.post(
        "/api/auth/reset-password",
        json={
            "request_id": "unknown-request",
            "code": "123456",
            "new_password": "newpassword123",
        },
    )

    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") == "900"
