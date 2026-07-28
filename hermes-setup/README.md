# Hermes Agent — Mac Studio + Telegram + Docker Sandbox

A complete, runnable setup for a full Hermes Agent that:

- **Runs on your Mac Studio** (Apple Silicon) as an always-on background service,
- is **controlled from Telegram** (chat with it from your phone anywhere),
- and executes every command the AI runs **inside a locked-down Docker
  container**, never directly on your Mac.

> **This README is the runbook.** Hand this whole `hermes-setup/` folder to
> Claude Cowork and tell it: *"Follow README.md to set up Hermes on this Mac."*
> Cowork can run every automated step; the four steps marked **🧑 MANUAL**
> need you (they involve external accounts, OAuth, or a GUI app).

---

## Architecture (why it's built this way)

```
  Telegram (your phone)
        │  bot API
        ▼
  ┌───────────────────────────────┐   Mac Studio (host)
  │  Hermes gateway (launchd svc) │   - always on, survives reboot/login
  │  Hermes agent + model client  │   - talks to Nous Portal / your LLM
  └───────────────┬───────────────┘
                  │ docker exec  (every terminal / execute_code call)
                  ▼
  ┌───────────────────────────────┐
  │  Sandbox container            │   - --cap-drop ALL, no-new-privileges
  │  python3.11 + node20          │   - pids-limit, tmpfs caps, mem/cpu caps
  │  /workspace  <-> ~/hermes-workspace
  └───────────────────────────────┘
```

The **gateway runs natively** (so it stays reachable and doesn't need
Docker-in-Docker), while the **agent's shell access is sandboxed**. This is the
security posture Nous's own docs recommend. If you instead want the *entire*
Hermes process inside a container too, see "Alternative" at the bottom — but on
macOS that forces Docker-in-Docker for the sandbox and is not recommended.

---

## Files in this folder

| File | What it is |
|------|------------|
| `README.md` | This runbook |
| `install-hermes.sh` | Installs Hermes, pulls the sandbox image, writes config, seeds `.env` |
| `config.yaml` | Hermes config — model + Docker terminal backend (copied to `~/.hermes/config.yaml`) |
| `.env.example` | Secrets template (copied to `~/.hermes/.env`) |
| `start-gateway.sh` | Installs + starts the always-on Telegram gateway service |
| `verify.sh` | Read-only health check |

Nothing here contains real secrets. Your real token/keys only ever live in
`~/.hermes/.env` on the Mac (chmod 600, never committed).

---

## Steps

### 🧑 MANUAL — Step 0: Prerequisites on the Mac Studio
1. **Docker Desktop** installed **and running** (menu-bar whale is steady, not
   animating). Alternative: `brew install colima && colima start`.
2. Command Line Tools present (`xcode-select --install` if `curl`/`git` missing).

### 🧑 MANUAL — Step 1: Create the Telegram bot
1. In Telegram, message **@BotFather** → `/newbot` → pick a name + a username
   ending in `bot`. Copy the **API token** it gives you.
2. Message **@userinfobot** → copy your **numeric user ID** (a number, not your
   @username).

### Step 2: Run the installer  *(Cowork can do this)*
```bash
cd hermes-setup
chmod +x *.sh
./install-hermes.sh
```
This installs Hermes, pulls the sandbox image, writes `~/.hermes/config.yaml`,
and seeds `~/.hermes/.env`.

### 🧑 MANUAL — Step 2b: Put your secrets in `.env`
Edit `~/.hermes/.env` and set the two values from Step 1:
```bash
TELEGRAM_BOT_TOKEN=<token from BotFather>
TELEGRAM_ALLOWED_USERS=<your numeric id>
```
(You can paste these to Cowork and let it write them, but treat the token as a
password — anyone with it controls the bot.)

### 🧑 MANUAL — Step 3: Authenticate a model provider
```bash
hermes setup      # choose "Quick Setup (Nous Portal)" → OAuth login in browser
```
This is interactive (browser OAuth) so a human clicks through it once.
Prefer your own key instead? Set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`, …)
in `~/.hermes/.env`, change `model:` in `config.yaml` accordingly, and run
`hermes model` to select it.

### Step 4: Start the always-on gateway  *(Cowork can do this)*
```bash
./start-gateway.sh
```
Installs the launchd service and starts it. From then on the bot is live and
survives reboots/logins.

### Step 5: Verify  *(Cowork can do this)*
```bash
./verify.sh
```
Every line should read `ok`. Then, on your phone: DM your bot `/start`, and send
`/sethome` in whatever group you want scheduled-task results delivered to.

---

## Day-to-day operation

```bash
hermes gateway status          # is the service running?
hermes gateway stop | start    # control it
hermes gateway install         # (re)install the launchd service
hermes pairing list            # authorized users
hermes pairing approve telegram <CODE>   # let a new user in (they DM the bot, get a code)
hermes doctor                  # diagnostics
docker ps                      # see the live sandbox container
```

Everything the agent writes to `/workspace` appears on your Mac under
`~/hermes-workspace` — inspect its output there.

---

## What you can do with it once it's up

- **Message it from anywhere.** "Summarize these logs", "scaffold a repo",
  "run this analysis" — from your phone, executed on your Mac Studio's power.
- **Sandboxed code execution.** It installs packages and runs code in the
  container, so a bad command can't touch your Mac's filesystem or creds.
- **Scheduled/unattended jobs.** `hermes cron` for recurring tasks; results land
  in your Telegram home channel.
- **Skills + memory.** It builds reusable skills from experience and keeps
  memory across sessions (`~/.hermes/skills`, `~/.hermes/memories`).
- **Subagents.** It can spawn isolated subagents for parallel work.

---

## Security notes (read once)

- The bot is a remote control for command execution on your Mac. Keep
  `TELEGRAM_ALLOWED_USERS` tight — ideally just your own ID — and never share
  the bot token.
- Only forward host env vars into the sandbox (`docker_forward_env`) that the
  agent truly needs. By default it forwards none.
- The sandbox is hardened but not a security boundary against a determined
  attacker with your Telegram access. Treat allow-listed users as trusted.
- `~/.hermes/.env` is chmod 600 and must never be committed to git.

---

## Alternative: run the *whole* Hermes process in Docker too

Possible, but on macOS the sandbox backend would then need Docker-in-Docker
(mount `/var/run/docker.sock` into the Hermes container, or nest a daemon),
which is fragile and weakens isolation. Unless you have a hard requirement to
containerize the gateway itself, prefer the default above. If you do need it,
say so and I'll produce a `docker-compose.yml` variant.

---

## Sources
- Hermes Agent: https://hermes-agent.nousresearch.com/
- Quickstart: https://hermes-agent.nousresearch.com/docs/getting-started/quickstart
- Docker backend: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/docker.md
- Telegram guide: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/guides/team-telegram-assistant.md
- Repo: https://github.com/NousResearch/hermes-agent
