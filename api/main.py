"""FastAPI backend. ClickHouse is called at runtime on every request."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent import queries
from agent.config import GEMINI_ENABLED, GEMINI_MODEL, gemini_backend
from agent.graph import run_workflow_sync
from agent.schema import CrewQuery, SearchResult
from production.crew import build_crew
from production.planner import break_down, plan_production
from production.operations import ReplanRequest, propose_replan
from production.roles import derive_roles, infer_brief
from production.schema import CrewPlan, ProductionPlan, ProductionPlanRequest
from production.store import ProjectStore

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
PROJECTS = ProjectStore()

app = FastAPI(
    title="Reel Crew",
    description="Crew discovery over IMDb public datasets, ranked by ClickHouse.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class SearchRequest(BaseModel):
    brief: str = Field(..., min_length=3, max_length=1000)
    limit: int = Field(12, ge=1, le=100)
    # When the filter controls are used, the exact spec is sent instead of
    # re-parsing the prose, so hand edits are not overwritten by the parser.
    query: CrewQuery | None = None


@app.get("/api/health")
def health():
    try:
        from agent.mcp_clickhouse import run_query
        run_query("SELECT 1")
        ch = "connected via official mcp-clickhouse"
    except Exception as exc:  # noqa: BLE001
        ch = f"error: {exc}"
    return {
        "status": "ok",
        "clickhouse": ch,
        "gemini": "enabled" if GEMINI_ENABLED else "disabled (deterministic fallback active)",
        "gemini_backend": gemini_backend(),
        "gemini_model": GEMINI_MODEL if GEMINI_ENABLED else None,
        "project_storage": PROJECTS.backend,
    }


@app.get("/api/stats")
def stats():
    """Corpus size, shown in the UI as the anti-wrapper signal."""
    try:
        return queries.corpus_stats()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"ClickHouse unavailable: {exc}") from exc


@app.post("/api/search", response_model=SearchResult)
def search(req: SearchRequest):
    """Brief in -> parsed query, ranked candidates, package, narration, trace.

    Deliberately a plain `def`: the workflow blocks on Gemini and on the MCP
    server, so FastAPI runs it in a worker thread rather than on the event loop.
    """
    try:
        payload = req.query.model_dump() if req.query is not None else {}
        payload["_brief"] = req.brief
        payload["_limit"] = req.limit
        return run_workflow_sync(json.dumps(payload), limit=req.limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/production/plan", response_model=ProductionPlan)
def production_plan(req: ProductionPlanRequest):
    """Screenplay + constraints -> deterministic schedule, top sheet, and risks."""
    return plan_production(req)


@app.post("/api/production/replan")
def production_replan(req: ReplanRequest):
    """Create a before/after proposal without mutating the approved baseline."""
    return propose_replan(req)


class ProjectRecord(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    plan: dict = Field(default_factory=dict)
    shortlist: list[dict] = Field(default_factory=list)
    roster: list[dict] = Field(default_factory=list)
    finance: list[dict] = Field(default_factory=list)
    availability: list[dict] = Field(default_factory=list)
    approvals: list[dict] = Field(default_factory=list)
    operations: list[dict] = Field(default_factory=list)


@app.put("/api/projects/{project_id}")
def save_project(project_id: str, record: ProjectRecord):
    if not project_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid project id")
    return PROJECTS.save(project_id, record.model_dump())


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    record = PROJECTS.get(project_id)
    if not record:
        raise HTTPException(status_code=404, detail="Project not found")
    return {**record, "audit": PROJECTS.events(project_id)}


class CrewPlanRequest(BaseModel):
    title: str = Field("Untitled Production", min_length=1, max_length=120)
    screenplay: str = Field(..., min_length=20, max_length=100_000)
    genres: list[str] | None = None      # overrides the genres inferred from the script
    year_from: int = Field(2015, ge=1900, le=2030)
    min_rating: float = Field(6.0, ge=0, le=10)
    min_votes: int = Field(1000, ge=0, le=500_000)
    min_credits: int = Field(2, ge=1, le=40)
    per_role: int = Field(3, ge=1, le=10)


@app.post("/api/production/crew", response_model=CrewPlan)
def production_crew(req: CrewPlanRequest):
    """Screenplay -> required roles -> a ranked, credit-backed slate per role.

    Every candidate is a row from a ClickHouse result set; the match score is
    arithmetic over that row's own columns.
    """
    try:
        scenes = break_down(req.screenplay)
        brief = infer_brief(req.screenplay, scenes)
        if req.genres is not None:
            brief = brief.model_copy(update={"genres": req.genres, "source": "producer override"})
        return build_crew(
            title=req.title, brief=brief, roles=derive_roles(scenes),
            year_from=req.year_from, min_rating=req.min_rating, min_votes=req.min_votes,
            min_credits=req.min_credits, per_role=req.per_role)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/profile/{nconst}")
def profile(nconst: str):
    """Q3 -- full capability profile for one person."""
    if not nconst.startswith("nm"):
        raise HTTPException(status_code=400, detail="nconst must look like nm0000123")
    try:
        prof, ms1, sql1 = queries.get_profile(nconst)
        if not prof or not prof[0]["credits"]:
            raise HTTPException(status_code=404, detail="No credits for that person")
        timeline, ms2, _ = queries.get_timeline(nconst)
        collabs, ms3, sql3 = queries.get_collaborators(nconst, 10)
        p = prof[0]
        return {
            "nconst": nconst,
            "name": p["name"],
            "credits": p["credits"],
            "career_span": [p["first_year"], p["last_year"]],
            "avg_rating": p["avg_rating"],
            "reach": p["reach"],
            "roles": p["roles"],
            "genre_mix": [{"genre": g, "credits": c} for g, c in p["genre_mix"]],
            "timeline": [
                {"year": t["year"], "avg_rating": t["avg_rating"],
                 "credits": t["credits"], "titles": t["titles"]}
                for t in timeline
            ],
            "collaborators": collabs,
            "engine": {"profile_ms": int(ms1), "timeline_ms": int(ms2),
                       "collaborators_ms": int(ms3), "sql": [sql1, sql3]},
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/similar/{nconst}")
def similar(nconst: str, under_reference: bool = False, limit: int = 12):
    """Q4 -- people whose body of work points the same way as this person's.

    `under_reference=true` keeps only those with less audience reach than the
    reference, which is the practical version of the question a line producer
    actually asks: someone who works like this, that the production can book.
    """
    if not nconst.startswith("nm"):
        raise HTTPException(status_code=400, detail="nconst must look like nm0000123")
    try:
        rows, ms, sql = queries.find_similar(
            nconst, under_reference=under_reference, limit=max(1, min(limit, 50)))
        return {
            "nconst": nconst,
            "role": rows[0]["role"] if rows else None,
            "under_reference": under_reference,
            "candidates": rows,
            "engine": {"similar_ms": int(ms), "sql": sql},
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(WEB_DIR / "index.html")
