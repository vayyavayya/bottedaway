import Database from "better-sqlite3";
import { drizzle } from "drizzle-orm/better-sqlite3";
import * as schema from "./schema";
import { mkdirSync } from "fs";
import { join } from "path";

// Ensure data directory exists
const dataDir = join(process.cwd(), "data");
try {
  mkdirSync(dataDir, { recursive: true });
} catch {}

const sqlite = new Database(join(dataDir, "mission-control.db"));
export const db = drizzle(sqlite, { schema });

// Initialize tables if they don't exist
sqlite.exec(`
  CREATE TABLE IF NOT EXISTS scanner_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    token_symbol TEXT NOT NULL,
    token_name TEXT,
    chain TEXT NOT NULL,
    address TEXT NOT NULL,
    market_cap REAL,
    price REAL,
    liquidity REAL,
    volume_24h REAL,
    change_24h REAL,
    source TEXT NOT NULL,
    score_engine_a REAL,
    score_engine_b REAL,
    score_engine_c REAL,
    notes TEXT,
    created_at INTEGER DEFAULT (unixepoch())
  );

  CREATE TABLE IF NOT EXISTS whale_wallets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT NOT NULL UNIQUE,
    label TEXT,
    network TEXT NOT NULL,
    confidence REAL,
    added_at INTEGER,
    notes TEXT
  );

  CREATE TABLE IF NOT EXISTS whale_buys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    token_symbol TEXT NOT NULL,
    token_address TEXT NOT NULL,
    amount REAL,
    value_usd REAL,
    score REAL,
    alerted INTEGER DEFAULT 0
  );

  CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'backlog',
    assignee TEXT,
    priority TEXT DEFAULT 'medium',
    due_date INTEGER,
    created_at INTEGER DEFAULT (unixepoch()),
    updated_at INTEGER DEFAULT (unixepoch()),
    tags TEXT
  );

  CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    schedule TEXT NOT NULL,
    description TEXT,
    last_run INTEGER,
    next_run INTEGER,
    status TEXT DEFAULT 'active',
    channel TEXT
  );

  CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT,
    created_at INTEGER DEFAULT (unixepoch())
  );

  CREATE TABLE IF NOT EXISTS cost_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    model TEXT NOT NULL,
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd REAL,
    session_id TEXT
  );

  CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    description TEXT,
    avatar TEXT,
    status TEXT DEFAULT 'idle',
    current_task TEXT,
    skills TEXT
  );
`);

// Insert default agents
const defaultAgents = [
  {
    name: "nadeshan",
    role: "main",
    description: "Primary assistant for bigbrother",
    avatar: "🤖",
    status: "working",
    current_task: "Mission Control development",
    skills: JSON.stringify(["trading", "infrastructure", "automation"]),
  },
];

const insertAgent = sqlite.prepare(`
  INSERT OR IGNORE INTO agents (name, role, description, avatar, status, current_task, skills)
  VALUES (?, ?, ?, ?, ?, ?, ?)
`);

defaultAgents.forEach((agent) => {
  insertAgent.run(
    agent.name,
    agent.role,
    agent.description,
    agent.avatar,
    agent.status,
    agent.current_task,
    agent.skills
  );
});

console.log("✅ Database initialized");
