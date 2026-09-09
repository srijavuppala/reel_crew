"""Parameterized ClickHouse queries.

Every candidate that reaches the UI comes out of one of these result sets.
The LLM never writes SQL and never invents a person -- it only parses the brief
and narrates rows that ClickHouse returned.
"""
from __future__ import annotations

import time
from typing import Any

from .mcp_clickhouse import render_query, run_query

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


# ------------------------------------------------------- Q4: similar profiles
# IMDb's genre list is a fixed, closed vocabulary. Holding it in Python rather
# than deriving it per query keeps the vector dimensions stable between calls,
# so two people are always compared on the same axes.
GENRE_VOCAB = [
    "Action", "Adult", "Adventure", "Animation", "Biography", "Comedy", "Crime",
    "Documentary", "Drama", "Family", "Fantasy", "Film-Noir", "Game-Show",
    "History", "Horror", "Music", "Musical", "Mystery", "News", "Reality-TV",
    "Romance", "Sci-Fi", "Short", "Sport", "Talk-Show", "Thriller", "War",
    "Western",
]

Q4_SIMILAR = """
WITH
    {vocab:Array(String)} AS vocab,
    -- the reference person's main craft: comparing a DP to a composer is meaningless
    (SELECT topK(1)(category)[1]
       FROM crew_credits WHERE nconst = {nconst:String})          AS ref_cat,
    -- one bucket per genre, counted over that person's credits in that craft
    (SELECT arrayMap(g -> countEqual(arrayFlatten(groupArray(genres)), g), vocab)
       FROM crew_credits
      WHERE nconst = {nconst:String} AND category = ref_cat)      AS ref_vec,
    (SELECT sum(votes)
       FROM crew_credits
      WHERE nconst = {nconst:String} AND category = ref_cat)      AS ref_reach
SELECT
    nconst,
    any(name)                                        AS name,
    -- NOT aliased `category`: that name would shadow the table's own column and
    -- silently turn the WHERE below into `ref_cat = ref_cat`, matching every craft
    ref_cat                                          AS role,
    count()                                          AS credits,
    round(avg(rating), 2)                            AS avg_rating,
    sum(votes)                                       AS reach,
    max(year)                                        AS most_recent,
    -- cosine normalises away career length, so a 6-credit DP can match a
    -- 30-credit one on the shape of the work rather than the volume of it
    round(1 - cosineDistance(
        arrayMap(g -> countEqual(arrayFlatten(groupArray(genres)), g), vocab),
        ref_vec), 3)                                 AS similarity,
    arraySlice(arrayDistinct(arrayMap(x -> x.2, arrayReverseSort(x -> x.1,
        groupArray((votes, title))))), 1, 3)         AS sample_titles
FROM crew_credits
WHERE crew_credits.category = ref_cat
  AND nconst   != {nconst:String}
  AND year     >= {year_from:UInt16}
  AND votes    >= {min_votes:UInt32}
GROUP BY nconst
HAVING credits >= {min_credits:UInt8}
   AND similarity > 0
   -- "someone who works like this, that I can actually get"
   AND ({under_reference:UInt8} = 0 OR reach < ref_reach)
ORDER BY similarity DESC, log10(reach + 10) * avg_rating DESC
LIMIT {limit:UInt8}
"""


# ------------------------------------------------------------ Q5: role funnel
# The "explain this recommendation" surface. Four counts, one per narrowing
# stage, so a producer can see the shortlist was cut out of the whole corpus by
# stated filters rather than chosen by a model.
Q5_FUNNEL = """
SELECT
    (SELECT uniqExact(nconst) FROM crew_credits
      WHERE category = {role:String})                                AS craft_people,
    (SELECT uniqExact(nconst) FROM crew_credits
      WHERE category = {role:String}
        AND (empty({genres:Array(String)})
             OR hasAny(genres, {genres:Array(String)})))             AS genre_people,
    (SELECT uniqExact(nconst) FROM crew_credits
      WHERE category = {role:String}
        AND (empty({genres:Array(String)})
             OR hasAny(genres, {genres:Array(String)}))
        AND year   >= {year_from:UInt16}
        AND rating >= {min_rating:Float32}
        AND votes  >= {min_votes:UInt32})                            AS threshold_people,
    (SELECT count() FROM (
        SELECT nconst FROM crew_credits
         WHERE category = {role:String}
           AND year   >= {year_from:UInt16}
           AND rating >= {min_rating:Float32}
           AND votes  >= {min_votes:UInt32}
         GROUP BY nconst
        HAVING countIf(empty({genres:Array(String)})
                       OR hasAny(genres, {genres:Array(String)}))
               >= {min_credits:UInt8}))                              AS shortlist_people
"""


