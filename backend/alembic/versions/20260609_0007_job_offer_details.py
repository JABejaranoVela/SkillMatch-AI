"""add job offer details

Revision ID: 20260609_0007
Revises: 20260608_0006
Create Date: 2026-06-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260609_0007"
down_revision = "20260608_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("salary_min", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("salary_max", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("salary_currency", sa.String(length=10), nullable=True))
    op.add_column("jobs", sa.Column("contract_type", sa.String(length=100), nullable=True))
    op.add_column("jobs", sa.Column("published_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "published_at")
    op.drop_column("jobs", "contract_type")
    op.drop_column("jobs", "salary_currency")
    op.drop_column("jobs", "salary_max")
    op.drop_column("jobs", "salary_min")
