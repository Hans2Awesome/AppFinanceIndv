"""Password rotation, email recovery, and verified permanent account deletion."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import sqlite3
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from finance_core.db.account_security import (
    consume_reset_request,
    create_reset_request,
    get_reset_request,
    lock_user,
    replace_password,
)
from finance_core.db.connection import open_database, transaction
from finance_core.db.users import AppUser, get_user_by_email

from ..auth.client_ip import client_ip
from ..auth.dependencies import get_current_user, get_db
from ..auth.google import GoogleTokenError, GoogleUnavailable, verify_google_id_token
from ..auth.jwt_handler import hash_password, verify_password
from ..auth.mailer import send_password_reset_email, smtp_is_configured
from ..auth.rate_limit import (
    SlidingWindowLimiter,
    account_action_limiter,
    forgot_password_email_limiter,
    forgot_password_limiter,
    reset_password_limiter,
)
from ..config import Settings, get_settings
from ..models.schemas import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
)
from .auth import _build_token_response

router = APIRouter(prefix="/api/auth", tags=["Account security"])
logger = logging.getLogger(__name__)
RESET_MESSAGE = "If this email has a password account, a reset code will be sent."
INVALID_CODE = "Reset code is invalid or expired. Request a new code."


def _throttle(limiter: SlidingWindowLimiter, key: str) -> None:
    if limiter.is_blocked(key):
        raise HTTPException(
            429, "Too many attempts. Try again in 15 minutes.", headers={"Retry-After": "900"}
        )
    limiter.register_failure(key)


def _code_digest(request_id: str, code: str, settings: Settings) -> str:
    return hmac.new(
        settings.secret_key.encode(), f"password-reset:{request_id}:{code}".encode(), hashlib.sha256
    ).hexdigest()


def _deliver_reset(email: str, code: str, request_id: str, settings: Settings) -> None:
    """Deliver after commit without exposing account existence or SMTP errors."""

    try:
        send_password_reset_email(email, code, settings)
    except Exception:
        # Never log the SMTP exception: provider diagnostics can contain addresses
        # or credentials. Delete only this request, not a newer concurrent resend.
        logger.warning("Password reset delivery failed; invalidating the challenge.")
        connection = None
        try:
            connection = open_database(settings.database_path, url=settings.database_url)
            with transaction(connection):
                connection.execute(
                    "DELETE FROM password_reset_requests WHERE request_id = ?", (request_id,)
                )
        except Exception:
            logger.error("Could not invalidate the undelivered password reset challenge.")
        finally:
            if connection is not None:
                connection.close()


def _locked_current(db: sqlite3.Connection, snapshot: AppUser) -> AppUser:
    user = lock_user(db, snapshot.id)
    if user is None or user.token_version != snapshot.token_version:
        raise HTTPException(401, "Session is no longer valid. Sign in again.")
    return user


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> TokenResponse:
    """Require the current password and revoke all previously issued sessions."""

    _throttle(account_action_limiter, f"account:{client_ip(request)}:{current_user.id}")
    if not current_user.password_hash:
        raise HTTPException(409, "This account uses Google. Manage its password with Google.")
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(401, "Current password is incorrect.")
    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(400, "Choose a different new password.")
    password_hash = hash_password(payload.new_password)
    with transaction(db):
        user = _locked_current(db, current_user)
        if user.password_hash != current_user.password_hash:
            raise HTTPException(401, "Session is no longer valid. Sign in again.")
        updated = replace_password(db, user.id, password_hash)
        if updated is None:
            raise HTTPException(401, "Account no longer exists.")
    return _build_token_response(updated)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: sqlite3.Connection = Depends(get_db),
) -> ForgotPasswordResponse:
    """Return the same response shape for every email, without disclosing codes."""

    _throttle(forgot_password_limiter, f"forgot:{client_ip(request)}")
    settings = get_settings()
    if not smtp_is_configured(settings):
        raise HTTPException(503, "Password recovery email is not configured. Try again later.")
    email = str(payload.email).strip().lower()
    email_key = hmac.new(settings.secret_key.encode(), email.encode(), hashlib.sha256).hexdigest()
    _throttle(forgot_password_email_limiter, f"forgot-email:{email_key}")
    request_id = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1_000_000):06d}"
    user = get_user_by_email(db, email)
    if user is not None and user.has_password:
        with transaction(db):
            locked = lock_user(db, user.id)
            if locked is not None and locked.has_password:
                now = int(time.time())
                create_reset_request(
                    db, locked, request_id, _code_digest(request_id, code, settings), now + 600
                )
                background_tasks.add_task(_deliver_reset, email, code, request_id, settings)
    return ForgotPasswordResponse(message=RESET_MESSAGE, request_id=request_id)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
) -> MessageResponse:
    """Persist failed guesses; consume and rotate the password in one transaction."""

    _throttle(reset_password_limiter, f"reset:{client_ip(request)}")
    settings = get_settings()
    now = int(time.time())
    row = get_reset_request(db, payload.request_id)
    if row is None or row["expires_at"] <= now or row["attempts"] >= 5:
        raise HTTPException(400, INVALID_CODE)
    digest = _code_digest(payload.request_id, payload.code, settings)
    # Reject random IDs and incorrect codes without expensive bcrypt work.
    # The locked consumption below rechecks state and persists wrong guesses.
    password_hash = (
        hash_password(payload.new_password)
        if hmac.compare_digest(row["code_hash"], digest)
        else None
    )
    with transaction(db):
        accepted = consume_reset_request(
            db,
            payload.request_id,
            digest,
            password_hash,
            int(time.time()),
        )
    # Reject after commit, otherwise get_db would roll back the guess budget.
    if not accepted:
        raise HTTPException(400, INVALID_CODE)
    return MessageResponse(message="Password reset. Sign in with your new password.")


@router.delete("/account", status_code=204)
def delete_account(
    payload: DeleteAccountRequest,
    request: Request,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    """Delete live account data only after explicit confirmation and reauthentication."""

    _throttle(account_action_limiter, f"account:{client_ip(request)}:{current_user.id}")
    if current_user.password_hash and (
        not payload.password or not verify_password(payload.password, current_user.password_hash)
    ):
        raise HTTPException(401, "Password is incorrect.")
    identity = None
    if not current_user.has_password:
        if not payload.id_token:
            raise HTTPException(401, "Verify your Google account again before deleting.")
        try:
            identity = verify_google_id_token(payload.id_token)
        except GoogleTokenError:
            raise HTTPException(401, "Google verification failed.") from None
        except GoogleUnavailable:
            raise HTTPException(503, "Google verification is unavailable. Try again later.") from None
        now = int(time.time())
        if identity.issued_at is None or not now - 300 <= identity.issued_at <= now + 60:
            raise HTTPException(401, "Google verification is too old. Verify again.")
    with transaction(db):
        user = _locked_current(db, current_user)
        if user.password_hash:
            if user.password_hash != current_user.password_hash:
                raise HTTPException(401, "Session is no longer valid. Sign in again.")
        elif identity is None or not user.google_sub or identity.subject != user.google_sub:
            raise HTTPException(401, "Google account does not match this account.")
        db.execute("DELETE FROM users WHERE id = ?", (user.id,))
