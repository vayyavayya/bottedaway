#!/usr/bin/env bash
# =============================================================================
# verify.sh — health check for the Hermes + Telegram + Docker-sandbox setup.
# Read-only: diagnoses, changes nothing.
# =============================================================================
set -uo pipefail

HERMES_DIR="${HOME}/.hermes"
SANDBOX_IMAGE="nikolaik/python-nodejs:python3.11-nodejs20"
ok()   { printf '\033[1;32m  ok  \033[0m %s\n' "$*"; }
bad()  { printf '\033[1;31m FAIL \033[0m %s\n' "$*"; }
info() { printf '\033[1;36m ---- \033[0m %s\n' "$*"; }

info "1. Docker daemon"
docker info >/dev/null 2>&1 && ok "docker running" || bad "docker not running — start Docker Desktop"

info "2. Sandbox image"
docker image inspect "$SANDBOX_IMAGE" >/dev/null 2>&1 && ok "$SANDBOX_IMAGE present" || bad "sandbox image missing — run ./install-hermes.sh"

info "3. Hermes CLI"
command -v hermes >/dev/null 2>&1 && ok "hermes on PATH ($(hermes --version 2>/dev/null))" || bad "hermes not installed"

info "4. Config files"
[ -f "${HERMES_DIR}/config.yaml" ] && ok "config.yaml present" || bad "config.yaml missing"
if [ -f "${HERMES_DIR}/.env" ]; then
  if grep -q 'PASTE_YOUR_BOTFATHER_TOKEN_HERE' "${HERMES_DIR}/.env"; then
    bad ".env still has the placeholder bot token — edit it"
  else
    ok ".env present with a bot token set"
  fi
else
  bad ".env missing"
fi

info "5. Terminal backend = docker"
if command -v hermes >/dev/null 2>&1; then
  backend="$(hermes config get terminal.backend 2>/dev/null || echo '?')"
  [ "$backend" = "docker" ] && ok "terminal.backend=docker" || bad "terminal.backend=$backend (expected docker)"
fi

info "6. hermes doctor"
command -v hermes >/dev/null 2>&1 && hermes doctor || bad "could not run hermes doctor"

info "7. Gateway status"
command -v hermes >/dev/null 2>&1 && hermes gateway status || info "gateway not installed yet (run ./start-gateway.sh)"

echo
info "Done. Any FAIL above must be resolved before the bot will work end-to-end."
