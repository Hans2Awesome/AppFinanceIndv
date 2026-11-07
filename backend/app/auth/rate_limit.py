"""In-memory rate limiting for authentication endpoints.

Single-process only: restarting the API clears the counters. For multi-worker
deployments this must move to Redis or the database.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_WINDOW_SECONDS = 15 * 60
# Batas kunci aktif di RAM agar serangan ribuan IP acak tidak habiskan memori VPS.
MAX_BUCKETS = 10_000


@dataclass
class _Bucket:
    failures: list[float] = field(default_factory=list)


class SlidingWindowLimiter:
    """Limit repeated failed attempts inside a rolling time window."""

    def __init__(
        self,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def is_blocked(self, key: str) -> bool:
        """Return True when the key exhausted its attempts in the window."""

        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                return False
            self._prune(bucket)
            return len(bucket.failures) >= self._max_attempts

    def register_failure(self, key: str) -> None:
        """Record one failed attempt for the key."""

        with self._lock:
            if key not in self._buckets and len(self._buckets) >= MAX_BUCKETS:
                self._evict_oldest()
            bucket = self._buckets.setdefault(key, _Bucket())
            self._prune(bucket)
            bucket.failures.append(time.monotonic())

    def reset(self, key: str) -> None:
        """Clear the counter for a key after a successful login."""

        with self._lock:
            self._buckets.pop(key, None)

    def _prune(self, bucket: _Bucket) -> None:
        cutoff = time.monotonic() - self._window_seconds
        bucket.failures = [moment for moment in bucket.failures if moment > cutoff]

    def _evict_oldest(self) -> None:
        """Buang kunci tertua ketika kapasitas penuh (FIFO eviction)."""

        if not self._buckets:
            return
        oldest_key = next(iter(self._buckets))
        self._buckets.pop(oldest_key, None)


login_limiter = SlidingWindowLimiter(max_attempts=5, window_seconds=15 * 60)
register_limiter = SlidingWindowLimiter(max_attempts=10, window_seconds=60 * 60)
refresh_limiter = SlidingWindowLimiter(max_attempts=30, window_seconds=15 * 60)
google_login_limiter = SlidingWindowLimiter(max_attempts=10, window_seconds=15 * 60)
google_link_limiter = SlidingWindowLimiter(max_attempts=5, window_seconds=15 * 60)