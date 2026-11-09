"""Shared test configuration for the FastAPI backend."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-1234567890123456789012")
# Keep the recurring scheduler out of TestClient runs; tests drive the runner directly.
os.environ.setdefault("RECURRING_SCHEDULER_ENABLED", "0")


@pytest.fixture(autouse=True)
def _reset_login_limiter() -> None:
    """Keep auth throttling state from leaking between tests."""

    from backend.app.auth.rate_limit import (
        google_link_limiter,
        google_login_limiter,
        login_limiter,
        refresh_limiter,
        register_limiter,
    )

    login_limiter._buckets.clear()
    refresh_limiter._buckets.clear()
    register_limiter._buckets.clear()
    google_login_limiter._buckets.clear()
    google_link_limiter._buckets.clear()
