#!/usr/bin/env bash
# =============================================================================
# install-hermes.sh
# One-shot(ish) installer for a Telegram-connected, Docker-sandboxed Hermes
# Agent on a Mac Studio (Apple Silicon).
#
# Safe to re-run: every step is idempotent and skips work already done.
#
# What it does NOT do (these need a human — the README flags them):
#   * create the Telegram bot token (@BotFather)
#   * the interactive Nous Portal OAuth login (`hermes setup`)
#   * install / launch Docker Desktop
#
# Usage:
#   chmod +x install-hermes.sh
#   ./install-hermes.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_DIR="${HOME}/.hermes"
WORKSPACE_DIR="${HOME}/hermes-workspace"
SANDBOX_IMAGE="nikolaik/python-nodejs:python3.11-nodejs20"

log()  { printf '\033[1;36m[hermes-setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[hermes-setup]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[hermes-setup] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# -----------------------------------------------------------------------------
# 0. Sanity: macOS + Docker running
# -----------------------------------------------------------------------------
[ "$(uname -s)" = "Darwin" ] || warn "Not macOS — script tuned for Mac Studio, continuing anyway."

if ! command -v docker >/dev/null 2>&1; then
  die "docker CLI not found. Install Docker Desktop (https://www.docker.com/products/docker-desktop/) or colima, then re-run."
fi
if ! docker info >/dev/null 2>&1; then
  die "Docker is installed but not running. Start Docker Desktop (or 'colima start') and re-run."
fi
log "Docker is up: $(docker --version)"

# -----------------------------------------------------------------------------
# 1. Install Hermes CLI (skip if present)
# -----------------------------------------------------------------------------
if command -v hermes >/dev/null 2>&1; then
  log "Hermes already installed: $(hermes --version 2>/dev/null || echo '(version unknown)')"
else
  log "Installing Hermes Agent..."
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
  # Load into current shell so the rest of the script can call `hermes`.
  # shellcheck disable=SC1090
  for rc in "${HOME}/.zshrc" "${HOME}/.bashrc"; do [ -f "$rc" ] && source "$rc" || true; done
  command -v hermes >/dev/null 2>&1 || die "hermes not on PATH after install. Open a new terminal and re-run this script."
fi

# -----------------------------------------------------------------------------
# 2. Pull the sandbox image
# -----------------------------------------------------------------------------
if docker image inspect "$SANDBOX_IMAGE" >/dev/null 2>&1; then
  log "Sandbox image already present: $SANDBOX_IMAGE"
else
  log "Pulling sandbox image ($SANDBOX_IMAGE)... this can take a minute."
  docker pull "$SANDBOX_IMAGE"
fi

# -----------------------------------------------------------------------------
# 3. Create dirs + install config.yaml and .env
# -----------------------------------------------------------------------------
mkdir -p "$HERMES_DIR"
mkdir -p "$WORKSPACE_DIR"
log "Agent sandbox workspace: $WORKSPACE_DIR  (mounts to /workspace inside the container)"

# config.yaml — back up any existing one before overwriting.
if [ -f "${HERMES_DIR}/config.yaml" ]; then
  cp "${HERMES_DIR}/config.yaml" "${HERMES_DIR}/config.yaml.bak.$(date +%Y%m%d%H%M%S)"
  warn "Existing config.yaml backed up."
fi
cp "${SCRIPT_DIR}/config.yaml" "${HERMES_DIR}/config.yaml"
log "Wrote ${HERMES_DIR}/config.yaml"

# .env — never clobber real secrets. Only seed from the example if missing.
if [ -f "${HERMES_DIR}/.env" ]; then
  warn ".env already exists — leaving it untouched. Make sure TELEGRAM_BOT_TOKEN + TELEGRAM_ALLOWED_USERS are set."
else
  cp "${SCRIPT_DIR}/.env.example" "${HERMES_DIR}/.env"
  chmod 600 "${HERMES_DIR}/.env"
  warn "Seeded ${HERMES_DIR}/.env from template — YOU MUST edit it with your real bot token + user id (README step 2)."
fi

# -----------------------------------------------------------------------------
# 4. Report what still needs a human, then hand off
# -----------------------------------------------------------------------------
cat <<'EOF'

------------------------------------------------------------------------------
 Base install done. Remaining MANUAL steps (see README.md):
   2)  Edit ~/.hermes/.env  -> real TELEGRAM_BOT_TOKEN + TELEGRAM_ALLOWED_USERS
   3)  Run `hermes setup`   -> Quick Setup (Nous Portal OAuth) OR set your API key
   4)  Run ./start-gateway.sh -> installs + starts the always-on Telegram service
   5)  Run ./verify.sh      -> health check
------------------------------------------------------------------------------
EOF
log "install-hermes.sh finished."
