"""Tests for lightweight Indonesian date parsing."""

from __future__ import annotations

from datetime import date

from finance_core.services.date_parser import ParsedDate, parse_transaction_date


def test_parse_transaction_date_defaults_to_today_when_no_date_token() -> None:
    today = date(2026, 5, 30)

    result = parse_transaction_date("makan 25000", today=today)

    assert result == ParsedDate(transaction_date=today, cleaned_text="makan 25000")


def test_parse_transaction_date_supports_hari_ini_token() -> None:
    today = date(2026, 5, 30)

    result = parse_transaction_date("makan 25000 hari ini", today=today)

    assert result == ParsedDate(transaction_date=today, cleaned_text="makan 25000")


def test_parse_transaction_date_supports_kemarin_token() -> None:
    today = date(2026, 5, 30)

    result = parse_transaction_date("makan 25000 kemarin", today=today)

    assert result == ParsedDate(
        transaction_date=date(2026, 5, 29),
        cleaned_text="makan 25000",
    )


def test_parse_transaction_date_supports_slash_date_format() -> None:
    result = parse_transaction_date("makan 25000 30/05/2026", today=date(2026, 1, 1))

    assert result == ParsedDate(
        transaction_date=date(2026, 5, 30),
        cleaned_text="makan 25000",
    )


def test_parse_transaction_date_supports_iso_date_format() -> None:
    result = parse_transaction_date("makan 25000 2026-05-30", today=date(2026, 1, 1))

    assert result == ParsedDate(
        transaction_date=date(2026, 5, 30),
        cleaned_text="makan 25000",
    )


def test_parse_transaction_date_normalizes_extra_spaces_after_cleaning() -> None:
    result = parse_transaction_date("  makan   25000   kemarin  ", today=date(2026, 5, 30))

    assert result.cleaned_text == "makan 25000"
