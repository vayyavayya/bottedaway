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
[✓] cron-manager              - OpenClaw cron job management
[✓] scanner-watchlist-bridge  - Auto-add scanner finds to watchlist
[✓] morning-briefing          - Daily 8 AM crypto briefing (NEW)
[✗] git-sync                  - TODO: Automated commit/push workflow
[✗] heartbeat-checker         - TODO: Rotating system checks

/data/
------
[✗] csv-cleaner         - TODO: Data cleaning pipelines
[✗] json-transform      - TODO: JSON manipulation utilities
[✗] report-generator    - TODO: HTML/PDF report generation

/system/
--------
[✓] skill-bootstrap       - Create new skill scaffolding
[✓] agent-orchestrator    - Spawn sub-agents, keep main responsive
[✓] git-backup            - Auto-backup to GitHub every 2h (NEW)
[✗] dependency-check      - TODO: Pre-flight dependency validation

ACTIVE CRON JOBS:
=================
1. memecoin-scanner-720min   - Every 12h → @pumpepump
2. polyclaw-autotrader       - DISABLED
3. morning-briefing-8am      - Daily 8am → @sasimestri (NEW)
4. daily-watchlist-8am       - Daily 8am → @sasimestri
5. me-ema50-monitor-2h       - DISABLED (position worthless)
6. selfclaw-ema50-monitor-2h - DISABLED (removed)
7. moltbook-learning-24h     - Daily midnight (MiniMax M2.5)
8. diary-telegram-update     - Daily 9am → @sasimestri
9. git-auto-backup-2h        - Every 2h [FIXED]

CURRENT WATCHLIST:
==================
- $Seedance (7 days, $174K MC, -29% dip)
- $PUP (4 days, $166K MC, +42% steady — Engine A)
- $LEO (4-10 days, $364K MC, +378% parabolic — Engine B+C)
- $TROPHY (Solana, $2M MC, -33% pullback — Multiple EMA50 holds)

OPEN POSITIONS:
===============
- Fed rate cut (March): $5 YES @ $0.065 → Currently -93%, worthless

AGENT ARCHITECTURE PRINCIPLES:
==============================
From Moltbook/agent network (Feb 15, 2026):

1. MAIN AGENT = COORDINATOR
   - Never do work directly
   - Spawn sub-agents for tasks
   - Monitor and relay
   - Stay responsive to user

2. SUB-AGENTS = WORKERS
   - Execute the actual task
   - Can fail independently
   - Can be retried/relaunched
   - Run in isolated sessions

3. PATTERN: Spawn → Monitor → Relay
   - User never loses contact with main
   - Failed tasks don't block conversation
   - Parallel execution possible

MIGRATION STATUS:
=================
[✗] memecoin-scanner    - Still direct (TODO: spawn pattern)
[✗] scanner-bridge      - Still direct (TODO: spawn pattern)
[✓] cron jobs           - Already use isolated sessions (good!)
[✗] report generation   - Still direct (TODO: spawn pattern)

User preference: SPAWN PATTERN for all new work

COMPACTION STATE:
=================
Last compacted: 2026-02-15 18:47 UTC
Context size: 77k/262k (29%)
Session ID: agent:main:main

---
To add a skill: See /skills/system/skill-bootstrap/create.py
To modify: Edit skill README.md first, then code
To archive: Move to /skills/.archive/ with date prefix
To spawn work: See /skills/system/agent-orchestrator/README.md
