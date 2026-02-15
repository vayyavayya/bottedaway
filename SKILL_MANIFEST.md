#!/usr/bin/env python3
"""
SKILL MANIFEST - Standard Operating Procedure
Skill-Based Shell Agent Architecture

HIERARCHY:
==========
1. THE SHELL (Container)
   - Check dependencies before answering
   - Run scripts/tools to get real answers
   - Never assume — always verify

2. THE SKILLS (/skills/)
   - Every repeatable task encoded as a Skill
   - Skills are executable, documented, versioned
   - When to use / when NOT to use (negative examples)

3. THE MEMORY (/mnt/data/)
   - Artifacts live here (reports, code, designs)
   - Handoff boundary between sessions
   - Compact context when long, never just forget

EXECUTION RULES:
================
1. Description over marketing
   - Tell exactly when to use and when NOT to
   - Document failures as negative examples

2. Artifacts first
   - All outputs saved to /mnt/data/
   - Assume this folder is our handoff boundary

3. Check before answering
   - Do I need to install something?
   - Do I need to run a script?
   - Get the REAL answer, not the assumed one

SKILL INVENTORY:
================

/crypto/
--------
[✓] memecoin-scanner    - Multi-source memecoin discovery (4-10 days, $100K-$500K MC)
[✓] ema-monitor         - EMA50 breakdown alerts for specific tokens
[✗] price-monitor       - TODO: Real-time price alerts (any token)
[✗] watchlist-manager   - TODO: CRUD operations for watchlist
[✗] trading-simulator   - TODO: Paper trading with alerts

/automation/
------------
[✓] cron-manager        - OpenClaw cron job management
[✗] git-sync            - TODO: Automated commit/push workflow
[✗] heartbeat-checker   - TODO: Rotating system checks

/data/
------
[✗] csv-cleaner         - TODO: Data cleaning pipelines
[✗] json-transform      - TODO: JSON manipulation utilities
[✗] report-generator    - TODO: HTML/PDF report generation

/system/
--------
[✗] dependency-check    - TODO: Pre-flight dependency validation
[✗] skill-bootstrap     - TODO: Create new skill scaffolding

ACTIVE CRON JOBS:
=================
1. memecoin-scanner-720min   - Every 12h (Gemini Flash)
2. polyclaw-autotrader       - Every 4h (Kimi K2.5)
3. daily-watchlist-8am       - Daily 8am (MiniMax M2.5)
4. me-ema50-monitor-2h       - Every 2h (MiniMax M2.5)
5. moltbook-learning-2h      - Every 2h (Gemini Flash)

CURRENT WATCHLIST:
==================
- $ME (5 days, $336K MC, -38% dip)
- $Seedance (7 days, $175K MC, -19% dip)
- $PUP (4 days, $131K MC, +7% steady)

OPEN POSITIONS:
===============
- Fed rate cut (March): $5 YES @ $0.065 → Currently -93%, worthless

COMPACTION STATE:
=================
Last compacted: 2026-02-15 18:47 UTC
Context size: 77k/262k (29%)
Session ID: agent:main:main

---
To add a skill: See /skills/system/skill-bootstrap (TODO)
To modify: Edit skill README.md first, then code
To archive: Move to /skills/.archive/ with date prefix
