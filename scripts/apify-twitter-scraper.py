#!/usr/bin/env python3
"""
Apify Twitter/X Scraper Integration for PolyClaw
Fetches tweets, sentiment, and engagement data for trading signals
"""

import os
import json
import requests
from typing import List, Dict, Optional
from datetime import datetime, timezone

# Apify Configuration
APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")  # User needs to set this
APIFY_BASE_URL = "https://api.apify.com/v2"

# Twitter Scraper Actor ID (official Apify actor)
TWITTER_SCRAPER_ACTOR = "apidojo/tweet-scraper"

class ApifyTwitterScraper:
    """Scrape Twitter/X data via Apify for sentiment analysis."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or APIFY_API_KEY
        if not self.api_key:
            raise ValueError("APIFY_API_KEY required. Get it from https://console.apify.com")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def search_tweets(
        self,
        query: str,
        max_tweets: int = 50,
        sort_by: str = "latest"  # latest, top
    ) -> List[Dict]:
        """
        Search tweets by keyword/query.
        
        Args:
            query: Search term (e.g., "BTC bitcoin price")
            max_tweets: Number of tweets to fetch
            sort_by: Sort order (latest for real-time)
        
        Returns:
            List of tweet data with text, engagement, timestamp
        """
        print(f"🔍 Searching tweets: '{query}' (max: {max_tweets})")
        
        # Run the Twitter scraper actor
        run_input = {
            "searchTerms": [query],
            "maxTweets": max_tweets,
            "sort": sort_by,
            "includeReplies": False,
            "includeRetweets": False
        }
        
        try:
            # Start actor run
            response = requests.post(
                f"{APIFY_BASE_URL}/acts/{TWITTER_SCRAPER_ACTOR}/runs",
                headers=self.headers,
                json={"runInput": run_input},
                timeout=300
            )
            response.raise_for_status()
            
            run_data = response.json()
            run_id = run_data["data"]["id"]
            
            print(f"   Started run: {run_id}")
            
            # Wait for completion and get results
            tweets = self._wait_for_results(run_id)
            
            print(f"   ✅ Fetched {len(tweets)} tweets")
            return tweets
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    def get_user_tweets(
        self,
        username: str,
        max_tweets: int = 20
    ) -> List[Dict]:
        """
        Get recent tweets from a specific user (e.g., @elonmusk).
        
        Args:
            username: Twitter handle (without @)
            max_tweets: Number of tweets to fetch
        """
        print(f"👤 Fetching tweets from @{username}")
        
        run_input = {
            "twitterHandles": [username],
            "maxTweets": max_tweets,
            "includeReplies": False
        }
        
        try:
            response = requests.post(
                f"{APIFY_BASE_URL}/acts/{TWITTER_SCRAPER_ACTOR}/runs",
                headers=self.headers,
                json={"runInput": run_input},
                timeout=300
            )
            response.raise_for_status()
            
            run_id = response.json()["data"]["id"]
            tweets = self._wait_for_results(run_id)
            
            print(f"   ✅ Fetched {len(tweets)} tweets from @{username}")
            return tweets
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    def _wait_for_results(self, run_id: str, timeout: int = 120) -> List[Dict]:
        """Wait for actor run to complete and fetch results."""
        import time
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check run status
            status_resp = requests.get(
                f"{APIFY_BASE_URL}/actor-runs/{run_id}",
                headers=self.headers,
                timeout=30
            )
            
            if status_resp.status_code == 200:
                status_data = status_resp.json()["data"]
                status = status_data.get("status")
                
                if status == "SUCCEEDED":
                    # Fetch results from dataset
                    dataset_id = status_data.get("defaultDatasetId")
                    return self._fetch_dataset(dataset_id)
                
                elif status in ["FAILED", "TIMED_OUT"]:
                    print(f"   Run failed with status: {status}")
                    return []
            
            time.sleep(5)  # Wait 5 seconds between checks
        
        print("   ⚠️ Timeout waiting for results")
        return []
    
    def _fetch_dataset(self, dataset_id: str) -> List[Dict]:
        """Fetch all items from Apify dataset."""
        try:
            response = requests.get(
                f"{APIFY_BASE_URL}/datasets/{dataset_id}/items",
                headers=self.headers,
                timeout=60
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"   ❌ Error fetching dataset: {e}")
            return []
    
    def analyze_sentiment(self, tweets: List[Dict]) -> Dict:
        """
        Simple sentiment analysis based on tweet content and engagement.
        
        Returns sentiment metrics for trading signals.
        """
        if not tweets:
            return {"sentiment": "neutral", "score": 0.5, "confidence": 0}
        
        # Positive/negative keywords
        positive_words = ['bull', 'bullish', 'pump', 'moon', ' ATH', 'breakout', 'green', 'up', 'rise', 'gain']
        negative_words = ['bear', 'bearish', 'dump', 'crash', 'dip', 'red', 'down', 'fall', 'loss', 'liquidated']
        
        bullish_count = 0
        bearish_count = 0
        total_engagement = 0
        
        for tweet in tweets:
            text = tweet.get("text", "").lower()
            engagement = (
                tweet.get("likeCount", 0) + 
                tweet.get("retweetCount", 0) + 
                tweet.get("replyCount", 0)
            )
            
            # Weight by engagement (viral tweets matter more)
            weight = 1 + (engagement / 100)  # Boost high-engagement tweets
            
            if any(word in text for word in positive_words):
                bullish_count += weight
            if any(word in text for word in negative_words):
                bearish_count += weight
            
            total_engagement += engagement
        
        # Calculate sentiment score
        total_signals = bullish_count + bearish_count
        if total_signals == 0:
            return {"sentiment": "neutral", "score": 0.5, "confidence": 0}
        
        sentiment_score = bullish_count / total_signals
        
        # Determine sentiment label
        if sentiment_score > 0.6:
            sentiment = "bullish"
        elif sentiment_score < 0.4:
            sentiment = "bearish"
        else:
            sentiment = "neutral"
        
        # Confidence based on volume of signals
        confidence = min(total_signals / 20, 1.0)  # Max confidence at 20+ signals
        
        return {
            "sentiment": sentiment,
            "score": sentiment_score,
            "confidence": confidence,
            "bullish_signals": bullish_count,
            "bearish_signals": bearish_count,
            "total_tweets": len(tweets),
            "total_engagement": total_engagement,
            "avg_engagement": total_engagement / len(tweets) if tweets else 0
        }

def get_btc_trading_signal() -> Dict:
    """
    Get BTC sentiment signal for Polymarket trading.
    
    Returns trading signal with direction, confidence, and metadata.
    """
    print("=" * 60)
    print("🐦 APIFY TWITTER SENTIMENT FOR BTC")
    print("=" * 60)
    
    try:
        scraper = ApifyTwitterScraper()
        
        # 1. Search BTC-related tweets
        btc_tweets = scraper.search_tweets(
            query="BTC bitcoin price",
            max_tweets=50,
            sort_by="latest"
        )
        
        # 2. Get tweets from key crypto accounts
        # Add more accounts as needed
        key_accounts = ["elonmusk"]  # Add: @saylor, @cz_binance, etc.
        
        for account in key_accounts:
            try:
                user_tweets = scraper.get_user_tweets(account, max_tweets=10)
                # Filter for BTC-related tweets only
                btc_user_tweets = [
                    t for t in user_tweets 
                    if any(word in t.get("text", "").lower() 
                           for word in ["btc", "bitcoin", "crypto"])
                ]
                btc_tweets.extend(btc_user_tweets)
            except Exception as e:
                print(f"   Skipping @{account}: {e}")
        
        # 3. Analyze sentiment
        analysis = scraper.analyze_sentiment(btc_tweets)
        
        print("\n📊 SENTIMENT ANALYSIS:")
        print(f"   Direction: {analysis['sentiment'].upper()}")
        print(f"   Score: {analysis['score']:.2f} (0=bearish, 1=bullish)")
        print(f"   Confidence: {analysis['confidence']:.0%}")
        print(f"   Bullish signals: {analysis['bullish_signals']:.1f}")
        print(f"   Bearish signals: {analysis['bearish_signals']:.1f}")
        print(f"   Total engagement: {analysis['total_engagement']:,}")
        
        # Trading signal
        signal = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "market": "BTC",
            "direction": "UP" if analysis['sentiment'] == "bullish" else "DOWN" if analysis['sentiment'] == "bearish" else "NEUTRAL",
            "confidence": analysis['confidence'],
            "sentiment_score": analysis['score'],
            "source": "twitter_sentiment",
            "reasoning": f"Twitter sentiment: {analysis['sentiment']} ({analysis['score']:.2f}) from {analysis['total_tweets']} tweets"
        }
        
        return signal
        
    except ValueError as e:
        print(f"\n⚠️  Setup required: {e}")
        print("\nTo get Apify API key:")
        print("1. Go to https://console.apify.com")
        print("2. Sign up (free tier available)")
        print("3. Get your API token from Settings → Integrations")
        print("4. Set environment variable: export APIFY_API_KEY='your_key'")
        
        return {
            "error": "APIFY_API_KEY not configured",
            "direction": "NEUTRAL",
            "confidence": 0
        }
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return {
            "error": str(e),
            "direction": "NEUTRAL",
            "confidence": 0
        }

if __name__ == "__main__":
    signal = get_btc_trading_signal()
    
    print("\n" + "=" * 60)
    print("🎯 TRADING SIGNAL:")
    print("=" * 60)
    print(json.dumps(signal, indent=2))
    print("=" * 60)
