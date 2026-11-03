"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finance_core.db.connection import close_pools, open_database
from finance_core.db.migrations import run_migrations

from .config import Settings, get_settings
from .routes.auth import router as auth_router
from .routes.categories import router as categories_router
from .routes.debts import router as debts_router
from .routes.recurring import router as recurring_router
from .routes.reports import router as reports_router
from .routes.transactions import router as transactions_router
from .scheduler import recurring_scheduler_loop

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application, applying migrations on startup."""

    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        # Re-read settings at startup so tests and deployments can override the
        # database path without rebuilding the application object.
        settings = get_settings()
        connection = open_database(settings.database_path, url=settings.database_url)
        try:
            version = run_migrations(connection)
            logger.info("Database schema ready at version %s", version)
        finally:
            connection.close()

        scheduler_task: asyncio.Task[None] | None = None
        if settings.recurring_scheduler_enabled:
            scheduler_task = asyncio.create_task(
                recurring_scheduler_loop(
                    settings.database_path,
                    settings.recurring_scheduler_interval_seconds,
                    database_url=settings.database_url,
                )
            )
            logger.info("Recurring transaction scheduler started")
        else:
            logger.info("Recurring transaction scheduler disabled")

        try:
            yield
        finally:
            if scheduler_task is not None:
                scheduler_task.cancel()
                with suppress(asyncio.CancelledError):
                    await scheduler_task
            # Tutup pool PostgreSQL secara eksplisit. Tanpa ini, restart lewat
            # systemd meninggalkan koneksi menggantung di sisi Supabase sampai
            # server memutusnya sendiri.
            close_pools()

    application = FastAPI(
        title="Personal Finance API",
        description=(
            "Backend API for personal finance tracking with quick text input parsing."
        ),
        version="1.0.0",
        lifespan=lifespan,
        # Production hides the schema: the VPS is reachable through a Cloudflare
        # Tunnel, so /docs and /openapi.json would hand scanners the full list of
        # endpoints and payloads for free.
        docs_url=None if resolved_settings.is_production else "/docs",
        redoc_url=None if resolved_settings.is_production else "/redoc",
        openapi_url=None if resolved_settings.is_production else "/openapi.json",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=resolved_settings.allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth_router)
    application.include_router(transactions_router)
    application.include_router(categories_router)
    application.include_router(reports_router)
    application.include_router(debts_router)
    application.include_router(recurring_router)

    @application.get("/", tags=["Health"])
    def health_check() -> dict[str, str]:
        """Health check and API info."""

        info = {
            "status": "online",
            "app": "Personal Finance API",
            "version": "1.0.0",
        }
        if not resolved_settings.is_production:
            info["docs_url"] = "/docs"
        return info

    return application


app = create_app()