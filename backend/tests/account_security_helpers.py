"""Shared helpers for the account-security endpoint tests.

The module name does not start with ``test_`` so pytest never collects it as a
suite. It owns the fixtures-free plumbing the ``test_api_*account*.py`` files
share: an isolated SQLite client with mockable SMTP configuration, a recorder
for the reset e-mail sender, and small database probes.

The contract under test lives in ``backend/app/routes/account_security.py``, a
module the parent session implements. Everything here is written against the
published contract, never against internals.
"""

from __future__ import annotations

import os

# Rate limiters the contract names. Cleared between tests through the shared
# ``backend/tests/conftest.py`` autouse fixture and by ``clear_account_security_limiters``.
NEW_LIMITER_NAMES = (
    "account_action_limiter",
    "forgot_password_limiter",
    "forgot_password_email_limiter",
    "reset_password_limiter",
)

SMTP_NAMES = (
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_SECURITY",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_FROM",
)


def clear_account_security_limiters() -> None:
    """Empty the account-security rate-limit buckets."""

    from backend.app.auth import rate_limit

    for name in NEW_LIMITER_NAMES:
        limiter = getattr(rate_limit, name, None)
        buckets = getattr(limiter, "_buckets", None)
        if buckets is not None:
            buckets.clear()


def configure_smtp(monkeypatch, *, host="smtp.example.test", sender="noreply@example.test") -> None:
    monkeypatch.setenv("SMTP_HOST", host)
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_SECURITY", "starttls")
    monkeypatch.setenv("SMTP_USERNAME", "mailer@example.test")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-secret")
    monkeypatch.setenv("SMTP_FROM", sender)


def unset_smtp(monkeypatch) -> None:
    for name in SMTP_NAMES:
        monkeypatch.delenv(name, raising=False)


def build_client(tmp_path, monkeypatch, *, smtp=True, db_name="account_security.sqlite3"):
    """Build a TestClient on a throwaway SQLite file with SMTP configured."""

    if smtp:
        configure_smtp(monkeypatch)
    else:
        unset_smtp(monkeypatch)

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / db_name))
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-1234567890123456789012")
    monkeypatch.setenv("RECURRING_SCHEDULER_ENABLED", "0")

    from fastapi.testclient import TestClient

    from backend.app.main import app

    return TestClient(app)


def register(client, email="user@example.com", password="password123", first_name="User"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "first_name": first_name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def open_test_db():
    from finance_core.db.connection import open_database

    return open_database(os.environ["DATABASE_PATH"])


def fetch_reset_requests(request_id=None):
    """Return ``sqlite3.Row`` objects for one reset request, or all of them."""

    connection = open_test_db()
    try:
        if request_id is None:
            return connection.execute("SELECT * FROM password_reset_requests").fetchall()
        return connection.execute(
            "SELECT * FROM password_reset_requests WHERE request_id = ?",
            (request_id,),
        ).fetchall()
    finally:
        connection.close()


def reset_request_count(user_id=None):
    connection = open_test_db()
    try:
        if user_id is None:
            return connection.execute(
                "SELECT COUNT(*) FROM password_reset_requests"
            ).fetchone()[0]
        return connection.execute(
            "SELECT COUNT(*) FROM password_reset_requests WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
    finally:
        connection.close()


def set_reset_expiry(request_id, expires_at):
    connection = open_test_db()
    try:
        connection.execute(
            "UPDATE password_reset_requests SET expires_at = ? WHERE request_id = ?",
            (expires_at, request_id),
        )
        connection.commit()
    finally:
        connection.close()


def table_count(table, where="", params=()):
    connection = open_test_db()
    try:
        sql = f"SELECT COUNT(*) FROM {table}"
        if where:
            sql += f" WHERE {where}"
        return connection.execute(sql, params).fetchone()[0]
    finally:
        connection.close()


class ResetEmailRecorder:
    """Callable stand-in for ``send_password_reset_email``.

    Accepts positional or keyword arguments so the route may call it either way.
    """

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        email = kwargs.get("email", args[0] if len(args) > 0 else None)
        code = kwargs.get("code", args[1] if len(args) > 1 else None)
        settings = kwargs.get("settings", args[2] if len(args) > 2 else None)
        self.calls.append({"email": email, "code": code, "settings": settings})

    @property
    def codes(self):
        return [call["code"] for call in self.calls]

    @property
    def emails(self):
        return [call["email"] for call in self.calls]


def capture_reset_email(monkeypatch):
    """Install a recorder at the contract's documented mock point."""

    import backend.app.routes.account_security as module

    recorder = ResetEmailRecorder()
    monkeypatch.setattr(module, "send_password_reset_email", recorder)
    return recorder


def create_google_only_user(google_sub="google-sub-1", email="google@example.com"):
    """Create a passwordless Google user straight through the repository."""

    from finance_core.db.connection import open_database, transaction
    from finance_core.db.users import create_google_user

    connection = open_database(os.environ["DATABASE_PATH"])
    try:
        with transaction(connection):
            user = create_google_user(connection, google_sub=google_sub, email=email)
        return user
    finally:
        connection.close()


def link_google_to_user(user_id, google_sub):
    from finance_core.db.connection import open_database, transaction
    from finance_core.db.users import link_google_identity

    connection = open_database(os.environ["DATABASE_PATH"])
    try:
        with transaction(connection):
            link_google_identity(connection, user_id=user_id, google_sub=google_sub)
    finally:
        connection.close()


def access_token_for(user):
    from backend.app.auth.jwt_handler import create_access_token

    return create_access_token(subject=user.id, token_version=user.token_version)


def refresh_token_for(user):
    from backend.app.auth.jwt_handler import create_refresh_token

    return create_refresh_token(subject=user.id, token_version=user.token_version)


def google_identity(subject, email, *, first_name="Google", issued_at=None):
    from backend.app.auth.google import VerifiedGoogleIdentity

    return VerifiedGoogleIdentity(
        subject=subject,
        email=email,
        first_name=first_name,
        issued_at=issued_at,
    )


def patch_delete_verifier(monkeypatch, behaviour):
    """Stub every plausible verifier name bound in the account_security module.

    The contract says the id-token check goes through
    ``backend.app.routes.account_security``. A tiny wrapper may delegate to the
    imported symbol, so both the public name and the common private aliases are
    replaced when present.
    """

    import backend.app.routes.account_security as module

    patched = []
    for name in ("verify_google_id_token", "_verify_google_token", "_verify_google_id_token"):
        if hasattr(module, name):
            monkeypatch.setattr(module, name, behaviour)
            patched.append(name)

    if not patched:
        monkeypatch.setattr(module, "verify_google_id_token", behaviour)


def request_password_reset(client, monkeypatch, email="user@example.com"):
    """Run forgot-password, returning ``(request_id, code, response)``.

    Patches the sender first so the delivered code is captured.
    """

    recorder = capture_reset_email(monkeypatch)
    response = client.post("/api/auth/forgot-password", json={"email": email})
    assert response.status_code == 200, response.text
    assert recorder.calls, "forgot-password did not send a reset e-mail"
    return response.json()["request_id"], recorder.codes[-1], response
