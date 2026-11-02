"""Background loop that materializes due recurring transactions.

FastAPI owns no job queue, so the API process runs this small loop. Each tick
opens its own connection (SQLite file or a pooled PostgreSQL connection), which
keeps it independent from request connections and safe to run in a worker
thread.
"""

from __future__ import annotations

import asyncio
import logging

from finance_core.db.connection import open_database
from finance_core.db.recurring import run_due_recurring

logger = logging.getLogger(__name__)


def run_due_recurring_once(database_path: str, *, database_url: str | None = None) -> int:
    """Process every schedule that is due, returning how many rows were created."""

    connection = open_database(database_path, url=database_url)
    try:
        return len(run_due_recurring(connection))
    finally:
        connection.close()


async def recurring_scheduler_loop(
    database_path: str,
    interval_seconds: int,
    *,
    database_url: str | None = None,
) -> None:
    """Run due schedules immediately, then poll until cancelled."""

    while True:
        try:
            created = await asyncio.to_thread(
                run_due_recurring_once,
                database_path,
                database_url=database_url,
            )
            if created:
                logger.info("Recurring scheduler created %s transaction(s)", created)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Recurring scheduler tick failed")

        await asyncio.sleep(interval_seconds)