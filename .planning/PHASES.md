# Reel Crew implementation phases

## Phase 1 — Eligibility and runtime foundation ✓

Completed September 9, 2026. All production queries now cross the official read-only `mcp-clickhouse` server; live health and corpus queries verified on Cloud Run.

## Phase 2 — Screenplay-first production flow ✓

Completed September 8, 2026. `derive_roles()` reads scene requirements and states which crew the
script implies; `infer_brief()` reads genre and tone off scene composition so crew search inherits
the script's own signals. Roles IMDb covers carry a `category` and get staffed; every other
department the script demands is reported with `in_corpus=False` rather than dropped.

## Phase 3 — Build My Crew ✓

Completed September 8, 2026. One ranked slate per staffable craft, a 100-point match score whose
four components each carry the column they were computed from, and Q5 — the ClickHouse funnel
behind each slate, stage by stage. Q6 reports which of the assembled crew already work together.

## Phase 4 — Producer command center

Connect project KPIs, crew coverage, schedule, budget, risks, and the agent workflow in one decision surface.

## Phase 5 — Replanning and optimization

Implement one high-quality constraint-change demo, producer approval, and before/after plan comparison.

## Phase 6 — Crew chemistry and handoff

Visualize shared-credit relationships and export a complete production package.

## Language and credibility applied across phases

Use “IMDb credit-backed” rather than “verified.” Keep availability, location, and rate limitations explicit. Every recommendation must remain traceable to query evidence.
