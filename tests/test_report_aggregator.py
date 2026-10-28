"""Tests for report aggregation."""

from __future__ import annotations

from finance_core.db.transactions import Transaction
from finance_core.reports.aggregator import (
    CategoryTotal,
    ReportSummary,
    aggregate_transactions,
)


def transaction(
    *,
    id: int,
    type: str,
    amount: int,
    category_id: int | None = None,
) -> Transaction:
    return Transaction(
        id=id,
        user_id=1,
        type=type,
        category_id=category_id,
        amount=amount,
        note=None,
        asset_name=None,
        transaction_date="2026-05-30",
    )


def test_aggregate_transactions_calculates_totals_net_and_investment_percentage() -> None:
    transactions = [
        transaction(id=1, type="income", amount=5_000_000),
        transaction(id=2, type="expense", amount=25_000, category_id=10),
        transaction(id=3, type="expense", amount=75_000, category_id=11),
        transaction(id=4, type="investment", amount=1_000_000),
    ]

    summary = aggregate_transactions(
        transactions,
        category_names={10: "Makan & Minum", 11: "Transportasi"},
    )

    assert summary == ReportSummary(
        total_income=5_000_000,
        total_expense=100_000,
        total_investment=1_000_000,
        net=3_900_000,
        average_expense=50_000,
        top_expense_categories=[
            CategoryTotal(name="Transportasi", amount=75_000, percentage=75.0),
            CategoryTotal(name="Makan & Minum", amount=25_000, percentage=25.0),
        ],
        investment_percentage=20.0,
    )


def test_aggregate_transactions_groups_top_expense_categories() -> None:
    transactions = [
        transaction(id=1, type="expense", amount=25_000, category_id=10),
        transaction(id=2, type="expense", amount=30_000, category_id=10),
        transaction(id=3, type="expense", amount=75_000, category_id=11),
    ]

    summary = aggregate_transactions(
        transactions,
        category_names={10: "Makan & Minum", 11: "Transportasi"},
    )

    assert summary.top_expense_categories == [
        CategoryTotal(name="Transportasi", amount=75_000, percentage=57.7),
        CategoryTotal(name="Makan & Minum", amount=55_000, percentage=42.3),
    ]


def test_aggregate_transactions_handles_no_income_without_dividing_by_zero() -> None:
    transactions = [transaction(id=1, type="investment", amount=100_000)]

    summary = aggregate_transactions(transactions, category_names={})

    assert summary.investment_percentage == 0.0
    assert summary.net == -100_000


def test_aggregate_transactions_returns_zero_summary_for_empty_transactions() -> None:
    assert aggregate_transactions([], category_names={}) == ReportSummary(
        total_income=0,
        total_expense=0,
        total_investment=0,
        net=0,
        average_expense=0,
        top_expense_categories=[],
        investment_percentage=0.0,
    )
