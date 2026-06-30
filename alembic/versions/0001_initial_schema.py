"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_key", sa.String(length=128), primary_key=True),
        sa.Column("quota_limit_credits", sa.Integer(), nullable=False),
        sa.Column("credit_multiplier", sa.Numeric(10, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "quota_reservations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_key", sa.String(length=128), sa.ForeignKey("users.user_key"), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("estimated_credits", sa.Integer(), nullable=False),
        sa.Column("estimated_total_tokens", sa.Integer(), nullable=False),
        sa.Column("actual_credits", sa.Integer(), nullable=True),
        sa.Column("actual_total_tokens", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "usage_ledger",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_key", sa.String(length=128), sa.ForeignKey("users.user_key"), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("multiplier_snapshot", sa.Numeric(10, 4), nullable=False),
        sa.Column("estimated_credits", sa.Integer(), nullable=False),
        sa.Column("billable_credits", sa.Integer(), nullable=False),
        sa.Column("output_text", sa.String(length=4000), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("usage_ledger")
    op.drop_table("quota_reservations")
    op.drop_table("users")
