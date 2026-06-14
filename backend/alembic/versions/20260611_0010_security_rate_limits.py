"""add persistent authentication rate limit buckets

Revision ID: 20260611_0010
Revises: 20260611_0009
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260611_0010"
down_revision: str | None = "20260611_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_rate_limit_buckets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_auth_rate_limit_buckets_key_hash",
        "auth_rate_limit_buckets",
        ["key_hash"],
        unique=True,
    )
    op.create_index(
        "ix_auth_rate_limit_buckets_action",
        "auth_rate_limit_buckets",
        ["action"],
    )
    op.create_index(
        "ix_auth_rate_limit_buckets_expires_at",
        "auth_rate_limit_buckets",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_rate_limit_buckets_expires_at",
        table_name="auth_rate_limit_buckets",
    )
    op.drop_index(
        "ix_auth_rate_limit_buckets_action",
        table_name="auth_rate_limit_buckets",
    )
    op.drop_index(
        "ix_auth_rate_limit_buckets_key_hash",
        table_name="auth_rate_limit_buckets",
    )
    op.drop_table("auth_rate_limit_buckets")