# --------------------------------------------------------- Q6: crew chemistry
# Do the people we just assembled already work together? Pairwise shared titles
# across the selected crew. a.nconst < b.nconst keeps each pair once.
Q6_CHEMISTRY = """
SELECT
    a.nconst                                   AS a_nconst,
    any(a.name)                                AS a_name,
    b.nconst                                   AS b_nconst,
    any(b.name)                                AS b_name,
    uniqExact(a.tconst)                        AS films_together,
    arraySlice(groupUniqArray(a.title), 1, 3)  AS shared_titles
FROM crew_credits AS a
INNER JOIN crew_credits AS b ON a.tconst = b.tconst
WHERE a.nconst IN {picks:Array(String)}
  AND b.nconst IN {picks:Array(String)}
  AND a.nconst < b.nconst
GROUP BY a.nconst, b.nconst
ORDER BY films_together DESC, a_name ASC
"""


def _run(sql: str, params: dict[str, Any]) -> tuple[list[dict], float, str]:
    """Execute a parameterized query; return rows, elapsed ms, and the SQL text."""
    rendered = render_query(sql, params)
    t0 = time.perf_counter()
    columns, result_rows = run_query(rendered)
    ms = (time.perf_counter() - t0) * 1000
    rows = [dict(zip(columns, r)) for r in result_rows]
    return rows, ms, sql.strip()


def search_crew(role: str, genres: list[str], min_rating: float, year_from: int,
                min_credits: int, min_votes: int = 1000, limit: int = 20):
    return _run(Q1_SEARCH, {
        "role": role, "genres": genres or [], "min_rating": float(min_rating),
        "year_from": int(year_from), "min_credits": int(min_credits),
        "min_votes": int(min_votes), "limit": int(limit),
    })


def role_funnel(role: str, genres: list[str], min_rating: float, year_from: int,
                min_credits: int, min_votes: int = 1000):
    return _run(Q5_FUNNEL, {
        "role": role, "genres": genres or [], "min_rating": float(min_rating),
        "year_from": int(year_from), "min_credits": int(min_credits),
        "min_votes": int(min_votes),
    })


def get_collaborators(nconst: str, limit: int = 10):
    return _run(Q2_COLLABORATORS, {"nconst": nconst, "limit": int(limit)})


def crew_chemistry(picks: list[str]):
    """Shared-credit edges among an assembled crew. Empty list -> no query."""
    if len(picks) < 2:
        return [], 0.0, Q6_CHEMISTRY.strip()
    return _run(Q6_CHEMISTRY, {"picks": picks})


def get_profile(nconst: str):
    return _run(Q3_PROFILE, {"nconst": nconst})


def get_timeline(nconst: str):
    return _run(Q3_TIMELINE, {"nconst": nconst})


def find_similar(nconst: str, under_reference: bool = False, year_from: int = 1900,
                 min_credits: int = 3, min_votes: int = 1000, limit: int = 12):
    """People whose genre mix points the same way as this person's.

    The reference's own craft and genre vector come out of the same query, so a
    caller only has to supply the person -- there is nothing to keep in sync.
    """
    return _run(Q4_SIMILAR, {
        "nconst": nconst, "vocab": GENRE_VOCAB,
        "under_reference": 1 if under_reference else 0,
        "year_from": int(year_from), "min_credits": int(min_credits),
        "min_votes": int(min_votes), "limit": int(limit),
    })


def corpus_stats() -> dict[str, int]:
    """Row counts shown in the UI as the anti-wrapper signal."""
    def scalar(sql: str) -> int:
        _, rows = run_query(sql)
        return int(rows[0][0])
    return {
        "crew_credits": scalar("SELECT count() FROM crew_credits"),
        "raw_principals": scalar("SELECT count() FROM title_principals"),
        "people": scalar("SELECT uniqExact(nconst) FROM crew_credits"),
        "titles": scalar("SELECT uniqExact(tconst) FROM crew_credits"),
    }
