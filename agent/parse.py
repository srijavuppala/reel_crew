"""Brief -> CrewQuery.

Gemini does structured extraction when a key is present. A deterministic
rule-based parser backs it up so the workflow never depends on the model
being reachable, and so the demo runs with no API key at all.
"""
from __future__ import annotations

import datetime
import json
import re

from .config import GEMINI_ENABLED, GEMINI_MODEL, get_genai_client
from .schema import ROLES, CrewQuery

IMDB_GENRES = [
    "Action", "Adventure", "Animation", "Biography", "Comedy", "Crime",
    "Documentary", "Drama", "Family", "Fantasy", "Film-Noir", "History",
    "Horror", "Music", "Musical", "Mystery", "Romance", "Sci-Fi", "Sport",
    "Thriller", "War", "Western",
]

# Industry slang -> IMDb `category` value.
ROLE_SYNONYMS = {
    "cinematographer": ["cinematographer", "dp", "d.p.", "director of photography",
                        "camera operator", "shooter", "videographer", "lensman", "camera"],
    "editor": ["editor", "cutter", "picture editor", "edit"],
    "composer": ["composer", "score", "scoring", "music"],
    "production_designer": ["production designer", "production design", "prod design",
                            "designer", "art director", "pd"],
    "casting_director": ["casting director", "casting"],
    "director": ["director", "helmer", "filmmaker"],
    "writer": ["writer", "screenwriter", "scribe", "scriptwriter"],
    "producer": ["producer", "line producer", "upm"],
}

GENRE_SYNONYMS = {
    "Sci-Fi": ["sci-fi", "scifi", "science fiction", "sf"],
    "Horror": ["horror", "scary", "slasher", "creature feature"],
    "Thriller": ["thriller", "suspense"],
    "Documentary": ["documentary", "doc", "docs"],
    "Film-Noir": ["film-noir", "noir"],
    "Romance": ["romance", "romantic", "rom-com"],
    "Comedy": ["comedy", "comedic", "rom-com", "funny"],
    "Action": ["action", "action movie"],
    "Animation": ["animation", "animated"],
    "Crime": ["crime", "heist", "gangster"],
    "Biography": ["biography", "biopic"],
    "Musical": ["musical"],
    "Western": ["western"],
    "Fantasy": ["fantasy"],
    "Mystery": ["mystery", "whodunit"],
    "War": ["war"],
    "Family": ["family", "kids"],
    "Adventure": ["adventure"],
    "Drama": ["drama", "dramatic"],
    "History": ["history", "historical", "period"],
    "Sport": ["sport", "sports"],
    "Music": ["music"],
}

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

PARSE_INSTRUCTION = f"""You convert a film producer's plain-English crew brief into a search query.
Valid roles: {', '.join(ROLES)}
Valid genres (exact casing): {', '.join(IMDB_GENRES)}
Map industry slang: "DP"/"director of photography" -> cinematographer; "cutter" -> editor;
"score"/"music" -> composer; "UPM"/"line producer" -> producer.
Resolve relative time ("last 8 years") against the current year {datetime.date.today().year}.
Return ONLY a JSON object with keys: role, genres, min_rating, year_from, min_credits, min_votes, keywords.
"""


def _rule_based(brief: str) -> CrewQuery:
    """Deterministic parser. Always available, no network, no key."""
    text = brief.lower()
    year_now = datetime.date.today().year

    role = "cinematographer"
    best = -1
    for canonical, words in ROLE_SYNONYMS.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", text) and len(w) > best:
                role, best = canonical, len(w)

    genres: list[str] = []
    for canonical, words in GENRE_SYNONYMS.items():
        if any(re.search(rf"\b{re.escape(w)}s?\b", text) for w in words):
            genres.append(canonical)

    # "rated above 6.5", "over 7", "7+"
    # Only read a number as a rating when it is explicitly rating-flavoured.
    # "at least 5 credits" and "2+ credits" are counts, not ratings.
    min_rating = 6.0
    m = (re.search(r"(?:rated|rating|imdb|scores?)\D{0,15}(\d(?:\.\d)?)", text)
         or re.search(r"(?:above|over|better than)\s+(\d\.\d)", text)
         or re.search(r"(\d\.\d)\s*\+", text))
    if m:
        val = float(m.group(1))
        if 0 < val <= 10:
            min_rating = val

    # "last 8 years" / "since 2015" / "in the past decade"
    year_from = 2015
    if m := re.search(r"(?:last|past)\s+(\d{1,2}|" + "|".join(NUMBER_WORDS) + r")\s+years?", text):
        g = m.group(1)
        year_from = year_now - (int(g) if g.isdigit() else NUMBER_WORDS[g])
    elif m := re.search(r"(?:since|after|from)\s+(19|20)(\d{2})", text):
        year_from = int(m.group(1) + m.group(2))
    elif "decade" in text:
        year_from = year_now - 10

    # "three or more", "at least 3 features"
    min_credits = 2
    if m := re.search(r"(\d{1,2}|" + "|".join(NUMBER_WORDS) + r")\s*(?:\+|or more|or better)", text):
        g = m.group(1)
        min_credits = int(g) if g.isdigit() else NUMBER_WORDS[g]
    elif m := re.search(r"at least\s+(\d{1,2}|" + "|".join(NUMBER_WORDS) + r")\s+(?:credit|feature|film|movie)", text):
        g = m.group(1)
        min_credits = int(g) if g.isdigit() else NUMBER_WORDS[g]

    stop = set("the a an and or with who has have for need looking find me of in on".split())
    keywords = [w for w in re.findall(r"[a-z][a-z'-]{3,}", text) if w not in stop][:8]

    return CrewQuery(role=role, genres=genres, min_rating=min_rating,
                     year_from=year_from, min_credits=max(1, min_credits),
                     min_votes=1000, keywords=keywords)


def _gemini(brief: str) -> CrewQuery | None:
    """Gemini structured output. Returns None so the caller can fall back."""
    try:
        from google.genai import types

        client = get_genai_client()
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=brief,
            config=types.GenerateContentConfig(
                system_instruction=PARSE_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=CrewQuery,
                temperature=0.0,
            ),
        )
        if getattr(resp, "parsed", None):
            return CrewQuery.model_validate(resp.parsed)
        return CrewQuery.model_validate(json.loads(resp.text))
    except Exception as exc:  # noqa: BLE001 - never let the demo die on the LLM
        print(f"[parse] Gemini unavailable, using rule-based parser: {exc}")
        return None


def parse_brief(brief: str) -> tuple[CrewQuery, str]:
    """Return (query, which_parser_was_used)."""
    if GEMINI_ENABLED:
        if q := _gemini(brief):
            return q, "gemini"
    return _rule_based(brief), "rule-based"
