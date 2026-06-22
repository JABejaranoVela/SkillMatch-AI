from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.user import User


def test_database_rejects_case_insensitive_duplicate_user_emails() -> None:
    db = SessionLocal()
    suffix = uuid4().hex
    try:
        db.add(
            User(
                email=f"Integrity-{suffix}@Example.com",
                hashed_password="argon2-placeholder",
            )
        )
        db.flush()

        db.add(
            User(
                email=f" integrity-{suffix}@example.com ",
                hashed_password="argon2-placeholder",
            )
        )

        with pytest.raises(IntegrityError):
            db.flush()
    finally:
        db.rollback()
        db.close()


def test_database_rejects_multiple_active_resumes_for_same_user() -> None:
    db = SessionLocal()
    suffix = uuid4().hex
    try:
        user = User(
            email=f"resume-integrity-{suffix}@example.com",
            hashed_password="argon2-placeholder",
        )
        db.add(user)
        db.flush()

        db.add(
            Resume(
                user_id=user.id,
                filename="one.pdf",
                file_path="/tmp/one.pdf",
                file_type="application/pdf",
                is_active=True,
            )
        )
        db.flush()

        db.add(
            Resume(
                user_id=user.id,
                filename="two.pdf",
                file_path="/tmp/two.pdf",
                file_type="application/pdf",
                is_active=True,
            )
        )

        with pytest.raises(IntegrityError):
            db.flush()
    finally:
        db.rollback()
        db.close()
