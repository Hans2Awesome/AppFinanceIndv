"""Bot04 application entrypoint."""

from __future__ import annotations

import argparse

from .bot.app import build_application
from .config import load_config


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""

    parser = argparse.ArgumentParser(description="Run Bot04 Telegram finance bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load configuration and exit without starting Telegram polling",
    )
    return parser


def main() -> None:
    """Run the Bot04 application."""

    parser = build_parser()
    args = parser.parse_args()
    config = load_config()

    if args.dry_run:
        print(
            "Bot04 configuration loaded: "
            f"database_path={config.database_path}, "
            f"timezone={config.timezone}, "
            f"currency={config.currency}"
        )
        return

    if not config.bot_token:
        raise SystemExit("BOT_TOKEN is required. Copy .env.example to .env and fill BOT_TOKEN.")

    application = build_application(config=config)
    application.run_polling()


if __name__ == "__main__":
    main()
