# Apify Twitter Scraper Skill

Scrape Twitter/X data via Apify for sentiment analysis and trading signals.

## Setup

1. **Get Apify API Key:**
   - Go to https://console.apify.com
   - Sign up (free tier: $5 credits/month)
   - Get API token from Settings → Integrations

2. **Set Environment Variable:**
   ```bash
   export APIFY_API_KEY='your_api_key_here'
   ```

3. **Add to OpenClaw config:**
   Add to your `~/.openclaw/config.yaml`:
   ```yaml
   env:
     APIFY_API_KEY: "${APIFY_API_KEY}"
   ```

## Usage

### Basic Tweet Search

```python
from scripts.apify_twitter_scraper import ApifyTwitterScraper

scraper = ApifyTwitterScraper()
tweets = scraper.search_tweets("BTC bitcoin price", max_tweets=50)

for tweet in tweets[:5]:
    print(f"@{tweet['author']['userName']}: {tweet['text'][:100]}...")
    print(f"  ❤️ {tweet['likeCount']} | 🔄 {tweet['retweetCount']}")
```

### Get User Tweets

```python
tweets = scraper.get_user_tweets("elonmusk", max_tweets=20)
```

### Sentiment Analysis

```python
analysis = scraper.analyze_sentiment(tweets)
print(f"Sentiment: {analysis['sentiment']} ({analysis['score']:.2f})")
```

### Trading Signal

```python
from scripts.apify_twitter_scraper import get_btc_trading_signal

signal = get_btc_trading_signal()
# Returns: {"direction": "UP", "confidence": 0.75, ...}
```

## Cost

- **Twitter Scraper Actor**: ~$0.25 per 1,000 tweets
- **Free tier**: $5/month credit (sufficient for ~20,000 tweets)
- **Typical usage**: 50 tweets × 4 scans/day = 6,000/month (~$1.50)

## Integration with PolyClaw

To use in autotrader, add to `polyclaw-autotrader.py`:

```python
from scripts.apify_twitter_scraper import get_btc_trading_signal

# In main() function, before edge scanning:
twitter_signal = get_btc_trading_signal()

if twitter_signal['confidence'] > 0.6:
    print(f"🐦 Twitter signal: {twitter_signal['direction']} "
          f"({twitter_signal['confidence']:.0%} confidence)")
    # Use as additional input for trade decisions
```

## Data Fields

Each tweet includes:
- `text`: Tweet content
- `createdAt`: Timestamp
- `likeCount`, `retweetCount`, `replyCount`: Engagement metrics
- `author`: User info (username, display name, followers)
- `url`: Direct link to tweet

## Rate Limits

- Apify: 100 concurrent actor runs
- Twitter/X: Rate limited by source (Apify handles rotation)

## Troubleshooting

**"APIFY_API_KEY not configured"**
→ Set the environment variable and restart OpenClaw

**"Run failed"**
→ Check Apify console for actor run details
→ May need to upgrade Apify account if hitting limits

**No tweets returned**
→ Check query syntax
→ Twitter/X may be blocking (Apify rotates IPs)

## References

- Apify Console: https://console.apify.com
- Twitter Scraper Actor: https://apify.com/apidojo/tweet-scraper
- Apify Docs: https://docs.apify.com/api
