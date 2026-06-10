"""add encrypted email outbox worker fields

Revision ID: 20260611_0009
Revises: 20260610_0008
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260611_0009"
down_revision: str | None = "20260610_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "email_outbox",
        sa.Column(
            "account_token_id",
            sa.Integer(),
            sa.ForeignKey("account_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "email_outbox",
        sa.Column("encrypted_payload", sa.Text(), nullable=True),
    )
    op.add_column(
        "email_outbox",
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "email_outbox",
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_email_outbox_account_token_id",
        "email_outbox",
        ["account_token_id"],
    )
    op.execute(
        "UPDATE email_outbox "
        "SET status = 'cancelled', "
        "last_error = 'Legacy outbox row has no encrypted payload', "
        "updated_at = CURRENT_TIMESTAMP "
        "WHERE status IN ('pending', 'sending') AND encrypted_payload IS NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_email_outbox_account_token_id", table_name="email_outbox")
    op.drop_column("email_outbox", "last_attempt_at")
    op.drop_column("email_outbox", "last_error")
    op.drop_column("email_outbox", "encrypted_payload")
    op.drop_column("email_outbox", "account_token_id")
