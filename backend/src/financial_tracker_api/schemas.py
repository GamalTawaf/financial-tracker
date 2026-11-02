"""Pydantic request/response schemas."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from financial_tracker_api.auth import validate_password_strength

QuantityUnit = Literal["ea", "kg", "lb", "g", "oz"]
TaxStatus = Literal["taxable", "zero_rated", "unknown"]


class RegisterRequest(BaseModel):
    """Create a new user account."""

    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str = ""

    @field_validator("password")
    @classmethod
    def _password_rules(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class LoginRequest(BaseModel):
    """Authenticate an existing user."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Exchange a refresh token for a new token pair."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Bearer tokens returned after login/register/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """Public user profile."""

    id: int
    email: EmailStr
    display_name: str
    province: str
    created_at: datetime


class UserUpdateRequest(BaseModel):
    """Patch current user profile."""

    display_name: str | None = None
    province: str | None = None


class LineItemResponse(BaseModel):
    """Line item on a receipt."""

    id: int
    name: str
    quantity: float
    quantity_unit: QuantityUnit = "ea"
    unit_price_cents: int
    line_total_cents: int
    category: str
    tax_status: TaxStatus
    tax_amount_cents: int
    confidence: float
    needs_review: bool


class LineItemUpdateRequest(BaseModel):
    """Edit a persisted line item."""

    name: str | None = None
    quantity: float | None = None
    quantity_unit: QuantityUnit | None = None
    unit_price_cents: int | None = None
    line_total_cents: int | None = None
    category: str | None = Field(default=None, max_length=64)
    tax_status: TaxStatus | None = None
    tax_amount_cents: int | None = None
    needs_review: bool | None = None


class StoreResponse(BaseModel):
    """Saved merchant location for a user."""

    id: int
    name: str
    address: str
    phone: str


class ReceiptResponse(BaseModel):
    """Receipt with nested line items."""

    id: int
    store_id: int | None = None
    store_name: str
    store: StoreResponse | None = None
    purchased_at: date | None
    subtotal_cents: int | None
    tax_total_cents: int | None
    total_cents: int | None
    needs_review: bool
    review_reasons: list[str]
    has_image: bool = False
    created_at: datetime
    line_items: list[LineItemResponse] = []


class ReceiptUpdateRequest(BaseModel):
    """Patch receipt header fields."""

    store_name: str | None = None
    purchased_at: date | None = None
    needs_review: bool | None = None
    review_reasons: list[str] | None = None


class CategoryTotal(BaseModel):
    """Spend rollup for one category."""

    category: str
    total_cents: int
    tax_cents: int
    item_count: int


class CategoryStatsResponse(BaseModel):
    """Category totals for a date range."""

    from_date: date | None
    to_date: date | None
    categories: list[CategoryTotal]


class ErrorBody(BaseModel):
    """Structured API error."""

    detail: str
    code: str = "error"
