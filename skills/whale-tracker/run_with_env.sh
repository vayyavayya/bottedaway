#!/bin/bash
# Load environment and run whale tracker
export HELIUS_API_KEY="292025a1-d64c-4831-bd17-f4787f2fd0dd"
export PATH="/usr/local/bin:/usr/bin:$PATH"
cd /Users/pterion2910/.openclaw/workspace/skills/whale-tracker
python3 scripts/whale_tracker.py
