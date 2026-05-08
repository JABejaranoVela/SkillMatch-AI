import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.services.nlp.normalization import normalize_token


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
                detected[skill.name] = {
                    "name": skill.name,
                    "category": skill.category,
                    "matched_term": term,
                    "confidence": 1.0,
                }
                break

    return sorted(detected.values(), key=lambda item: item["name"])
