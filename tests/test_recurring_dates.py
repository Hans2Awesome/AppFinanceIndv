"""Unit tests for the pure recurring schedule math."""

from __future__ import annotations

from datetime import date

import pytest

from finance_core.recurring import (
    first_on_or_after,
    monthly_occurrence,
    next_after,
    validate_schedule,
)


def test_weekly_first_on_or_after_uses_monday_zero() -> None:
    # 2026-10-01 is a Thursday; the next Monday is 2026-10-05.
    assert first_on_or_after(date(2026, 10, 1), "weekly", 0, None) == date(2026, 10, 5)


def test_weekly_same_day_is_not_skipped() -> None:
    assert first_on_or_after(date(2026, 10, 5), "weekly", 0, None) == date(2026, 10, 5)


def test_weekly_next_after_moves_one_week() -> None:
    assert next_after(date(2026, 10, 5), "weekly", 0, None) == date(2026, 10, 12)


def test_monthly_clamps_to_last_day() -> None:
    assert monthly_occurrence(2026, 2, 31) == date(2026, 2, 28)
    assert monthly_occurrence(2028, 2, 31) == date(2028, 2, 29)
    assert monthly_occurrence(2026, 4, 31) == date(2026, 4, 30)


def test_monthly_first_on_or_after_uses_this_month_or_next() -> None:
    assert first_on_or_after(date(2026, 1, 1), "monthly", None, 15) == date(2026, 1, 15)
    assert first_on_or_after(date(2026, 1, 16), "monthly", None, 15) == date(2026, 2, 15)


def test_monthly_rolls_over_december() -> None:
    assert next_after(date(2026, 12, 31), "monthly", None, 31) == date(2027, 1, 31)


def test_validate_schedule_rejects_inconsistent_fields() -> None:
    with pytest.raises(ValueError):
        validate_schedule("weekly", None, None)
    with pytest.raises(ValueError):
        validate_schedule("weekly", 7, None)
    with pytest.raises(ValueError):
        validate_schedule("monthly", None, 0)
    with pytest.raises(ValueError):
        validate_schedule("monthly", None, 32)
    with pytest.raises(ValueError):
        validate_schedule("daily", 0, None)