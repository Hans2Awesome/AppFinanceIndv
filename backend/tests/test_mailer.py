"""Tests for ``backend/app/auth/mailer.py``.

``smtplib.SMTP`` and ``smtplib.SMTP_SSL`` are replaced with recorders, so no
socket is opened. The suite pins four things the recovery flow depends on:

- STARTTLS is negotiated with a verifying certificate context before login.
- ``ssl`` mode uses implicit TLS and never falls back to plaintext.
- Incomplete or plaintext SMTP configuration is refused before connecting.
- A send failure raises without writing the code, password, or provider text
  to the logs.
"""

from __future__ import annotations

import logging
import smtplib
import ssl

import pytest

import backend.app.auth.mailer as mailer
from backend.app.config import Settings

VALID = dict(
    secret_key="test-secret-key-1234567890123456789012",
    smtp_host="smtp.example.test",
    smtp_port=587,
    smtp_security="starttls",
    smtp_username="mailer@example.test",
    smtp_password="smtp-secret",
    smtp_from="noreply@example.test",
)


def _settings(**overrides) -> Settings:
    values = dict(VALID)
    values.update(overrides)
    return Settings(**values)


class _ServerBehaviour:
    """Shared recorder behaviour for the fake SMTP classes."""

    def _init(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.events = []
        self.logins = []
        self.messages = []
        self.starttls_context = None

    def __enter__(self):
        self.events.append("enter")
        return self

    def __exit__(self, *exc):
        self.events.append("exit")
        return False

    def ehlo(self):
        self.events.append("ehlo")

    def starttls(self, *, context=None, **_kwargs):
        if self._fail_on_starttls:
            raise smtplib.SMTPException("STARTTLS refused")
        self.starttls_context = context
        self.events.append("starttls")

    def login(self, username, password):
        if self._fail_on_login:
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
        self.logins.append((username, password))
        self.events.append("login")

    def send_message(self, message):
        if self._fail_on_send:
            raise smtplib.SMTPException("550 relaying denied")
        self.messages.append(message)
        self.events.append("send")


@pytest.fixture
def smtp(monkeypatch):
    """Install fake SMTP classes and return the per-call recorders."""

    record = {"plain": [], "ssl": []}

    class FakeSMTP(_ServerBehaviour):
        def __init__(self, host, port, timeout=None):
            self._init(host, port, timeout)
            record["plain"].append(self)

    class FakeSMTP_SSL(_ServerBehaviour):
        def __init__(self, host, port, timeout=None, context=None, **_kwargs):
            self._init(host, port, timeout)
            self.ssl_context = context
            record["ssl"].append(self)

    def _install(*, fail_on_send=False, fail_on_login=False, fail_on_starttls=False):
        for cls in (FakeSMTP, FakeSMTP_SSL):
            cls._fail_on_send = fail_on_send
            cls._fail_on_login = fail_on_login
            cls._fail_on_starttls = fail_on_starttls
        monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
        monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTP_SSL)
        return record

    _install()
    record["install"] = _install
    return record


# --- STARTTLS --------------------------------------------------------------


def test_starttls_negotiates_tls_then_logs_in_and_sends(smtp):
    settings = _settings(smtp_security="starttls", smtp_username="mailer", smtp_password="pw")

    mailer.send_password_reset_email("person@example.com", "123456", settings)

    assert smtp["ssl"] == []
    assert len(smtp["plain"]) == 1
    server = smtp["plain"][0]

    assert (server.host, server.port, server.timeout) == ("smtp.example.test", 587, 10)
    assert server.events == ["enter", "ehlo", "starttls", "ehlo", "login", "send", "exit"]
    assert server.logins == [("mailer", "pw")]

    context = server.starttls_context
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True

    [message] = server.messages
    assert message["From"] == "noreply@example.test"
    assert message["To"] == "person@example.com"
    body = message.get_content()
    assert "123456" in body


def test_starttls_skips_login_when_no_credentials(smtp):
    settings = _settings(smtp_username="", smtp_password="")

    mailer.send_password_reset_email("person@example.com", "123456", settings)

    server = smtp["plain"][0]
    assert "login" not in server.events
    assert "send" in server.events


# --- Implicit TLS ----------------------------------------------------------


