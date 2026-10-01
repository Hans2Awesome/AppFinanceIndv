"""Pydantic schemas for request and response validation."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# --- Auth Schemas ---

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    first_name: Optional[str] = None
    timezone: str = "Asia/Jakarta"
    currency: str = "IDR"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str] = None
    timezone: str = "Asia/Jakarta"
    currency: str = "IDR"
    created_at: Optional[str] = None


# --- Category Schemas ---

class CategoryCreate(BaseModel):
    type: str  # income, expense, investment
    name: str
    aliases: str = ""


class CategoryResponse(BaseModel):
    id: int
    user_id: int
    type: str
    name: str
    aliases: str = ""
    is_default: int = 0


# --- Transaction Schemas ---

class TransactionCreate(BaseModel):
    type: str  # income, expense, investment
    category_id: Optional[int] = None
    category_name: Optional[str] = None  # alternatively by category name
    amount: int = Field(..., gt=0)
    note: Optional[str] = None
    asset_name: Optional[str] = None
    transaction_date: str  # YYYY-MM-DD


class TransactionUpdate(BaseModel):
    amount: Optional[int] = Field(None, gt=0)
    category_id: Optional[int] = None
    transaction_date: Optional[str] = None
    note: Optional[str] = None
    asset_name: Optional[str] = None


class TransactionResponse(BaseModel):
    id: int
    user_id: int
    type: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    amount: int
    note: Optional[str] = None
    asset_name: Optional[str] = None
    transaction_date: str


class QuickInputRequest(BaseModel):
    text: str = Field(..., min_length=1)
    reference_date: Optional[str] = None  # YYYY-MM-DD or None (today)


class QuickInputPreviewResponse(BaseModel):
    type: Optional[str] = None
    type_label: Optional[str] = None
    category_name: Optional[str] = None
    amount: Optional[int] = None
    note: Optional[str] = None
    asset_name: Optional[str] = None
    transaction_date: Optional[str] = None
    is_valid: bool
    error: Optional[str] = None


# --- Report Schemas ---

class CategoryTotalItem(BaseModel):
    name: str
    amount: int
    percentage: float = 0.0


class PeriodReportResponse(BaseModel):
    title: str
    start_date: str
    end_date: str
    total_income: int
    total_expense: int
    total_investment: int
    net: int
    average_expense: int
    investment_percentage: float
    top_expense_categories: List[CategoryTotalItem]


class CategoryBreakdownResponse(BaseModel):
    title: str
    type: str
    categories: List[CategoryTotalItem]
    total_amount: int


class InvestmentReportResponse(BaseModel):
    title: str
    total_investment: int
    investment_percentage: float
    by_type: List[CategoryTotalItem]
    by_asset: List[CategoryTotalItem]


# --- Debt / Receivable Schemas ---

class DebtCreate(BaseModel):
    type: str  # 'debt' or 'receivable'
    person_name: str = Field(..., min_length=1)
    total_amount: int = Field(..., gt=0)
    note: Optional[str] = None
    due_date: Optional[str] = None  # YYYY-MM-DD


class DebtUpdate(BaseModel):
    person_name: Optional[str] = None
    total_amount: Optional[int] = Field(None, gt=0)
    note: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None  # 'active' or 'settled'


class DebtResponse(BaseModel):
    id: int
    user_id: int
    type: str
    person_name: str
    total_amount: int
    paid_amount: int
    note: Optional[str] = None
    due_date: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DebtPaymentCreate(BaseModel):
    amount: int = Field(..., gt=0)
    note: Optional[str] = None
    payment_date: str  # YYYY-MM-DD


class DebtPaymentResponse(BaseModel):
    id: int
    debt_id: int
    amount: int
    note: Optional[str] = None
    payment_date: str
    created_at: Optional[str] = None


class DebtSummaryResponse(BaseModel):
    total_debt_remaining: int
    total_receivable_remaining: int
    active_debt_count: int
    active_receivable_count: int
    due_soon_count: int

