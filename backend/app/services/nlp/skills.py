import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.services.nlp.ner_extractor import detect_skills_with_ner
from app.services.nlp.normalization import normalize_token
from app.services.nlp.skill_candidate import merge_skill_candidate
from app.services.nlp.taxonomy import infer_skill_category

TECH_CONTEXT_TERMS = (
    "aptitudes",
    "competencias",
    "conocimientos",
    "framework",
    "herramientas",
    "skills",
    "stack",
    "tecnologias",
    "tecnologias",
    "tools",
)

COMMON_FALSE_POSITIVES = {
    "about",
    "antonio",
    "bejarano",
    "cuento",
    "cv",
    "dam",
    "dashboard",
    "data",
    "davante",
    "developer",
    "desarrollador",
    "desarrolladora",
    "email",
    "email",
    "eso",
    "fp",
    "full-stack",
    "grupo",
    "jose",
    "junior",
    "linkedin",
    "madrid",
    "medac",
    "perfil",
    "science",
    "senior",
    "stack",
    "telefono",
    "tecnologia",
    "tecnologias",
    "vela",
}


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    category: str
    aliases: tuple[str, ...]

    @property
    def terms(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


@lru_cache(maxsize=1)
def load_skill_dictionary() -> tuple[SkillDefinition, ...]:
    path = Path(settings.SKILLS_DICTIONARY_PATH)
    if not path.is_absolute():
        candidates = [
            Path.cwd() / path,
            Path.cwd().parent / path,
        ]
        path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])

    with path.open(encoding="utf-8") as file:
        raw_skills = json.load(file)

    return tuple(
        SkillDefinition(
            name=item["name"],
            category=item["category"],
            aliases=tuple(item.get("aliases", [])),
        )
        for item in raw_skills
    )


def detect_skills(text: str) -> list[dict]:
    normalized_text = normalize_token(text)
    detected: dict[str, dict] = {}

    for skill in load_skill_dictionary():
        for term in skill.terms:
            normalized_term = normalize_token(term)
            pattern = rf"(?<!\w){re.escape(normalized_term)}(?!\w)"
            if re.search(pattern, normalized_text):
                merge_skill_candidate(
                    detected,
                    raw_name=skill.name,
                    matched_term=term,
                    confidence=1.0,
                    source="dictionary",
                    category=skill.category,
                )
                break

    for candidate in detect_unlisted_technical_terms(text, detected):
        merge_skill_candidate(
            detected,
            raw_name=candidate["name"],
            matched_term=candidate["matched_term"],
            confidence=candidate["confidence"],
            source=candidate["source"],
            category=candidate["category"],
        )

    for candidate in detect_skills_with_ner(text, detected):
        merge_skill_candidate(
            detected,
            raw_name=candidate["name"],
            matched_term=candidate["matched_term"],
            confidence=candidate["confidence"],
            source=candidate["source"],
            category=candidate["category"],
        )

    return sorted(detected.values(), key=lambda item: item["name"])


def detect_unlisted_technical_terms(text: str, detected: dict[str, dict]) -> list[dict]:
    """Find obvious technical terms not present in the curated dictionary.

    This is intentionally conservative. Dictionary matches keep confidence 1.0;
    pattern-based terms are lower confidence and should be reviewed over time.
    """

    normalized_detected = {normalize_token(name) for name in detected}
    candidates: dict[str, dict] = {}
    likely_lines = [
        line
        for line in text.splitlines()
        if any(term in normalize_token(line) for term in TECH_CONTEXT_TERMS)
    ]

    for line in likely_lines:
        for raw_term in re.findall(r"\b[A-Z0-9][A-Za-z0-9.+#/-]{1,24}\b", line):
            normalized_term = normalize_token(raw_term)
            if _should_keep_unlisted_term(raw_term, normalized_term, normalized_detected):
                name = _format_unlisted_term(raw_term)
                candidates[name] = {
                    "name": name,
                    "category": infer_skill_category(name),
                    "matched_term": raw_term,
                    "confidence": 0.55,
                    "source": "pattern",
                }

    return sorted(candidates.values(), key=lambda item: item["name"])


def _should_keep_unlisted_term(raw_term: str, term: str, detected_terms: set[str]) -> bool:
    if term in detected_terms or term in COMMON_FALSE_POSITIVES:
        return False
    if any(term in detected_term.split() for detected_term in detected_terms):
        return False
    if len(term) < 2 or len(term) > 24:
        return False
    if term.isdigit():
        return False
    if re.fullmatch(r"[a-z]+", term) and len(term) < 4:
        return False
    return (
        bool(re.search(r"[a-z]", term) and re.search(r"[0-9.+#/-]", term))
        or raw_term.isupper()
        or raw_term[:1].isupper()
    )


def _format_unlisted_term(raw_term: str) -> str:
    known_upper = {"aws", "gcp", "api", "etl", "sql", "nosql", "llm", "nlp", "ci/cd"}
    normalized = raw_term.strip().strip(".,;:")
    if normalized.lower() in known_upper:
        return normalized.upper()
    return normalized
