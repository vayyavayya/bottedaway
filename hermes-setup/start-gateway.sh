#!/usr/bin/env bash
# =============================================================================
# start-gateway.sh
# Installs Hermes' Telegram gateway as an always-on background service (launchd
# LaunchAgent on macOS) and starts it. Re-runnable.
#
# Prereqs (fail fast if missing):
#   * hermes installed
#   * ~/.hermes/.env has a real TELEGRAM_BOT_TOKEN
#   * a model provider is authed (`hermes setup` done)
# =============================================================================
set -euo pipefail

HERMES_DIR="${HOME}/.hermes"
log()  { printf '\033[1;36m[gateway]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[gateway] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

command -v hermes >/dev/null 2>&1 || die "hermes not found. Run ./install-hermes.sh first."
[ -f "${HERMES_DIR}/.env" ] || die "${HERMES_DIR}/.env missing. Run ./install-hermes.sh, then edit it."

if ! grep -q '^TELEGRAM_BOT_TOKEN=' "${HERMES_DIR}/.env" || \
   grep -q 'PASTE_YOUR_BOTFATHER_TOKEN_HERE' "${HERMES_DIR}/.env"; then
  die "TELEGRAM_BOT_TOKEN not set (still the placeholder). Edit ${HERMES_DIR}/.env first."
fi

# Optional: quick foreground smoke test before daemonizing.
# Uncomment to watch it connect, Ctrl-C to stop, then re-run for the service.
# log "Foreground smoke test (Ctrl-C to stop)..."; hermes gateway; exit 0

log "Installing gateway as a background LaunchAgent..."
hermes gateway install

log "Starting gateway..."
hermes gateway start

sleep 2
log "Status:"
hermes gateway status || true

cat <<'EOF'

------------------------------------------------------------------------------
 Telegram gateway is live. Now, on your phone:
   * Open a DM with your bot and send /start (or any message).
   * Send /sethome in the group/channel where you want scheduled-task output.
 Useful ops:
   hermes gateway status     # is it running?
   hermes gateway stop|start # control the service
   hermes pairing list       # who is authorized
   hermes pairing approve telegram <CODE>   # approve a new user's DM pairing code
------------------------------------------------------------------------------
EOF
