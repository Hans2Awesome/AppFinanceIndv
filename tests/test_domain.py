"""Tests for Bot04 domain transaction types."""

from __future__ import annotations

import pytest

from finance_core.domain import (
    TransactionType,
    transaction_type_label,
    valid_transaction_type_values,
)


def test_valid_transaction_type_values_are_exactly_the_three_supported_values() -> None:
    assert valid_transaction_type_values() == {"income", "expense", "investment"}


def test_transaction_type_rejects_unsupported_values() -> None:
    with pytest.raises(ValueError):
        TransactionType("transfer")


def test_transaction_type_labels_are_in_indonesian() -> None:
    assert transaction_type_label(TransactionType.INCOME) == "Pemasukan"
    assert transaction_type_label(TransactionType.EXPENSE) == "Pengeluaran"
    assert transaction_type_label(TransactionType.INVESTMENT) == "Investasi"
