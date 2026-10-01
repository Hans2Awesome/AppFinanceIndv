"""Authentication routes."""

from __future__ import annotations

import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status
from ..auth.dependencies import get_current_user, get_db
from ..auth.jwt_handler import create_access_token, hash_password, verify_password
from ..database.users import AppUser, create_mobile_user, get_user_by_email
from ..models.schemas import TokenResponse, UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: sqlite3.Connection = Depends(get_db)) -> TokenResponse:
    """Register a new user account."""
    existing = get_user_by_email(db, payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email sudah terdaftar.",
        )

    pwd_hash = hash_password(payload.password)
    user = create_mobile_user(
        db,
        email=payload.email,
        password_hash=pwd_hash,
        first_name=payload.first_name,
        timezone=payload.timezone,
        currency=payload.currency,
    )

    access_token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email or "",
            first_name=user.first_name,
            timezone=user.timezone,
            currency=user.currency,
            created_at=user.created_at,
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: sqlite3.Connection = Depends(get_db)) -> TokenResponse:
    """Log in with email and password."""
    user = get_user_by_email(db, payload.email)
    if user is None or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau kata sandi salah.",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau kata sandi salah.",
        )

    access_token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email or "",
            first_name=user.first_name,
            timezone=user.timezone,
            currency=user.currency,
            created_at=user.created_at,
        ),
    )


@router.get("/me", response_model=UserResponse)
def get_profile(current_user: AppUser = Depends(get_current_user)) -> UserResponse:
    """Get profile of currently logged in user."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email or "",
        first_name=current_user.first_name,
        timezone=current_user.timezone,
        currency=current_user.currency,
        created_at=current_user.created_at,
    )
