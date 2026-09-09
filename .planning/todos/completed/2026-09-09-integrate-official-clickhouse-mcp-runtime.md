---
created: 2026-09-09T02:46:48.734Z
title: Integrate official ClickHouse MCP runtime
area: database
files:
  - agent/config.py:9
  - agent/queries.py:1
  - api/main.py:49
  - requirements.txt:1
---

## Problem

Reel Crew currently calls ClickHouse Cloud through `clickhouse-connect`. The hackathon feedback says the ClickHouse track requires active runtime use through the official `mcp-clickhouse` server, so the current direct-client architecture may be an eligibility risk.

## Solution

Verify the current hackathon rule and implement an official MCP-backed ClickHouse runtime adapter while preserving parameter validation, query evidence, health reporting, and a safe local-development path. Make the MCP request visible in the product trace and repository documentation.
