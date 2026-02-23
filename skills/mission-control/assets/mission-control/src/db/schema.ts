import { sqliteTable, text, integer, real } from "drizzle-orm/sqlite-core";
import { sql } from "drizzle-orm";

// Scanner Results
export const scannerResults = sqliteTable("scanner_results", {
  id: integer("id").primaryKey(),
  timestamp: integer("timestamp", { mode: "timestamp" }).notNull(),
  tokenSymbol: text("token_symbol").notNull(),
  tokenName: text("token_name"),
  chain: text("chain").notNull(),
  address: text("address").notNull(),
  marketCap: real("market_cap"),
  price: real("price"),
  liquidity: real("liquidity"),
  volume24h: real("volume_24h"),
  change24h: real("change_24h"),
  source: text("source").notNull(), // dexscreener, birdeye
  scoreEngineA: real("score_engine_a"),
  scoreEngineB: real("score_engine_b"),
  scoreEngineC: real("score_engine_c"),
  notes: text("notes"),
  createdAt: integer("created_at", { mode: "timestamp" }).default(sql`(unixepoch())`),
});

// Whale Tracker
export const whaleWallets = sqliteTable("whale_wallets", {
  id: integer("id").primaryKey(),
  address: text("address").notNull().unique(),
  label: text("label"),
  network: text("network").notNull(),
  confidence: real("confidence"),
  addedAt: integer("added_at", { mode: "timestamp" }),
  notes: text("notes"),
});

export const whaleBuys = sqliteTable("whale_buys", {
  id: integer("id").primaryKey(),
  walletId: integer("wallet_id").notNull(),
  timestamp: integer("timestamp", { mode: "timestamp" }).notNull(),
  tokenSymbol: text("token_symbol").notNull(),
  tokenAddress: text("token_address").notNull(),
  amount: real("amount"),
  valueUsd: real("value_usd"),
  score: real("score"),
  alerted: integer("alerted", { mode: "boolean" }).default(false),
});

// Tasks
export const tasks = sqliteTable("tasks", {
  id: integer("id").primaryKey(),
  title: text("title").notNull(),
  description: text("description"),
  status: text("status").notNull().default("backlog"), // backlog, in_progress, review, done
  assignee: text("assignee"), // user or agent name
  priority: text("priority").default("medium"), // low, medium, high, urgent
  dueDate: integer("due_date", { mode: "timestamp" }),
  createdAt: integer("created_at", { mode: "timestamp" }).default(sql`(unixepoch())`),
  updatedAt: integer("updated_at", { mode: "timestamp" }).default(sql`(unixepoch())`),
  tags: text("tags"), // JSON array
});

// Calendar / Cron Jobs
export const scheduledJobs = sqliteTable("scheduled_jobs", {
  id: integer("id").primaryKey(),
  name: text("name").notNull(),
  schedule: text("schedule").notNull(), // cron expression or "every 12h"
  description: text("description"),
  lastRun: integer("last_run", { mode: "timestamp" }),
  nextRun: integer("next_run", { mode: "timestamp" }),
  status: text("status").default("active"), // active, paused, error
  channel: text("channel"), // discord channel for alerts
});

// Memory / Daily Notes
export const memories = sqliteTable("memories", {
  id: integer("id").primaryKey(),
  date: text("date").notNull(), // YYYY-MM-DD
  category: text("category").notNull(), // decision, learning, event, task
  content: text("content").notNull(),
  tags: text("tags"), // JSON array
  createdAt: integer("created_at", { mode: "timestamp" }).default(sql`(unixepoch())`),
});

// Cost Tracking
export const costLogs = sqliteTable("cost_logs", {
  id: integer("id").primaryKey(),
  timestamp: integer("timestamp", { mode: "timestamp" }).notNull(),
  model: text("model").notNull(),
  tokensIn: integer("tokens_in"),
  tokensOut: integer("tokens_out"),
  costUsd: real("cost_usd"),
  sessionId: text("session_id"),
});

// Agents / Team
export const agents = sqliteTable("agents", {
  id: integer("id").primaryKey(),
  name: text("name").notNull(),
  role: text("role").notNull(), // developer, writer, designer, researcher
  description: text("description"),
  avatar: text("avatar"), // emoji or image path
  status: text("status").default("idle"), // idle, working, busy
  currentTask: text("current_task"),
  skills: text("skills"), // JSON array
});
