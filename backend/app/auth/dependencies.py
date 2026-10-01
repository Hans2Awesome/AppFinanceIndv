"""FastAPI dependencies for database access and authentication."""

from __future__ import annotations

import sqlite3
from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from ..config import get_settings
from ..database.connection import connect
from ..database.schema import init_db
from ..database.users import AppUser, get_user_by_id
from .jwt_handler import decode_access_token

security = HTTPBearer(auto_error=True)


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Provide a database connection per request."""
    settings = get_settings()
    connection = connect(settings.database_path)
    init_db(connection)
    try:
        yield connection
    finally:
        connection.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: sqlite3.Connection = Depends(get_db),
) -> AppUser:
    """Validate Bearer token and return the authenticated user."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid atau sudah kedaluwarsa.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(payload["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Subjek token tidak valid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pengguna tidak ditemukan.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
