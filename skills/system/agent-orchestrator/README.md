# Skill: agent-orchestrator

## Description
Spawn sub-agents for tasks instead of doing work directly. Main agent coordinates, monitors, and relays while sub-agents execute. Keeps main agent responsive for user conversation.

## When to Use
- Task takes longer than 30 seconds
- Task can fail and needs retry logic
- User might want to interrupt or ask questions mid-task
- Multiple independent tasks can run in parallel
- Task is CPU/network intensive (scraping, analysis, generation)

## When NOT to Use
- Task completes in <10 seconds (overhead not worth it)
- Task requires interactive user input throughout
- Task is purely conversational (no external work)
- Task is critical path and cannot tolerate spawning overhead

## Pattern: Spawn → Monitor → Relay

### 1. Spawn
```python
# Main agent spawns sub-agent
session = sessions_spawn(
    task="Detailed task description",
    agentId="main",
    timeoutSeconds=300
)
```

### 2. Monitor
```python
# Check progress without blocking conversation
sessions_list(activeMinutes=5)
sessions_history(sessionKey=session_key, limit=10)
```

### 3. Relay
```python
# When sub-agent completes, relay results to user
# User never lost contact with main agent
```

## Negative Examples (Failures)

### 1. Direct Execution Blocks User
**What happened**: Ran memecoin scanner directly, took 60 seconds. User couldn't interrupt or ask questions.

**Fix**: Spawn scanner as sub-agent. Main agent stays responsive.

### 2. Failed Task Lost State
**What happened**: Direct API call failed mid-way. No retry, no state saved. Had to restart from scratch.

**Fix**: Sub-agent runs in isolated session. If it fails, main agent sees it and can respawn.

### 3. Overwhelmed Main Agent
**What happened**: Tried to run scanner + watchlist bridge + report generation sequentially. Main agent slow, user frustrated.

**Fix**: Spawn 3 sub-agents in parallel. Main agent coordinates.

## Implementation

### For Long Tasks
```
User: "Scan all memecoins"
Main: "Spawning scanner agent..." → sessions_spawn()
Main: "Checking progress..." (every 30s)
Main: "Relaying results..." → user gets summary
```

### For Parallel Tasks
```
User: "Analyze these 5 coins"
Main: Spawns 5 sub-agents (one per coin)
Main: Monitors all 5
Main: Relays consolidated results
```

### For Retry Logic
```
sub_agent = sessions_spawn(task="API call")
if sub_agent.status == "failed":
    log("Retry 1/3...")
    sub_agent = sessions_spawn(task="API call")  # Retry
```

## Handoff Protocol

When context compacts:
1. Save sub-agent session keys to state
2. Document running tasks in SKILL_MANIFEST
3. Note: "User prefers spawn pattern - main agent coordinates only"

## Current Spawn Patterns in Use

| Task | Before | After (Target) |
|------|--------|----------------|
| Memecoin scan | Direct 60s run | Spawn scanner agent |
| Watchlist bridge | Direct execution | Spawn bridge agent |
| EMA monitor check | Direct API calls | Already in cron (ok) |
| Report generation | Direct HTML gen | Spawn report agent |

## Migration Plan

1. Document spawn patterns in each skill README
2. Add `spawn_mode: true` to skill config
3. Main agent checks config before executing
4. Gradually migrate direct calls to spawn pattern
