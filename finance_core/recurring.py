"""Schedule math for recurring transactions.

Kept free of database access so the date rules can be tested on their own.
Weeks follow Python's ``date.weekday()``: 0 is Monday and 6 is Sunday.
Monthly schedules clamp to the last day of short months, so day 31 becomes
30 April, 28 or 29 February.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

FREQUENCIES = ("weekly", "monthly")


def validate_schedule(
    frequency: str,
    day_of_week: int | None,
    day_of_month: int | None,
) -> None:
    """Raise ``ValueError`` when the schedule fields are inconsistent."""

    if frequency not in FREQUENCIES:
        raise ValueError("Frekuensi harus 'weekly' atau 'monthly'.")
    if frequency == "weekly":
        if day_of_week is None or not 0 <= day_of_week <= 6:
            raise ValueError("Hari mingguan harus antara 0 (Senin) dan 6 (Minggu).")
    if frequency == "monthly":
        if day_of_month is None or not 1 <= day_of_month <= 31:
            raise ValueError("Tanggal bulanan harus antara 1 dan 31.")


def monthly_occurrence(year: int, month: int, day_of_month: int) -> date:
    """Return the requested day, clamped to the last day of the month."""

    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day_of_month, last_day))


def first_on_or_after(
    anchor: date,
    frequency: str,
    day_of_week: int | None = None,
    day_of_month: int | None = None,
) -> date:
    """Return the first occurrence on or after ``anchor``."""

    validate_schedule(frequency, day_of_week, day_of_month)

    if frequency == "weekly":
        assert day_of_week is not None
        return anchor + timedelta(days=(day_of_week - anchor.weekday()) % 7)

    assert day_of_month is not None
    candidate = monthly_occurrence(anchor.year, anchor.month, day_of_month)
    if candidate >= anchor:
        return candidate

    next_year = anchor.year + 1 if anchor.month == 12 else anchor.year
    next_month = 1 if anchor.month == 12 else anchor.month + 1
    return monthly_occurrence(next_year, next_month, day_of_month)


def next_after(
    current: date,
    frequency: str,
    day_of_week: int | None = None,
    day_of_month: int | None = None,
) -> date:
    """Return the first occurrence strictly after ``current``."""

    return first_on_or_after(
        current + timedelta(days=1),
        frequency,
        day_of_week,
        day_of_month,
    )