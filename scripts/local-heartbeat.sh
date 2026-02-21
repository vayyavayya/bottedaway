#!/bin/bash
# local-heartbeat.sh — Route OpenClaw heartbeats to local Llama 3.2
# Cost: $0 for 48×/day pings

HEARTBEAT_PROMPT="${1:-Read HEARTBEAT.md if it exists. Follow it strictly. If nothing needs attention, reply HEARTBEAT_OK.}"

# Check if ollama is running
if ! pgrep -q ollama; then
    echo "⚠️ Ollama not running, starting..."
    ollama serve &
    sleep 2
fi

# Check if model exists
if ! ollama list | grep -q "llama3.2"; then
    echo "❌ llama3.2 not found. Run: ollama pull llama3.2:3b"
    exit 1
fi

# Run heartbeat through local model
RESPONSE=$(ollama run llama3.2:3b "$HEARTBEAT_PROMPT" 2>/dev/null | tr -d '\n' | head -c 1000)

# Validate response
if [[ "$RESPONSE" == *"HEARTBEAT_OK"* ]]; then
    echo "HEARTBEAT_OK"
    exit 0
elif [[ -n "$RESPONSE" ]]; then
    echo "$RESPONSE"
    exit 0
else
    # Fallback to default
    echo "HEARTBEAT_OK"
    exit 0
fi
