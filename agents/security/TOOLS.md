# TOOLS.md - Security Agent

## Available Tools

### File Operations (Read-Only Preferred)
- `read` — Read file contents
- `memory_search` — Search memory files for context
- `memory_get` — Read specific memory snippets

### Shell Operations (Read-Only)
- `exec` — Run read-only audit commands:
  - `ls -la` (check permissions)
  - `find` (locate files)
  - `grep` (search for patterns)
  - `git log` (review commits)
  - `cat` (read logs)

### System Status
- `session_status` — Check current session/cost status
- `sessions_list` — Review active sessions

## Tool Restrictions

### Forbidden (Modification)
- ❌ `write` — No creating files
- ❌ `edit` — No modifying files
- ❌ `exec` with modification commands (rm, chmod, chown)
- ❌ `process` — No process management
- ❌ `sessions_send` — No sending messages to sessions

### Allowed (Monitoring Only)
- ✅ Reading files and logs
- ✅ Checking permissions
- ✅ Searching for patterns
- ✅ Listing directory contents
- ✅ Reviewing git history

## Audit Commands

### Credential File Permissions
```bash
ls -la ~/.config/*/
find ~/.config -type f -perm +066
```

### Search for Secrets in Code
```bash
grep -r "api_key\|apikey\|secret\|password\|token" --include="*.py" --include="*.js" --include="*.env" .
```

### Check Recent Commits
```bash
git log --oneline -20
```

### Review Cron Logs
```bash
cat ~/.openclaw/logs/*.log 2>/dev/null | tail -100
```

## Working Directory

Audit scope:
```
/Users/pterion2910/.openclaw/
/Users/pterion2910/.openclaw/workspace/
~/.config/
```

## Model Preference

- **Primary:** `kimi-coding/k2p5` (fast, cost-effective for audits)
- **Analysis:** `minimax-portal/MiniMax-M2.5` (complex log analysis)

## Cost Limits

- Max $1 per audit
- Should be mostly local commands ($0)
