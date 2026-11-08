#!/bin/bash
# Push RadBrain from the Mac to the 5090 PC over SSH and run install.ps1 there (code only — no data travels).
# Usage: ./deploy-pc.sh [--no-start]
set -euo pipefail
HOST=${RADBRAIN_PC:-pc5090}
HERE="$(cd "$(dirname "$0")" && pwd)"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
rsync -a --exclude .venv --exclude __pycache__ --exclude .pytest_cache --exclude '*.pyc' "$HERE/" "$STAGE/radbrain/"
tar -C "$STAGE" -czf "$STAGE/radbrain.tgz" radbrain
ssh "$HOST" 'powershell -NoProfile -Command "New-Item -ItemType Directory -Force -Path C:\RadBrain\src | Out-Null"'
scp -q "$STAGE/radbrain.tgz" "$HOST:C:/RadBrain/radbrain.tgz"
ssh "$HOST" 'powershell -NoProfile -Command "Remove-Item -Recurse -Force C:\RadBrain\src\radbrain -ErrorAction SilentlyContinue; tar -xzf C:\RadBrain\radbrain.tgz -C C:\RadBrain\src; Remove-Item C:\RadBrain\radbrain.tgz"'
ssh "$HOST" "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\RadBrain\\src\\radbrain\\install.ps1 $*"
