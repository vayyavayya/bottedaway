# Agent Team Manifest

_Four specialized agents, one orchestrator._

## Architecture

```
bigbrother (you)
    ↓
nadeshan (orchestrator)
    ├──→ clawcoder (coding agent)
    ├──→ clawsec (security agent)
    ├──→ clawresearch (research agent)
    └──→ clawanalyst (analysis agent)
```

## Agent Directory Structure

```
agents/
├── coder/
│   ├── SOUL.md      # Who they are, boundaries
│   └── TOOLS.md     # What they can access
├── security/
│   ├── SOUL.md
│   └── TOOLS.md
├── researcher/
│   ├── SOUL.md
│   └── TOOLS.md
└── analyst/
    ├── SOUL.md
    └── TOOLS.md
```

## Agent Roles

### 1. clawcoder (Coder Agent) 💻
**Purpose:** Write clean, documented code
**Tools:** File ops, shell (local only), git
**Restrictions:** NO web access, NO deployment without approval
**Use for:** Scripts, refactoring, bug fixes, config files

**Example dispatch:**
```
Coder: Write a Python script that monitors NOOK price every hour
and sends Telegram alerts on >10% moves. Use Helius API.
```

### 2. clawsec (Security Agent) 🔒
**Purpose:** Monitor system for threats and violations
**Tools:** Read-only file system, log analysis, permission checks
**Restrictions:** NO modifications without approval, read-only audits
**Use for:** Daily security audits, credential checks, secret scanning

**Example dispatch:**
```
Security: Run a full audit. Check credential file permissions,
scan for exposed API keys in code, review recent commits.
```

### 3. clawresearch (Research Agent) 🔍
**Purpose:** Gather information from approved external sources
**Tools:** web_search, web_fetch, browser
**Restrictions:** NEVER share internal context externally, cite sources
**Use for:** Market research, competitor analysis, finding alternatives

**Example dispatch:**
```
Researcher: Find Base L2 prediction markets as alternatives to 
Polymarket. What's the current landscape? Who are the players?
```

### 4. clawanalyst (Analysis Agent) 📊
**Purpose:** Analyze prediction markets, crypto assets, and market sentiment. Runs sentiment analysis, plays devil's advocate, and provides data-driven insights.
**Tools:** web_search, web_fetch, data analysis
**Restrictions:** NEVER trades, NO credentials/access to trading accounts, produces analysis only (no actions)
**Use for:** Market edge analysis, prediction market evaluation, sentiment scoring, risk assessment

**Example dispatch:**
```
Analyst: What's the edge on this Polymarket election market?
```

**Cost Limits:**
- $0.50 per analysis
- $10/day maximum

## Orchestrator Role

**nadeshan** coordinates the team:
- Classifies incoming requests
- Dispatches to appropriate agent(s)
- Synthesizes results
- Reports back to bigbrother

## Communication Flow

1. **bigbrother** asks orchestrator something
2. **orchestrator** decides which agent(s) to spawn
3. **agent(s)** do the work, report back
4. **orchestrator** synthesizes and delivers final answer

## Spawning Agents

To dispatch a task:
```
sessions_spawn(
    agentId="orchestrator",  # Use orchestrator to dispatch
    task="Coder: Write a script that...",
    mode="run"
)
```

Or directly (for isolated tasks):
```
sessions_spawn(
    task="Research Base prediction markets",
    mode="run",
    # Agent type inferred from task
)
```

## Security Model

- **Coder:** No web access = reduced attack surface
- **Security:** Read-only = can't break things while auditing
- **Researcher:** Isolated context = internal data never leaks
- **Analyst:** Analysis-only = no trading credentials or actions
- **Orchestrator:** Coordinates, doesn't have full access to all tools

## Cost Control

| Agent | Cost Limit | Typical Cost |
|-------|------------|--------------|
| Coder | $2/task | $0.50-1.50 |
| Security | $1/audit | $0.10-0.50 |
| Researcher | $3/task | $1-2 |
| Analyst | $0.50/analysis | $0.20-0.40 |

## Daily Operations

- **2am:** Security agent runs full audit (automated)
- **On demand:** Coder writes/modifies code
- **On demand:** Researcher gathers information
- **On demand:** Analyst evaluates markets and opportunities
- **Always:** Orchestrator coordinates

---

_Created: March 2, 2026_  
_Pattern: The First 72 Hours with OpenClaw guide_
