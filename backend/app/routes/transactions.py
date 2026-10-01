"""Transaction management routes."""

from __future__ import annotations

import sqlite3
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from ..auth.dependencies import get_current_user, get_db
from ..database.transactions import (
    create_transaction,
    delete_transaction,
    get_transaction_by_id,
    list_transactions,
    update_transaction,
)
from ..database.users import AppUser
from ..models.domain import transaction_type_label, valid_transaction_type_values
from ..models.schemas import (
    QuickInputPreviewResponse,
    QuickInputRequest,
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)
from ..services.quick_input_parser import parse_quick_input
from ..services.transaction_service import (
    TransactionServiceError,
    find_or_create_category,
    save_quick_input_transaction,
)

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_new_transaction(
    payload: TransactionCreate,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> TransactionResponse:
    """Create a new transaction manually."""
    if payload.type not in valid_transaction_type_values():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipe transaksi tidak valid: {payload.type}",
        )

    cat_id = payload.category_id
    if cat_id is None and payload.category_name:
        cat_id = find_or_create_category(
            db,
            user_id=current_user.id,
            category_type=payload.type,
            category_name=payload.category_name,
        )

    tx = create_transaction(
        db,
        user_id=current_user.id,
        type=payload.type,
        category_id=cat_id,
        amount=payload.amount,
        note=payload.note,
        asset_name=payload.asset_name,
        transaction_date=payload.transaction_date,
    )

    return TransactionResponse(
        id=tx.id,
        user_id=tx.user_id,
        type=tx.type,
        category_id=tx.category_id,
        category_name=tx.category_name,
        amount=tx.amount,
        note=tx.note,
        asset_name=tx.asset_name,
        transaction_date=tx.transaction_date,
    )


@router.post("/quick-input", response_model=QuickInputPreviewResponse)
def preview_quick_input(
    payload: QuickInputRequest,
    current_user: AppUser = Depends(get_current_user),
) -> QuickInputPreviewResponse:
    """Parse quick input text and return preview before saving."""
    from datetime import date
    ref_date = date.fromisoformat(payload.reference_date) if payload.reference_date else None
    result = parse_quick_input(payload.text, today=ref_date, timezone=current_user.timezone)

    if result.error:
        return QuickInputPreviewResponse(
            type=None,
            type_label=None,
            category_name=None,
            amount=None,
            note=result.note,
            asset_name=None,
            transaction_date=None,
            is_valid=False,
            error=result.error,
        )

    return QuickInputPreviewResponse(
        type=result.type,
        type_label=transaction_type_label(result.type) if result.type else None,
        category_name=result.category_name,
        amount=result.amount,
        note=result.note,
        asset_name=result.asset_name,
        transaction_date=result.transaction_date.isoformat() if result.transaction_date else None,
        is_valid=True,
        error=None,
    )


@router.post("/quick-input/confirm", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def confirm_quick_input(
    payload: QuickInputRequest,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> TransactionResponse:
    """Parse and immediately save quick input."""
    from datetime import date
    ref_date = date.fromisoformat(payload.reference_date) if payload.reference_date else None
    result = parse_quick_input(payload.text, today=ref_date, timezone=current_user.timezone)

    if result.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    try:
        tx = save_quick_input_transaction(db, user_id=current_user.id, preview=result)
        return TransactionResponse(
            id=tx.id,
            user_id=tx.user_id,
            type=tx.type,
            category_id=tx.category_id,
            category_name=tx.category_name or result.category_name,
            amount=tx.amount,
            note=tx.note,
            asset_name=tx.asset_name,
            transaction_date=tx.transaction_date,
        )
    except TransactionServiceError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("", response_model=List[TransactionResponse])
def get_transactions(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    type: Optional[str] = Query(None, description="Transaction type filter"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[TransactionResponse]:
    """List transactions with optional filters and pagination."""
    items = list_transactions(
        db,
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        transaction_type=type,
        limit=limit,
        offset=offset,
    )
    return [
        TransactionResponse(
            id=t.id,
            user_id=t.user_id,
            type=t.type,
            category_id=t.category_id,
            category_name=t.category_name,
            amount=t.amount,
            note=t.note,
            asset_name=t.asset_name,
            transaction_date=t.transaction_date,
        )
        for t in items
    ]


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> TransactionResponse:
    """Get single transaction by ID."""
    tx = get_transaction_by_id(db, user_id=current_user.id, transaction_id=transaction_id)
    if tx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaksi tidak ditemukan.",
        )
    return TransactionResponse(
        id=tx.id,
        user_id=tx.user_id,
        type=tx.type,
        category_id=tx.category_id,
        category_name=tx.category_name,
        amount=tx.amount,
        note=tx.note,
        asset_name=tx.asset_name,
        transaction_date=tx.transaction_date,
    )


@router.put("/{transaction_id}", response_model=TransactionResponse)
def edit_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> TransactionResponse:
    """Update fields of an existing transaction."""
    updated = update_transaction(
        db,
        user_id=current_user.id,
        transaction_id=transaction_id,
        amount=payload.amount,
        category_id=payload.category_id,
        transaction_date=payload.transaction_date,
        note=payload.note,
        asset_name=payload.asset_name,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaksi tidak ditemukan.",
        )
    return TransactionResponse(
        id=updated.id,
        user_id=updated.user_id,
        type=updated.type,
        category_id=updated.category_id,
        category_name=updated.category_name,
        amount=updated.amount,
        note=updated.note,
        asset_name=updated.asset_name,
        transaction_date=updated.transaction_date,
    )


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_transaction(
    transaction_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    """Delete a transaction."""
    success = delete_transaction(db, user_id=current_user.id, transaction_id=transaction_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaksi tidak ditemukan.",
        )
