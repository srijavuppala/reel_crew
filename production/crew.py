"""Build My Crew: a screenplay's role list -> a ranked, evidence-backed slate.

Every candidate in every slate came out of a ClickHouse result set. The score is
arithmetic over columns that query returned, and each component carries the
number it was computed from, so "why is this person first" is answerable without
trusting the narration.
"""
from __future__ import annotations

import datetime
import math

from agent import queries
from .schema import (
    CrewCandidate, CrewPlan, ProductionBrief, RoleFunnel, RoleRequirement,
    RoleSlate, ScoreComponent,
)

THIS_YEAR = datetime.date.today().year

# Weights sum to 100. Genre fit dominates because it is the only component that
# answers the question actually asked: has this person made this kind of film.
W_GENRE, W_QUALITY, W_REACH, W_RECENCY = 40.0, 25.0, 20.0, 15.0


def _score(row: dict, best_genre: int, best_reach: int,
           genres: list[str]) -> tuple[float, list[ScoreComponent]]:
    genre_credits = row["genre_credits"] or 0
    genre_pts = W_GENRE * (genre_credits / best_genre if best_genre else 0)

    rating = float(row["avg_rating"] or 0)
    quality_pts = W_QUALITY * min(rating / 10.0, 1.0)

    reach = int(row["reach"] or 0)
    # log scale: the gap between 1k and 100k votes matters, 8M vs 9M does not
    reach_pts = W_REACH * (math.log10(reach + 10) / math.log10(best_reach + 10)
                           if best_reach else 0)

    gap = max(0, THIS_YEAR - int(row["most_recent"] or 0))
    recency_pts = W_RECENCY * max(0.0, 1.0 - gap / 12.0)

    label = "/".join(genres) if genres else "matching"
    components = [
        ScoreComponent(label="Genre fit", points=round(genre_pts, 1), max_points=W_GENRE,
                       basis=f"{genre_credits} {label} credit(s); best in this slate has {best_genre}"),
        ScoreComponent(label="Track record", points=round(quality_pts, 1), max_points=W_QUALITY,
                       basis=f"{rating} average IMDb rating across {row['credits']} credit(s)"),
        ScoreComponent(label="Audience reach", points=round(reach_pts, 1), max_points=W_REACH,
                       basis=f"{reach:,} votes on credited titles (log-scaled)"),
        ScoreComponent(label="Recency", points=round(recency_pts, 1), max_points=W_RECENCY,
                       basis=f"most recent credit {row['most_recent']}"
                             f"{f'; {gap} year(s) ago' if gap else '; current year'}"),
    ]
    return round(sum(c.points for c in components), 1), components


