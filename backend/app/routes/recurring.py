"""Recurring transaction schedule routes."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from finance_core.db.categories import category_belongs_to
from finance_core.db.connection import transaction
from finance_core.db.recurring import (
    create_recurring,
    delete_recurring,
    get_recurring,
    list_recurring,
    update_recurring,
)
from finance_core.db.users import AppUser
from finance_core.recurring import first_on_or_after, validate_schedule
from finance_core.services.transaction_service import find_or_create_category
from finance_core.timezones import today_in

from ..auth.dependencies import get_current_user, get_db
from ..models.schemas import RecurringCreate, RecurringResponse, RecurringUpdate

router = APIRouter(prefix="/api/recurring", tags=["Recurring Transactions"])

NOT_FOUND_DETAIL = "Jadwal transaksi berulang tidak ditemukan."
INVALID_CATEGORY_DETAIL = "Kategori tidak valid untuk transaksi ini."


def _resolve_category(
    db: sqlite3.Connection,
    *,
    user_id: int,
    transaction_type: str,
    category_id: int | None,
    category_name: str | None,
) -> int | None:
    """Validate a category id or create a category by name."""

    if category_id is not None:
        if not category_belongs_to(
            db,
            user_id=user_id,
            category_id=category_id,
            category_type=transaction_type,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=INVALID_CATEGORY_DETAIL,
            )
        return category_id

    if category_name:
        return find_or_create_category(
            db,
            user_id=user_id,
            category_type=transaction_type,
            category_name=category_name,
        )
    return None


def _next_run_date(
    *,
    start_date: date,
    last_run_date: str | None,
    today: date,
    frequency: str,
    day_of_week: int | None,
    day_of_month: int | None,
) -> date:
    """Pick the next occurrence without replaying history the user already has."""

    anchor = max(start_date, today)
    if last_run_date:
        last_run = date.fromisoformat(last_run_date)
        if anchor <= last_run:
            anchor = last_run + timedelta(days=1)
    return first_on_or_after(anchor, frequency, day_of_week, day_of_month)


@router.get("", response_model=list[RecurringResponse])
def get_recurring_transactions(
    active_only: bool = Query(False),
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[RecurringResponse]:
    """List the user's recurring schedules, soonest due first."""

    items = list_recurring(db, user_id=current_user.id, active_only=active_only)
    return [RecurringResponse.model_validate(item) for item in items]


@router.post("", response_model=RecurringResponse, status_code=status.HTTP_201_CREATED)
def create_recurring_transaction(
    payload: RecurringCreate,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> RecurringResponse:
    """Create a weekly or monthly schedule."""

    validate_schedule(payload.frequency, payload.day_of_week, payload.day_of_month)
    category_id = _resolve_category(
        db,
        user_id=current_user.id,
        transaction_type=payload.type,
        category_id=payload.category_id,
        category_name=payload.category_name,
    )

    today = today_in(current_user.timezone)
    next_run = _next_run_date(
        start_date=payload.start_date,
        last_run_date=None,
        today=today,
        frequency=payload.frequency,
        day_of_week=payload.day_of_week,
        day_of_month=payload.day_of_month,
    )

    with transaction(db):
        recurring = create_recurring(
            db,
            user_id=current_user.id,
            type=payload.type,
            category_id=category_id,
            amount=payload.amount,
            note=payload.note,
            asset_name=payload.asset_name,
            frequency=payload.frequency,
            day_of_week=payload.day_of_week if payload.frequency == "weekly" else None,
            day_of_month=payload.day_of_month if payload.frequency == "monthly" else None,
            start_date=payload.start_date.isoformat(),
            next_run_date=next_run.isoformat(),
            is_active=payload.is_active,
        )
    return RecurringResponse.model_validate(recurring)


@router.put("/{recurring_id}", response_model=RecurringResponse)
def edit_recurring_transaction(
    recurring_id: int,
    payload: RecurringUpdate,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> RecurringResponse:
    """Update a schedule. Already generated transactions are not rewritten."""

    existing = get_recurring(db, user_id=current_user.id, recurring_id=recurring_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )

    updates = payload.model_dump(exclude_unset=True)
    fields_set = payload.model_fields_set

    final_type = updates.get("type", existing.type)
    category_id = updates.get("category_id", existing.category_id)
    if "category_name" in fields_set:
        category_name = updates.pop("category_name")
        if category_name:
            category_id = find_or_create_category(
                db,
                user_id=current_user.id,
                category_type=final_type,
                category_name=category_name,
            )
    else:
        updates.pop("category_name", None)

    if category_id is not None and not category_belongs_to(
        db,
        user_id=current_user.id,
        category_id=category_id,
        category_type=final_type,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_CATEGORY_DETAIL,
        )

    frequency = updates.get("frequency", existing.frequency)
    day_of_week = updates.get("day_of_week", existing.day_of_week)
    day_of_month = updates.get("day_of_month", existing.day_of_month)
    if frequency == "weekly":
        day_of_month = None
    else:
        day_of_week = None
    validate_schedule(frequency, day_of_week, day_of_month)

    start_date = updates.get("start_date", date.fromisoformat(existing.start_date))
    is_active = updates.get("is_active", bool(existing.is_active))

    schedule_changed = bool(
        {"frequency", "day_of_week", "day_of_month", "start_date"} & fields_set
    )
    activating = not existing.is_active and is_active
    if schedule_changed or activating:
        next_run = _next_run_date(
            start_date=start_date,
            last_run_date=existing.last_run_date,
            today=today_in(current_user.timezone),
            frequency=frequency,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
        )
    else:
        next_run = date.fromisoformat(existing.next_run_date)

    with transaction(db):
        updated = update_recurring(
            db,
            user_id=current_user.id,
            recurring_id=recurring_id,
            type=final_type,
            category_id=category_id,
            amount=updates.get("amount", existing.amount),
            note=updates.get("note", existing.note),
            asset_name=updates.get("asset_name", existing.asset_name),
            frequency=frequency,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            start_date=start_date.isoformat(),
            next_run_date=next_run.isoformat(),
            is_active=is_active,
        )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )
    return RecurringResponse.model_validate(updated)


@router.delete("/{recurring_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_recurring_transaction(
    recurring_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    """Delete a schedule. Transactions it already generated stay in the ledger."""

    with transaction(db):
        deleted = delete_recurring(db, user_id=current_user.id, recurring_id=recurring_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )