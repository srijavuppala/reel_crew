"""The deterministic ADK Workflow graph.

    START -> parse -> search -> collaborators -> narrate

Each node is an ordinary typed Python function, so the graph is deterministic:
the LLM influences node *inputs* (parsing) and node *output prose* (narration),
never the control flow and never the candidate set.
"""
from __future__ import annotations

import time
from typing import Optional

from pydantic import BaseModel, Field

from . import queries
from .narrate import narrate
from .parse import parse_brief
from .schema import Candidate, Collaborator, CrewQuery, SearchResult, TraceStep


class RunState(BaseModel):
    """Threaded through every node; each node returns an enriched copy."""
    brief: str
    limit: int = 12
    collaborator_limit: int = 8
    query: Optional[CrewQuery] = None
    candidates: list[Candidate] = Field(default_factory=list)
    package: list[Collaborator] = Field(default_factory=list)
    package_lead: Optional[str] = None
    narration: str = ""
    trace: list[TraceStep] = Field(default_factory=list)
    engine: dict = Field(default_factory=dict)


# ------------------------------------------------------------------ graph nodes
# ADK binds a parameter named exactly `node_input` to the upstream node's output
# (see FunctionNode._bind_parameters). Keeping that name is what makes these
# plain functions chain inside the Workflow runtime.
def node_parse(node_input: str) -> RunState:
    """Plain English -> CrewQuery (Gemini structured output, or rule-based).

    Entry node: takes the raw brief straight from START, so the ADK runtime
    binds the user message to it without any state plumbing.
    """
    t0 = time.perf_counter()
    state = RunState(brief=node_input)
    q, how = parse_brief(state.brief)
    state.query = q
    state.engine["parser"] = how
    state.trace.append(TraceStep(
        step="parse",
        detail=f"{how}: role={q.role}, genres={q.genres or 'any'}, "
               f"rating>={q.min_rating}, year>={q.year_from}, credits>={q.min_credits}",
        ms=int((time.perf_counter() - t0) * 1000),
    ))
    return state


def node_search(node_input: RunState) -> RunState:
    """Q1 -- ranked crew search. Parameterized SQL, never model-generated."""
    state = node_input
    q = state.query
    rows, ms, sql = queries.search_crew(
        role=q.role, genres=q.genres, min_rating=q.min_rating,
        year_from=q.year_from, min_credits=q.min_credits,
        min_votes=q.min_votes, limit=state.limit,
    )
    state.candidates = [Candidate(**r) for r in rows]
    state.trace.append(TraceStep(
        step="search", detail="ClickHouse Q1: ranked aggregation over crew_credits",
        ms=int(ms), rows=len(rows), sql=sql,
    ))
    return state


def node_collaborators(node_input: RunState) -> RunState:
    """Q2 -- who the top candidate actually works with. The 'hire a department' view."""
    state = node_input
    if not state.candidates:
        state.trace.append(TraceStep(step="collaborators", detail="skipped: no candidates", ms=0, rows=0))
        return state
    lead = state.candidates[0]
    rows, ms, sql = queries.get_collaborators(lead.nconst, state.collaborator_limit)
    state.package = [Collaborator(**r) for r in rows]
    state.package_lead = lead.name
    state.trace.append(TraceStep(
        step="collaborators", detail=f"ClickHouse Q2: self-join on shared titles for {lead.name}",
        ms=int(ms), rows=len(rows), sql=sql,
    ))
    return state


def node_narrate(node_input: RunState) -> RunState:
    """Gemini (or computed fallback) explains rows that SQL already returned."""
    state = node_input
    t0 = time.perf_counter()
    text, rationales, engine = narrate(state.query, state.candidates)
    state.narration = text
    for c in state.candidates:
        c.rationale = rationales.get(c.nconst, "")
    state.engine["narrator"] = engine
    state.trace.append(TraceStep(
        step="narrate", detail=f"{engine}: summarised {len(state.candidates)} retrieved rows",
        ms=int((time.perf_counter() - t0) * 1000), rows=len(state.candidates),
    ))
    return state


# ------------------------------------------------------------------- the graph
def build_workflow():
    """Construct the ADK Workflow. Imported lazily so the API works if ADK changes."""
    from google.adk import Workflow

    return Workflow(
        name="below_the_line",
        description="Producer brief -> ranked crew shortlist with collaboration package",
        edges=[
            ("START", node_parse),
            (node_parse, node_search),
            (node_search, node_collaborators),
            (node_collaborators, node_narrate),
        ],
    )


def _to_result(state: RunState) -> SearchResult:
    return SearchResult(
        query=state.query, candidates=state.candidates, package=state.package,
        package_lead=state.package_lead, narration=state.narration,
        trace=state.trace, engine=state.engine,
    )


def run_direct(brief: str, limit: int = 12) -> SearchResult:
    """Run the same four nodes in order without the ADK runtime (fallback path)."""
    state = node_parse(brief)
    state.limit = limit
    for node in (node_search, node_collaborators, node_narrate):
        state = node(state)
    state.engine["runtime"] = "direct"
    return _to_result(state)


async def run_workflow(brief: str, limit: int = 12) -> SearchResult:
    """Run through the ADK Workflow runtime; fall back to direct on any runtime error."""
    try:
        from google.adk.agents.context import Context  # noqa: F401
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        wf = build_workflow()
        runner = InMemoryRunner(node=wf, app_name="below_the_line")
        session = await runner.session_service.create_session(
            app_name="below_the_line", user_id="producer"
        )
        final_state = None
        async for event in runner.run_async(
            user_id="producer", session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=brief)]),
        ):
            out = getattr(event, "output", None)
            if isinstance(out, RunState):
                final_state = out
            elif isinstance(out, dict) and "brief" in out:
                final_state = RunState.model_validate(out)
        if final_state is not None and final_state.candidates:
            final_state.engine["runtime"] = "adk-workflow"
            return _to_result(final_state)
    except Exception as exc:  # noqa: BLE001
        print(f"[graph] ADK runtime path unavailable ({exc}); using direct node execution")
    res = run_direct(brief, limit)
    return res


if __name__ == "__main__":
    import sys

    brief = " ".join(sys.argv[1:]) or (
        "I need a DP who has shot three or more horror features "
        "rated above 6.5 in the last eight years"
    )
    r = run_direct(brief)
    print(f"\nBRIEF: {brief}")
    print(f"PARSED: {r.query.model_dump()}\n")
    print(f"NARRATION: {r.narration}\n")
    print(f"{'NAME':<26}{'MATCH':>6}{'RATING':>8}{'REACH':>12}   TITLES")
    for c in r.candidates:
        print(f"{c.name:<26}{c.genre_credits:>6}{c.avg_rating:>8}{c.reach:>12,}   {', '.join(c.sample_titles[:2])}")
    if r.package:
        print(f"\nPACKAGE around {r.package_lead}:")
        for p in r.package:
            print(f"  {p.name:<26}{'/'.join(p.roles):<28}{p.films_together} films together")
    print("\nTRACE:")
    for t in r.trace:
        print(f"  {t.step:<15}{t.ms:>5}ms  rows={t.rows}  {t.detail[:70]}")
