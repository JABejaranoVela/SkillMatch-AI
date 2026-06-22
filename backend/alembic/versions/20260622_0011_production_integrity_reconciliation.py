"""production integrity reconciliation

Revision ID: 20260622_0011
Revises: 20260611_0010
Create Date: 2026-06-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260622_0011"
down_revision: str | None = "20260611_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicate_emails = bind.execute(
        sa.text(
            """
            SELECT lower(btrim(email)) AS normalized_email, count(*) AS total
            FROM users
            GROUP BY lower(btrim(email))
            HAVING count(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate_emails is not None:
        raise RuntimeError(
            "Cannot create ix_users_email_normalized_unique: "
            "duplicate normalized user emails exist"
        )

    duplicate_active_resumes = bind.execute(
        sa.text(
            """
            SELECT user_id, count(*) AS total
            FROM resumes
            WHERE is_active IS TRUE
            GROUP BY user_id
            HAVING count(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate_active_resumes is not None:
        raise RuntimeError(
            "Cannot create uq_resumes_one_active_per_user: "
            "users with multiple active resumes exist"
        )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_normalized_unique
        ON users (lower(btrim(email)))
        """
    )
    op.create_index(
        "uq_resumes_one_active_per_user",
        "resumes",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
    )
    op.create_index(
        "ix_user_job_interactions_match_result_id",
        "user_job_interactions",
        ["match_result_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_job_interactions_match_result_id",
        table_name="user_job_interactions",
    )
    op.drop_index("uq_resumes_one_active_per_user", table_name="resumes")
    op.drop_index("ix_users_email_normalized_unique", table_name="users")
