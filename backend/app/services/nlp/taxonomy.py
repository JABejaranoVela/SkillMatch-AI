import json
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.services.nlp.normalization import normalize_token


DEFAULT_TAXONOMY_PATH = "data/skills/skill_taxonomy.es.json"


@lru_cache(maxsize=1)
def load_skill_taxonomy() -> dict:
    path = Path(DEFAULT_TAXONOMY_PATH)
    if not path.is_absolute():
        candidates = [
            Path.cwd() / path,
            Path.cwd().parent / path,
            Path(settings.SKILLS_DICTIONARY_PATH).parent / path.name,
        ]
        path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def canonical_skill_name(raw_name: str) -> str:
    taxonomy = load_skill_taxonomy()
    normalized = normalize_token(raw_name)
    aliases = taxonomy.get("canonical_aliases", {})
    return aliases.get(normalized, _format_skill_name(raw_name))


def infer_skill_category(skill_name: str, fallback: str = "detected_technical_term") -> str:
    taxonomy = load_skill_taxonomy()
    normalized = normalize_token(skill_name)

    for category, config in taxonomy.get("categories", {}).items():
        for keyword in config.get("keywords", []):
            if normalize_token(keyword) in normalized:
                return category

    return fallback


def _format_skill_name(raw_name: str) -> str:
    value = raw_name.strip().strip(".,;:()[]{}")
    known_upper = {"api", "aws", "ci/cd", "csv", "etl", "gcp", "html", "ia", "json", "llm", "ml", "nlp", "sql", "xml"}
    if value.lower() in known_upper:
        return value.upper()
    if value.isupper():
        return value
    if any(separator in value for separator in (".", "-", "/", "#")):
        return value
    return " ".join(part.capitalize() for part in value.split())
