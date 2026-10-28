"""Tests for Indonesian money parsing."""

from __future__ import annotations

import pytest

from finance_core.services.money_parser import MoneyParseError, parse_money


@pytest.mark.parametrize(
    ("text", "expected_amount"),
    [
        ("25000", 25000),
        ("25.000", 25000),
        ("25,000", 25000),
        ("Rp25.000", 25000),
        ("rp 25.000", 25000),
        ("25k", 25000),
        ("1.5jt", 1500000),
        ("1,5 juta", 1500000),
    ],
)
def test_parse_money_supports_indonesian_amount_formats(
    text: str,
    expected_amount: int,
) -> None:
    assert parse_money(text) == expected_amount


def test_parse_money_can_extract_amount_from_longer_text() -> None:
    assert parse_money("makan rp 25.000 kopi") == 25000


def test_parse_money_raises_clear_error_when_text_has_no_amount() -> None:
    with pytest.raises(MoneyParseError, match="nominal"):
        parse_money("makan siang")
