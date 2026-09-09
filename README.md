# Below the Line

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
| LLM | **Gemini** (`gemini-2.5-flash`) for brief parsing and narration |
| Data | **ClickHouse Cloud**, `clickhouse-connect` called on every request |
| Backend | FastAPI |
| Frontend | Single page, no build step |

### Runtime evidence

- `agent/queries.py` — `clickhouse_connect` client, three parameterized queries.
- `agent/graph.py` — `from google.adk import Workflow`, edges `START → parse → search → collaborators → narrate`.
- `agent/parse.py` / `agent/narrate.py` — `google.genai` structured output.

The UI reports which engine served each stage (`parse: gemini | rule-based`,
`runtime: adk-workflow`), so what actually ran is visible rather than claimed.

## The three queries that are the product

**Q1 — ranked search.** Aggregates matching credits, average rating, reach and recency per
person, ranked by genre match then reach-weighted quality.

**Q2 — the collaboration graph.** A self-join on shared titles. Productions hire in packs:
a DP brings their gaffer, a director brings their editor. Ask it about the DP of *Hereditary*
and it returns Ari Aster, the composer, the editor, the producer and the casting director —
reconstructed from credits alone.

> You are not hiring a DP. You are hiring a camera department.

**Q3 — profile assembly.** Career span, genre distribution, rating trajectory and top
collaborators. The statistics are SQL; only the prose is Gemini.

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

**Gemini is optional.** With no `GOOGLE_API_KEY` the workflow runs end to end on a
deterministic parser and computed narration, and the UI says so. Adding a key upgrades both
stages without changing the ranking, because the ranking was never the model's job.

## Honest scope

- Credit data: **real** — IMDb public datasets, refreshed daily.
- Ranking, collaboration graph, every evidence column: **real computation over real data**.
- Availability, rates and location: **not modelled**. No public source exists, so the tool
  does not pretend to have them.

## Data licence

Credit data comes from [IMDb public datasets](https://datasets.imdbws.com), used under their
**personal and non-commercial** licence. This project is a non-commercial demonstration.
Code is MIT (see `LICENSE`); the IMDb data is not redistributed here.
