"""Initial schema including refresh sessions and quantity units.

Revision ID: 20261102_0001
Revises:
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261102_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("province", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "refreshsession",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("jti", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_refreshsession_user_id", "refreshsession", ["user_id"])
    op.create_index("ix_refreshsession_jti", "refreshsession", ["jti"], unique=True)

    op.create_table(
        "category",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
    )
    op.create_index("ix_category_slug", "category", ["slug"], unique=True)

    op.create_table(
        "store",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_store_user_id", "store", ["user_id"])
    op.create_index("ix_store_name", "store", ["name"])

    op.create_table(
        "receipt",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("store.id"), nullable=True),
        sa.Column("image_path", sa.String(), nullable=False),
        sa.Column("store_name", sa.String(), nullable=False),
        sa.Column("purchased_at", sa.Date(), nullable=True),
        sa.Column("subtotal_cents", sa.Integer(), nullable=True),
        sa.Column("tax_total_cents", sa.Integer(), nullable=True),
        sa.Column("total_cents", sa.Integer(), nullable=True),
        sa.Column("raw_ocr_text", sa.String(), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        sa.Column("review_reasons", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_receipt_user_id", "receipt", ["user_id"])
    op.create_index("ix_receipt_store_id", "receipt", ["store_id"])

    op.create_table(
        "lineitem",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("receipt_id", sa.Integer(), sa.ForeignKey("receipt.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("quantity_unit", sa.String(), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("line_total_cents", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("tax_status", sa.String(), nullable=False),
        sa.Column("tax_amount_cents", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_lineitem_receipt_id", "lineitem", ["receipt_id"])


def downgrade() -> None:
    op.drop_table("lineitem")
    op.drop_table("receipt")
    op.drop_table("store")
    op.drop_table("category")
    op.drop_table("refreshsession")
    op.drop_table("user")
