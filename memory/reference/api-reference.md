# API Reference

Quick reference for all APIs the agent uses.

---

## Birdeye

- **Base URL:** `https://public-api.birdeye.so`
- **Auth:** Header `X-API-KEY`
- **Key Location:** Environment variable / hardcoded
- **Key:** `bb463164ead7429686f982258664fdb9`

### Endpoints

```bash
# Get token market data
curl "https://public-api.birdeye.so/defi/v3/token/market-data?chain=solana&address=TOKEN_ADDRESS" \
  -H "accept: application/json" \
  -H "X-API-KEY: $BIRDEYE_API_KEY"

# Scan tokens
curl "https://public-api.birdeye.so/defi/v2/tokens/all?chain=solana&sort_by=v24hUSD&limit=50" \
  -H "accept: application/json" \
  -H "X-API-KEY: $BIRDEYE_API_KEY"

# OHLCV candles
curl "https://public-api.birdeye.so/defi/ohlcv?address=TOKEN&type=1H&time_from=START&time_to=END" \
  -H "accept: application/json" \
  -H "X-API-KEY: $BIRDEYE_API_KEY"
```

### Rate Limits
- Standard tier: 100 req/min
- No strict limits mentioned for public endpoints

---

## CoinGecko

- **Base URL:** `https://api.coingecko.com/api/v3`
- **Auth:** None (public)

### Endpoints

```bash
# Trending coins
curl "https://api.coingecko.com/api/v3/search/trending"

# Coin data
curl "https://api.coingecko.com/api/v3/coins/bitcoin"
```

### Rate Limits
- 10-30 calls/minute on free tier
- No API key required for basic endpoints

---

## DexScreener

- **Base URL:** `https://api.dexscreener.com/latest/dex`
- **Auth:** None (public)

### Endpoints

```bash
# Get token pairs
curl "https://api.dexscreener.com/token-pairs/v1/solana/TOKEN_ADDRESS"

# Boosted tokens
curl "https://api.dexscreener.com/token-boosts/latest/v1"

# Token profiles
curl "https://api.dexscreener.com/token-profiles/latest/v1"
```

### Rate Limits
- Search: 300/min
- Pairs: 300/min
- Boosts/Profiles: 60/min

---

## Solscan

- **Base URL:** `https://api.solscan.io`
- **Web:** `https://solscan.io/token/{address}`
- **Auth:** None for basic lookups

---

## BaseScan

- **Base URL:** `https://api.basescan.org`
- **Web:** `https://basescan.org/token/{address}`
- **Auth:** API key for API, none for web

---

## GMGN.ai

- **Web:** `https://gmgn.ai`
- **Note:** No public API. Web-only interface for Solana memecoin discovery.

---

## Telegram Bot API

- **Bot Token:** Stored in OpenClaw config
- **Base URL:** `https://api.telegram.org/bot{BOT_TOKEN}`

---

## Supabase (Future)

- **Project URL:** TBD
- **Anon Key:** TBD
- **Service Role Key:** TBD (store securely)
- **Tables:** tasks, projects, content, documents

---

## Quick Command Reference

```bash
# Run scanner manually
python3 /Users/pterion2910/.openclaw/workspace/scripts/memecoin-scanner.sh

# Check cron jobs
openclaw cron list

# Check gateway status
openclaw gateway status

# Restart gateway
openclaw gateway restart
```
