"""Tests for the production configuration guards.

The guards exist because the dangerous failure mode is silent: a production
process that keeps running on the local SQLite file, or a pytest run that writes
into the hosted database. Every case here asserts a hard failure instead.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from finance_core.config import get_common_settings


def _clear_shared_env(monkeypatch) -> None:
    for name in ("DATABASE_URL", "DATABASE_PATH", "ENVIRONMENT", "TIMEZONE", "CURRENCY"):
        monkeypatch.delenv(name, raising=False)

def test_production_requires_database_url(monkeypatch) -> None:
    _clear_shared_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="requires DATABASE_URL"):
        get_common_settings(load_dotenv_file=False)

def test_production_accepts_an_explicit_database_url(monkeypatch) -> None:
    _clear_shared_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@127.0.0.1:5432/postgres")

    settings = get_common_settings(load_dotenv_file=False)

    assert settings.is_production
    assert settings.database_url == "postgresql://user:pass@127.0.0.1:5432/postgres"

def test_development_may_stay_on_sqlite(monkeypatch) -> None:
    _clear_shared_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "development")

    settings = get_common_settings(load_dotenv_file=False)

    assert settings.database_url is None

def test_bot_config_fails_loudly_in_production_without_database_url(monkeypatch) -> None:
    """The bot reads the same settings, so it must fail too."""

    from bot04.config import load_config

    _clear_shared_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="requires DATABASE_URL"):
        load_config(load_dotenv_file=False)

def test_production_rejects_wildcard_cors(monkeypatch) -> None:
    from backend.app.config import get_settings

    _clear_shared_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@127.0.0.1:5432/postgres")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("CORS_ORIGINS", "*")

    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        get_settings(load_dotenv_file=False)

def test_production_accepts_explicit_origins(monkeypatch) -> None:
    from backend.app.config import get_settings

    _clear_shared_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@127.0.0.1:5432/postgres")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("CORS_ORIGINS", "https://api.example.test")

    settings = get_settings(load_dotenv_file=False)

    assert settings.cors_origins == ("https://api.example.test",)
    assert settings.allow_credentials

def test_development_still_allows_wildcard_cors(monkeypatch) -> None:
    from backend.app.config import get_settings

    _clear_shared_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "short-is-fine-in-development")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    settings = get_settings(load_dotenv_file=False)

    assert settings.cors_origins == ("*",)

def test_production_hides_the_api_schema(monkeypatch) -> None:
    from backend.app.config import get_settings
    from backend.app.main import create_app

    _clear_shared_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@127.0.0.1:5432/postgres")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("CORS_ORIGINS", "https://api.example.test")

    application = create_app(get_settings(load_dotenv_file=False))

    assert application.docs_url is None
    assert application.redoc_url is None
    assert application.openapi_url is None

def test_development_keeps_the_api_schema(monkeypatch, tmp_path) -> None:
    from backend.app.config import get_settings
    from backend.app.main import create_app

    _clear_shared_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "short-is-fine-in-development")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "docs.sqlite3"))
    monkeypatch.setenv("RECURRING_SCHEDULER_ENABLED", "0")

    application = create_app(get_settings(load_dotenv_file=False))

    assert application.docs_url == "/docs"
    assert application.openapi_url == "/openapi.json"

    with TestClient(application) as client:
        response = client.get("/")

    assert response.json()["docs_url"] == "/docs"

def test_health_check_hides_docs_url_in_production(monkeypatch) -> None:
    from backend.app.config import Settings
    from backend.app.main import create_app

    application = create_app(
        Settings(
            secret_key="x" * 64,
            database_url="postgresql://user:pass@127.0.0.1:5432/postgres",
            cors_origins=("https://api.example.test",),
            environment="production",
        )
    )

    health = next(
        route.endpoint for route in application.routes if getattr(route, "path", None) == "/"
    )

    assert health() == {
        "status": "online",
        "app": "Personal Finance API",
        "version": "1.0.0",
    }

def test_tests_refuse_the_hosted_production_database() -> None:
    from finance_core.db.connection import connect_url

    with pytest.raises(RuntimeError, match="production database"):
        connect_url("postgresql://user:pass@aws-1-eu-central-1.pooler.supabase.com:6543/postgres")

def test_guard_leaves_local_databases_alone() -> None:
    from finance_core.db.connection import _reject_production_url_during_tests

    _reject_production_url_during_tests("postgresql://postgres@127.0.0.1:5432/postgres")
    _reject_production_url_during_tests("postgresql://postgres@localhost:5432/postgres")

def test_conftest_blanks_database_url_even_with_override(monkeypatch, tmp_path) -> None:
    """``load_dotenv(override=True)`` must not restore a real database URL."""

    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql://real:secret@example.test/postgres\n")

    from finance_core.config import _load_dotenv_once

    monkeypatch.setenv("DATABASE_URL", "")
    _load_dotenv_once.cache_clear()
    try:
        import dotenv

        dotenv.load_dotenv(str(env_file), override=True)
    finally:
        _load_dotenv_once.cache_clear()

    import os

    assert os.environ["DATABASE_URL"] == ""

def test_conftest_keeps_a_url_set_by_the_test(monkeypatch, tmp_path) -> None:
    """A test that deliberately sets a local PostgreSQL URL keeps it."""

    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql://real:secret@example.test/postgres\n")

    from finance_core.config import _load_dotenv_once

    monkeypatch.setenv("DATABASE_URL", "postgresql://test@127.0.0.1:5432/postgres")
    _load_dotenv_once.cache_clear()
    try:
        import dotenv

        dotenv.load_dotenv(str(env_file), override=False)
    finally:
        _load_dotenv_once.cache_clear()

    import os

    assert os.environ["DATABASE_URL"] == "postgresql://test@127.0.0.1:5432/postgres"
