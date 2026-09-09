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

## Phase 4 — Producer command center ✓

Completed September 9, 2026. The overview now connects project KPIs, crew coverage, schedule, budget, risks, and a six-stage agent workflow in one producer decision surface.

## Phase 5 — Replanning and optimization ✓

Completed September 9, 2026. Budget, shoot-day, and crew-unavailable events produce a reversible
before/after proposal; the approved baseline changes only after an explicit producer decision.

## Phase 6 — Crew chemistry and handoff ✓

Completed September 9, 2026. Shared-credit relationships render as a crew network and the handoff
exports plan, roster, shortlist, finance, availability, approvals, operating events, and evidence.

## Phase 7 — Shared projects, finance, and approvals ✓

Move project, shortlist, roster, budget, and approval records out of browser-only storage into a
transactional database. Add project accounts, estimate/committed/actual budget states, variance,
CSV import/export, approval history, and an audit trail. ClickHouse remains the analytics and
credit-search store; no payment or hiring decision is autonomous.

Completed September 9, 2026. Shared Cloud Run records use Firestore with delete protection; local
development uses SQLite. Project saves create audit events, and finance separates estimate,
committed, actual, and variance.

## Phase 8 — Scheduling, availability, and call sheets ✓

Add an availability-aware stripboard, cast and crew conflict detection, location and turnaround
constraints, and versioned call sheets. Every schedule revision requires human approval and shows
the people, locations, requirements, and estimated cost affected by the change.

Completed September 9, 2026 (demo scope). Availability conflicts are attached to shoot days and
call-sheet revisions require an explicit producer approval. Drag/drop optimization remains future depth.

## Phase 9 — Production operations and submission readiness ◑

Connect daily progress, pages shot, schedule drift, cost variance, department views, open approvals,
and post-production delivery milestones to the shared production record. Complete end-to-end QA,
record the public English demo, verify repository metadata and license display, and submit the
stable Cloud Run build with buffer.

In progress. Daily production events and handoff data are implemented. Final live QA, repository
metadata review, demo recording, and Devpost submission remain.

## Language and credibility applied across phases

Use “IMDb credit-backed” rather than “verified.” Keep availability, location, and rate limitations explicit. Every recommendation must remain traceable to query evidence.
