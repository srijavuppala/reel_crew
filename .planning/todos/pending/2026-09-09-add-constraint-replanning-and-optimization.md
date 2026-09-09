---
created: 2026-09-09T02:46:48.734Z
title: Add constraint replanning and optimization
area: api
files:
  - production/planner.py:1
  - production/schema.py:1
  - web/index.html:1
---

## Problem

Production plans are static after generation. The demo needs an agentic change event—such as a budget reduction or unavailable crew member—that produces a transparent before-and-after plan.

## Solution

Support one deterministic constraint-change workflow first, then optimization objectives for cost, shoot days, location moves, risk, and crew continuity. Require producer approval before accepting a revised baseline.
