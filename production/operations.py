from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from .planner import plan_production
from .schema import ProductionPlan, ProductionPlanRequest


class ConstraintChange(BaseModel):
    kind: Literal["budget", "shoot_days", "crew_unavailable"]
    value: str
    reason: str = Field(..., min_length=3, max_length=500)


class ReplanRequest(BaseModel):
    baseline: ProductionPlanRequest
    change: ConstraintChange


class ReplanProposal(BaseModel):
    proposal_id: str
    status: Literal["proposed", "approved", "rejected"] = "proposed"
    created_at: str
    change: ConstraintChange
    before: ProductionPlan
    after: ProductionPlan
    impacts: list[str]
    approval_required: bool = True


def propose_replan(req: ReplanRequest) -> ReplanProposal:
    before_req = req.baseline.model_copy(update={"revised_budget": None, "revised_shoot_days": None})
    before = plan_production(before_req)
    updates: dict = {}
    impacts: list[str] = []
    if req.change.kind == "budget":
        value = int(req.change.value)
        updates["total_budget"] = value
        impacts.append(f"Budget changes from {before_req.total_budget:,} to {value:,} {before_req.currency}.")
    elif req.change.kind == "shoot_days":
        value = int(req.change.value)
        updates["target_shoot_days"] = value
        impacts.append(f"Shoot target changes from {before_req.target_shoot_days} to {value} days.")
    else:
        impacts.append(f"{req.change.value} is unavailable; their assignment must be reviewed before call sheets are approved.")
    after_req = before_req.model_copy(update=updates)
    after = plan_production(after_req)
    impacts.extend([
        f"Daily allowance changes by {after.summary['budget_per_shoot_day'] - before.summary['budget_per_shoot_day']:,} {before.currency}.",
        f"The revised draft has {len(after.risks)} risk signal(s); the baseline has {len(before.risks)}.",
        "No baseline, booking, payment, or call sheet changes until a producer approves this proposal.",
    ])
    stamp = datetime.now(timezone.utc)
    return ReplanProposal(
        proposal_id=f"rp-{stamp.strftime('%Y%m%d%H%M%S%f')}", created_at=stamp.isoformat(),
        change=req.change, before=before, after=after, impacts=impacts,
    )

