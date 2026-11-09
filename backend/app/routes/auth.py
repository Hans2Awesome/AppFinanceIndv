"""Authentication routes."""

from __future__ import annotations

import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status

from finance_core.db.connection import transaction as db_transaction
from finance_core.db.users import (
    AppUser,
    bump_token_version,
    create_google_user,
    create_mobile_user,
    create_telegram_link_code,
    get_user_by_email,
    get_user_by_google_sub,
    get_user_by_id,
    link_google_identity,
    unlink_telegram_account,
)

from ..auth.client_ip import client_ip
from ..auth.dependencies import get_current_user, get_db
from ..auth.google import (
    GoogleTokenError,
    GoogleUnavailable,
    VerifiedGoogleIdentity,
    verify_google_id_token,
)
from ..auth.jwt_handler import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..auth.jwt_handler import (
    token_version as claimed_token_version,
)
from ..auth.rate_limit import (
    google_link_limiter,
    google_login_limiter,
    login_limiter,
    refresh_limiter,
    register_limiter,
)
from ..config import get_settings
from ..models.schemas import (
    GoogleAuthRequest,
    GoogleLinkRequest,
    RefreshRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _rate_limit_key(request: Request, email: str) -> str:
    return f"{client_ip(request)}:{email.strip().lower()}"


def _build_token_response(user: AppUser) -> TokenResponse:
    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(subject=user.id, token_version=user.token_version),
        refresh_token=create_refresh_token(subject=user.id, token_version=user.token_version),
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


def _verify_google_token(raw_token: str) -> VerifiedGoogleIdentity:
    """Translate verifier outcomes into HTTP responses.

    Invalid tokens are 401; a missing configuration or an unreachable Google
    certificate endpoint is 503, so clients know to retry rather than to drop
    the token.
    """

    try:
        return verify_google_id_token(raw_token)
    except GoogleTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Google tidak valid atau sudah kedaluwarsa.",
        ) from None
    except GoogleUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login Google sedang tidak tersedia. Coba lagi nanti.",
        ) from None


def _google_rate_limited() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Terlalu banyak percobaan login Google. Coba lagi dalam 15 menit.",
        headers={"Retry-After": "900"},
    )


