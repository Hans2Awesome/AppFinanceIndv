"""Debt and receivable management routes."""

from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from finance_core.db.connection import transaction
from finance_core.db.debts import (
    create_debt,
    create_debt_payment,
    delete_debt,
    delete_debt_payment,
    get_debt_by_id,
    get_debt_summary,
    list_debt_payments,
    list_debts,
    sync_derived_debt_transaction,
    update_debt,
)
from finance_core.db.transactions import create_transaction
from finance_core.db.users import AppUser
from finance_core.services.transaction_service import find_or_create_category
from finance_core.timezones import today_in

from ..auth.dependencies import get_current_user, get_db
from ..models.schemas import (
    DebtCreate,
    DebtPaymentCreate,
    DebtPaymentResponse,
    DebtResponse,
    DebtSummaryResponse,
    DebtUpdate,
)

router = APIRouter(prefix="/api/debts", tags=["Debts & Receivables"])

NOT_FOUND_DETAIL = "Hutang/piutang tidak ditemukan."
CASH_CATEGORY_NAME = "Lainnya"


def _cash_note(base: str, note: str | None) -> str:
    """Keep the generated note clear while preserving the user's own note."""

    if not note:
        return base
    return f"{base}: {note}"[:500]


def _cash_transaction_type(debt_type: str, *, opening: bool) -> str:
    """Borrowing and receiving a payment add cash; lending and paying remove it."""

    if debt_type == "debt":
        return "income" if opening else "expense"
    return "expense" if opening else "income"


def _record_payment_cash(
    db: sqlite3.Connection,
    *,
    user_id: int,
    debt,
    payment,
) -> None:
    """Write the cash row for one installment when the debt is cash-synced."""

    if not debt.cash_synced:
        return

    cash_type = _cash_transaction_type(debt.type, opening=False)
    category_id = find_or_create_category(
        db,
        user_id=user_id,
        category_type=cash_type,
        category_name=CASH_CATEGORY_NAME,
    )
    base_note = (
        f"Bayar hutang ke {debt.person_name}"
        if debt.type == "debt"
        else f"Terima piutang dari {debt.person_name}"
    )
    create_transaction(
        db,
        user_id=user_id,
        type=cash_type,
        category_id=category_id,
        amount=payment.amount,
        note=_cash_note(base_note, payment.note),
        asset_name=None,
        transaction_date=payment.payment_date,
        source_key=f"debt_payment:{user_id}:{payment.id}",
    )


