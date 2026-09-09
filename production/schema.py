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
    summary: dict
    scenes: list[Scene]
    schedule: list[ShootDay]
    budget: list[BudgetLine]
    risks: list[Risk]
    assumptions: list[str]
    change_impact: ChangeImpact
