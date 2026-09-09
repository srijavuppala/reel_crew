"""Parameterized ClickHouse queries.

Every candidate that reaches the UI comes out of one of these result sets.
The LLM never writes SQL and never invents a person -- it only parses the brief
and narrates rows that ClickHouse returned.
"""
from __future__ import annotations

import time
from typing import Any

from .config import get_client

# ---------------------------------------------------------------- Q1: ranked search
Q1_SEARCH = """
SELECT
    nconst,
    any(name)                                        AS name,
    count()                                          AS credits,
    -- with no genre filter every credit counts, so an unfiltered brief
    -- still passes the HAVING floor instead of returning nothing
    countIf(empty({genres:Array(String)})
            OR hasAny(genres, {genres:Array(String)}))  AS genre_credits,
    round(avg(rating), 2)                            AS avg_rating,
    sum(votes)                                       AS reach,
    max(year)                                        AS most_recent,
    -- strongest genre-matching credits first, so the evidence shown is the
    -- evidence that earned the ranking (falls back to all credits if no genre filter)
    arraySlice(
      arrayDistinct(arrayMap(x -> x.2, arrayReverseSort(x -> x.1,
        groupArrayIf(
          (votes, title),
          empty({genres:Array(String)}) OR hasAny(genres, {genres:Array(String)})
        )))), 1, 3)                                  AS sample_titles
FROM crew_credits
WHERE category = {role:String}
  AND year    >= {year_from:UInt16}
  AND rating  >= {min_rating:Float32}
  AND votes   >= {min_votes:UInt32}
GROUP BY nconst
HAVING genre_credits >= {min_credits:UInt8}
ORDER BY genre_credits DESC, log10(reach + 10) * avg_rating DESC
LIMIT {limit:UInt8}
"""

# ------------------------------------------------------- Q2: collaboration graph
# uniqExact de-duplicates people who hold several roles on the same title
# (a director who is also the writer would otherwise be counted twice).
Q2_COLLABORATORS = """
SELECT
    b.nconst                                          AS nconst,
    any(b.name)                                       AS name,
    groupUniqArray(b.category)                        AS roles,
    uniqExact(a.tconst)                               AS films_together,
    arraySlice(groupUniqArray(b.title), 1, 4)         AS shared_titles
FROM crew_credits AS a
INNER JOIN crew_credits AS b ON a.tconst = b.tconst
WHERE a.nconst  = {nconst:String}
  AND b.nconst != {nconst:String}
GROUP BY b.nconst
ORDER BY films_together DESC, name ASC
LIMIT {limit:UInt8}
"""

# ------------------------------------------------------------- Q3: profile stats
Q3_PROFILE = """
SELECT
    any(name)                                   AS name,
    count()                                     AS credits,
    min(year)                                   AS first_year,
    max(year)                                   AS last_year,
    round(avg(rating), 2)                       AS avg_rating,
    sum(votes)                                  AS reach,
    groupUniqArray(category)                    AS roles,
    arraySlice(
      arrayReverseSort(x -> x.2, arrayMap(
        (g, c) -> (g, c),
        arrayDistinct(arrayFlatten(groupArray(genres))),
        arrayMap(g -> countEqual(arrayFlatten(groupArray(genres)), g),
                 arrayDistinct(arrayFlatten(groupArray(genres))))
      )), 1, 6)                                 AS genre_mix
FROM crew_credits
WHERE nconst = {nconst:String}
"""

Q3_TIMELINE = """
SELECT year, round(avg(rating), 2) AS avg_rating, count() AS credits,
       arraySlice(groupUniqArray(title), 1, 2) AS titles
FROM crew_credits
WHERE nconst = {nconst:String} AND year > 0
GROUP BY year ORDER BY year
"""


def _run(sql: str, params: dict[str, Any]) -> tuple[list[dict], float, str]:
    """Execute a parameterized query; return rows, elapsed ms, and the SQL text."""
    client = get_client()
    t0 = time.perf_counter()
    res = client.query(sql, parameters=params)
    ms = (time.perf_counter() - t0) * 1000
    rows = [dict(zip(res.column_names, r)) for r in res.result_rows]
    return rows, ms, sql.strip()


def search_crew(role: str, genres: list[str], min_rating: float, year_from: int,
                min_credits: int, min_votes: int = 1000, limit: int = 20):
    return _run(Q1_SEARCH, {
        "role": role, "genres": genres or [], "min_rating": float(min_rating),
        "year_from": int(year_from), "min_credits": int(min_credits),
        "min_votes": int(min_votes), "limit": int(limit),
    })


def get_collaborators(nconst: str, limit: int = 10):
    return _run(Q2_COLLABORATORS, {"nconst": nconst, "limit": int(limit)})


def get_profile(nconst: str):
    return _run(Q3_PROFILE, {"nconst": nconst})


def get_timeline(nconst: str):
    return _run(Q3_TIMELINE, {"nconst": nconst})


def corpus_stats() -> dict[str, int]:
    """Row counts shown in the UI as the anti-wrapper signal."""
    c = get_client()
    return {
        "crew_credits": c.query("SELECT count() FROM crew_credits").result_rows[0][0],
        "raw_principals": c.query("SELECT count() FROM title_principals").result_rows[0][0],
        "people": c.query("SELECT uniqExact(nconst) FROM crew_credits").result_rows[0][0],
        "titles": c.query("SELECT uniqExact(tconst) FROM crew_credits").result_rows[0][0],
    }
