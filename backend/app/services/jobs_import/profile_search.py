from app.models.profile import ProfessionalProfile


def build_job_search_terms(profile: ProfessionalProfile) -> list[str]:
    terms: list[str] = []

    if profile.profile_type:
        terms.append(profile.profile_type.replace(" Developer", "").lower())

    technologies = profile.technologies or []
    priority_terms = [
        "Java",
        "Spring Boot",
        "Python",
        "TypeScript",
        "Vue",
        "Angular",
        "Docker",
        "SQL",
        "Node.js",
    ]
    for term in priority_terms:
        if term in technologies:
            terms.append(term.lower())

    if not terms:
        terms.append("software developer")

    unique_terms: list[str] = []
    for term in terms:
        if term and term not in unique_terms:
            unique_terms.append(term)
    return unique_terms[:5]
