"""Tests for in-memory pending confirmation store."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from bot04.services.pending_store import PendingConfirmationStore
from finance_core.services.quick_input_parser import QuickInputResult


def preview(note: str = "kopi") -> QuickInputResult:
    return QuickInputResult(
        type="expense",
        category_name="Makan & Minum",
        amount=25000,
        note=note,
        asset_name=None,
        transaction_date=date(2026, 5, 30),
        confidence=1.0,
        needs_review=False,
        original_text="makan 25000 kopi",
        error=None,
    )


def test_pending_store_sets_and_gets_preview_for_user() -> None:
    now = datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)
    store = PendingConfirmationStore(now_provider=lambda: now)
    parsed_preview = preview()

    store.set(telegram_user_id=796529359, preview=parsed_preview)

    assert store.get(telegram_user_id=796529359) == parsed_preview


def test_pending_store_replaces_existing_preview_for_same_user() -> None:
    now = datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)
    store = PendingConfirmationStore(now_provider=lambda: now)

    store.set(telegram_user_id=796529359, preview=preview("lama"))
    store.set(telegram_user_id=796529359, preview=preview("baru"))

    assert store.get(telegram_user_id=796529359) == preview("baru")


def test_pending_store_clear_removes_user_preview() -> None:
    now = datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)
    store = PendingConfirmationStore(now_provider=lambda: now)

    store.set(telegram_user_id=796529359, preview=preview())
    store.clear(telegram_user_id=796529359)

    assert store.get(telegram_user_id=796529359) is None


def test_pending_store_keeps_users_separated() -> None:
    now = datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)
    store = PendingConfirmationStore(now_provider=lambda: now)
    user_a_preview = preview("user a")
    user_b_preview = preview("user b")

    store.set(telegram_user_id=1, preview=user_a_preview)
    store.set(telegram_user_id=2, preview=user_b_preview)

    assert store.get(telegram_user_id=1) == user_a_preview
    assert store.get(telegram_user_id=2) == user_b_preview


def test_pending_store_expires_preview_after_ten_minutes() -> None:
    current_time = datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)

    def now_provider() -> datetime:
        return current_time

    store = PendingConfirmationStore(now_provider=now_provider)
    store.set(telegram_user_id=796529359, preview=preview())

    current_time = current_time + timedelta(minutes=10, seconds=1)

    assert store.get(telegram_user_id=796529359) is None


def test_pending_store_keeps_preview_at_exact_ten_minute_boundary() -> None:
    current_time = datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)

    def now_provider() -> datetime:
        return current_time

    store = PendingConfirmationStore(now_provider=now_provider)
    parsed_preview = preview()
    store.set(telegram_user_id=796529359, preview=parsed_preview)

    current_time = current_time + timedelta(minutes=10)

    assert store.get(telegram_user_id=796529359) == parsed_preview
