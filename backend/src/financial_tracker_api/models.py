"""SQLModel database models."""

from datetime import UTC, date, datetime

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class User(SQLModel, table=True):
    """Registered application user."""

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    display_name: str = ""
    province: str = "ON"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    receipts: list["Receipt"] = Relationship(back_populates="user")
    refresh_sessions: list["RefreshSession"] = Relationship(back_populates="user")


class RefreshSession(SQLModel, table=True):
    """Revocable refresh-token sessions."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    jti: str = Field(index=True, unique=True)
    expires_at: datetime
    revoked: bool = False
    created_at: datetime = Field(default_factory=utcnow)

    user: User | None = Relationship(back_populates="refresh_sessions")


class Category(SQLModel, table=True):
    """Global spend category seed."""

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str


class CategoryRule(SQLModel, table=True):
    """User-taught item name → category mapping for future receipts."""

    __table_args__ = (UniqueConstraint("user_id", "name_key", name="uq_categoryrule_user_name"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name_key: str = Field(index=True)
    category: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Store(SQLModel, table=True):
    """User-scoped merchant location, unique on name + address."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(index=True)
    address: str = ""
    phone: str = ""
    created_at: datetime = Field(default_factory=utcnow)

    receipts: list["Receipt"] = Relationship(back_populates="store")


class Receipt(SQLModel, table=True):
    """Uploaded receipt belonging to a user."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    store_id: int | None = Field(default=None, foreign_key="store.id", index=True)
    image_path: str
    store_name: str = ""
    purchased_at: date | None = None
    subtotal_cents: int | None = None
    tax_total_cents: int | None = None
    total_cents: int | None = None
    raw_ocr_text: str = ""
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)

    user: User | None = Relationship(back_populates="receipts")
    store: Store | None = Relationship(back_populates="receipts")
    line_items: list["LineItem"] = Relationship(back_populates="receipt")


class LineItem(SQLModel, table=True):
    """Parsed line item on a receipt."""

    id: int | None = Field(default=None, primary_key=True)
    receipt_id: int = Field(foreign_key="receipt.id", index=True)
    name: str
    quantity: float = 1.0
    quantity_unit: str = "ea"  # ea | kg | lb | g | oz
    unit_price_cents: int = 0
    line_total_cents: int = 0
    category: str = "other"
    tax_status: str = "unknown"  # taxable | zero_rated | unknown
    tax_amount_cents: int = 0
    confidence: float = 0.0
    needs_review: bool = False

    receipt: Receipt | None = Relationship(back_populates="line_items")
