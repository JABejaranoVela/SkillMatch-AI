"""initial schema

Revision ID: 20260508_0001
Revises:
Create Date: 2026-05-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = "20260508_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    user_role = postgresql.ENUM("USER", "ADMIN", name="userrole", create_type=False)
    resume_status = postgresql.ENUM(
        "UPLOADED", "PROCESSING", "PROCESSED", "FAILED", name="resumestatus", create_type=False
    )
    job_status = postgresql.ENUM("ACTIVE", "INACTIVE", name="jobstatus", create_type=False)
    interaction_type = postgresql.ENUM(
        "VIEWED", "SAVED", "DISCARDED", "APPLIED", name="interactiontype", create_type=False
    )

    for enum_type in (user_role, resume_status, job_status, interaction_type):
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("role", user_role, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("normalized_name", sa.String(length=150), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=True),
    )
    op.create_index("ix_skills_normalized_name", "skills", ["normalized_name"], unique=True)
    op.create_unique_constraint("uq_skills_name", "skills", ["name"])

    op.create_table(
        "resumes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("status", resume_status, nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("clean_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_resumes_user_id", "resumes", ["user_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("modality", sa.String(length=50), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("status", job_status, nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
    )
    op.create_index("ix_jobs_title", "jobs", ["title"])

    op.create_table(
        "professional_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id"), nullable=False),
        sa.Column("summary", sa.String(length=1000), nullable=True),
        sa.Column("experience_years", sa.Float(), nullable=True),
        sa.Column("education", sa.JSON(), nullable=True),
        sa.Column("languages", sa.JSON(), nullable=True),
        sa.Column("technologies", sa.JSON(), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("resume_id"),
    )

    op.create_table(
        "profile_skills",
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("professional_profiles.id"), primary_key=True),
        sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), primary_key=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
    )

    op.create_table(
        "job_skills",
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), primary_key=True),
        sa.Column("required_level", sa.String(length=50), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False),
    )

    op.create_table(
        "match_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("rules_score", sa.Float(), nullable=False),
        sa.Column("semantic_score", sa.Float(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.Column("algorithm_version", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_match_results_user_id", "match_results", ["user_id"])
    op.create_index("ix_match_results_resume_id", "match_results", ["resume_id"])
    op.create_index("ix_match_results_job_id", "match_results", ["job_id"])

    op.create_table(
        "user_job_interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("match_result_id", sa.Integer(), sa.ForeignKey("match_results.id"), nullable=True),
        sa.Column("interaction_type", interaction_type, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_job_interactions_user_id", "user_job_interactions", ["user_id"])
    op.create_index("ix_user_job_interactions_job_id", "user_job_interactions", ["job_id"])

    op.create_table(
        "job_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("records_total", sa.Integer(), nullable=False),
        sa.Column("records_ok", sa.Integer(), nullable=False),
        sa.Column("records_error", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("job_imports")
    op.drop_index("ix_user_job_interactions_job_id", table_name="user_job_interactions")
    op.drop_index("ix_user_job_interactions_user_id", table_name="user_job_interactions")
    op.drop_table("user_job_interactions")
    op.drop_index("ix_match_results_job_id", table_name="match_results")
    op.drop_index("ix_match_results_resume_id", table_name="match_results")
    op.drop_index("ix_match_results_user_id", table_name="match_results")
    op.drop_table("match_results")
    op.drop_table("job_skills")
    op.drop_table("profile_skills")
    op.drop_table("professional_profiles")
    op.drop_index("ix_jobs_title", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_resumes_user_id", table_name="resumes")
    op.drop_table("resumes")
    op.drop_constraint("uq_skills_name", "skills", type_="unique")
    op.drop_index("ix_skills_normalized_name", table_name="skills")
    op.drop_table("skills")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    sa.Enum(name="interactiontype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="jobstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="resumestatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
