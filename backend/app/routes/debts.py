"""Debt and receivable management routes."""

from __future__ import annotations

import sqlite3
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from ..auth.dependencies import get_current_user, get_db
from ..database.debts import (
    create_debt,
    create_debt_payment,
    delete_debt,
    get_debt_by_id,
    get_debt_summary,
    list_debt_payments,
    list_debts,
    update_debt,
)
from ..database.users import AppUser
from ..models.schemas import (
    DebtCreate,
    DebtPaymentCreate,
    DebtPaymentResponse,
    DebtResponse,
    DebtSummaryResponse,
    DebtUpdate,
)

router = APIRouter(prefix="/api/debts", tags=["Debts & Receivables"])


def _debt_to_response(d) -> DebtResponse:
    """Convert a Debt dataclass to a DebtResponse."""
    return DebtResponse(
        id=d.id,
        user_id=d.user_id,
        type=d.type,
        person_name=d.person_name,
        total_amount=d.total_amount,
        paid_amount=d.paid_amount,
        note=d.note,
        due_date=d.due_date,
        status=d.status,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


@router.post("", response_model=DebtResponse, status_code=status.HTTP_201_CREATED)
def create_new_debt(
    payload: DebtCreate,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> DebtResponse:
    """Create a new debt or receivable record."""
    if payload.type not in ("debt", "receivable"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipe harus 'debt' (hutang) atau 'receivable' (piutang).",
        )

    d = create_debt(
        db,
        user_id=current_user.id,
        type=payload.type,
        person_name=payload.person_name,
        total_amount=payload.total_amount,
        note=payload.note,
        due_date=payload.due_date,
    )
    return _debt_to_response(d)


@router.get("/summary", response_model=DebtSummaryResponse)
def get_summary(
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> DebtSummaryResponse:
    """Get aggregated summary of debts and receivables."""
    summary = get_debt_summary(db, user_id=current_user.id)
    return DebtSummaryResponse(**summary)


@router.get("", response_model=List[DebtResponse])
def get_debts(
    type: Optional[str] = Query(None, description="Filter: 'debt' or 'receivable'"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter: 'active' or 'settled'"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[DebtResponse]:
    """List debts/receivables with optional filters."""
    items = list_debts(
        db,
        user_id=current_user.id,
        debt_type=type,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [_debt_to_response(d) for d in items]


@router.get("/{debt_id}", response_model=DebtResponse)
def get_debt(
    debt_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> DebtResponse:
    """Get a single debt/receivable by ID."""
    d = get_debt_by_id(db, user_id=current_user.id, debt_id=debt_id)
    if d is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hutang/piutang tidak ditemukan.",
        )
    return _debt_to_response(d)


@router.put("/{debt_id}", response_model=DebtResponse)
def edit_debt(
    debt_id: int,
    payload: DebtUpdate,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> DebtResponse:
    """Update fields of an existing debt/receivable."""
    if payload.status and payload.status not in ("active", "settled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status harus 'active' atau 'settled'.",
        )

    updated = update_debt(
        db,
        user_id=current_user.id,
        debt_id=debt_id,
        person_name=payload.person_name,
        total_amount=payload.total_amount,
        note=payload.note,
        due_date=payload.due_date,
        status=payload.status,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hutang/piutang tidak ditemukan.",
        )
    return _debt_to_response(updated)


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_debt(
    debt_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    """Delete a debt/receivable and all its payments."""
    success = delete_debt(db, user_id=current_user.id, debt_id=debt_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hutang/piutang tidak ditemukan.",
        )


# ---------------------------------------------------------------------------
# Debt Payments
# ---------------------------------------------------------------------------


@router.post("/{debt_id}/payments", response_model=DebtPaymentResponse, status_code=status.HTTP_201_CREATED)
def add_payment(
    debt_id: int,
    payload: DebtPaymentCreate,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> DebtPaymentResponse:
    """Record a payment/installment for a debt or receivable."""
    try:
        payment = create_debt_payment(
            db,
            debt_id=debt_id,
            user_id=current_user.id,
            amount=payload.amount,
            note=payload.note,
            payment_date=payload.payment_date,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )

    return DebtPaymentResponse(
        id=payment.id,
        debt_id=payment.debt_id,
        amount=payment.amount,
        note=payment.note,
        payment_date=payment.payment_date,
        created_at=payment.created_at,
    )


@router.get("/{debt_id}/payments", response_model=List[DebtPaymentResponse])
def get_payments(
    debt_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[DebtPaymentResponse]:
    """List all payments for one debt/receivable."""
    payments = list_debt_payments(db, debt_id=debt_id, user_id=current_user.id)
    return [
        DebtPaymentResponse(
            id=p.id,
            debt_id=p.debt_id,
            amount=p.amount,
            note=p.note,
            payment_date=p.payment_date,
            created_at=p.created_at,
        )
        for p in payments
    ]
