# Mission Control

A unified dashboard for tracking OpenClaw operations — scanner results, whale tracker, calendar, tasks, memory, costs, and team.

## Quick Start

```bash
# Navigate to the project
cd ~/.openclaw/workspace/skills/mission-control/assets/mission-control

# Install dependencies
npm install

# Initialize the database (creates SQLite DB with schema)
npm run db:push
# OR if that doesn't work:
python3 ../../scripts/sync-data.py

# Start the development server
npm run dev
```

Open http://localhost:3000 in your browser.

## Features

| Module | Description |
|--------|-------------|
| **Overview** | Dashboard with key stats, recent activity |
| **Scanner Feed** | Memecoin opportunities from DexScreener/Birdeye |
| **Whale Tracker** | 5-wallet monitoring with buy alerts |
| **Calendar** | Visual cron job schedule |
| **Tasks Board** | Kanban board for tracking work |
| **Memory Browser** | Searchable history of decisions/events |
| **Cost Dashboard** | API usage tracking, model costs |
| **Team** | Agent roster with roles and skills |

## Data Sync

To populate the database with your existing OpenClaw data:

```bash
# Run the sync script
python3 ../../scripts/sync-data.py
```

This imports:
- Whale wallets from `skills/whale-tracker/data/whales/whales.json`
- Scanner logs from `memory/scanner-*.log`
- Scheduled jobs from your OpenClaw config

## Architecture

- **Frontend:** NextJS 14 (App Router) + React + TypeScript
- **Styling:** Tailwind CSS
- **Database:** SQLite (better-sqlite3)
- **ORM:** Drizzle ORM

## Tech Stack

- NextJS 14
- React 18
- TypeScript 5
- Tailwind CSS
- Drizzle ORM
- better-sqlite3

## Development

```bash
# Run dev server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

## Screenshots

The dashboard includes:
- Dark theme optimized for trading/monitoring
- Real-time stats and activity feeds
- Responsive layout
- Modular architecture for easy extension

## Future Enhancements

- [ ] Real-time WebSocket updates
- [ ] Scanner log parser (structured data import)
- [ ] Cost tracking API integration
- [ ] Trading journal integration
- [ ] Alert notifications
- [ ] Mobile-responsive sidebar

## Notes

This is a custom-built dashboard for your specific OpenClaw setup. The database schema and components are designed around your crypto trading workflow.
