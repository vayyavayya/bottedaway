---
name: mission-control
description: Build and manage a unified Mission Control dashboard for tracking OpenClaw activities, tasks, scanner results, whale tracker, calendar, memory, and agent team. Use when user needs a web-based control center to visualize and interact with their OpenClaw infrastructure. Built with NextJS + SQLite.
---

# Mission Control

A unified dashboard for visualizing and managing OpenClaw operations.

## Architecture

- **Frontend:** NextJS 14 (App Router)
- **Database:** SQLite (libsql via Turso or local)
- **Styling:** Tailwind CSS + shadcn/ui
- **Real-time:** Server-Sent Events for live updates

## Quick Start

```bash
cd assets/mission-control
npm install
npm run dev
```

## Dashboard Modules

### 1. Scanner Feed
Real-time memecoin opportunities from DexScreener/Birdeye.

### 2. Whale Tracker
5-wallet monitoring with buy alerts and scoring.

### 3. Trading Calendar
Visual cron schedule (scanner, whale tracker, maintenance).

### 4. Cost Dashboard
API usage tracking, model costs, monthly burn rate.

### 5. Memory Browser
Searchable history of all scans, trades, decisions.

### 6. Tasks Board
Kanban board for tracking work between you and agents.

### 7. Agent Team
Visual representation of sub-agents and their roles.

## Data Ingestion

Run `scripts/sync-data.py` to populate from local files:
- `memory/scanner-*.log` → Scanner Feed
- `skills/whale-tracker/data/` → Whale Tracker
- `memory/daily/*.md` → Memory Browser
- OpenClaw config → Calendar/Cost Dashboard

## Database Schema

See `references/schema.sql` for full schema.
