"""Unit tests for the Google ID token verifier.

Only the boundary to Google is mocked: ``id_token.verify_oauth2_token`` and the
shared transport request. The claim checks, the audience wiring and the error
translation are exercised for real.
"""

from __future__ import annotations

import pytest
from google.auth import exceptions as google_exceptions

from backend.app.auth import google as google_module
from backend.app.auth.google import (
    GOOGLE_ISSUERS,
    GoogleTokenError,
    GoogleUnavailable,
    verify_google_id_token,
)

CLIENT_ID = "test-client-id.apps.googleusercontent.com"


@pytest.fixture
def audience(monkeypatch):
    """Configure a Web client ID so the verifier passes its config guard."""

    monkeypatch.setenv("GOOGLE_WEB_CLIENT_ID", CLIENT_ID)
    return CLIENT_ID


class _Recorder:
    """Stand-in for the Google transport request; never touches the network."""

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return object()


def _patch_verifier(monkeypatch, claims, *, error=None):
    """Replace the official verifier and capture the exact call arguments."""

    recorder = _Recorder()
    calls = {}

    def fake_verify(raw_token, request, **kwargs):
        calls["raw_token"] = raw_token
        calls["request"] = request
        calls.update(kwargs)
        if error is not None:
            raise error
        return claims

    monkeypatch.setattr(google_module.id_token, "verify_oauth2_token", fake_verify)
    monkeypatch.setattr(google_module, "_request", lambda: recorder)
    return calls


def _claims(**overrides):
    base = {
        "iss": "accounts.google.com",
        "sub": "subject-123",
        "email": "user@example.com",
        "email_verified": True,
    }
    base.update(overrides)
    return base


def test_audience_and_request_come_from_server_not_caller(audience, monkeypatch):
    calls = _patch_verifier(monkeypatch, _claims())

    identity = verify_google_id_token("raw-token")

    # The client cannot influence the audience; the server's own value is used.
    assert calls["audience"] == audience
    assert calls["raw_token"] == "raw-token"
    # A transport request object is supplied, not taken from the token.
    assert calls["request"].__class__ is _Recorder
    assert identity.subject == "subject-123"


def test_unexpected_issuer_is_rejected(audience, monkeypatch):
    _patch_verifier(monkeypatch, _claims(iss="https://evil.example.com"))

    with pytest.raises(GoogleTokenError):
        verify_google_id_token("raw-token")


@pytest.mark.parametrize("iss", GOOGLE_ISSUERS)
def test_both_google_issuers_are_accepted(audience, monkeypatch, iss):
    _patch_verifier(monkeypatch, _claims(iss=iss))

    identity = verify_google_id_token("raw-token")

    assert identity.subject == "subject-123"


@pytest.mark.parametrize("subject", [None, "", 123, [], {}])
def test_empty_or_missing_subject_is_rejected(audience, monkeypatch, subject):
    claims = _claims()
    if subject is None:
        claims.pop("sub")
    else:
        claims["sub"] = subject
    _patch_verifier(monkeypatch, claims)

    with pytest.raises(GoogleTokenError):
        verify_google_id_token("raw-token")


def test_missing_email_is_rejected(audience, monkeypatch):
    claims = _claims()
    claims.pop("email")
    _patch_verifier(monkeypatch, claims)

    with pytest.raises(GoogleTokenError):
        verify_google_id_token("raw-token")


@pytest.mark.parametrize(
    "verified",
    [False, "true", "false", 1, None, 0],
    ids=["false", "string-true", "string-false", "int-1", "none", "int-0"],
)
def test_unverified_email_shapes_are_rejected(audience, monkeypatch, verified):
    _patch_verifier(monkeypatch, _claims(email_verified=verified))

    with pytest.raises(GoogleTokenError):
        verify_google_id_token("raw-token")


def test_missing_email_verified_is_rejected(audience, monkeypatch):
    claims = _claims()
    claims.pop("email_verified")
    _patch_verifier(monkeypatch, claims)

    with pytest.raises(GoogleTokenError):
        verify_google_id_token("raw-token")


def test_email_is_lowercased_and_trimmed(audience, monkeypatch):
    _patch_verifier(monkeypatch, _claims(email="  MiXeD@Example.COM  "))

    identity = verify_google_id_token("raw-token")

    assert identity.email == "mixed@example.com"


def test_transport_error_becomes_unavailable(audience, monkeypatch):
    _patch_verifier(monkeypatch, None, error=google_exceptions.TransportError("no route"))

    with pytest.raises(GoogleUnavailable):
        verify_google_id_token("raw-token")


def test_value_error_becomes_token_error(audience, monkeypatch):
    _patch_verifier(monkeypatch, None, error=ValueError("wrong audience"))

    with pytest.raises(GoogleTokenError):
        verify_google_id_token("raw-token")


def test_absent_client_id_raises_unavailable(monkeypatch):
    monkeypatch.setenv("GOOGLE_WEB_CLIENT_ID", "")
    calls = _patch_verifier(monkeypatch, _claims())

    with pytest.raises(GoogleUnavailable):
        verify_google_id_token("raw-token")

    # The verifier must not even be called without a configured audience.
    assert calls == {}


def test_given_name_is_preferred(audience, monkeypatch):
    _patch_verifier(monkeypatch, _claims(given_name="  Andi ", name="Andi Wijaya"))

    identity = verify_google_id_token("raw-token")

    assert identity.first_name == "Andi"


def test_name_is_used_when_given_name_is_absent(audience, monkeypatch):
    _patch_verifier(monkeypatch, _claims(name="Andi Wijaya"))

    identity = verify_google_id_token("raw-token")

    assert identity.first_name == "Andi Wijaya"


def test_name_truncated_and_blank_name_becomes_none(audience, monkeypatch):
    _patch_verifier(monkeypatch, _claims(given_name="x" * 200))

    identity = verify_google_id_token("raw-token")
    assert identity.first_name == "x" * 80

    _patch_verifier(monkeypatch, _claims(name="   "))

    identity = verify_google_id_token("raw-token")
    assert identity.first_name is None
