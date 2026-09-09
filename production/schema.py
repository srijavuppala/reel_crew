from __future__ import annotations

from pydantic import BaseModel, Field


class ProductionPlanRequest(BaseModel):
    title: str = Field("Untitled Production", min_length=1, max_length=120)
    screenplay: str = Field(..., min_length=20, max_length=100_000)
    total_budget: int = Field(..., ge=1_000, le=1_000_000_000)
    currency: str = Field("USD", min_length=3, max_length=3)
    target_shoot_days: int = Field(..., ge=1, le=365)
    revised_budget: int | None = Field(None, ge=1_000, le=1_000_000_000)
    revised_shoot_days: int | None = Field(None, ge=1, le=365)


class Scene(BaseModel):
    number: int
    heading: str
    interior_exterior: str
    location: str
    time_of_day: str
    estimated_pages: float
    requirements: list[str]


class ShootDay(BaseModel):
    day: int
    scene_numbers: list[int]
    location: str
    time_of_day: str
    estimated_pages: float
    warning: str | None = None


class BudgetLine(BaseModel):
    category: str
    percent: float
    amount: int
    basis: str


class Risk(BaseModel):
    severity: str
    area: str
    issue: str
    mitigation: str


class ChangeImpact(BaseModel):
    changed: bool
    budget_delta: int = 0
    shoot_day_delta: int = 0
    daily_cost_delta: int = 0
    actions: list[str] = Field(default_factory=list)


class ProductionPlan(BaseModel):
    title: str
    currency: str
    brief: "ProductionBrief | None" = None
    roles: list["RoleRequirement"] = Field(default_factory=list)
    summary: dict
    scenes: list[Scene]
    schedule: list[ShootDay]
    budget: list[BudgetLine]
    risks: list[Risk]
    assumptions: list[str]
    change_impact: ChangeImpact


class RoleRequirement(BaseModel):
    """One crew position the screenplay demands.

    `staffable` is the honest half: it is False for every department IMDb's
    principal-crew data does not cover, and those roles are still reported.
    """
    role: str
    category: str | None = None          # IMDb `category` when the corpus covers it
    department: str
    priority: str                        # core | recommended | required | attached
    reason: str
    scene_numbers: list[int] = Field(default_factory=list)
    in_corpus: bool = True     # IMDb's principal-crew data covers this craft
    staffable: bool            # ...and we will actually build a slate for it


class ProductionBrief(BaseModel):
    genres: list[str]
    tone: str
    scene_count: int
    location_count: int
    source: str


class ScoreComponent(BaseModel):
    label: str
    points: float
    max_points: float
    basis: str


class CrewCandidate(BaseModel):
    nconst: str
    name: str
    match_score: float
    components: list[ScoreComponent]
    credits: int
    genre_credits: int
    avg_rating: float
    reach: int
    most_recent: int
    sample_titles: list[str]
    evidence: str


class RoleFunnel(BaseModel):
    """The ClickHouse narrowing behind one role, stage by stage."""
    craft_people: int
    genre_people: int
    threshold_people: int
    shortlist_people: int
    scored_pool: int = 0                 # rows scored before the top N were taken
    shown: int
    sql: str
    ms: int


class RoleSlate(BaseModel):
    role: str
    category: str
    department: str
    priority: str
    reason: str
    candidates: list[CrewCandidate]
    funnel: RoleFunnel


class CrewPlan(BaseModel):
    title: str
    brief: ProductionBrief
    slates: list[RoleSlate]
    unstaffable: list[RoleRequirement]
    chemistry: list[dict] = Field(default_factory=list)
    engine: dict = Field(default_factory=dict)


ProductionPlan.model_rebuild()
