"""add authentication foundation

Revision ID: 20260610_0008
Revises: 20260609_0007
Create Date: 2026-06-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260610_0008"
down_revision: str | None = "20260609_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    user_status = postgresql.ENUM(
        "pending",
        "active",
        "disabled",
        name="userstatus",
        create_type=False,
    )
    token_purpose = postgresql.ENUM(
        "email_verification",
        "password_reset",
        name="accounttokenpurpose",
        create_type=False,
    )
    outbox_status = postgresql.ENUM(
        "pending",
        "sending",
        "sent",
        "failed",
        "cancelled",
        name="emailoutboxstatus",
        create_type=False,
    )
    bind = op.get_bind()
    for enum_type in (user_status, token_purpose, outbox_status):
        enum_type.create(bind, checkfirst=True)

    op.add_column(
        "users",
        sa.Column(
            "status",
            user_status,
            nullable=True,
            server_default=sa.text("'pending'::userstatus"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE users "
        "SET status = 'active', email_verified_at = CURRENT_TIMESTAMP "
        "WHERE status IS NULL OR email_verified_at IS NULL"
    )
    op.alter_column("users", "status", nullable=False)
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index(
        "ix_auth_sessions_token_hash",
        "auth_sessions",
        ["token_hash"],
        unique=True,
    )
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_index(
        "ix_auth_sessions_user_active",
        "auth_sessions",
        ["user_id", "revoked_at", "expires_at"],
    )

    op.create_table(
        "account_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", token_purpose, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_account_tokens_user_id", "account_tokens", ["user_id"])
    op.create_index(
        "ix_account_tokens_token_hash",
        "account_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index("ix_account_tokens_expires_at", "account_tokens", ["expires_at"])
    op.create_index(
        "ix_account_tokens_user_purpose",
        "account_tokens",
        ["user_id", "purpose"],
    )

    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("template", sa.String(length=100), nullable=False),
        sa.Column(
            "variables",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            outbox_status,
            nullable=False,
            server_default=sa.text("'pending'::emailoutboxstatus"),
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_email_outbox_recipient", "email_outbox", ["recipient"])
    op.create_index(
        "ix_email_outbox_pending",
        "email_outbox",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_outbox_pending", table_name="email_outbox")
    op.drop_index("ix_email_outbox_recipient", table_name="email_outbox")
    op.drop_table("email_outbox")

    op.drop_index("ix_account_tokens_user_purpose", table_name="account_tokens")
    op.drop_index("ix_account_tokens_expires_at", table_name="account_tokens")
    op.drop_index("ix_account_tokens_token_hash", table_name="account_tokens")
    op.drop_index("ix_account_tokens_user_id", table_name="account_tokens")
    op.drop_table("account_tokens")

    op.drop_index("ix_auth_sessions_user_active", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_index("ix_users_status", table_name="users")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "status")

    bind = op.get_bind()
    postgresql.ENUM(name="emailoutboxstatus").drop(bind, checkfirst=True)
    postgresql.ENUM(name="accounttokenpurpose").drop(bind, checkfirst=True)
    postgresql.ENUM(name="userstatus").drop(bind, checkfirst=True)