def test_ssl_mode_uses_implicit_tls_without_plaintext_downgrade(smtp):
    settings = _settings(smtp_security="ssl", smtp_port=465)

    mailer.send_password_reset_email("person@example.com", "654321", settings)

    assert smtp["plain"] == []
    assert len(smtp["ssl"]) == 1
    server = smtp["ssl"][0]

    assert (server.host, server.port, server.timeout) == ("smtp.example.test", 465, 10)
    assert "starttls" not in server.events
    assert server.events == ["enter", "login", "send", "exit"]

    assert isinstance(server.ssl_context, ssl.SSLContext)
    assert server.ssl_context.verify_mode == ssl.CERT_REQUIRED
    assert server.ssl_context.check_hostname is True
    assert "654321" in server.messages[0].get_content()


# --- Configuration guards --------------------------------------------------


def test_valid_configuration_is_accepted():
    assert mailer.smtp_is_configured(_settings()) is True


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"smtp_host": ""}, id="missing-host"),
        pytest.param({"smtp_from": ""}, id="missing-from"),
        pytest.param({"smtp_security": "none"}, id="plaintext-none"),
        pytest.param({"smtp_security": "plaintext"}, id="plaintext-word"),
        pytest.param({"smtp_security": ""}, id="plaintext-empty"),
        pytest.param({"smtp_port": 0}, id="port-zero"),
        pytest.param({"smtp_port": 70000}, id="port-too-high"),
        pytest.param({"smtp_username": "user", "smtp_password": ""}, id="username-without-password"),
        pytest.param({"smtp_username": "", "smtp_password": "pw"}, id="password-without-username"),
        pytest.param(
            {"smtp_from": "noreply@example.test\nBcc: evil@example.test"}, id="from-header-injection"
        ),
    ],
)
def test_incomplete_or_plaintext_configuration_is_refused_before_connecting(smtp, overrides):
    settings = _settings(**overrides)
    assert mailer.smtp_is_configured(settings) is False

    with pytest.raises(RuntimeError):
        mailer.send_password_reset_email("person@example.com", "123456", settings)

    assert smtp["plain"] == []
    assert smtp["ssl"] == []


# --- Failure hygiene -------------------------------------------------------


def test_send_failure_raises_without_logging_code_or_password(smtp, caplog):
    smtp["install"](fail_on_send=True)
    settings = _settings(smtp_password="top-secret-password")

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(smtplib.SMTPException):
            mailer.send_password_reset_email("person@example.com", "998877", settings)

    assert "998877" not in caplog.text
    assert "top-secret-password" not in caplog.text
    assert "550 relaying denied" not in caplog.text


def test_login_failure_raises_without_logging_credentials(smtp, caplog):
    smtp["install"](fail_on_login=True)
    settings = _settings(smtp_username="mailer", smtp_password="top-secret-password")

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(smtplib.SMTPAuthenticationError):
            mailer.send_password_reset_email("person@example.com", "112233", settings)

    assert "112233" not in caplog.text
    assert "top-secret-password" not in caplog.text


def test_delivery_wrapper_logs_no_code_or_secret_and_invalidates_request(tmp_path, monkeypatch, caplog):
    """The route's failure path is generic: no code, secret, or provider text."""

    from backend.app.routes import account_security as route
    from finance_core.db.account_security import create_reset_request
    from finance_core.db.connection import connect
    from finance_core.db.migrations import run_migrations
    from finance_core.db.users import create_mobile_user

    db_path = str(tmp_path / "delivery.sqlite3")
    connection = connect(db_path)
    run_migrations(connection)
    user = create_mobile_user(connection, email="route@example.com", password_hash="hash")
    create_reset_request(connection, user, "dead-request", "digest", 10**12)
    connection.commit()
    connection.close()

    settings = _settings(
        database_path=db_path,
        smtp_password="top-secret-password",
    )

    def failing_sender(*_args, **_kwargs):
        raise RuntimeError("550 relaying denied for person@example.com")

    monkeypatch.setattr(route, "send_password_reset_email", failing_sender)

    with caplog.at_level(logging.DEBUG):
        route._deliver_reset("person@example.com", "445566", "dead-request", settings)

    assert "445566" not in caplog.text
    assert "top-secret-password" not in caplog.text
    assert "550 relaying denied" not in caplog.text

    verification = connect(db_path)
    try:
        remaining = verification.execute(
            "SELECT COUNT(*) FROM password_reset_requests WHERE request_id = ?",
            ("dead-request",),
        ).fetchone()[0]
    finally:
        verification.close()
    assert remaining == 0
