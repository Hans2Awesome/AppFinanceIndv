"""Tests for Bot04 configuration loading."""

from __future__ import annotations

from bot04.config import Config, load_config


def test_load_config_uses_defaults_when_env_is_empty(monkeypatch) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("TIMEZONE", raising=False)
    monkeypatch.delenv("CURRENCY", raising=False)

    config = load_config(load_dotenv_file=False)

    assert config == Config(
        bot_token="",
        database_path="bot04.sqlite3",
        timezone="Asia/Jakarta",
        currency="IDR",
    )


def test_load_config_uses_environment_overrides(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:test-token")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/custom-bot04.sqlite3")
    monkeypatch.setenv("TIMEZONE", "UTC")
    monkeypatch.setenv("CURRENCY", "USD")

    config = load_config(load_dotenv_file=False)

    assert config.bot_token == "123:test-token"
    assert config.database_path == "/tmp/custom-bot04.sqlite3"
    assert config.timezone == "UTC"
    assert config.currency == "USD"


def test_load_config_strips_surrounding_whitespace(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "  token-with-space  ")
    monkeypatch.setenv("DATABASE_PATH", "  data.sqlite3  ")
    monkeypatch.setenv("TIMEZONE", "  Asia/Jakarta  ")
    monkeypatch.setenv("CURRENCY", "  IDR  ")

    config = load_config(load_dotenv_file=False)

    assert config.bot_token == "token-with-space"
    assert config.database_path == "data.sqlite3"
    assert config.timezone == "Asia/Jakarta"
    assert config.currency == "IDR"


def test_backend_and_bot_read_the_same_database_path(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", "/tmp/shared-finance.sqlite3")
    monkeypatch.setenv("SECRET_KEY", "shared-config-test-secret-key-0123456789")

    from backend.app.config import get_settings

    assert (
        load_config(load_dotenv_file=False).database_path
        == get_settings(load_dotenv_file=False).database_path
        == "/tmp/shared-finance.sqlite3"
    )
