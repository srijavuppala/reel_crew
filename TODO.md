# Build tracker

## Phase 0 — MVP  ✅ complete
- [x] ClickHouse Cloud connected (`SELECT 1` from Python)
- [x] All four IMDb files ingested — 101,655,603 raw credits in ~52s
- [x] `crew_credits` denormalized — 1,295,494 rankable rows in ~6s
- [x] `agent/queries.py` — Q1 parameterized, real names returned for cinematographer + Horror
- [x] `agent/parse.py` — brief → `CrewQuery` (Gemini structured output + rule-based fallback)
- [x] `agent/graph.py` — ADK `Workflow`, START → parse → search → collaborators → narrate
- [x] CLI: `python -m agent.graph "<brief>"`
- [x] `api/main.py` — `POST /api/search` returns `{query, candidates[], package[], narration, trace}`
- [x] `web/` — brief input, ranked crew list, evidence columns, rationale
- [x] `README.md` + MIT `LICENSE`

## Phase 1 — The differentiator  ✅ complete
- [x] Q2 collaboration graph, called automatically for the top candidate
- [x] "The unit" panel — lead plus their most frequent collaborators as a hireable package
- [x] Profile drill-down (Q3): career span, genre mix, rating-by-year, top collaborators
- [x] Executed SQL and row counts shown in the UI (the anti-wrapper signal)
- [x] Multi-step trace with per-step timings

## Phase 1.5 — Product depth  ✅ complete
- [x] Renamed to **Reel Crew**
- [x] Editable filter controls that replace the parse step and re-run the same ADK graph
- [x] Sortable evidence columns + "show more"
- [x] Shortlist with CSV export; role/genres stamped per candidate at pin time
- [x] Clickable collaborators — walk the graph from any person to any other
- [x] IMDb verification link on every candidate

## Phase 1.6 — Similarity search  ✅ complete
- [x] Q4: 28-genre credit vector per person, `cosineDistance` against a reference, same craft only
- [x] `GET /api/similar/{nconst}` with an `under_reference` reach cap
- [x] "Works like X" panel in every profile, chainable like the collaborator list
- [x] Fixed: aliasing the output column `category` shadowed the table column and silently
      disabled the craft filter, returning writers and producers for a DP query

## Phase 2 — Design and impact  ◑ in progress
- [x] Empty and error states written as product copy, not stack traces
- [x] Keyboard access, focus states, reduced-motion, mobile breakpoint
- [x] `Dockerfile` + `scripts/deploy_cloudrun.sh`
- [x] Google Cloud CLI installed and authenticated (deploy script resolves Homebrew's cask path)
- [x] Deployed to Cloud Run: https://reel-crew-10453428907.us-central1.run.app
- [x] Gemini Enterprise Agent Platform (Vertex AI) integrated — express-key and ADC paths,
      auto-detected from the key prefix, backend reported in `/api/health`
- [x] **Gemini live** — AI Studio key working; parse and narrate both run on gemini-2.5-flash
- [x] Backend fallback: the key prefix does not identify the backend, so calls try the other
      endpoint once on PERMISSION_DENIED
- [ ] Comparison beat recorded: plain Gemini vs the agent (`scripts/compare.py` now runnable)

## Phase 3 — Submission
- [ ] 3-minute demo video (screen recording, functioning product)
- [x] Demo narration and recording checklist drafted (`DEMO_SCRIPT.md`)
- [x] Devpost write-up drafted: inspiration → product → implementation → challenges → learned → next (`SUBMISSION.md`)
- [x] ClickHouse selected as the submission track in the submission draft
- [x] Public repo pushed: https://github.com/srijavuppala/reel_crew
- [ ] Confirm GitHub displays the MIT license and set the repository About metadata
- [x] Hosted URL live and verified end to end
- [ ] Demo video public and in English
- [ ] Submit with buffer — not at 4:55pm

## Blocked on you
1. **Rotate the API key before this goes anywhere public** — it was shared in a chat transcript.
2. **Public demo video** — record from the stable Cloud Run URL.

## Open decisions from the PRD
1. Solo or team? Phases 1 and 2 parallelize cleanly (data/agent vs UI/deploy).
2. ClickHouse over Parallel — **confirmed**, and the ingest is already done.
3. SCRIPT → SCREEN as the "what's next" slide (screenplay breakdown → derived crew
   requirements → auto-staffed production). Costs nothing to say, strong closer.
