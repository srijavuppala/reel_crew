from __future__ import annotations

import math
import re
from collections import defaultdict

from .roles import derive_roles, infer_brief
from .schema import (
    BudgetLine, ChangeImpact, ProductionPlan, ProductionPlanRequest, Risk, Scene, ShootDay,
)

HEADING = re.compile(r"(?im)^\s*((?:INT\.?|EXT\.?|INT\.?/EXT\.?|I/E)\s+[^\n]+)$")
BUDGET_SHARES = [
    ("Cast", 0.12, "performer fees and casting allowance"),
    ("Crew", 0.27, "production crew labor allowance"),
    ("Locations", 0.08, "permits, fees, holding and site costs"),
    ("Camera, grip and electric", 0.10, "equipment rental allowance"),
    ("Art, wardrobe, hair and makeup", 0.10, "physical production materials"),
    ("Travel, transport and catering", 0.08, "company movement and daily support"),
    ("Post-production", 0.11, "edit, sound, music, color and delivery"),
    ("Insurance, legal and administration", 0.06, "production overhead allowance"),
    ("Contingency", 0.08, "unallocated risk reserve"),
]


def _scene_parts(heading: str) -> tuple[str, str, str]:
    clean = re.sub(r"\s+", " ", heading.strip().upper())
    ie = "INT/EXT" if clean.startswith(("INT/EXT", "I/E")) else ("EXT" if clean.startswith("EXT") else "INT")
    rest = re.sub(r"^(?:INT\.?/EXT\.?|INT\.?|EXT\.?|I/E)\s+", "", clean)
    chunks = [x.strip() for x in re.split(r"\s+-\s+", rest)]
    tod = chunks[-1] if chunks and chunks[-1] in {"DAY", "NIGHT", "DAWN", "DUSK", "CONTINUOUS", "LATER"} else "UNSPECIFIED"
    location = " - ".join(chunks[:-1]) if tod != "UNSPECIFIED" else rest
    return ie, location or "UNSPECIFIED", tod


def _requirements(body: str, ie: str, tod: str) -> list[str]:
    text = body.lower()
    req = []
    signals = [
        ("vehicle", ("car", "truck", "vehicle", "drives")),
        ("stunts/safety", ("fight", "falls", "weapon", "gun", "fire", "explosion")),
        ("animals", ("dog", "cat", "horse", "animal")),
        ("special effects", ("rain", "smoke", "blood", "fire", "explosion")),
        ("music/playback", ("song", "music", "dances", "band")),
        ("crowd/background", ("crowd", "customers", "students", "passengers")),
    ]
    for label, words in signals:
        if any(re.search(rf"\b{re.escape(w)}\b", text) for w in words):
            req.append(label)
    if ie != "INT":
        req.append("weather cover")
    if tod in {"NIGHT", "DAWN", "DUSK"}:
        req.append("night lighting")
    return req


def break_down(screenplay: str) -> list[Scene]:
    matches = list(HEADING.finditer(screenplay))
    if not matches:
        matches = [re.match(r".*", "INT. UNSPECIFIED LOCATION - DAY")]
        bodies = [screenplay]
    else:
        bodies = [screenplay[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(screenplay)] for i, m in enumerate(matches)]
    scenes = []
    for i, (match, body) in enumerate(zip(matches, bodies), 1):
        heading = match.group(1) if match.lastindex else "INT. UNSPECIFIED LOCATION - DAY"
        ie, location, tod = _scene_parts(heading)
        pages = max(0.125, round(len(body.strip()) / 1800 * 8) / 8)
        scenes.append(Scene(number=i, heading=heading.strip(), interior_exterior=ie,
                            location=location, time_of_day=tod, estimated_pages=pages,
                            requirements=_requirements(body, ie, tod)))
    return scenes


def build_schedule(scenes: list[Scene], target_days: int) -> list[ShootDay]:
    groups: dict[tuple[str, str], list[Scene]] = defaultdict(list)
    for scene in scenes:
        groups[(scene.location, scene.time_of_day)].append(scene)
    ordered = sorted(groups.items(), key=lambda x: (-sum(s.estimated_pages for s in x[1]), x[0]))
    buckets: list[list[Scene]] = [[] for _ in range(min(target_days, max(1, len(scenes))))]
    loads = [0.0] * len(buckets)
    for _, group in ordered:
        idx = min(range(len(buckets)), key=lambda n: loads[n])
        buckets[idx].extend(group)
        loads[idx] += sum(s.estimated_pages for s in group)
    result = []
    for day, bucket in enumerate(buckets, 1):
        if not bucket:
            continue
        pages = round(sum(s.estimated_pages for s in bucket), 3)
        locations = list(dict.fromkeys(s.location for s in bucket))
        warning = "Heavy page count—review overtime or split the day." if pages > 8 else None
        if len(locations) > 1:
            warning = "Company move required; confirm travel and reset time." if not warning else warning + " Company move required."
        result.append(ShootDay(day=day, scene_numbers=[s.number for s in bucket],
                               location=" / ".join(locations),
                               time_of_day=" / ".join(dict.fromkeys(s.time_of_day for s in bucket)),
                               estimated_pages=pages, warning=warning))
    return result


