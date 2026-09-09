---
created: 2026-09-09T02:46:48.734Z
title: Build evidence-backed crew agent
area: api
files:
  - agent/graph.py:1
  - agent/queries.py:1
  - agent/narrate.py:1
  - web/index.html:1
---

## Problem

Users must manually search one role at a time. Reel Crew should infer which roles a screenplay needs, query ClickHouse for each craft, assemble a team, and explain every recommendation with match signals.

## Solution

Add Build My Crew orchestration, per-role candidate selection, match scores, credit-backed evidence, and an Explain Recommendation surface showing the ClickHouse funnel from candidate credits to shortlist.
