import re
from functools import lru_cache

from app.core.config import settings
from app.services.nlp.normalization import normalize_token
from app.services.nlp.skill_candidate import merge_skill_candidate
from app.services.nlp.taxonomy import infer_skill_category

NER_LABELS = [
    "programming language",
    "framework",
    "library",
    "database",
    "cloud platform",
    "devops tool",
    "data engineering tool",
    "artificial intelligence skill",
    "software tool",
]

NER_CATEGORY_HINTS = {
    "programming language": "programming_language",
    "framework": "backend",
    "library": "tools",
    "database": "database",
    "cloud platform": "cloud",
    "devops tool": "devops",
    "data engineering tool": "data_engineering",
    "artificial intelligence skill": "ai",
    "software tool": "tools",
}

NER_FALSE_POSITIVES = {
    "antonio",
    "bejarano",
    "cv",
    "dam",
    "data",
    "davante",
    "developer",
    "desarrollador",
    "desarrolladora",
    "email",
    "full-stack",
    "grupo",
    "jose",
    "junior",
    "madrid",
    "medac",
    "perfil",
    "science",
    "senior",
    "telefono",
    "vela",
}

TECHNICAL_CONTEXT_TERMS = (
    "aptitudes",
    "competencias",
    "conocimientos",
    "framework",
    "herramientas",
    "skills",
    "stack",
    "tecnologias",
    "tecnologías",
    "tools",
)


@lru_cache(maxsize=1)
def _load_gliner_model():
    if not settings.SKILL_NER_ENABLED:
        return None

    try:
        from gliner import GLiNER  # type: ignore
    except ImportError:
        return None

    try:
        return GLiNER.from_pretrained(settings.SKILL_NER_MODEL_NAME)
    except Exception:
        return None


def detect_skills_with_ner(text: str, detected: dict[str, dict]) -> list[dict]:
    model = _load_gliner_model()
    if model is None:
        return []

    candidates: dict[str, dict] = {}
    existing_terms = {normalize_token(skill["name"]) for skill in detected.values()}

    for chunk in _chunk_text(text):
        try:
            entities = model.predict_entities(chunk, NER_LABELS, threshold=0.42)
        except Exception:
            continue

        for entity in entities:
            raw_text = str(entity.get("text", "")).strip()
            if not _should_keep_ner_candidate(text, raw_text, existing_terms):
                continue
            label = str(entity.get("label", "software tool"))
            score = float(entity.get("score", 0.72))
            merge_skill_candidate(
                candidates,
                raw_name=raw_text,
                matched_term=raw_text,
                confidence=max(0.72, min(score, 0.92)),
                source="ner",
                category=NER_CATEGORY_HINTS.get(label),
            )

    return sorted(candidates.values(), key=lambda item: item["name"])


def _should_keep_ner_candidate(text: str, raw_text: str, existing_terms: set[str]) -> bool:
    normalized = normalize_token(raw_text)
    if not raw_text or normalized in existing_terms or normalized in NER_FALSE_POSITIVES:
        return False
    if len(normalized) < 2 or len(normalized) > 40:
        return False
    if normalized.isdigit():
        return False
    if _has_technical_shape(raw_text):
        return True
    if infer_skill_category(raw_text) != "detected_technical_term":
        return True
    return _appears_in_technical_line(text, raw_text)


def _has_technical_shape(raw_text: str) -> bool:
    return (
        bool(re.search(r"[0-9.+#/-]", raw_text))
        or raw_text.isupper()
        or any(char.isupper() for char in raw_text[1:])
    )


def _appears_in_technical_line(text: str, raw_text: str) -> bool:
    normalized_target = normalize_token(raw_text)
    for line in text.splitlines():
        normalized_line = normalize_token(line)
        if normalized_target in normalized_line and any(
            term in normalized_line for term in TECHNICAL_CONTEXT_TERMS
        ):
            return True
    return False


def _chunk_text(text: str, max_chars: int = 1800) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in text.splitlines() if paragraph.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 > max_chars:
            if current:
                chunks.append(current)
            current = paragraph[:max_chars]
        else:
            current = f"{current}\n{paragraph}".strip()

    if current:
        chunks.append(current)

    return chunks or [text[:max_chars]]