def _is_unique_violation(error: Exception) -> bool:
    """True for a duplicate key on SQLite or PostgreSQL."""

    return isinstance(error, sqlite3.IntegrityError) or getattr(error, "sqlstate", None) == "23505"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserRegister,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
) -> TokenResponse:
    """Register a new user account."""

    limiter_key = f"register:{client_ip(request)}"
    if register_limiter.is_blocked(limiter_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Terlalu banyak pendaftaran dari alamat ini. Coba lagi nanti.",
            headers={"Retry-After": "3600"},
        )
    register_limiter.register_failure(limiter_key)

    if get_user_by_email(db, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email sudah terdaftar.",
        )

    with db_transaction(db):
        user = create_mobile_user(
            db,
            email=payload.email,
            password_hash=hash_password(payload.password),
            first_name=payload.first_name,
            timezone=payload.timezone,
            currency=payload.currency,
        )
    return _build_token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLogin,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
) -> TokenResponse:
    """Log in with email and password, with brute-force throttling."""

    limiter_key = _rate_limit_key(request, payload.email)
    if login_limiter.is_blocked(limiter_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Terlalu banyak percobaan login. Coba lagi dalam 15 menit.",
            headers={"Retry-After": "900"},
        )

    user = get_user_by_email(db, payload.email)
    if user is None or not user.password_hash or not verify_password(
        payload.password, user.password_hash
    ):
        login_limiter.register_failure(limiter_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau kata sandi salah.",
        )

    login_limiter.reset(limiter_key)
    return _build_token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token for a new token pair."""

    limiter_key = f"refresh:{client_ip(request)}"
    if refresh_limiter.is_blocked(limiter_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Terlalu banyak percobaan refresh. Coba lagi nanti.",
            headers={"Retry-After": "900"},
        )

    claims = decode_token(payload.refresh_token, expected_type=REFRESH_TOKEN_TYPE)
    if claims is None:
        refresh_limiter.register_failure(limiter_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token tidak valid atau sudah kedaluwarsa.",
        )

    try:
        user_id = int(claims["sub"])
    except (KeyError, ValueError):
        refresh_limiter.register_failure(limiter_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token tidak valid atau sudah kedaluwarsa.",
        ) from None

    user = get_user_by_id(db, user_id)
    if user is None:
        refresh_limiter.register_failure(limiter_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pengguna tidak ditemukan.",
        )
    if claimed_token_version(claims) != user.token_version:
        refresh_limiter.register_failure(limiter_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token sudah tidak berlaku. Silakan login kembali.",
        )

    refresh_limiter.reset(limiter_key)
    return _build_token_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    """Revoke every access and refresh token issued to the current user."""

    with db_transaction(db):
        bump_token_version(db, user_id=current_user.id)


@router.get("/me", response_model=UserResponse)
def get_profile(current_user: AppUser = Depends(get_current_user)) -> UserResponse:
    """Get the profile of the currently logged-in user."""

    return UserResponse.model_validate(current_user)


@router.post("/telegram-link-token", status_code=status.HTTP_201_CREATED)
def create_telegram_link_token(
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> dict[str, str | int]:
    """Buat kode tautan 6 digit untuk menghubungkan akun ini dengan Bot Telegram.

    Kode berlaku 10 menit dan boleh digunakan satu kali. Pengguna mengirimkannya
    ke Bot Telegram dengan perintah ``/link <kode>``. Hanya kode terbaru yang
    berlaku: membuat kode baru membatalkan kode sebelumnya.
    """

    for _ in range(5):
        code = f"{secrets.randbelow(1_000_000):06d}"
        try:
            with db_transaction(db):
                create_telegram_link_code(db, user_id=current_user.id, code=code)
        except sqlite3.IntegrityError:
            # Kode sudah dipakai pengguna lain; coba kode acak berikutnya.
            continue
        return {"code": code, "expires_in_minutes": 10}

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Gagal membuat kode tautan. Coba lagi.",
    )


@router.post("/google", response_model=TokenResponse)
def google_sign_in(
    payload: GoogleAuthRequest,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
) -> TokenResponse:
    """Sign in or register with a Google ID token from Android.

    The Google subject is the identity. An unknown subject whose verified email
    already belongs to an account is refused instead of silently linked, so an
    existing password account can only be joined through explicit linking.
    """

    limiter_key = f"google:{client_ip(request)}"
    if google_login_limiter.is_blocked(limiter_key):
        raise _google_rate_limited()
    google_login_limiter.register_failure(limiter_key)

    identity = _verify_google_token(payload.id_token)

    existing = get_user_by_google_sub(db, identity.subject)
    if existing is not None:
        google_login_limiter.reset(limiter_key)
        return _build_token_response(existing)

    if get_user_by_email(db, identity.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Email ini sudah terdaftar. Masuk dengan kata sandi, lalu tautkan "
                "Google di Pengaturan."
            ),
        )

    settings = get_settings()
    try:
        with db_transaction(db):
            user = create_google_user(
                db,
                google_sub=identity.subject,
                email=identity.email,
                first_name=identity.first_name,
                timezone=settings.timezone,
                currency=settings.currency,
            )
    except Exception as error:
        if not _is_unique_violation(error):
            raise
        # A concurrent request won the race. Re-read; the winner's row is used.
        user = get_user_by_google_sub(db, identity.subject)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Akun Google ini baru saja terdaftar. Coba masuk lagi.",
            ) from None

    google_login_limiter.reset(limiter_key)
    return _build_token_response(user)


@router.post("/google/link", response_model=UserResponse)
def link_google_sign_in(
    payload: GoogleLinkRequest,
    request: Request,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> UserResponse:
    """Attach a Google identity to the signed-in account.

    The password is mandatory while the account has one, so a stolen access token
    alone cannot bind an attacker's Google account. The Google email must match
    the account email.
    """

    limiter_key = f"google-link:{client_ip(request)}"
    if google_link_limiter.is_blocked(limiter_key):
        raise _google_rate_limited()
    google_link_limiter.register_failure(limiter_key)

    if current_user.email is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Akun ini tidak punya email untuk dicocokkan dengan Google.",
        )

    if current_user.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Akun ini tidak memakai kata sandi. Tautkan Google lewat pendaftaran.",
        )

    if not payload.password or not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kata sandi salah.",
        )

    identity = _verify_google_token(payload.id_token)

    if identity.email != current_user.email.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email Google harus sama dengan email akun ini.",
        )

    if current_user.google_sub is not None:
        if current_user.google_sub == identity.subject:
            google_link_limiter.reset(limiter_key)
            return UserResponse.model_validate(current_user)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Akun ini sudah tertaut ke identitas Google lain.",
        )

    owner = get_user_by_google_sub(db, identity.subject)
    if owner is not None and owner.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Akun Google ini sudah tertaut ke akun lain.",
        )

    try:
        with db_transaction(db):
            link_google_identity(db, user_id=current_user.id, google_sub=identity.subject)
    except Exception as error:
        if not _is_unique_violation(error):
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Akun Google ini sudah tertaut ke akun lain.",
        ) from None

    updated = get_user_by_id(db, current_user.id)
    if updated is None or updated.google_sub != identity.subject:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tautan Google gagal disimpan. Silakan coba lagi.",
        )

    google_link_limiter.reset(limiter_key)
    return UserResponse.model_validate(updated)


@router.delete("/telegram-link", status_code=status.HTTP_200_OK)
def remove_telegram_link(
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> dict[str, bool]:
    """Lepas tautan Telegram dari akun ini tanpa menghapus datanya.

    Dipakai ketika pengguna berganti nomor atau akun Telegram. Data keuangan
    tetap utuh; hanya ``telegram_user_id`` yang dikosongkan. Setelah ini
    pengguna bisa meminta kode baru dan menautkan akun Telegram lain.
    """

    with db_transaction(db):
        unlink_telegram_account(db, user_id=current_user.id)
    return {"telegram_linked": False}