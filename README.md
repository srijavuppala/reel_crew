# Reel Crew

**Crew discovery for film production.** A producer describes the crew they need in plain
English; the agent finds real people whose actual credit history matches, ranks them on
evidence, and shows the collaborators they normally work with.

*"Below the line"* is the industry term for crew — DPs, gaffers, editors, ADs, composers —
as opposed to above-the-line talent.

> **No profiles are created for anyone.** This tool does not manufacture accounts or
> personal pages. It computes capability summaries from public filmography data and shows
> the credits behind every ranking.

---

## The problem

Crew hiring runs on personal networks. A line producer staffing a horror feature in Atlanta
calls the four DPs they know. The other three hundred qualified DPs — including cheaper,
more available, better-matched ones — are invisible, because there is no queryable index of
*who has actually done this kind of work*.

IMDb has the data and cannot answer the question. It tells you what one person worked on.
It cannot tell you **who has shot three or more horror features rated above 6.5 in the last
eight years, and who they normally bring with them.**

## What it does

```
Producer brief (plain English)
   ↓  Gemini structured output  (deterministic rule-based parser as fallback)
CrewQuery { role, genres[], min_rating, year_from, min_credits, min_votes }
   ↓  ClickHouse — parameterized aggregation, never LLM-generated SQL
Ranked candidates with evidence columns
   ↓  ClickHouse — self-join on shared titles
The unit: who this person actually works with
   ↓  Gemini narration over returned rows only
Shortlist with per-candidate rationale
```

**The model parses and narrates. ClickHouse ranks.** No candidate reaches the screen that
did not come out of a SQL result set — which is why the UI shows the executed SQL and the
row count on every search.

## Scale

| | |
|---|---|
| Raw credits ingested | **101,655,603** |
| Rankable crew credits | 1,295,494 |
| People | 344,752 |
| Titles | 157,624 |
| Ranked search (Q1) | ~55 ms |
| Collaboration graph (Q2) | ~90 ms |
| Full ingest, four files | ~52 s |

## Architecture

| Layer | Choice |
|---|---|
| Agent framework | **Google ADK 2.8** `Workflow` — a deterministic four-node graph |
| LLM | **Gemini** (`gemini-2.5-flash`) via **Gemini Enterprise Agent Platform** (Vertex AI), or AI Studio |
| Data | **ClickHouse Cloud**, `clickhouse-connect` called on every request |
| Backend | FastAPI |
| Frontend | Single page, no build step |

### Runtime evidence

- `agent/queries.py` — `clickhouse_connect` client, three parameterized queries.
- `agent/graph.py` — `from google.adk import Workflow`, edges `START → parse → search → collaborators → narrate`.
- `agent/parse.py` / `agent/narrate.py` — `google.genai` structured output.

The UI reports which engine served each stage (`parse: gemini | rule-based`,
`runtime: adk-workflow`), so what actually ran is visible rather than claimed.

## The four queries that are the product

**Q1 — ranked search.** Aggregates matching credits, average rating, reach and recency per
person, ranked by genre match then reach-weighted quality.

**Q2 — the collaboration graph.** A self-join on shared titles. Productions hire in packs:
a DP brings their gaffer, a director brings their editor. Ask it about the DP of *Hereditary*
and it returns Ari Aster, the composer, the editor, the producer and the casting director —
reconstructed from credits alone.

> You are not hiring a DP. You are hiring a camera department.

**Q3 — profile assembly.** Career span, genre distribution, rating trajectory and top
collaborators. The statistics are SQL; only the prose is Gemini.

**Q4 — similar profiles.** Every person becomes a 28-dimensional vector of credits per genre,
compared with `cosineDistance` against a reference person, restricted to the same craft.
Cosine normalises away career length, so a six-credit DP can match a thirty-credit one on the
shape of the work rather than the volume of it.

