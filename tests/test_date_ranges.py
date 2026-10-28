"""Tests for report date range helpers."""

from __future__ import annotations

from datetime import date

from finance_core.reports.date_ranges import (
    DateRange,
    month_range,
    today_range,
    week_range,
)


def test_today_range_returns_same_start_and_end_date() -> None:
    current_date = date(2026, 5, 30)

    assert today_range(current_date) == DateRange(
        start_date=date(2026, 5, 30),
        end_date=date(2026, 5, 30),
    )


def test_week_range_starts_on_monday_and_ends_on_sunday() -> None:
    current_date = date(2026, 5, 30)  # Saturday

    assert week_range(current_date) == DateRange(
        start_date=date(2026, 5, 25),
        end_date=date(2026, 5, 31),
    )


def test_week_range_for_monday_starts_on_same_day() -> None:
    current_date = date(2026, 5, 25)

    assert week_range(current_date) == DateRange(
        start_date=date(2026, 5, 25),
        end_date=date(2026, 5, 31),
    )


def test_month_range_returns_first_and_last_day_of_month() -> None:
    current_date = date(2026, 5, 30)

    assert month_range(current_date) == DateRange(
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
    )


def test_month_range_handles_february_in_leap_year() -> None:
    current_date = date(2024, 2, 10)

    assert month_range(current_date) == DateRange(
        start_date=date(2024, 2, 1),
        end_date=date(2024, 2, 29),
    )
