from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.resumes import DELETE_RESUME_ERROR, delete_resume
from app.db.session import SessionLocal
from app.models.feedback import InteractionType, UserJobInteraction
from app.models.job import Job
from app.models.matching import MatchResult
from app.models.profile import ProfessionalProfile, ProfileSkill, Skill
from app.models.resume import Resume
from app.models.user import User, UserStatus


def make_user(db, *, email_prefix: str = "resume-delete") -> User:
    user = User(
        email=f"{email_prefix}-{uuid4().hex}@example.com",
        hashed_password="argon2-placeholder",
        status=UserStatus.ACTIVE,
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    return user


def create_resume_graph(db, tmp_path: Path, user: User) -> dict:
    suffix = uuid4().hex
    file_path = tmp_path / f"{suffix}.pdf"
    file_path.write_bytes(b"%PDF-private-cv")

    resume = Resume(
        user_id=user.id,
        filename=f"cv-{suffix}.pdf",
        file_path=str(file_path),
        file_type=".pdf",
        raw_text="private raw cv text",
        clean_text="private clean cv text",
        is_active=True,
    )
    db.add(resume)
    db.flush()

    profile = ProfessionalProfile(
        resume_id=resume.id,
        profile_type="Full Stack Developer",
        summary="Derived private profile",
        technologies=["Python", "FastAPI"],
        analysis={"matching": "derived"},
    )
    db.add(profile)
    db.flush()

    skill = Skill(
        name=f"Python {suffix}",
        normalized_name=f"python-{suffix}",
        category="backend",
    )
    db.add(skill)
    db.flush()
    db.add(ProfileSkill(profile_id=profile.id, skill_id=skill.id))

    job = Job(
        title=f"Backend Engineer {suffix}",
        description="Shared global job",
        source="test",
        external_id=suffix,
    )
    db.add(job)
    db.flush()

    match_result = MatchResult(
        user_id=user.id,
        resume_id=resume.id,
        job_id=job.id,
        final_score=88.0,
        explanation={"matching_skills": ["Python"], "missing_skills": []},
    )
    db.add(match_result)
    db.flush()

    interaction = UserJobInteraction(
        user_id=user.id,
        job_id=job.id,
        match_result_id=match_result.id,
        interaction_type=InteractionType.SAVED,
    )
    db.add(interaction)
    db.commit()

    return {
        "file_path": file_path,
        "resume_id": resume.id,
        "profile_id": profile.id,
        "skill_id": skill.id,
        "job_id": job.id,
        "match_result_id": match_result.id,
        "interaction_id": interaction.id,
    }


def test_user_can_delete_own_resume_and_derived_data(tmp_path) -> None:
    db = SessionLocal()
    try:
        user = make_user(db)
        graph = create_resume_graph(db, tmp_path, user)

        result = delete_resume(graph["resume_id"], db, user)

        assert result is None
        assert not graph["file_path"].exists()
        assert db.get(Resume, graph["resume_id"]) is None
        assert db.get(ProfessionalProfile, graph["profile_id"]) is None
        assert db.get(MatchResult, graph["match_result_id"]) is None
        assert db.get(Job, graph["job_id"]) is not None
        assert db.get(Skill, graph["skill_id"]) is not None

        interaction = db.get(UserJobInteraction, graph["interaction_id"])
        assert interaction is not None
        assert interaction.job_id == graph["job_id"]
        assert interaction.interaction_type == InteractionType.SAVED
        assert interaction.match_result_id is None
    finally:
        db.rollback()
        db.close()


def test_user_cannot_delete_foreign_resume(tmp_path) -> None:
    db = SessionLocal()
    try:
        owner = make_user(db, email_prefix="owner")
        attacker = make_user(db, email_prefix="attacker")
        graph = create_resume_graph(db, tmp_path, owner)

        with pytest.raises(HTTPException) as exc_info:
            delete_resume(graph["resume_id"], db, attacker)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "CV no encontrado"
        assert graph["file_path"].exists()
        assert db.get(Resume, graph["resume_id"]) is not None
    finally:
        db.rollback()
        db.close()


def test_delete_missing_resume_returns_safe_404() -> None:
    db = SessionLocal()
    try:
        user = make_user(db)

        with pytest.raises(HTTPException) as exc_info:
            delete_resume(999_999_999, db, user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "CV no encontrado"
    finally:
        db.rollback()
        db.close()


def test_delete_resume_continues_when_file_is_already_absent(tmp_path) -> None:
    db = SessionLocal()
    try:
        user = make_user(db)
        graph = create_resume_graph(db, tmp_path, user)
        graph["file_path"].unlink()

        delete_resume(graph["resume_id"], db, user)

        assert db.get(Resume, graph["resume_id"]) is None
        assert db.get(MatchResult, graph["match_result_id"]) is None
    finally:
        db.rollback()
        db.close()


def test_delete_resume_aborts_if_file_deletion_fails(tmp_path, monkeypatch) -> None:
    db = SessionLocal()
    try:
        user = make_user(db)
        graph = create_resume_graph(db, tmp_path, user)

        def fail_unlink(_path):
            raise OSError("permission denied: /private/path/cv.pdf")

        monkeypatch.setattr(Path, "unlink", fail_unlink)

        with pytest.raises(HTTPException) as exc_info:
            delete_resume(graph["resume_id"], db, user)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == DELETE_RESUME_ERROR
        assert "/private/path" not in exc_info.value.detail
        assert db.get(Resume, graph["resume_id"]) is not None
        assert db.get(MatchResult, graph["match_result_id"]) is not None
        interaction = db.get(UserJobInteraction, graph["interaction_id"])
        assert interaction.match_result_id == graph["match_result_id"]
    finally:
        db.rollback()
        db.close()
