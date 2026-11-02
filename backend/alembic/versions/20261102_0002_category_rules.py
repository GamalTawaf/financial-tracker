"""Add per-user learned item category rules.

Revision ID: 20261102_0002
Revises: 20261102_0001
Create Date: 2026-11-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261102_0002"
down_revision = "20261102_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categoryrule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name_key", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name_key", name="uq_categoryrule_user_name"),
    )
    op.create_index("ix_categoryrule_user_id", "categoryrule", ["user_id"])
    op.create_index("ix_categoryrule_name_key", "categoryrule", ["name_key"])


def downgrade() -> None:
    op.drop_index("ix_categoryrule_name_key", table_name="categoryrule")
    op.drop_index("ix_categoryrule_user_id", table_name="categoryrule")
    op.drop_table("categoryrule")
