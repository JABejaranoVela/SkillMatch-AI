"""active resume and profile type

Revision ID: 20260508_0002
Revises: 20260508_0001
Create Date: 2026-05-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0002"
down_revision: str | None = "20260508_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("resumes", sa.Column("is_active", sa.Boolean(), nullable=True))
    op.execute("UPDATE resumes SET is_active = TRUE")
    op.alter_column("resumes", "is_active", nullable=False)
    op.add_column("professional_profiles", sa.Column("profile_type", sa.String(length=150), nullable=True))


def downgrade() -> None:
    op.drop_column("professional_profiles", "profile_type")
    op.drop_column("resumes", "is_active")

