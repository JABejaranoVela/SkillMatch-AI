import re

from app.services.nlp.skills import detect_skills


def build_profile_from_text(clean_text: str) -> dict:
    skills = detect_skills(clean_text)
    languages = detect_languages(clean_text)
    experience_years = detect_experience_years(clean_text)
    technologies = [skill["name"] for skill in skills]
    profile_type = infer_profile_type(clean_text, technologies)

    return {
        "profile_type": profile_type,
        "summary": build_summary(profile_type, technologies, experience_years),
        "experience_years": experience_years,
        "education": {"raw": detect_education_snippets(clean_text)},
        "languages": languages,
        "technologies": technologies,
        "skills": skills,
    }


def infer_profile_type(text: str, technologies: list[str]) -> str:
    normalized_text = text.lower()
    normalized_skills = {skill.lower() for skill in technologies}

    profile_rules = [
        (
            "Full Stack Developer",
            {"java", "spring boot", "vue", "typescript", "mysql", "docker"},
            ("full stack", "full-stack", "backend", "frontend", "dashboard web"),
        ),
        (
            "Backend Developer",
            {"java", "spring boot", "python", "sql", "mysql", "api rest", "jwt"},
            ("api", "backend", "microservicios", "rest", "endpoints", "logica de negocio"),
        ),
        (
            "Frontend Developer",
            {"angular", "vue", "typescript", "html", "css"},
            ("frontend", "typescript", "html", "css", "scss"),
        ),
        (
            "Data Analyst",
            {"sql", "python", "machine learning"},
            ("analisis de datos", "data analyst", "power bi", "tableau", "pandas"),
        ),
        (
            "AI/ML Junior",
            {"python", "machine learning"},
            ("inteligencia artificial", "machine learning", "modelo", "nlp"),
        ),
    ]

    best_profile = "Perfil Tecnico General"
    best_score = 0
    for profile_name, skill_terms, text_terms in profile_rules:
        score = len(normalized_skills & skill_terms)
        score += sum(1 for term in text_terms if term in normalized_text)
        if score > best_score:
            best_profile = profile_name
            best_score = score

    return best_profile


def build_summary(profile_type: str, technologies: list[str], experience_years: float | None) -> str:
    skills_text = ", ".join(technologies[:12]) if technologies else "sin skills tecnicas detectadas"
    experience_text = (
        f"{experience_years:g} anos de experiencia detectados"
        if experience_years is not None
        else "experiencia no cuantificada"
    )
    return f"{profile_type}: {skills_text}. {experience_text}."


def detect_languages(text: str) -> list[str]:
    candidates = {
        "Espanol": ["espanol", "castellano", "spanish", "españa"],
        "Ingles": ["ingles", "english", "b2", "c1", "c2"],
        "Frances": ["frances", "french"],
        "Aleman": ["aleman", "german"],
    }
    text_lower = text.lower()
    return [language for language, terms in candidates.items() if any(term in text_lower for term in terms)]


def detect_experience_years(text: str) -> float | None:
    text_lower = text.lower()
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
    snippets: list[str] = []
    for line in text.splitlines():
        normalized = line.lower()
        if any(keyword in normalized for keyword in keywords):
            snippets.append(line.strip())
    return snippets[:10]
