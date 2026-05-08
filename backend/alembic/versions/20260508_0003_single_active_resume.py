"""single active resume per user

Revision ID: 20260508_0003
Revises: 20260508_0002
Create Date: 2026-05-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260508_0003"
down_revision: str | None = "20260508_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked_resumes AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id
                    ORDER BY created_at DESC, id DESC
                ) AS resume_rank
            FROM resumes
        )
        UPDATE resumes
        SET is_active = ranked_resumes.resume_rank = 1
        FROM ranked_resumes
        WHERE resumes.id = ranked_resumes.id
        """
    )


def downgrade() -> None:
    op.execute("UPDATE resumes SET is_active = TRUE")

