from typing import Literal

from pydantic import BaseModel


class PublicDemoAnalysisRead(BaseModel):
    profile_type: str
    summary: str
    skills: list[str]
    languages: list[str]
    education: list[str]
    experience_summary: str | None = None
    is_demo: Literal[True] = True
