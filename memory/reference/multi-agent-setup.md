# Multi-Agent PolyClaw with Supabase

Full multi-agent trading system with Supabase backend for coordination.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      SUPABASE BACKEND                        │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  agent_jobs  │agent_messages│ agent_status │trade_opportunities│
│  (Queue)     │  (Messaging) │  (Health)    │  (Pipeline)    │
└──────────────┴──────────────┴──────────────┴────────────────┘
         ▲              ▲              ▲              ▲
         │              │              │              │
    ┌────┴────┐    ┌────┴────┐    ┌────┴────┐    ┌────┴────┐
    │ SCANNER │    │ TRADER  │    │RESEARCHER│   │COORDINATOR│
    │  Agent  │───▶│  Agent  │◀───│  Agent   │   │  Agent   │
    └─────────┘    └─────────┘    └──────────┘   └──────────┘
         │                                               │
         │         ┌─────────────────┐                   │
         └────────▶│  POLYCLAW CLI   │◀──────────────────┘
                   │  (Trading)      │
                   └─────────────────┘
```

## Agent Types

| Agent | Role | Actions |
|-------|------|---------|
| **Scanner** | Finds opportunities | Scans markets → Creates jobs |
| **Trader** | Executes trades | Claims jobs → Executes trades |
| **Researcher** | Deep analysis | Research specific markets |
| **Coordinator** | System health | Monitors all agents, escalates issues |

## Quick Start

### 1. Setup Supabase

```bash
# Install Supabase client
pip install supabase

# Set environment variables
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_KEY="your-service-role-key"
```

### 2. Create Database

Run the SQL schema:
```bash
psql $DATABASE_URL -f supabase/agent_coordination_schema.sql
```

Or use Supabase Dashboard → SQL Editor → New Query → Paste schema.

### 3. Run Agents

**Scanner Agent** (finds opportunities):
```bash
export AGENT_MODE=scanner
export ENABLE_SUPABASE=true
python scripts/polyclaw-multi-agent.py
```

**Trader Agent** (executes trades):
```bash
export AGENT_MODE=trader
export ENABLE_SUPABASE=true
export LIVE_TRADING=1
python scripts/polyclaw-multi-agent.py
```

**Coordinator Agent** (monitors health):
```bash
export AGENT_MODE=coordinator
export ENABLE_SUPABASE=true
python scripts/polyclaw-multi-agent.py
```

## Database Schema

### Tables

| Table | Purpose |
|-------|---------|
| `agent_jobs` | Job queue with priorities |
| `agent_messages` | Agent-to-agent messaging |
| `agent_status` | Health monitoring |
| `trade_opportunities` | Discovered trade opportunities |
| `trade_executions` | Trade execution log |
| `agent_performance` | Performance metrics |
| `system_config` | Global configuration |

### Key Features

- **Realtime**: All tables publish changes for live updates
- **RLS**: Row-level security enabled
- **Functions**: `claim_next_job()`, `complete_job()`, `broadcast_message()`
- **Views**: Dashboard views for monitoring

## Workflow

### 1. Scanner Discovers Opportunity

```python
# Scanner agent
scanner.create_opportunity(
    market_id="12345",
    market_question="Will BTC reach $100K?",
    side="YES",
    confidence=0.75,
    edge=0.12,
    research_summary="Bullish sentiment..."
)
# → Creates trade_opportunity + agent_job
```

### 2. Trader Claims Job

```python
# Trader agent
job = trader.claim_job()  # Gets next pending job
# → Executes trade via PolyClaw
# → Logs to trade_executions
# → Completes job
```

### 3. Coordinator Monitors

```python
# Coordinator agent
coordinator.run_health_check()
# → Checks stale agents
# → Dispatches stuck jobs
# → Broadcasts alerts
```

## Monitoring

### Views Available

```sql
-- Active jobs
SELECT * FROM v_active_jobs;

-- Agent dashboard
SELECT * FROM v_agent_dashboard;

-- Opportunity pipeline
SELECT * FROM v_opportunity_pipeline;

-- Daily performance
SELECT * FROM v_daily_performance;
```

### Alerting

Agents automatically broadcast on:
- New opportunities (high priority)
- Agent blocked/error
- System config changes
- Health check issues

## Scaling

**Multiple instances of each agent type:**

```bash
# Terminal 1: Scanner
cd /workspace && AGENT_MODE=scanner python scripts/polyclaw-multi-agent.py

# Terminal 2: Trader 1
cd /workspace && AGENT_MODE=trader python scripts/polyclaw-multi-agent.py

# Terminal 3: Trader 2
cd /workspace && AGENT_MODE=trader python scripts/polyclaw-multi-agent.py

# Terminal 4: Coordinator
cd /workspace && AGENT_MODE=coordinator python scripts/polyclaw-multi-agent.py
```

All coordinate through Supabase job queue.

## Integration with Existing Setup

Your current `polyclaw-autotrader.py` works alongside this:
- Keep it for simple single-agent mode
- Use multi-agent for complex coordination
- Both share the same wallet and config

## Security

- Use **service role key** for agents (bypasses RLS)
- Store keys in environment variables
- Never commit keys to git
- Rotate keys periodically

## Troubleshooting

**"Supabase coordinator not available"**
→ `pip install supabase`

**"Could not initialize Supabase"**
→ Check `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`

**"No trade jobs available"**
→ Run scanner first to create opportunities

**"Agent not registered"**
→ Check agent_status table in Supabase

## Cost

- **Supabase Free Tier**: Sufficient for small agent teams
- **Database**: ~500MB included
- **Realtime**: Included
- **API calls**: Generous limits

Upgrade to Pro when:
- > 10,000 jobs/day
- Need backups/point-in-time recovery
- > 5 agents running continuously

## Files

| File | Purpose |
|------|---------|
| `supabase/agent_coordination_schema.sql` | Database schema |
| `scripts/supabase_agent_coordinator.py` | Agent coordination library |
| `scripts/polyclaw-multi-agent.py` | Multi-agent entry point |

## Next Steps

1. Set up Supabase project
2. Run schema SQL
3. Set environment variables
4. Start scanner agent
5. Start trader agent(s)
6. Monitor in Supabase dashboard

## References

- Supabase Docs: https://supabase.com/docs
- Python Client: https://github.com/supabase/supabase-py
- Realtime: https://supabase.com/docs/guides/realtime
