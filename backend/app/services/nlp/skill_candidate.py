from app.services.nlp.normalization import normalize_token
from app.services.nlp.taxonomy import canonical_skill_name, infer_skill_category


def merge_skill_candidate(
    detected: dict[str, dict],
    *,
    raw_name: str,
    matched_term: str,
    confidence: float,
    source: str,
    category: str | None = None,
) -> None:
    name = raw_name.strip() if source == "dictionary" else canonical_skill_name(raw_name)
    normalized_name = normalize_token(name)
    resolved_category = category or infer_skill_category(name)

    existing_key = next(
        (key for key in detected if normalize_token(key) == normalized_name),
        None,
    )
    overlapping_key = next(
        (
            key
            for key in detected
            if source != "dictionary"
            and _is_overlapping_skill(normalized_name, normalize_token(key))
        ),
        None,
    )
    if overlapping_key is not None:
        return

    candidate = {
        "name": name,
        "category": resolved_category,
        "matched_term": matched_term,
        "confidence": confidence,
        "source": source,
    }

    if existing_key is None:
        detected[name] = candidate
        return

    existing = detected[existing_key]
    if confidence > existing.get("confidence", 0):
        detected.pop(existing_key)
        detected[name] = candidate


def _is_overlapping_skill(candidate: str, existing: str) -> bool:
    candidate_parts = set(candidate.split())
    existing_parts = set(existing.split())
    if not candidate_parts or not existing_parts:
        return False
    if candidate in existing or existing in candidate:
        return True
    return bool(candidate_parts & existing_parts)
