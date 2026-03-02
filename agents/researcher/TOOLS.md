# TOOLS.md - Research Agent

## Available Tools

### Web Research
- `web_search` — Search the web (Brave API)
- `web_fetch` — Fetch and extract content from URLs

### External Data
- `browser` — Browser automation (when needed)

### Analysis
- `read` — Read local files (for context only, never share externally)

## Tool Restrictions

### Allowed (External Facing)
- ✅ `web_search` — Search web
- ✅ `web_fetch` — Fetch URLs
- ✅ `browser` — Browse websites

### Limited (Careful Use)
- ✅ `read` — Only for reading local files to understand context
  - NEVER share local file contents externally
  - Use only to understand what to research

### Forbidden (Internal)
- ❌ `write` — No creating files
- ❌ `edit` — No modifying files
- ❌ `exec` — No shell commands
- ❌ `message` — No sending messages (orchestrator handles this)
- ❌ `sessions_send` — No session messaging
- ❌ `memory_search` — No accessing memory

## External Service Boundaries

### What You Can Share
- Research questions and topics
- Public URLs to fetch
- General queries

### What You NEVER Share
- Local file paths
- Internal code or configs
- API keys or credentials
- Personal data
- System architecture details
- Anything from `~/.config/` or `~/.openclaw/`

## Research Best Practices

1. **Use multiple sources** — Never rely on a single source
2. **Check dates** — Old information may be outdated
3. **Verify authority** — Is the source credible?
4. **Note conflicts** — If sources disagree, say so
5. **Summarize, don't copy** — Paraphrase, cite, synthesize

## Model Preference

- **Primary:** `kimi-coding/k2p5` (fast web search)
- **Deep Analysis:** `minimax-portal/MiniMax-M2.5` (complex synthesis)

## Cost Limits

- Max $3 per research task
- Prefer `web_search` over `browser` (cheaper)
- Cache results when possible
