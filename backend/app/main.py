"""FastAPI application main entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .database.connection import connect
from .database.schema import init_db
from .routes.auth import router as auth_router
from .routes.categories import router as categories_router
from .routes.reports import router as reports_router
from .routes.transactions import router as transactions_router
from .routes.debts import router as debts_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize database tables on application startup."""
    settings = get_settings()
    connection = connect(settings.database_path)
    try:
        init_db(connection)
    finally:
        connection.close()
    yield


settings = get_settings()

app = FastAPI(
    title="Personal Finance API",
    description="Backend API for personal finance tracking with quick text input parsing.",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup CORS for mobile and web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.cors_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(auth_router)
app.include_router(transactions_router)
app.include_router(categories_router)
app.include_router(reports_router)
app.include_router(debts_router)


@app.get("/", tags=["Health"])
def health_check() -> dict[str, str]:
    """Health check and API info."""
    return {
        "status": "online",
        "app": "Personal Finance API",
        "version": "1.0.0",
        "docs_url": "/docs",
    }
