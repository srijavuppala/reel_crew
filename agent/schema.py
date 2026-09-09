"""Typed contracts passed between workflow nodes."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ROLES = [
    "cinematographer", "editor", "composer", "production_designer",
    "casting_director", "director", "writer", "producer",
]

RoleT = Literal[
    "cinematographer", "editor", "composer", "production_designer",
    "casting_director", "director", "writer", "producer",
]


class CrewQuery(BaseModel):
    """The structured search extracted from a producer's plain-English brief."""
    role: RoleT = Field(default="cinematographer", description="Crew role to staff")
    genres: list[str] = Field(default_factory=list, description="Genres, IMDb-cased e.g. Horror")
    min_rating: float = Field(default=6.0, ge=0, le=10)
    year_from: int = Field(default=2015, ge=1900, le=2030)
    min_credits: int = Field(default=2, ge=1, description="Min matching genre credits")
    min_votes: int = Field(default=1000, ge=0, description="Per-title vote floor: filters amateur output")
    keywords: list[str] = Field(default_factory=list)


class Candidate(BaseModel):
    nconst: str
    name: str
    credits: int
    genre_credits: int
    avg_rating: float
    reach: int
    most_recent: int
    sample_titles: list[str]
    rationale: str = ""


class Collaborator(BaseModel):
    nconst: str
    name: str
    roles: list[str]
    films_together: int
    shared_titles: list[str]


class TraceStep(BaseModel):
    step: str
    detail: str
    ms: int
    rows: Optional[int] = None
    sql: Optional[str] = None


class SearchResult(BaseModel):
    query: CrewQuery
    candidates: list[Candidate]
    package: list[Collaborator] = Field(default_factory=list)
    package_lead: Optional[str] = None
    narration: str = ""
    trace: list[TraceStep] = Field(default_factory=list)
    engine: dict[str, Any] = Field(default_factory=dict)
