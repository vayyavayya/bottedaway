#!/bin/bash
# Punch Token Price Monitor
# Contract: NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump
# Runs hourly, alerts on significant price moves

TOKEN_MINT="NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump"
TOKEN_SYMBOL="PUNCH"
DATA_DIR="/Users/pterion2910/.openclaw/workspace/skills/price-monitor/data"
LOG_FILE="$DATA_DIR/punch_monitor.log"
ALERT_THRESHOLD_PCT=10  # Alert on 10%+ price change

mkdir -p "$DATA_DIR"

# Fetch price from DexScreener
fetch_price() {
    local response=$(curl -s "https://api.dexscreener.com/latest/dex/tokens/$TOKEN_MINT" \
        -H "Accept: application/json" 2>/dev/null)
    
    echo "$response" | jq -r '.pairs[0] | {
        priceUsd: .priceUsd,
        priceChange24h: .priceChange?.h24,
        volume24h: .volume?.h24,
        liquidity: .liquidity?.usd,
        marketCap: .marketCap,
        dex: .dexId,
        pair: .pairAddress
    }' 2>/dev/null
}

# Get previous price
get_previous_price() {
    if [ -f "$DATA_DIR/punch_last_price.txt" ]; then
        cat "$DATA_DIR/punch_last_price.txt"
    else
        echo "0"
    fi
}

# Save current price
save_price() {
    echo "$1" > "$DATA_DIR/punch_last_price.txt"
}

# Send alert
send_alert() {
    local message="$1"
    
    # Log to file
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" >> "$LOG_FILE"
    
    # Send to Telegram if configured
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d "chat_id=$TELEGRAM_CHAT_ID" \
            -d "text=$message" \
            -d "parse_mode=Markdown" >/dev/null 2>&1
    fi
    
    # Also print to stdout for cron logging
    echo "$message"
}

# Main logic
main() {
    local data=$(fetch_price)
    
    if [ -z "$data" ] || [ "$data" = "null" ]; then
        send_alert "⚠️ $TOKEN_SYMBOL: Failed to fetch price data"
        exit 1
    fi
    
    local price=$(echo "$data" | jq -r '.priceUsd // "0"')
    local change24h=$(echo "$data" | jq -r '.priceChange24h // "0"')
    local volume=$(echo "$data" | jq -r '.volume24h // "0"')
    local liquidity=$(echo "$data" | jq -r '.liquidity // "0"')
    local marketCap=$(echo "$data" | jq -r '.marketCap // "0"')
    local dex=$(echo "$data" | jq -r '.dex // "unknown"')
    
    local prev_price=$(get_previous_price)
    save_price "$price"
    
    # Calculate change since last check
    local change_since_last=0
    if [ "$prev_price" != "0" ] && [ "$prev_price" != "" ]; then
        change_since_last=$(echo "scale=4; (($price - $prev_price) / $prev_price) * 100" | bc 2>/dev/null || echo "0")
    fi
    
    # Format message
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local price_fmt=$(printf "%.8f" "$price" 2>/dev/null || echo "$price")
    local mc_fmt=$(echo "$marketCap" | awk '{printf "%.0f", $1}' 2>/dev/null || echo "$marketCap")
    local vol_fmt=$(echo "$volume" | awk '{printf "%.0f", $1}' 2>/dev/null || echo "$volume")
    
    # Build status message
    local status="📊 *$TOKEN_SYMBOL Price Update*\n"
    status+="💰 Price: \$$price_fmt\n"
    status+="📈 24h Change: ${change24h}%\n"
    status+="💎 Market Cap: \$$mc_fmt\n"
    status+="📊 24h Volume: \$$vol_fmt\n"
    status+="💧 Liquidity: \$$liquidity\n"
    status+="🏦 DEX: $dex\n"
    status+="🕐 $timestamp"
    
    # Check for significant moves
    local abs_change=$(echo "$change_since_last" | sed 's/-//')
    if (( $(echo "$abs_change > $ALERT_THRESHOLD_PCT" | bc -l 2>/dev/null || echo "0") )); then
        local direction="📈"
        if (( $(echo "$change_since_last < 0" | bc -l 2>/dev/null || echo "0") )); then
            direction="📉"
        fi
        status="🚨 *$TOKEN_SYMBOL ALERT: ${direction} ${change_since_last}% in 1h*\n\n$status"
    fi
    
    send_alert "$status"
}

main
