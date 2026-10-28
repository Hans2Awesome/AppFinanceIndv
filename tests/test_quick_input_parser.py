"""Tests for the main quick input parser."""

from __future__ import annotations

from datetime import date

import pytest

from finance_core.services.quick_input_parser import QuickInputResult, parse_quick_input


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "makan 25000",
            QuickInputResult(
                type="expense",
                category_name="Makan & Minum",
                amount=25000,
                note="",
                asset_name=None,
                transaction_date=date(2026, 5, 30),
                confidence=1.0,
                needs_review=False,
                original_text="makan 25000",
                error=None,
            ),
        ),
        (
            "transport 15000 gojek",
            QuickInputResult(
                type="expense",
                category_name="Transportasi",
                amount=15000,
                note="gojek",
                asset_name=None,
                transaction_date=date(2026, 5, 30),
                confidence=1.0,
                needs_review=False,
                original_text="transport 15000 gojek",
                error=None,
            ),
        ),
        (
            "gaji 5000000",
            QuickInputResult(
                type="income",
                category_name="Gaji",
                amount=5000000,
                note="",
                asset_name=None,
                transaction_date=date(2026, 5, 30),
                confidence=1.0,
                needs_review=False,
                original_text="gaji 5000000",
                error=None,
            ),
        ),
        (
            "invest btc 100000",
            QuickInputResult(
                type="investment",
                category_name="Crypto",
                amount=100000,
                note="",
                asset_name="BTC",
                transaction_date=date(2026, 5, 30),
                confidence=1.0,
                needs_review=False,
                original_text="invest btc 100000",
                error=None,
            ),
        ),
        (
            "btc 100000 dca mingguan",
            QuickInputResult(
                type="investment",
                category_name="Crypto",
                amount=100000,
                note="dca mingguan",
                asset_name="BTC",
                transaction_date=date(2026, 5, 30),
                confidence=1.0,
                needs_review=False,
                original_text="btc 100000 dca mingguan",
                error=None,
            ),
        ),
        (
            "kopi 25k kemarin",
            QuickInputResult(
                type="expense",
                category_name="Makan & Minum",
                amount=25000,
                note="",
                asset_name=None,
                transaction_date=date(2026, 5, 29),
                confidence=1.0,
                needs_review=False,
                original_text="kopi 25k kemarin",
                error=None,
            ),
        ),
    ],
)
def test_parse_quick_input_combines_money_date_and_category_parsers(
    text: str,
    expected: QuickInputResult,
) -> None:
    assert parse_quick_input(text, today=date(2026, 5, 30)) == expected


def test_parse_quick_input_returns_error_when_text_is_empty() -> None:
    result = parse_quick_input("   ", today=date(2026, 5, 30))

    assert result.error == "Tulis transaksi dulu"
    assert result.needs_review is True


def test_parse_quick_input_returns_error_when_amount_is_missing() -> None:
    result = parse_quick_input("makan siang", today=date(2026, 5, 30))

    assert result.error == "Nominal belum ditemukan"
    assert result.needs_review is True


def test_parse_quick_input_returns_error_when_amount_is_zero() -> None:
    result = parse_quick_input("makan 0", today=date(2026, 5, 30))

    assert result.error == "Nominal harus lebih dari 0"
    assert result.needs_review is True


def test_parse_quick_input_marks_uncertain_category_for_review() -> None:
    result = parse_quick_input("random 12345", today=date(2026, 5, 30))

    assert result.type == "expense"
    assert result.category_name == "Lainnya"
    assert result.needs_review is True
    assert result.confidence == 0.0