@router.post("", response_model=DebtResponse, status_code=status.HTTP_201_CREATED)
def create_new_debt(
    payload: DebtCreate,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> DebtResponse:
    """Create a new debt or receivable record."""

    with transaction(db):
        debt = create_debt(
            db,
            user_id=current_user.id,
            type=payload.type,
            person_name=payload.person_name,
            total_amount=payload.total_amount,
            note=payload.note,
            due_date=payload.due_date.isoformat() if payload.due_date else None,
            cash_synced=payload.sync_cash,
        )

        if payload.sync_cash:
            cash_type = _cash_transaction_type(payload.type, opening=True)
            category_id = find_or_create_category(
                db,
                user_id=current_user.id,
                category_type=cash_type,
                category_name=CASH_CATEGORY_NAME,
            )
            base_note = (
                f"Pinjaman dari {debt.person_name}"
                if payload.type == "debt"
                else f"Piutang ke {debt.person_name}"
            )
            create_transaction(
                db,
                user_id=current_user.id,
                type=cash_type,
                category_id=category_id,
                amount=debt.total_amount,
                note=_cash_note(base_note, debt.note),
                asset_name=None,
                transaction_date=today_in(current_user.timezone).isoformat(),
                source_key=f"debt:{current_user.id}:{debt.id}",
            )

    return DebtResponse.model_validate(debt)


@router.get("/summary", response_model=DebtSummaryResponse)
def get_summary(
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> DebtSummaryResponse:
    """Get an aggregated summary of debts and receivables."""

    summary = get_debt_summary(
        db,
        user_id=current_user.id,
        today=today_in(current_user.timezone).isoformat(),
    )
    return DebtSummaryResponse(**summary)


@router.get("", response_model=list[DebtResponse])
def get_debts(
    type: Optional[str] = Query(None, pattern="^(debt|receivable)$"),
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(active|settled)$"),
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
    return [DebtResponse.model_validate(item) for item in items]


@router.get("/{debt_id}", response_model=DebtResponse)
def get_debt(
    debt_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> DebtResponse:
    """Get a single debt/receivable by ID."""

    debt = get_debt_by_id(db, user_id=current_user.id, debt_id=debt_id)
    if debt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_DETAIL)
    return DebtResponse.model_validate(debt)


@router.put("/{debt_id}", response_model=DebtResponse)
def edit_debt(
    debt_id: int,
    payload: DebtUpdate,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> DebtResponse:
    """Update fields of an existing debt/receivable.

    Marking a record as settled records the remaining balance as one payment,
    so ``paid_amount`` reaches ``total_amount`` and the optional cash row is
    written the same way an installment would be.
    """

    existing = get_debt_by_id(db, user_id=current_user.id, debt_id=debt_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_DETAIL)

    try:
        with transaction(db):
            if payload.status == "settled" and existing.status != "settled":
                target_total = (
                    payload.total_amount
                    if payload.total_amount is not None
                    else existing.total_amount
                )
                remaining = target_total - existing.paid_amount
                if remaining > 0:
                    payment = create_debt_payment(
                        db,
                        debt_id=debt_id,
                        user_id=current_user.id,
                        amount=remaining,
                        note="Pelunasan",
                        payment_date=today_in(current_user.timezone).isoformat(),
                    )
                    _record_payment_cash(
                        db,
                        user_id=current_user.id,
                        debt=existing,
                        payment=payment,
                    )

            updated = update_debt(
                db,
                user_id=current_user.id,
                debt_id=debt_id,
                person_name=payload.person_name,
                total_amount=payload.total_amount,
                note=payload.note,
                due_date=payload.due_date.isoformat() if payload.due_date else None,
                status=payload.status,
            )

            # Jika nominal utang berubah, ikut perbarui baris kas hasil
            # pembukaan utang (source_key = debt:<user_id>:<debt_id>) sehingga
            # saldo kas tidak pernah berselisih dengan nominal utang.
            if payload.total_amount is not None and payload.total_amount != existing.total_amount:
                sync_derived_debt_transaction(
                    db,
                    user_id=current_user.id,
                    debt_id=debt_id,
                    amount=payload.total_amount,
                )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_DETAIL)
    return DebtResponse.model_validate(updated)


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_debt(
    debt_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    """Delete a debt/receivable, all its payments, and their cash rows."""

    with transaction(db):
        deleted = delete_debt(db, user_id=current_user.id, debt_id=debt_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_DETAIL)


@router.post(
    "/{debt_id}/payments",
    response_model=DebtPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_payment(
    debt_id: int,
    payload: DebtPaymentCreate,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> DebtPaymentResponse:
    """Record a payment/installment for a debt or receivable."""

    debt = get_debt_by_id(db, user_id=current_user.id, debt_id=debt_id)

    try:
        with transaction(db):
            payment = create_debt_payment(
                db,
                debt_id=debt_id,
                user_id=current_user.id,
                amount=payload.amount,
                note=payload.note,
                payment_date=payload.payment_date.isoformat(),
            )

            if debt is not None:
                _record_payment_cash(
                    db,
                    user_id=current_user.id,
                    debt=debt,
                    payment=payment,
                )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except sqlite3.IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pembayaran tidak dapat disimpan.",
        ) from error

    return DebtPaymentResponse.model_validate(payment)


@router.delete("/{debt_id}/payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_payment(
    debt_id: int,
    payment_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    """Hapus satu cicilan, baris kasnya, dan hitung ulang sisa utang/piutang."""

    with transaction(db):
        deleted = delete_debt_payment(
            db,
            user_id=current_user.id,
            debt_id=debt_id,
            payment_id=payment_id,
        )
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_DETAIL)


@router.get("/{debt_id}/payments", response_model=list[DebtPaymentResponse])
def get_payments(
    debt_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[DebtPaymentResponse]:
    """List all payments for one debt/receivable."""

    payments = list_debt_payments(db, debt_id=debt_id, user_id=current_user.id)
    return [DebtPaymentResponse.model_validate(payment) for payment in payments]