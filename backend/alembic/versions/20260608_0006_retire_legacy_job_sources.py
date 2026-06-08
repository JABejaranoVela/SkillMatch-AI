"""retire legacy job sources

Revision ID: 20260608_0006
Revises: 20260608_0005
Create Date: 2026-06-08
"""

from alembic import op


revision = "20260608_0006"
down_revision = "20260608_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE jobs SET status = 'INACTIVE' "
        "WHERE source IN ('remotive', 'arbeitnow') AND status = 'ACTIVE'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE jobs SET status = 'ACTIVE' "
        "WHERE source IN ('remotive', 'arbeitnow') AND status = 'INACTIVE'"
    )
