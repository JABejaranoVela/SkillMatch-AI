from datetime import datetime
from enum import Enum as PythonEnum
from enum import StrEnum
from typing import TypeVar

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class UserStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"


EnumType = TypeVar("EnumType", bound=PythonEnum)


def enum_values(enum_class: type[EnumType]) -> list[str]:
    return [item.value for item in enum_class]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, values_callable=enum_values, name="userstatus"),
        default=UserStatus.PENDING,
        index=True,
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    resumes = relationship("Resume", back_populates="user")
    auth_sessions = relationship(
        "AuthSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    account_tokens = relationship(
        "AccountToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
