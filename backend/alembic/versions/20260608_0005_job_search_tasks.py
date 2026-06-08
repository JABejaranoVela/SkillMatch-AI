"""add job search tasks

Revision ID: 20260608_0005
Revises: 20260603_0004
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260608_0005"
down_revision = "20260603_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_search_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("imported", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_search_tasks_task_id"), "job_search_tasks", ["task_id"], unique=True)
    op.create_index(op.f("ix_job_search_tasks_user_id"), "job_search_tasks", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_search_tasks_user_id"), table_name="job_search_tasks")
    op.drop_index(op.f("ix_job_search_tasks_task_id"), table_name="job_search_tasks")
    op.drop_table("job_search_tasks")
