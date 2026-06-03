import re
from collections import defaultdict

from app.services.nlp.skills import detect_skills
from app.services.nlp.normalization import normalize_token

SECONDARY_PROFILE_MIN_SCORE = 30


PROFILE_RULES = [
    {
        "name": "Backend Developer",
        "skills": {
            "java": 12,
            "spring boot": 12,
            "spring security": 8,
            "python": 6,
            "fastapi": 8,
            "node.js": 7,
            "api rest": 10,
            "jwt": 6,
            "sql": 7,
            "postgresql": 8,
            "mysql": 7,
            "mongodb": 5,
            "redis": 5,
            "apache kafka": 8,
            "rabbitmq": 6,
            "microservicios": 10,
            "docker": 5,
            "aws": 6,
        },
        "text_signals": {
            "backend": 8,
            "api": 5,
            "microservicios": 8,
            "rest": 4,
            "endpoints": 4,
            "logica de negocio": 5,
        },
        "target_score": 70,
    },
    {
        "name": "Full Stack Developer",
        "skills": {
            "java": 8,
            "spring boot": 8,
            "python": 5,
            "fastapi": 6,
            "node.js": 7,
            "api rest": 7,
            "javascript": 8,
            "typescript": 9,
            "angular": 10,
            "vue": 8,
            "react": 9,
            "html": 5,
            "css": 5,
            "sql": 5,
            "mysql": 5,
            "postgresql": 5,
            "docker": 5,
        },
        "text_signals": {
            "full stack": 10,
            "full-stack": 10,
            "frontend": 5,
            "backend": 5,
            "aplicaciones web": 5,
            "dashboard web": 5,
        },
        "target_score": 64,
    },
    {
        "name": "AI Developer",
        "skills": {
            "python": 12,
            "machine learning": 12,
            "nlp": 10,
            "llm": 10,
            "embeddings": 8,
            "sentence-transformers": 8,
            "scikit-learn": 10,
            "pandas": 8,
            "numpy": 8,
            "tensorflow": 10,
            "pytorch": 10,
            "fastapi": 4,
            "api rest": 4,
        },
        "text_signals": {
            "inteligencia artificial": 10,
            "machine learning": 8,
            "modelo": 4,
            "nlp": 8,
            "embeddings": 8,
            "clasificacion": 4,
        },
        "target_score": 55,
    },
    {
        "name": "Data Engineer",
        "skills": {
            "python": 8,
            "sql": 10,
            "postgresql": 7,
            "apache kafka": 10,
            "spark": 10,
            "hadoop": 8,
            "airflow": 9,
            "etl": 9,
            "aws": 8,
            "docker": 5,
            "pandas": 5,
        },
        "text_signals": {
            "data engineer": 10,
            "etl": 8,
            "pipelines": 7,
            "big data": 8,
            "streaming": 6,
        },
        "target_score": 55,
    },
    {
        "name": "Frontend Developer",
        "skills": {
            "javascript": 10,
            "typescript": 10,
            "angular": 12,
            "vue": 10,
            "react": 12,
            "html": 8,
            "css": 8,
            "npm": 4,
        },
        "text_signals": {
            "frontend": 10,
            "interfaz": 5,
            "responsive": 5,
            "componentes": 5,
        },
        "target_score": 52,
    },
    {
        "name": "DevOps Junior",
        "skills": {
            "docker": 10,
            "kubernetes": 12,
            "aws": 10,
            "terraform": 10,
            "jenkins": 8,
            "github actions": 8,
            "ci/cd": 8,
            "linux": 7,
            "bash": 6,
            "nginx": 6,
        },
        "text_signals": {
            "devops": 10,
            "despliegue": 6,
            "contenedores": 6,
            "infraestructura": 5,
            "pipeline": 5,
        },
        "target_score": 52,
    },
]


def build_profile_from_text(clean_text: str) -> dict:
    skills = detect_skills(clean_text)
    languages = detect_languages(clean_text)
    experience_years = detect_experience_years(clean_text)
    technologies = [skill["name"] for skill in skills]
    profile_scores = infer_profile_scores(clean_text, skills)
    primary_profile = profile_scores[0]["name"] if profile_scores else "Perfil Tecnico General"
    secondary_profile = infer_secondary_profile(profile_scores)
    skill_categories = group_skills_by_category(skills)

    return {
        "profile_type": primary_profile,
        "summary": build_summary(primary_profile, secondary_profile, technologies, experience_years),
        "experience_years": experience_years,
        "education": {"raw": detect_education_snippets(clean_text)},
        "languages": languages,
        "technologies": technologies,
        "skills": skills,
        "analysis": {
            "primary_profile": profile_scores[0] if profile_scores else None,
            "secondary_profile": secondary_profile,
            "profile_scores": profile_scores,
            "skill_categories": skill_categories,
            "skill_sources": summarize_skill_sources(skills),
        },
    }


