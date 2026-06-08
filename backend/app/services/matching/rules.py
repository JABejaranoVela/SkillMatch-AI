from app.models.job import Job
from app.models.profile import ProfessionalProfile
from app.services.embeddings.semantic import cosine_similarity
from app.services.nlp.skills import detect_skills


RULES_WEIGHT = 0.65
SEMANTIC_WEIGHT = 0.35


def calculate_rules_match(profile: ProfessionalProfile, job: Job) -> dict:
    profile_skills = {skill.lower() for skill in (profile.technologies or [])}
    job_text = " ".join(part for part in [job.title, job.description, job.requirements or ""] if part)
    job_skills = {skill["name"].lower() for skill in detect_skills(job_text)}

    matching_skills = sorted(profile_skills & job_skills)
    missing_skills = sorted(job_skills - profile_skills)

    skills_score = len(matching_skills) / len(job_skills) if job_skills else 0.0
    final_score = round(skills_score * 100, 2)

    return {
        "rules_score": final_score,
        "semantic_score": 0.0,
        "final_score": final_score,
        "explanation": {
            "matching_skills": matching_skills,
            "missing_skills": missing_skills,
            "positive_signals": [
                f"Coinciden {len(matching_skills)} skills detectadas"
            ],
            "penalties": [
                f"Faltan {len(missing_skills)} skills requeridas"
            ] if missing_skills else [],
        },
    }


def calculate_hybrid_match(profile: ProfessionalProfile, job: Job) -> dict:
    rules_result = calculate_rules_match(profile, job)
    semantic_score = float(round(cosine_similarity(profile.embedding, job.embedding) * 100, 2))
    final_score = float(round(
        (rules_result["rules_score"] * RULES_WEIGHT) + (semantic_score * SEMANTIC_WEIGHT),
        2,
    ))

    explanation = rules_result["explanation"]
    explanation["score_breakdown"] = {
        "rules_weight": RULES_WEIGHT,
        "semantic_weight": SEMANTIC_WEIGHT,
        "rules_score": float(rules_result["rules_score"]),
        "semantic_score": semantic_score,
    }
    explanation["positive_signals"].append(
        f"Similitud semántica CV-oferta: {semantic_score}%"
    )
    explanation["positive_signals"].append(
        "Score final = 65% skills detectadas + 35% similitud semántica"
    )

    return {
        "rules_score": rules_result["rules_score"],
        "semantic_score": semantic_score,
        "final_score": final_score,
        "explanation": explanation,
    }
