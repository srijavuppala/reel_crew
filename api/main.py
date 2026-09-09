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
from agent.graph import run_workflow
from agent.schema import CrewQuery, SearchResult
from production.planner import plan_production
from production.schema import ProductionPlan, ProductionPlanRequest

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

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
    }


@app.get("/api/stats")
def stats():
    """Corpus size, shown in the UI as the anti-wrapper signal."""
    try:
        return queries.corpus_stats()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"ClickHouse unavailable: {exc}") from exc


@app.post("/api/search", response_model=SearchResult)
async def search(req: SearchRequest):
    """Brief in -> parsed query, ranked candidates, package, narration, trace."""
    try:
        payload = req.query.model_dump() if req.query is not None else {}
        payload["_brief"] = req.brief
        payload["_limit"] = req.limit
        return await run_workflow(json.dumps(payload), limit=req.limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/production/plan", response_model=ProductionPlan)
def production_plan(req: ProductionPlanRequest):
    """Screenplay + constraints -> deterministic schedule, top sheet, and risks."""
    return plan_production(req)


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
