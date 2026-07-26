#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Hearth one-command setup.
#
# Run this on YOUR machine (macOS/Linux/WSL). It wires a Supabase project to the
# app: applies the database + storage bucket, deploys the AI edge function, sets
# your Anthropic key as a server-side secret, and writes web/config.js.
#
# Your secrets stay on this machine — nothing is uploaded anywhere except to your
# own Supabase project and (for the key) stored as a Supabase Function secret.
#
# Prerequisites:
#   - bash, curl, python3
#   - Supabase CLI            https://supabase.com/docs/guides/cli   (`brew install supabase/tap/supabase`)
#   - A Supabase project      (create one at https://supabase.com → "New project")
#   - A Supabase access token (https://supabase.com/dashboard/account/tokens)
#   - An Anthropic API key    (https://console.anthropic.com)
#
# Usage:
#   cd family-expense-tracker
#   ./scripts/setup.sh
# ---------------------------------------------------------------------------
set -euo pipefail

API="https://api.supabase.com"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
info() { printf "  \033[36m•\033[0m %s\n" "$1"; }
die()  { printf "\033[31m✗ %s\033[0m\n" "$1" >&2; exit 1; }

ask() { # ask VAR "prompt" [silent]
  local __var="$1" __prompt="$2" __silent="${3:-}" __val=""
  if [ -n "$__silent" ]; then read -r -s -p "  $__prompt: " __val; echo
  else read -r -p "  $__prompt: " __val; fi
  printf -v "$__var" '%s' "$__val"
}

json_query() { # json_query <project_ref> <sql-file>  → runs SQL via Management API
  local ref="$1" file="$2"
  local payload
  payload="$(python3 -c 'import json,sys; print(json.dumps({"query": open(sys.argv[1]).read()}))' "$file")"
  local resp
  resp="$(curl -sS -w $'\n%{http_code}' -X POST "$API/v1/projects/$ref/database/query" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")"
  local code="${resp##*$'\n'}"
  local body="${resp%$'\n'*}"
  if [ "$code" != "200" ] && [ "$code" != "201" ]; then
    echo "$body" >&2
    die "SQL step failed ($file) — HTTP $code"
  fi
}

bold "Hearth setup"
echo

command -v curl >/dev/null    || die "curl is required"
command -v python3 >/dev/null || die "python3 is required"
command -v supabase >/dev/null || die "Supabase CLI not found. Install: brew install supabase/tap/supabase"

# --- Collect inputs -------------------------------------------------------
bold "1) Credentials"
: "${SUPABASE_ACCESS_TOKEN:=}"
if [ -z "$SUPABASE_ACCESS_TOKEN" ]; then
  ask SUPABASE_ACCESS_TOKEN "Supabase access token (sbp_...)" silent
fi
TOKEN="$SUPABASE_ACCESS_TOKEN"
export SUPABASE_ACCESS_TOKEN="$TOKEN"
[ -n "$TOKEN" ] || die "access token is required"

ask PROJECT_REF "Supabase project ref (the xxxx in xxxx.supabase.co)"
[ -n "$PROJECT_REF" ] || die "project ref is required"

ask ANTHROPIC_API_KEY "Anthropic API key (sk-ant-...)" silent
[ -n "$ANTHROPIC_API_KEY" ] || die "Anthropic key is required"

echo
info "Model controls AI quality vs. cost:"
info "  1) claude-opus-5    (best quality)"
info "  2) claude-sonnet-5  (balanced — recommended)"
info "  3) claude-haiku-4-5 (cheapest)"
ask MODEL_CHOICE "Choose 1/2/3 [2]"
case "${MODEL_CHOICE:-2}" in
  1) MODEL="claude-opus-5" ;;
  3) MODEL="claude-haiku-4-5" ;;
  *) MODEL="claude-sonnet-5" ;;
esac
ask CURRENCY "Default currency [USD]"
CURRENCY="${CURRENCY:-USD}"

echo
# --- Verify project + fetch anon key -------------------------------------
bold "2) Checking project"
ANON_JSON="$(curl -sS "$API/v1/projects/$PROJECT_REF/api-keys?reveal=true" \
  -H "Authorization: Bearer $TOKEN" || true)"
ANON_KEY="$(printf '%s' "$ANON_JSON" | python3 -c '
import json,sys
try:
    data=json.load(sys.stdin)
    keys={k.get("name"):k.get("api_key") for k in data if isinstance(k,dict)}
    print(keys.get("anon",""))
except Exception:
    print("")
')"
[ -n "$ANON_KEY" ] || die "Could not read the project anon key. Check the token has access to project '$PROJECT_REF'."
ok "Project reachable, anon key retrieved"

# --- Apply database + storage --------------------------------------------
bold "3) Applying database schema"
json_query "$PROJECT_REF" "supabase/migrations/0001_init.sql"; ok "Tables, RLS, and household functions"
json_query "$PROJECT_REF" "supabase/migrations/0002_storage.sql"; ok "Private storage bucket + policies"

# --- Deploy the edge function --------------------------------------------
bold "4) Deploying the AI function"
supabase functions deploy analyze-document --project-ref "$PROJECT_REF" >/dev/null
ok "analyze-document deployed"
supabase secrets set --project-ref "$PROJECT_REF" \
  "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" "ANTHROPIC_MODEL=$MODEL" >/dev/null
ok "Anthropic key + model ($MODEL) stored as Function secrets"

# --- Write web config -----------------------------------------------------
bold "5) Writing web/config.js"
cat > web/config.js <<EOF
// Generated by scripts/setup.sh — safe to commit? The anon key is public-safe,
// but this file is git-ignored by default.
window.APP_CONFIG = {
  SUPABASE_URL: 'https://$PROJECT_REF.supabase.co',
  SUPABASE_ANON_KEY: '$ANON_KEY',
  DEFAULT_CURRENCY: '$CURRENCY',
};
EOF
ok "web/config.js created"

echo
bold "Done! ✅  Next steps:"
info "1. (Optional) Turn OFF 'Confirm email' in Supabase → Authentication → Providers → Email"
info "   for a friction-free 2-person start."
info "2. Host the app: drag the 'web' folder onto https://app.netlify.com/drop"
info "3. Open the URL in Safari on each iPhone → Share → Add to Home Screen."
info "4. First person: Create account → Create household. Share the invite code (Settings)."
echo
info "Test locally right now:  (cd web && python3 -m http.server 8080)  → http://localhost:8080"
