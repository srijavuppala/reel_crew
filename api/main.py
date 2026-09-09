"""FastAPI backend. ClickHouse is called at runtime on every request."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent import queries
from agent.config import GEMINI_ENABLED, GEMINI_MODEL
from agent.graph import run_workflow
from agent.schema import SearchResult

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(
    title="Below the Line",
    description="Crew discovery over IMDb public datasets, ranked by ClickHouse.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class SearchRequest(BaseModel):
    brief: str = Field(..., min_length=3, max_length=1000)
    limit: int = Field(12, ge=1, le=50)


@app.get("/api/health")
def health():
    try:
        queries.get_client().query("SELECT 1")
        ch = "connected"
    except Exception as exc:  # noqa: BLE001
        ch = f"error: {exc}"
    return {
        "status": "ok",
        "clickhouse": ch,
        "gemini": "enabled" if GEMINI_ENABLED else "disabled (deterministic fallback active)",
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
        return await run_workflow(req.brief, limit=req.limit)
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


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(WEB_DIR / "index.html")
