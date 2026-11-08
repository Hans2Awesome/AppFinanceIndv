"""Verify Google ID tokens for Android sign-in.

The client obtains an ID token from Google Credential Manager and sends it here.
Only the official Google verifier is used, with the Web client ID fixed on the
server so a token minted for another app cannot pass.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import cachecontrol
import requests
from google.auth import exceptions as google_exceptions
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from ..config import get_settings

GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
EMAIL_MAX_LENGTH = 320
SUBJECT_MAX_LENGTH = 255
NAME_MAX_LENGTH = 80


class GoogleTokenError(ValueError):
    """The ID token is malformed, expired, or intended for another audience."""


class GoogleUnavailable(RuntimeError):
    """Google's verifier or its certificate endpoint cannot be reached."""


@dataclass(frozen=True)
class VerifiedGoogleIdentity:
    """The only Google claims the application trusts."""

    subject: str
    email: str
    first_name: str | None
    issued_at: int | None = None


class _TimeoutRequest(Request):
    """Google transport request with a short default timeout."""

    def __call__(self, *args, **kwargs):
        kwargs.setdefault("timeout", 5)
        return super().__call__(*args, **kwargs)


_local = threading.local()


def _request() -> Request:
    request = getattr(_local, "request", None)
    if request is None:
        # CacheControl honours Google's certificate caching headers, so the
        # public keys are not re-downloaded on every login.
        session = requests.session()
        request = _TimeoutRequest(session=cachecontrol.CacheControl(session))
        _local.request = request
    return request


def verify_google_id_token(raw_token: str) -> VerifiedGoogleIdentity:
    """Verify a Google ID token and return its trusted identity claims.

    Raises:
        GoogleUnavailable: Google configuration is absent or keys cannot be fetched.
        GoogleTokenError: Signature, audience, issuer, expiry, or claims are invalid.
    """

    audience = get_settings().google_web_client_id
    if not audience:
        raise GoogleUnavailable("Google sign-in is not configured.")

    try:
        claims = id_token.verify_oauth2_token(
            raw_token,
            _request(),
            audience=audience,
            clock_skew_in_seconds=60,
        )
    except google_exceptions.TransportError as error:
        raise GoogleUnavailable("Google certificate endpoint is unavailable.") from error
    except (ValueError, google_exceptions.GoogleAuthError) as error:
        raise GoogleTokenError("Google ID token is invalid.") from error

    issuer = claims.get("iss")
    subject = claims.get("sub")
    email = claims.get("email")

    if issuer not in GOOGLE_ISSUERS:
        raise GoogleTokenError("Google ID token has an unexpected issuer.")
    if not isinstance(subject, str) or not subject:
        raise GoogleTokenError("Google ID token has no subject.")
    if len(subject) > SUBJECT_MAX_LENGTH:
        raise GoogleTokenError("Google subject is too long.")
    if not isinstance(email, str) or not email:
        raise GoogleTokenError("Google account has no email.")
    if len(email) > EMAIL_MAX_LENGTH:
        raise GoogleTokenError("Google email is too long.")
    if claims.get("email_verified") is not True:
        raise GoogleTokenError("Google email is not verified.")

    first_name = claims.get("given_name") or claims.get("name")
    if not isinstance(first_name, str) or not first_name.strip():
        first_name = None
    else:
        first_name = first_name.strip()[:NAME_MAX_LENGTH]

    return VerifiedGoogleIdentity(
        subject=subject,
        email=email.strip().lower(),
        first_name=first_name,
        issued_at=(
            claims["iat"]
            if isinstance(claims.get("iat"), int) and not isinstance(claims.get("iat"), bool)
            else None
        ),
    )