def build_budget(total: int) -> list[BudgetLine]:
    lines, allocated = [], 0
    for i, (category, share, basis) in enumerate(BUDGET_SHARES):
        amount = total - allocated if i == len(BUDGET_SHARES) - 1 else round(total * share)
        allocated += amount
        lines.append(BudgetLine(category=category, percent=round(amount / total * 100, 2), amount=amount, basis=basis))
    return lines


def assess_risks(scenes: list[Scene], schedule: list[ShootDay], budget: int, days: int) -> list[Risk]:
    risks = []
    exteriors = sum(s.interior_exterior != "INT" for s in scenes)
    night = sum(s.time_of_day in {"NIGHT", "DAWN", "DUSK"} for s in scenes)
    stunts = sum("stunts/safety" in s.requirements for s in scenes)
    if exteriors:
        risks.append(Risk(severity="medium", area="locations", issue=f"{exteriors} exterior scene(s) depend on weather and permits.", mitigation="Hold weather cover and confirm permit lead times."))
    if night:
        risks.append(Risk(severity="high", area="schedule", issue=f"{night} night/twilight scene(s) may compress workable hours.", mitigation="Group night work and verify turnaround before approval."))
    if stunts:
        risks.append(Risk(severity="high", area="safety", issue=f"{stunts} scene(s) contain possible stunt or weapon signals.", mitigation="Require qualified coordination, rehearsal, insurance and written safety review."))
    if any(d.warning for d in schedule):
        risks.append(Risk(severity="medium", area="schedule", issue="At least one draft shoot day has a load or company-move warning.", mitigation="AD/UPM must review the stripboard before baseline approval."))
    if budget / days < 10_000:
        risks.append(Risk(severity="medium", area="finance", issue="Budget per shoot day is constrained for a full production footprint.", mitigation="Reduce scope, confirm donated resources, or increase contingency before commitments."))
    return risks


def plan_production(req: ProductionPlanRequest) -> ProductionPlan:
    scenes = break_down(req.screenplay)
    schedule = build_schedule(scenes, req.target_shoot_days)
    budget = build_budget(req.total_budget)
    new_budget = req.revised_budget or req.total_budget
    new_days = req.revised_shoot_days or req.target_shoot_days
    budget_delta = new_budget - req.total_budget
    day_delta = new_days - req.target_shoot_days
    old_daily = round(req.total_budget / req.target_shoot_days)
    new_daily = round(new_budget / new_days)
    actions = []
    if budget_delta < 0:
        actions += ["Rebaseline every department allowance before commitments.", "Protect insurance and contingency; reduce creative scope explicitly."]
    if day_delta < 0:
        actions += ["Rebuild the stripboard and flag page loads above eight pages.", "Reprice overtime, company moves, and equipment weeks."]
    change = ChangeImpact(changed=bool(budget_delta or day_delta), budget_delta=budget_delta,
                          shoot_day_delta=day_delta, daily_cost_delta=new_daily - old_daily,
                          actions=actions)
    return ProductionPlan(
        title=req.title, currency=req.currency.upper(), scenes=scenes, schedule=schedule,
        brief=infer_brief(req.screenplay, scenes), roles=derive_roles(scenes),
        budget=budget, risks=assess_risks(scenes, schedule, req.total_budget, req.target_shoot_days),
        assumptions=[
            "Budget lines are planning allowances, not bids, commitments, actuals, or payment instructions.",
            "One screenplay page is approximated from 1,800 characters until a formatted PDF parser is added.",
            "The schedule groups locations and time-of-day, but has no cast availability or turnaround data yet.",
            "Every schedule, staffing, safety, contract, and finance decision requires human approval.",
        ],
        summary={"scene_count": len(scenes), "estimated_pages": round(sum(s.estimated_pages for s in scenes), 3),
                 "planned_shoot_days": len(schedule), "target_shoot_days": req.target_shoot_days,
                 "total_budget": req.total_budget, "budget_per_shoot_day": old_daily,
                 "location_count": len({s.location for s in scenes}),
                 "exterior_scenes": sum(s.interior_exterior != "INT" for s in scenes),
                 "night_scenes": sum(s.time_of_day in {"NIGHT", "DAWN", "DUSK"} for s in scenes)},
        change_impact=change,
    )
