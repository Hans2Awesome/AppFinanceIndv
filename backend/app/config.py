"""Configuration loading for the Finance API."""

from __future__ import annotations

from dataclasses import dataclass, field

from finance_core.config import env_value, get_common_settings

MIN_PRODUCTION_SECRET_LENGTH = 32


@dataclass(frozen=True)
class Settings:
    """Application configuration values."""

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    database_path: str = "bot04.sqlite3"
    database_url: str | None = None
    timezone: str = "Asia/Jakarta"
    currency: str = "IDR"
    cors_origins: tuple[str, ...] = field(default_factory=lambda: ("*",))
    environment: str = "development"
    recurring_scheduler_enabled: bool = True
    recurring_scheduler_interval_seconds: int = 30

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def allow_credentials(self) -> bool:
        """Credentials cannot be combined with a wildcard CORS origin."""

        return "*" not in self.cors_origins


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean environment flag with a permissive set of false values."""

    raw = env_value(name, "1" if default else "0").strip().lower()
    return raw not in {"", "0", "false", "no", "off"}


def get_settings(*, load_dotenv_file: bool = True) -> Settings:
    """Load and validate configuration from the environment.

    Settings are read on every call so tests can override the environment, but
    the ``.env`` file itself is parsed only once.
    """

    common = get_common_settings(load_dotenv_file=load_dotenv_file)

    secret_key = env_value("SECRET_KEY", "")
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY is not set. Copy backend/.env.example to backend/.env "
            "and set a random secret before starting the API."
        )

    environment = common.environment
    if environment.lower() == "production" and len(secret_key) < MIN_PRODUCTION_SECRET_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY must be at least {MIN_PRODUCTION_SECRET_LENGTH} characters in production."
        )

    cors_raw = env_value("CORS_ORIGINS", "*")
    cors_origins = tuple(origin.strip() for origin in cors_raw.split(",") if origin.strip()) or (
        "*",
    )

    # Android and the Telegram bot are not browsers, so a wildcard origin buys
    # nothing in production and silently allows any website to call the API.
    if environment.lower() == "production" and "*" in cors_origins:
        raise RuntimeError(
            "CORS_ORIGINS='*' is not allowed in production. "
            "Set an explicit comma separated list of origins."
        )

    settings = Settings(
        secret_key=secret_key,
        algorithm=env_value("ALGORITHM", "HS256"),
        access_token_expire_minutes=int(env_value("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
        refresh_token_expire_days=int(env_value("REFRESH_TOKEN_EXPIRE_DAYS", "30")),
        database_path=common.database_path,
        database_url=common.database_url,
        timezone=common.timezone,
        currency=common.currency,
        cors_origins=cors_origins,
        environment=environment,
        recurring_scheduler_enabled=_env_bool("RECURRING_SCHEDULER_ENABLED", True),
        recurring_scheduler_interval_seconds=max(
            5,
            int(env_value("RECURRING_SCHEDULER_INTERVAL_SECONDS", "30")),
        ),
    )

    return settings