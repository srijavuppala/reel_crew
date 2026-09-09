"""Narration over rows ClickHouse already returned.

The model is given the result set and told to explain it. It is never asked
to recall or invent a person, so no candidate can appear that SQL did not rank.
"""
from __future__ import annotations

import json

from .config import GEMINI_ENABLED, GEMINI_MODEL, get_genai_client
from .schema import Candidate, CrewQuery

NARRATE_INSTRUCTION = """You are a crew-staffing analyst briefing a line producer.
You will receive a search spec and a ranked candidate list retrieved from a credits database.
Rules:
- Use ONLY the people and titles present in the supplied rows. Never add a name.
- Never invent a credit, award, rate, or availability.
- Write 2-3 sentences summarising the shortlist, then one short rationale per candidate
  citing their actual numbers (matching credits, average rating, notable titles).
Return ONLY JSON: {"narration": str, "rationales": {"<nconst>": str}}"""


def _fallback_narration(q: CrewQuery, cands: list[Candidate]) -> tuple[str, dict[str, str]]:
    """Deterministic prose built from the returned numbers."""
    if not cands:
        return ("No crew matched that brief. Loosen the rating floor, widen the year "
                "range, or lower the minimum credit count."), {}
    genre = "/".join(q.genres) if q.genres else "all"
    role = q.role.replace("_", " ")
    top = cands[0]
    narration = (
        f"{len(cands)} {role}s match a {genre} brief with at least {q.min_credits} "
        f"qualifying credit(s) since {q.year_from} at IMDb {q.min_rating}+. "
        f"{top.name} leads on evidence with {top.genre_credits} matching credit(s) "
        f"averaging {top.avg_rating}, including {', '.join(top.sample_titles[:2])}. "
        f"Every candidate below is ranked from real credit history, not model recall."
    )
    rationales = {
        c.nconst: (
            f"{c.genre_credits} matching credit(s) of {c.credits} total since {q.year_from}, "
            f"averaging {c.avg_rating} across {c.reach:,} votes. "
            f"Most recent: {c.most_recent}. Notable: {', '.join(c.sample_titles[:3])}."
        )
        for c in cands
    }
    return narration, rationales


def narrate(q: CrewQuery, cands: list[Candidate]) -> tuple[str, dict[str, str], str]:
    """Return (narration, rationales_by_nconst, engine_used)."""
    if GEMINI_ENABLED and cands:
        try:
            from google.genai import types

            payload = {
                "spec": q.model_dump(),
                "candidates": [
                    {"nconst": c.nconst, "name": c.name, "matching_credits": c.genre_credits,
                     "total_credits": c.credits, "avg_rating": c.avg_rating,
                     "votes": c.reach, "most_recent": c.most_recent,
                     "titles": c.sample_titles}
                    for c in cands
                ],
            }
            client = get_genai_client()
            resp = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=json.dumps(payload),
                config=types.GenerateContentConfig(
                    system_instruction=NARRATE_INSTRUCTION,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            data = json.loads(resp.text)
            valid = {c.nconst for c in cands}
            rats = {k: v for k, v in (data.get("rationales") or {}).items() if k in valid}
            return data.get("narration", ""), rats, "gemini"
        except Exception as exc:  # noqa: BLE001
            print(f"[narrate] Gemini unavailable, using computed narration: {exc}")
    n, r = _fallback_narration(q, cands)
    return n, r, "computed"
