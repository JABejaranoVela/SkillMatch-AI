from app.services.nlp.skills import detect_skills


def skill_names(text: str) -> set[str]:
    return {skill["name"] for skill in detect_skills(text)}


def test_detects_curated_cloud_and_streaming_skills() -> None:
    names = skill_names("Experiencia con AWS, Apache Kafka, Spring Boot, PostgreSQL y Docker.")

    assert {"AWS", "Apache Kafka", "Spring Boot", "PostgreSQL", "Docker"} <= names


def test_normalizes_known_aliases() -> None:
    names = skill_names("Stack: postgres, k8s, fast api, scikit learn.")

    assert {"PostgreSQL", "Kubernetes", "FastAPI", "scikit-learn"} <= names


def test_detects_unlisted_technical_terms_with_low_confidence() -> None:
    skills = detect_skills("Tecnologias: Snowflake, Databricks, GraphQL, Firebase.")
    by_name = {skill["name"]: skill for skill in skills}

    assert {"Snowflake", "Databricks", "GraphQL", "Firebase"} <= set(by_name)
    assert by_name["Snowflake"]["source"] == "pattern"
    assert by_name["Snowflake"]["confidence"] < 1