This is the second way into the corpus. Instead of describing the job, point at someone whose
work you already know. Asked for cinematographers like Jarin Blaschke, it returns Julie
Kirkwood (*The Blackcoat's Daughter*), Kiyomi Kuroda (*Onibaba*, 1964), Shin'ya Tsukamoto
(*Tetsuo*) and Decha Srimantra (*The Eye*) — Japanese, Thai and Mexican horror alongside the
American names, which is the coverage argument made into a feature.

"Only lower-profile" caps candidates at the reference's own audience reach. That is the
practical form of the question a line producer actually asks: someone who works like this,
that the production can afford to book.

## Using it

- **Brief** — type what you need in plain English and hit Find crew.
- **Filters** — the parsed query becomes live controls (role, genres, rating, year, credit and
  vote floors). Adjusting them replaces the parse step and re-runs the same graph, so a wrong
  parse is correctable instead of fatal.
- **Sort** — reorder by match, rating, reach or recency without re-querying.
- **Shortlist** — pin people across several searches, then export CSV. Each row keeps the role
  and genres from the search that found it, so a mixed shortlist stays correctly labelled.
- **Works like** — every profile ends with the people whose credit history points the same
  way, with a toggle to keep only those below the reference's reach.
- **Follow the graph** — select anyone in the department panel or a profile to open their own
  profile and keep walking the collaboration network.
- **Verify** — every row links to the person's IMDb page. The titles check out.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env      # add your ClickHouse credentials
./scripts/ch.sh "$(cat ingest/load.sql)"   # or paste statements into the SQL console
.venv/bin/uvicorn api.main:app --reload
```

Open `http://localhost:8000`. A CLI is available too:

```bash
.venv/bin/python -m agent.graph "editor with at least 5 credits on crime dramas since 2010"
```

### Gemini backend

Two backends are supported and auto-detected from the key prefix, because sending one key to
the other endpoint fails with a misleading 403:

| Key | Backend | Endpoint |
|---|---|---|
| `AQ.…` | Gemini Enterprise Agent Platform (Vertex AI) express | `aiplatform.googleapis.com` |
| `AIza…` | AI Studio Gemini API | `generativelanguage.googleapis.com` |

Set `GOOGLE_GENAI_USE_VERTEXAI=true` to force Agent Platform, or leave `GOOGLE_API_KEY` empty
and set `GOOGLE_CLOUD_PROJECT` to use application-default credentials instead of a key.
`GET /api/health` reports which backend is live.

**Gemini is optional.** With no `GOOGLE_API_KEY` the workflow runs end to end on a
deterministic parser and computed narration, and the UI says so. Adding a key upgrades both
stages without changing the ranking, because the ranking was never the model's job.

## What the data adds over recall

`scripts/compare.py` asks Gemini the same brief with no tools, verifies every name it
returns against the credit database, then runs the agent.

Gemini is usually *right* about the famous names — this is not a hallucination demo, and
pitching it as one invites a correction. What it cannot do is rank, show evidence, apply
thresholds, or reach past the canon. A representative run:

```
3 of 6 ranked candidates never came up from memory
  + Jishnu Bhattacharjee   Stree 2, Bhediya
  + Shehnad Jalal          Bramayugam, Dies Irae
  + Ical Tanjung           Impetigore, Satan's Slaves 2: Communion
```

Indian, Malayalam and Indonesian horror — major industries with working DPs that a
memory-based answer does not surface. A line producer does not need help remembering Jarin
Blaschke. They need the other three hundred.

## Honest scope

- Credit data: **real** — IMDb public datasets, refreshed daily.
- Ranking, collaboration graph, every evidence column: **real computation over real data**.
- Availability, rates and location: **not modelled**. No public source exists, so the tool
  does not pretend to have them.

## Data licence

Credit data comes from [IMDb public datasets](https://datasets.imdbws.com), used under their
**personal and non-commercial** licence. This project is a non-commercial demonstration.
Code is MIT (see `LICENSE`); the IMDb data is not redistributed here.
