"""Configuration loading for the FastAPI Backend."""

from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Application configuration values."""

    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    database_path: str
    timezone: str
    currency: str
    cors_origins: list[str]


def _env_value(name: str, default: str) -> str:
    """Read and normalize one environment value."""
    return os.getenv(name, default).strip()


def get_settings(*, load_dotenv_file: bool = True) -> Settings:
    """Load configuration from environment and optional .env file."""
    if load_dotenv_file:
        load_dotenv()

    cors_raw = _env_value("CORS_ORIGINS", "*")
    cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]

    return Settings(
        secret_key=_env_value("SECRET_KEY", "dev-secret-key-please-change-in-production-12345"),
        algorithm=_env_value("ALGORITHM", "HS256"),
        access_token_expire_minutes=int(_env_value("ACCESS_TOKEN_EXPIRE_MINUTES", "43200")),  # 30 days
        database_path=_env_value("DATABASE_PATH", "bot04.sqlite3"),
        timezone=_env_value("TIMEZONE", "Asia/Jakarta"),
        currency=_env_value("CURRENCY", "IDR"),
        cors_origins=cors_origins,
    )
