"""food vertical tables: batches, quality holds, stock movements

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "batch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("production_date", sa.Date(), nullable=False),
        sa.Column("planned_units", sa.Integer(), nullable=False),
        sa.Column("actual_units", sa.Integer(), nullable=False),
    )
    op.create_table(
        "quality_hold",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("batch.id"), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("hold_date", sa.Date(), nullable=False),
        sa.Column("released", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "stock_movement",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("batch.id"), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("movement_date", sa.Date(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("stock_movement")
    op.drop_table("quality_hold")
    op.drop_table("batch")
