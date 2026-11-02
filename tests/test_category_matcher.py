"""Tests for alias-based category matching."""

from __future__ import annotations

import pytest

from finance_core.services.category_matcher import CategoryMatch, match_category


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "gaji 5000000",
            CategoryMatch("income", "Gaji", asset_name=None, confidence=1.0, needs_review=False),
        ),
        (
            "bonus 100000",
            CategoryMatch("income", "Bonus", asset_name=None, confidence=1.0, needs_review=False),
        ),
        (
            "makan 25000",
            CategoryMatch(
                "expense",
                "Makan & Minum",
                asset_name=None,
                confidence=1.0,
                needs_review=False,
            ),
        ),
        (
            "gojek 15000",
            CategoryMatch(
                "expense",
                "Transportasi",
                asset_name=None,
                confidence=1.0,
                needs_review=False,
            ),
        ),
    ],
)
def test_match_category_uses_default_aliases(text: str, expected: CategoryMatch) -> None:
    assert match_category(text) == expected


def test_match_category_detects_invest_btc_as_crypto_with_btc_asset() -> None:
    assert match_category("invest btc 100000") == CategoryMatch(
        "investment",
        "Crypto",
        asset_name="BTC",
        confidence=1.0,
        needs_review=False,
    )


def test_match_category_detects_btc_as_crypto_with_asset_even_without_invest_word() -> None:
    assert match_category("btc 100000 dca mingguan") == CategoryMatch(
        "investment",
        "Crypto",
        asset_name="BTC",
        confidence=1.0,
        needs_review=False,
    )


def test_match_category_detects_emas_as_investment() -> None:
    assert match_category("emas 500000") == CategoryMatch(
        "investment",
        "Emas",
        asset_name="Emas",
        confidence=1.0,
        needs_review=False,
    )


def test_match_category_falls_back_to_expense_lainnya_with_review_when_uncertain() -> None:
    assert match_category("sesuatu random 12345") == CategoryMatch(
        "expense",
        "Lainnya",
        asset_name=None,
        confidence=0.0,
        needs_review=True,
    )


def test_match_category_custom_category_takes_priority_over_default() -> None:
    # "Pulsa" secara default cocok ke Tagihan, tetapi pengguna punya kategori kustom
    # bernama "Pulsa" dengan tipe income, sehingga kustom harus menang.
    assert match_category(
        "pulsa 50000",
        custom_categories=[("income", "Pulsa")],
    ) == CategoryMatch(
        "income",
        "Pulsa",
        asset_name=None,
        confidence=1.0,
        needs_review=False,
    )


def test_match_category_custom_category_substring_match() -> None:
    assert match_category(
        "bayar asuransi jiwa",
        custom_categories=[("expense", "Asuransi")],
    ) == CategoryMatch(
        "expense",
        "Asuransi",
        asset_name=None,
        confidence=1.0,
        needs_review=False,
    )


def test_match_category_without_custom_uses_default() -> None:
    assert match_category("gaji 5000000", custom_categories=[]) == CategoryMatch(
        "income",
        "Gaji",
        asset_name=None,
        confidence=1.0,
        needs_review=False,
    )


def test_match_category_custom_name_is_word_bounded() -> None:
    # "Asi" tidak boleh cocok di dalam kata "kasir".
    assert match_category(
        "kasir 20000",
        custom_categories=[("expense", "Asi")],
    ) == CategoryMatch(
        "expense",
        "Lainnya",
        asset_name=None,
        confidence=0.0,
        needs_review=True,
    )
