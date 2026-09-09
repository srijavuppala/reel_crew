---
created: 2026-09-09T02:46:48.734Z
title: Unify screenplay production entry flow
area: ui
files:
  - web/index.html:400
  - production/planner.py:1
  - api/main.py:1
---

## Problem

Crew discovery and production planning currently feel like adjacent tools. The product needs one clear story: start with a screenplay, derive production requirements, then move into crew, schedule, budget, and risks.

## Solution

Create a Start Production flow that accepts a screenplay, returns a production brief and required departments, and becomes the shared project context for every workspace page.
