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

## Phase 2 — Design and impact  ◑ in progress
- [x] Empty and error states written as product copy, not stack traces
- [x] Keyboard access, focus states, reduced-motion, mobile breakpoint
- [x] `Dockerfile` + `scripts/deploy_cloudrun.sh`
- [ ] **Deploy to Cloud Run and capture the hosted URL** — needs `gcloud` (not installed) + a GCP project
- [ ] Comparison beat recorded: plain Gemini vs the agent (`scripts/compare.py` written, needs `GOOGLE_API_KEY`)

## Phase 3 — Submission
- [ ] 3-minute demo video (screen recording, functioning product)
- [ ] Devpost write-up: inspiration → what it does → how we built it → challenges → learned → next
- [ ] Select the ClickHouse track explicitly
- [ ] Public repo pushed, LICENSE detectable in the About section
- [ ] Hosted URL live, video public and in English
- [ ] Submit with buffer — not at 4:55pm

## Blocked on you
1. **`GOOGLE_API_KEY`** — paste into `.env`. Everything runs without it; the key upgrades
   parsing and narration from deterministic to Gemini, and unlocks the comparison beat.
2. **GCP project + `gcloud`** — required for the Cloud Run deploy and the hosted URL the
   submission asks for.
3. **Push target** — repo is committed locally on `main`; tell me the GitHub remote and
   whether to push.

## Open decisions from the PRD
1. Solo or team? Phases 1 and 2 parallelize cleanly (data/agent vs UI/deploy).
2. ClickHouse over Parallel — **confirmed**, and the ingest is already done.
3. SCRIPT → SCREEN as the "what's next" slide (screenplay breakdown → derived crew
   requirements → auto-staffed production). Costs nothing to say, strong closer.
