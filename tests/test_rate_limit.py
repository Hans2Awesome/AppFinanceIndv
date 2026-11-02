"""Tests for in-memory rate limiter with max-keys eviction."""

from __future__ import annotations

from backend.app.auth.rate_limit import MAX_BUCKETS, SlidingWindowLimiter


def test_evicts_oldest_bucket_when_at_capacity() -> None:
    limiter = SlidingWindowLimiter(max_attempts=1, window_seconds=60)

    # Isi kapasitas penuh dengan kunci unik.
    for index in range(MAX_BUCKETS):
        limiter.register_failure(f"key-{index}")

    assert len(limiter._buckets) == MAX_BUCKETS

    # Kunci terbaru harus mengusir kunci tertua (key-0).
    limiter.register_failure("brand-new-key")
    assert len(limiter._buckets) == MAX_BUCKETS
    assert "key-0" not in limiter._buckets
    assert "brand-new-key" in limiter._buckets


def test_existing_key_is_not_evicted() -> None:
    limiter = SlidingWindowLimiter(max_attempts=1, window_seconds=60)

    for index in range(MAX_BUCKETS):
        limiter.register_failure(f"key-{index}")

    # Menambahkan kegagalan lagi pada kunci yang sudah ada tidak boleh mengusir apa-apa.
    limiter.register_failure("key-0")
    assert len(limiter._buckets) == MAX_BUCKETS
    assert "key-0" in limiter._buckets
