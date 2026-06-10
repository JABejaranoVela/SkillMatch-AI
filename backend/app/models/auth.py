from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import enum_values


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AccountTokenPurpose(StrEnum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


class EmailOutboxStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_user_active", "user_id", "revoked_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user = relationship("User", back_populates="auth_sessions")


class AccountToken(Base):
    __tablename__ = "account_tokens"
    __table_args__ = (
        Index("ix_account_tokens_user_purpose", "user_id", "purpose"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    purpose: Mapped[AccountTokenPurpose] = mapped_column(
        Enum(
            AccountTokenPurpose,
            values_callable=enum_values,
            name="accounttokenpurpose",
        )
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user = relationship("User", back_populates="account_tokens")


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    __table_args__ = (
        Index("ix_email_outbox_pending", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_token_id: Mapped[int | None] = mapped_column(
        ForeignKey("account_tokens.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recipient: Mapped[str] = mapped_column(String(320), index=True)
    template: Mapped[str] = mapped_column(String(100))
    variables: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    encrypted_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[EmailOutboxStatus] = mapped_column(
        Enum(
            EmailOutboxStatus,
            values_callable=enum_values,
            name="emailoutboxstatus",
        ),
        default=EmailOutboxStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    account_token = relationship("AccountToken")
