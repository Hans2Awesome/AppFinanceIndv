"""Configuration loading for Bot04."""

from __future__ import annotations

from dataclasses import dataclass

from finance_core.config import CommonSettings, env_value, get_common_settings


@dataclass(frozen=True)
class Config:
    """Application configuration values."""

    bot_token: str
    database_path: str
    timezone: str
    currency: str

    @classmethod
    def from_env(cls, *, load_dotenv_file: bool = True) -> "Config":
        """Build the bot config from the shared environment settings."""

        common: CommonSettings = get_common_settings(load_dotenv_file=load_dotenv_file)
        return cls(
            bot_token=env_value("BOT_TOKEN", ""),
            database_path=common.database_path,
            timezone=common.timezone,
            currency=common.currency,
        )


def load_config(*, load_dotenv_file: bool = True) -> Config:
    """Load configuration from environment and optional .env file.

    Args:
        load_dotenv_file: When true, load values from a local ``.env`` file before
            reading environment variables. Tests can disable this for isolation.
    """

    return Config.from_env(load_dotenv_file=load_dotenv_file)
