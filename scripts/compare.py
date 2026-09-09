#!/usr/bin/env python
"""The comparison beat: plain Gemini with no data, versus the agent.

Do NOT pitch this as "the LLM hallucinates". It often does not -- Gemini can
usually name the famous horror DPs correctly, and a judge who knows the field
will notice if you claim otherwise. Measured across runs it is also unstable:
the same prompt returned 8/8 verifiable names once and 6/8 the next time.

The honest and stronger point is coverage and rank:
  * recall returns the handful of people you already knew, unranked, with no
    evidence, and a different set each time you ask
  * the credit data returns those people WITH evidence, in a defensible order,
    plus the working professionals recall will never surface

That long tail is the product. A line producer does not need help remembering
Jarin Blaschke; they need the other three hundred.

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
            # An exact-name miss is usually a misspelling, not an invented person.
            # Say which, or the comparison overstates its case.
            near = client.query(
                """SELECT any(name) AS name, countIf(hasAny(genres, ['Horror']) AND year >= 2018) AS horror_recent
                   FROM crew_credits
                   WHERE category = 'cinematographer'
                     AND lower(splitByChar(' ', name)[-1]) = lower(splitByChar(' ', {n:String})[-1])
                   GROUP BY nconst ORDER BY horror_recent DESC LIMIT 1""",
                parameters={"n": n},
            ).result_rows
            if near and near[0][0]:
                note = f"no exact match; closest real credit is {near[0][0]} ({near[0][1]} recent horror)"
                horror = 0
            else:
                note = "no such cinematographer in the credit data"
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

    recalled: list[str] = []
    print("\n[A] Plain Gemini, no data, answering from memory")
    print("-" * 78)
    if not GEMINI_ENABLED:
        print("  GOOGLE_API_KEY not set -- skipping. Add the key to .env to record this beat.")
    else:
        try:
            names = ask_plain_gemini(BRIEF)
            recalled = list(names)
            checked = verify(names)
            for n, horror, note in checked:
                mark = "OK  " if horror > 0 else "??  "
                print(f"  {mark}{n:<30} {note}")
            unverified = sum(1 for _, h, _ in checked if h == 0)
            print(f"\n  {unverified} of {len(checked)} could not be verified as named. "
                  f"Some are misspellings of real people -- which is the point: you cannot "
                  f"staff from a name you cannot resolve.")
        except Exception as exc:  # noqa: BLE001
            print(f"  Gemini call failed: {exc}")

    print("\n[B] Reel Crew -- ranked by ClickHouse over real credits")
    print("-" * 78)
    r = run_direct(BRIEF, limit=12)
    for i, c in enumerate(r.candidates, 1):
        print(f"  {i}. {c.name:<28} {c.genre_credits} matching credit(s), "
              f"avg {c.avg_rating}, {', '.join(c.sample_titles[:2])}")
    q1 = next((t for t in r.trace if t.step == "search"), None)
    if q1:
        print(f"\n  {q1.rows} rows from ClickHouse in {q1.ms} ms. Every title above is checkable on IMDb.")

    if GEMINI_ENABLED and recalled:
        known = {n.lower() for n in recalled}
        new_names = [c for c in r.candidates if c.name.lower() not in known]
        print("\n[C] What recall did not surface")
        print("-" * 78)
        if new_names:
            for c in new_names:
                print(f"  + {c.name:<28} {c.genre_credits} matching credit(s), "
                      f"{', '.join(c.sample_titles[:2])}")
            print(f"\n  {len(new_names)} of {len(r.candidates)} ranked candidates never came up "
                  f"from memory -- and they are working professionals with verifiable credits.")
            print("  This is the gap the tool closes. Not accuracy: coverage, evidence and rank.")
        else:
            print("  Recall covered the whole shortlist this time. The difference is still that")
            print("  these are ranked on evidence, filterable, and come with the collaboration graph.")


if __name__ == "__main__":
    main()