def _slate_for(requirement: RoleRequirement, genres: list[str], year_from: int,
               min_rating: float, min_votes: int, min_credits: int,
               per_role: int) -> tuple[RoleSlate, list[str]]:
    """One role. Relaxes filters rather than returning an empty slate, and says so."""
    category = requirement.category
    relaxations: list[str] = []
    attempts = [
        (genres, min_credits, min_rating),
        (genres, 1, min_rating),
        (genres, 1, max(0.0, min_rating - 1.0)),
        ([], 1, max(0.0, min_rating - 1.0)),
    ]
    rows, ms, sql = [], 0.0, ""
    used_genres, used_credits, used_rating = genres, min_credits, min_rating
    # Q1 orders by genre-credit volume, so asking it for exactly `per_role` rows
    # would make the match score decorative -- it could only reshuffle the three
    # highest-volume people. Pull a wide pool and let the score do the choosing,
    # which is what lets quality and recency outrank sheer credit count.
    pool = max(per_role * 8, 24)
    for i, (g, c, r) in enumerate(attempts):
        rows, ms, sql = queries.search_crew(
            role=category, genres=g, min_rating=r, year_from=year_from,
            min_credits=c, min_votes=min_votes, limit=pool)
        used_genres, used_credits, used_rating = g, c, r
        if rows:
            if i:
                bits = []
                if c != min_credits:
                    bits.append(f"minimum matching credits {min_credits} -> {c}")
                if r != min_rating:
                    bits.append(f"minimum rating {min_rating} -> {r}")
                if not g and genres:
                    bits.append(f"dropped the {'/'.join(genres)} filter")
                relaxations.append(f"{requirement.role}: {'; '.join(bits)}")
            break

    best_genre = max((x["genre_credits"] or 0) for x in rows) if rows else 0
    best_reach = max((x["reach"] or 0) for x in rows) if rows else 0
    scored = []
    for row in rows:
        scored.append((_score(row, best_genre, best_reach, used_genres), row))
    scored.sort(key=lambda pair: -pair[0][0])
    candidates = []
    for (score, components), row in scored[:per_role]:
        titles = row["sample_titles"][:3]
        label = "/".join(used_genres) if used_genres else "credited"
        candidates.append(CrewCandidate(
            nconst=row["nconst"], name=row["name"], match_score=score, components=components,
            credits=row["credits"], genre_credits=row["genre_credits"],
            avg_rating=row["avg_rating"], reach=row["reach"], most_recent=row["most_recent"],
            sample_titles=titles,
            evidence=f"{row['genre_credits']} {label} credit(s) since {year_from}"
                     + (f" — {', '.join(titles)}" if titles else ""),
        ))

    frows, fms, fsql = queries.role_funnel(
        role=category, genres=used_genres, min_rating=used_rating, year_from=year_from,
        min_credits=used_credits, min_votes=min_votes)
    f = frows[0] if frows else {}
    funnel = RoleFunnel(
        craft_people=f.get("craft_people", 0), genre_people=f.get("genre_people", 0),
        threshold_people=f.get("threshold_people", 0),
        shortlist_people=f.get("shortlist_people", 0), shown=len(candidates),
        scored_pool=len(rows),
        sql=sql, ms=int(ms + fms),
    )
    return RoleSlate(
        role=requirement.role, category=category, department=requirement.department,
        priority=requirement.priority, reason=requirement.reason,
        candidates=candidates, funnel=funnel,
    ), relaxations


def build_crew(title: str, brief: ProductionBrief, roles: list[RoleRequirement],
               year_from: int = 2015, min_rating: float = 6.0, min_votes: int = 1000,
               min_credits: int = 2, per_role: int = 3) -> CrewPlan:
    staffable = [r for r in roles if r.staffable and r.category]
    slates, relaxations = [], []
    for requirement in staffable:
        slate, relaxed = _slate_for(requirement, brief.genres, year_from, min_rating,
                                    min_votes, min_credits, per_role)
        slates.append(slate)
        relaxations.extend(relaxed)

    # Chemistry runs over the top pick of each role: the crew as actually proposed.
    picks = [s.candidates[0].nconst for s in slates if s.candidates]
    edges, cms, _ = queries.crew_chemistry(picks)
    lookup = {s.candidates[0].nconst: s.role for s in slates if s.candidates}
    chemistry = [{
        "a_name": e["a_name"], "a_role": lookup.get(e["a_nconst"], ""),
        "b_name": e["b_name"], "b_role": lookup.get(e["b_nconst"], ""),
        "films_together": e["films_together"], "shared_titles": e["shared_titles"],
    } for e in edges]

    return CrewPlan(
        title=title, brief=brief, slates=slates,
        unstaffable=[r for r in roles if not r.in_corpus],
        chemistry=chemistry,
        engine={
            "roles_staffed": len(slates),
            "roles_flagged_not_in_corpus": len([r for r in roles if not r.in_corpus]),
            "clickhouse_queries": len(slates) * 2 + (1 if len(picks) > 1 else 0),
            "chemistry_ms": int(cms),
            "relaxations": relaxations,
            "filters": {"genres": brief.genres, "year_from": year_from,
                        "min_rating": min_rating, "min_votes": min_votes,
                        "min_credits": min_credits},
        },
    )
