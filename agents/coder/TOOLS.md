# TOOLS.md - Coder Agent

## Available Tools

### File Operations
- `read` — Read file contents
- `write` — Create/overwrite files
- `edit` — Make precise edits to files

### Shell Operations
- `exec` — Run shell commands (local only)
- `process` — Manage background processes

### Version Control
- `exec` (git commands) — Commit, push, pull

## Tool Restrictions

### Forbidden (Security)
- ❌ `web_search` — No web access
- ❌ `web_fetch` — No fetching URLs
- ❌ `browser` — No browser automation
- ❌ `nodes` — No remote device access
- ❌ `message` — No sending messages (orchestrator handles this)

### Allowed (Local Only)
- ✅ File system operations
- ✅ Local git commands
- ✅ Local Python/Node execution
- ✅ Testing scripts locally

## Working Directory

All work happens within the workspace:
```
/Users/pterion2910/.openclaw/workspace/
```

## Security Protocol

1. **Never** write API keys or secrets to code
2. Use environment variables or credential files
3. If you see a secret in code, flag it immediately
4. Prefer `trash` over `rm` for recoverability

## Model Preference

- **Primary:** `kimi-coding/k2p5` (cost-effective, good for coding)
- **Fallback:** `minimax-portal/MiniMax-M2.5` (complex refactoring)

## Cost Limits

- Max $2 per task
- Alert orchestrator if approaching limit
