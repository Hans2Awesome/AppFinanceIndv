"""Financial reporting routes."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from ..auth.dependencies import get_current_user, get_db
from ..database.categories import get_category_names_map
from ..database.transactions import list_transactions_in_range
from ..database.users import AppUser
from ..models.schemas import (
    CategoryBreakdownResponse,
    CategoryTotalItem,
    InvestmentReportResponse,
    PeriodReportResponse,
)
from ..reports.aggregator import (
    aggregate_by_category,
    aggregate_investments,
    aggregate_transactions,
)
from ..reports.date_ranges import month_range, today_range, week_range

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/daily", response_model=PeriodReportResponse)
def get_daily_report(
    target_date: Optional[str] = Query(None, description="Target date (YYYY-MM-DD), defaults to today"),
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> PeriodReportResponse:
    """Generate daily financial summary."""
    ref_date = date.fromisoformat(target_date) if target_date else date.today()
    rng = today_range(ref_date)
    start_str = rng.start_date.isoformat()
    end_str = rng.end_date.isoformat()

    txs = list_transactions_in_range(db, user_id=current_user.id, start_date=start_str, end_date=end_str)
    cat_names = get_category_names_map(db, current_user.id)
    summary = aggregate_transactions(txs, category_names=cat_names)

    return PeriodReportResponse(
        title=f"Laporan Harian ({rng.start_date.strftime('%d %b %Y')})",
        start_date=start_str,
        end_date=end_str,
        total_income=summary.total_income,
        total_expense=summary.total_expense,
        total_investment=summary.total_investment,
        net=summary.net,
        average_expense=summary.average_expense,
        investment_percentage=summary.investment_percentage,
        top_expense_categories=[
            CategoryTotalItem(name=c.name, amount=c.amount, percentage=c.percentage)
            for c in summary.top_expense_categories
        ],
    )


@router.get("/weekly", response_model=PeriodReportResponse)
def get_weekly_report(
    target_date: Optional[str] = Query(None, description="Any date within the week (YYYY-MM-DD)"),
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> PeriodReportResponse:
    """Generate weekly financial summary."""
    ref_date = date.fromisoformat(target_date) if target_date else date.today()
    rng = week_range(ref_date)
    start_str = rng.start_date.isoformat()
    end_str = rng.end_date.isoformat()

    txs = list_transactions_in_range(db, user_id=current_user.id, start_date=start_str, end_date=end_str)
    cat_names = get_category_names_map(db, current_user.id)
    summary = aggregate_transactions(txs, category_names=cat_names)

    return PeriodReportResponse(
        title=f"Laporan Mingguan ({rng.start_date.strftime('%d %b')} - {rng.end_date.strftime('%d %b %Y')})",
        start_date=start_str,
        end_date=end_str,
        total_income=summary.total_income,
        total_expense=summary.total_expense,
        total_investment=summary.total_investment,
        net=summary.net,
        average_expense=summary.average_expense,
        investment_percentage=summary.investment_percentage,
        top_expense_categories=[
            CategoryTotalItem(name=c.name, amount=c.amount, percentage=c.percentage)
            for c in summary.top_expense_categories
        ],
    )


@router.get("/monthly", response_model=PeriodReportResponse)
def get_monthly_report(
    year: Optional[int] = Query(None, description="Year (e.g. 2026)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> PeriodReportResponse:
    """Generate monthly financial summary."""
    today = date.today()
    target_year = year or today.year
    target_month = month or today.month
    ref_date = date(target_year, target_month, 1)
    rng = month_range(ref_date)
    start_str = rng.start_date.isoformat()
    end_str = rng.end_date.isoformat()

    txs = list_transactions_in_range(db, user_id=current_user.id, start_date=start_str, end_date=end_str)
    cat_names = get_category_names_map(db, current_user.id)
    summary = aggregate_transactions(txs, category_names=cat_names)

    return PeriodReportResponse(
        title=f"Laporan Bulanan ({rng.start_date.strftime('%B %Y')})",
        start_date=start_str,
        end_date=end_str,
        total_income=summary.total_income,
        total_expense=summary.total_expense,
        total_investment=summary.total_investment,
        net=summary.net,
        average_expense=summary.average_expense,
        investment_percentage=summary.investment_percentage,
        top_expense_categories=[
            CategoryTotalItem(name=c.name, amount=c.amount, percentage=c.percentage)
            for c in summary.top_expense_categories
        ],
    )


@router.get("/category-breakdown", response_model=CategoryBreakdownResponse)
def get_category_breakdown(
    type: str = Query("expense", description="Category type (income, expense, investment)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> CategoryBreakdownResponse:
    """Get category breakdown with amounts and percentages for pie charts."""
    today = date.today()
    start_str = start_date or date(today.year, today.month, 1).isoformat()
    rng = month_range(today)
    end_str = end_date or rng.end_date.isoformat()

    txs = list_transactions_in_range(db, user_id=current_user.id, start_date=start_str, end_date=end_str)
    cat_names = get_category_names_map(db, current_user.id)
    items, total = aggregate_by_category(txs, category_type=type, category_names=cat_names)

    return CategoryBreakdownResponse(
        title=f"Breakdown Kategori {type.capitalize()}",
        type=type,
        categories=[CategoryTotalItem(name=i.name, amount=i.amount, percentage=i.percentage) for i in items],
        total_amount=total,
    )


@router.get("/investment", response_model=InvestmentReportResponse)
def get_investment_report(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> InvestmentReportResponse:
    """Get investment allocations by asset and type."""
    today = date.today()
    start_str = start_date or date(today.year, today.month, 1).isoformat()
    rng = month_range(today)
    end_str = end_date or rng.end_date.isoformat()

    txs = list_transactions_in_range(db, user_id=current_user.id, start_date=start_str, end_date=end_str)
    cat_names = get_category_names_map(db, current_user.id)
    by_type, by_asset, total_inv = aggregate_investments(txs, category_names=cat_names)

    # Calculate percentage of total income
    total_income = sum(t.amount for t in txs if t.type == "income")
    inv_pct = round((total_inv / total_income * 100), 2) if total_income > 0 else 0.0

    return InvestmentReportResponse(
        title="Laporan Alokasi Investasi",
        total_investment=total_inv,
        investment_percentage=inv_pct,
        by_type=[CategoryTotalItem(name=i.name, amount=i.amount, percentage=i.percentage) for i in by_type],
        by_asset=[CategoryTotalItem(name=i.name, amount=i.amount, percentage=i.percentage) for i in by_asset],
    )
