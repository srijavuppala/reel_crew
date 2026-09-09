# Script → Screen — Production Workspace PRD

## Product thesis

Reel Crew becomes the crew-intelligence layer inside a shared production operating
system. A producer supplies a screenplay, budget, and deadline. The system converts
them into one versioned production plan connecting scenes, schedule, departments,
crew needs, budget, risks, and changes.

This is not accounting software and it does not invent quotes, availability, rates,
contracts, or legal terms. Early estimates are planning allowances, visibly labeled
as estimates. Actual costs arrive only from authorized production users or connected
finance systems.

## Users

- Producer / line producer: owns budget, schedule, approvals, and tradeoffs.
- Unit production manager: turns the plan into daily execution.
- First assistant director: owns stripboard order, call sheets, and schedule changes.
- Department head: sees assigned scenes, requirements, allowance, and open decisions.
- Production accountant: imports approved commitments and actuals, then reconciles variance.

## Core workflow

```text
Screenplay + budget + target days
  → scene breakdown
  → schedule and department requirements
  → top-sheet budget and contingency
  → risks and unresolved assumptions
  → crew discovery for each department (existing Reel Crew engine)
  → approved plan
  → changes produce a new version and variance report
```

## Phase 0 — Production brief (implemented)

One request creates a deterministic first-pass plan containing:

- scene headings, INT/EXT, location, day/night, estimated page count;
- grouped shoot days with page-load warnings;
- a top-sheet budget across cast, crew, locations, equipment, art, travel,
  post-production, insurance/legal, and contingency;
- department allowances and cost per shoot day;
- operational risks and explicit assumptions;
- a change-impact preview for a reduced budget or reduced shoot-day target.

Success: a producer can paste a short screenplay excerpt and receive a coherent,
internally balanced plan in under one second without model-generated arithmetic.

## Phase 1 — Crew plan

- Derive required departments and crew briefs from the scene breakdown.
- Run those briefs through the existing Gemini → ClickHouse Reel Crew workflow.
- Attach shortlisted people to departments and preserve the evidence behind each choice.
- Track unfilled roles and conflicts in the production workspace.

Success: every derived department has a searchable evidence-based staffing path.

## Phase 2 — Persistent finance and approvals

- Production/project accounts and role-based access.
- Versioned budget lines: estimate, committed, actual, variance.
- Purchase orders, petty cash, invoices, payroll-export placeholders, and approval states.
- CSV import/export and an audit log; no autonomous payments.
- Store production records in a transactional database; keep ClickHouse for analytics.

Success: totals reconcile, every change has an author and timestamp, and finance can
trace a dashboard number to source entries.

## Phase 3 — Scheduling and call sheets

- Drag/drop stripboard with cast, location, company move, turnaround, and page constraints.
- Availability calendars and conflict detection.
- Call-sheet generation with human approval and revision history.
- Weather/location integrations only from authorized sources.

Success: moving a scene updates affected people, locations, requirements, and estimated cost.

## Phase 4 — Agentic replanning

- Producer agent coordinates specialist analysis for schedule, budget, continuity,
  locations, staffing, and risk.
- Events such as “lead unavailable on day 7” create a proposed plan version and impact report.
- Hard constraints are deterministic; Gemini explains options and tradeoffs.
- A human approves every schedule, staffing, contract, or finance mutation.

Success: a disruption produces feasible alternatives, a complete change set, and no
silent mutation of the approved plan.

## Phase 5 — Production command center

- Daily progress, pages shot, schedule drift, cost variance, risk trend, and open approvals.
- Department-specific views over the same shared production record.
- Post-production handoff: footage, edit, VFX, sound, music, delivery milestones.
- Analytics in ClickHouse across plan versions and production events.

## Architecture boundaries

- Gemini/ADK: extraction, orchestration, explanations, and option generation.
- Deterministic Python: arithmetic, constraint validation, schedule feasibility, and change sets.
- ClickHouse: crew-credit search plus aggregate production analytics.
- Transactional database (Phase 2): projects, budgets, approvals, actuals, and audit history.
- Cloud Run: API and web product.

## Finance guardrails

- Estimated, committed, and actual money are separate fields and never conflated.
- Totals use decimal/fixed-point arithmetic, not floating-point model output.
- Every estimate states its assumptions and currency.
- No payment, contract, hiring, or approval action is autonomous.
- Changes create a new version; an approved baseline is immutable.

## Phase 0 API

`POST /api/production/plan`

Input: title, screenplay text, total budget, currency, target shoot days, optional
reduced budget, and optional revised shoot days.

Output: summary, scenes, schedule, budget lines, risks, assumptions, and change impact.
