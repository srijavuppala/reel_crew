#!/usr/bin/env python
"""The comparison beat: plain Gemini with no data, versus the agent.

Asks Gemini the same brief with no tools, then checks each name it produced
against the credit database, then runs the real agent. The point is not that
the model is stupid -- it is that unverified recall cannot be staffed from.

    .venv/bin/python scripts/compare.py "<brief>"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import GEMINI_ENABLED, GEMINI_MODEL, GOOGLE_API_KEY  # noqa: E402
from agent.graph import run_direct  # noqa: E402
from agent.queries import get_client  # noqa: E402

BRIEF = " ".join(sys.argv[1:]) or (
    "Name 8 cinematographers who have shot three or more horror features "
    "rated above 6.5 in the last eight years."
)


def ask_plain_gemini(brief: str) -> list[str]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GOOGLE_API_KEY)
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=brief,
        config=types.GenerateContentConfig(
            system_instruction='Answer from memory. Return ONLY JSON: {"names": [str]}',
            response_mime_type="application/json",
            temperature=0.4,
        ),
    )
    return json.loads(resp.text).get("names", [])


def verify(names: list[str]) -> list[tuple[str, int, str]]:
    """Check each name against crew_credits. Returns (name, matching_credits, note)."""
    client = get_client()
    out = []
    for n in names:
        rows = client.query(
            """SELECT count() AS credits,
                      countIf(hasAny(genres, ['Horror']) AND year >= 2018) AS horror_recent
               FROM crew_credits
               WHERE category = 'cinematographer' AND name = {n:String}""",
            parameters={"n": n},
        ).result_rows
        credits, horror = (rows[0] if rows else (0, 0))
        if credits == 0:
            note = "not in the credit data as a cinematographer"
        elif horror == 0:
            note = "real, but no recent horror credits"
        else:
            note = f"verified: {horror} recent horror credit(s)"
        out.append((n, horror, note))
    return out


def main() -> None:
    print("=" * 78)
    print("BRIEF:", BRIEF)
    print("=" * 78)

    print("\n[A] Plain Gemini, no data, answering from memory")
    print("-" * 78)
    if not GEMINI_ENABLED:
        print("  GOOGLE_API_KEY not set -- skipping. Add the key to .env to record this beat.")
    else:
        try:
            names = ask_plain_gemini(BRIEF)
            checked = verify(names)
            for n, horror, note in checked:
                mark = "OK  " if horror > 0 else "??  "
                print(f"  {mark}{n:<30} {note}")
            unverified = sum(1 for _, h, _ in checked if h == 0)
            print(f"\n  {unverified} of {len(checked)} could not be verified against real credits.")
        except Exception as exc:  # noqa: BLE001
            print(f"  Gemini call failed: {exc}")

    print("\n[B] Below the Line -- ranked by ClickHouse over real credits")
    print("-" * 78)
    r = run_direct(BRIEF, limit=8)
    for i, c in enumerate(r.candidates, 1):
        print(f"  {i}. {c.name:<28} {c.genre_credits} matching credit(s), "
              f"avg {c.avg_rating}, {', '.join(c.sample_titles[:2])}")
    q1 = next((t for t in r.trace if t.step == "search"), None)
    if q1:
        print(f"\n  {q1.rows} rows from ClickHouse in {q1.ms} ms. Every title above is checkable on IMDb.")


if __name__ == "__main__":
    main()