def infer_profile_scores(text: str, skills: list[dict]) -> list[dict]:
    normalized_text = normalize_token(text)
    normalized_skills = {skill["name"].lower(): skill for skill in skills}
    profile_scores: list[dict] = []

    for rule in PROFILE_RULES:
        matched_skills: list[str] = []
        matched_signals: list[str] = []
        score = 0
        target_score = rule["target_score"]

        for skill_name, weight in rule["skills"].items():
            if skill_name in normalized_skills:
                score += weight
                matched_skills.append(normalized_skills[skill_name]["name"])

        for signal, weight in rule["text_signals"].items():
            if normalize_token(signal) in normalized_text:
                score += weight
                matched_signals.append(signal)

        affinity = round(min((score / target_score) * 100, 100), 2) if target_score else 0.0
        profile_scores.append(
            {
                "name": rule["name"],
                "score": affinity,
                "raw_score": score,
                "matched_skills": sorted(set(matched_skills)),
                "matched_signals": sorted(set(matched_signals)),
            }
        )

    return sorted(profile_scores, key=lambda item: item["score"], reverse=True)


def infer_secondary_profile(profile_scores: list[dict]) -> dict | None:
    if len(profile_scores) < 2:
        return None
    secondary = profile_scores[1]
    if secondary["score"] < SECONDARY_PROFILE_MIN_SCORE:
        return None
    return secondary


def group_skills_by_category(skills: list[dict]) -> dict[str, list[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for skill in skills:
        grouped[skill["category"]].add(skill["name"])
    return {category: sorted(values) for category, values in sorted(grouped.items())}


def summarize_skill_sources(skills: list[dict]) -> dict:
    dictionary_count = sum(1 for skill in skills if skill.get("source", "dictionary") == "dictionary")
    pattern_count = sum(1 for skill in skills if skill.get("source") == "pattern")
    ner_count = sum(1 for skill in skills if skill.get("source") == "ner")
    return {
        "dictionary": dictionary_count,
        "ner": ner_count,
        "pattern": pattern_count,
        "total": len(skills),
    }


def build_summary(
    profile_type: str,
    secondary_profile: dict | None,
    technologies: list[str],
    experience_years: float | None,
) -> str:
    skills_text = ", ".join(technologies[:12]) if technologies else "sin skills tecnicas detectadas"
    experience_text = (
        f"{experience_years:g} años de experiencia detectados"
        if experience_years is not None
        else "experiencia no cuantificada"
    )
    secondary_text = (
        f" Perfil secundario: {secondary_profile['name']} ({secondary_profile['score']}%)."
        if secondary_profile
        else ""
    )
    return f"{profile_type}: {skills_text}. {experience_text}.{secondary_text}"


def detect_languages(text: str) -> list[str]:
    candidates = {
        "Español": ["espanol", "español", "castellano", "spanish", "espana", "españa"],
        "Inglés": ["ingles", "inglés", "english", "b2", "c1", "c2"],
        "Francés": ["frances", "francés", "french"],
        "Alemán": ["aleman", "alemán", "german"],
    }
    normalized_text = normalize_token(text)
    return [
        language
        for language, terms in candidates.items()
        if any(normalize_token(term) in normalized_text for term in terms)
    ]


def detect_experience_years(text: str) -> float | None:
    text_lower = normalize_token(text)
    year_matches = re.findall(r"(\d{1,2})\s*(?:anos|years)\s+de\s+experiencia", text_lower)
    month_matches = re.findall(r"(\d{1,2})\s*mes(?:es)?", text_lower)
    values = [float(match) for match in year_matches]
    values.extend(round(int(match) / 12, 2) for match in month_matches)
    if not values:
        return None
    return max(values)


def detect_education_snippets(text: str) -> list[str]:
    keywords = (
        "grado",
        "dam",
        "desarrollo de aplicaciones",
        "master",
        "fp",
        "formacion profesional",
        "universidad",
        "bootcamp",
    )
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    snippets: list[str] = []
    seen: set[str] = set()

    for index, line in enumerate(lines):
        normalized = normalize_token(line)
        if any(keyword in normalized for keyword in keywords):
            year = find_nearby_year(lines, index)
            value = f"{line} · {year}" if year else line
            normalized_value = normalize_token(value)
            if normalized_value not in seen:
                seen.add(normalized_value)
                snippets.append(value)
    return snippets[:10]


def find_nearby_year(lines: list[str], index: int) -> str | None:
    for line in lines[index : index + 4]:
        match = re.search(r"(20\d{2}\s*[–-]\s*20\d{2}|20\d{2})", line)
        if match:
            return match.group(1)
    return None
