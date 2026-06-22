from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProfessionalProfile(Base):
    __tablename__ = "professional_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), unique=True)
    profile_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    experience_years: Mapped[float | None] = mapped_column(nullable=True)
    education: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    languages: Mapped[list | None] = mapped_column(JSON, nullable=True)
    technologies: Mapped[list | None] = mapped_column(JSON, nullable=True)
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    embedding: Mapped[list | None] = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    resume = relationship("Resume", back_populates="profile")
    skills = relationship("ProfileSkill", back_populates="profile")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    normalized_name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(100))
    aliases: Mapped[list | None] = mapped_column(JSON, nullable=True)


class ProfileSkill(Base):
    __tablename__ = "profile_skills"

    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)
    confidence: Mapped[float] = mapped_column(default=1.0)
    source: Mapped[str] = mapped_column(String(50), default="dictionary")

    profile = relationship("ProfessionalProfile", back_populates="skills")
    skill = relationship("Skill")
