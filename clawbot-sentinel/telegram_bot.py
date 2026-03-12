#!/usr/bin/env python3
"""
ClawBot Sentinel - Telegram Handler v2
Updated with Engine A/B/C implementations and Claude Sonnet
"""

import os
import sys
import json
import re
import logging
import asyncio
from datetime import datetime
from pathlib import Path
import requests

# Setup paths - import the sentinel engine
sys.path.insert(0, str(Path.home()))

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Import engine functions from sentinel_test
sys.path.insert(0, str(Path.home()))
import sentinel_test
from sentinel_test import (
    get_token_data, calc_ema, get_candles,
    run_engine_a, run_engine_b, run_engine_c, get_verdict
)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# CONFIGURATION
# ============================================
class Config:
    TELEGRAM_TOKEN = None
    ANTHROPIC_KEY = None
    HELIUS_KEY = None
    BIRDEYE_KEY = None
    
    @classmethod
    def load(cls):
        # Load from keys.env
        keys_file = Path.home() / ".openclaw/workspace/keys.env"
        if keys_file.exists():
            content = keys_file.read_text()
            for line in content.split("\n"):
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    cls.TELEGRAM_TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("ANTHROPIC_API_KEY="):
                    cls.ANTHROPIC_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("BIRDEYE_API_KEY="):
                    cls.BIRDEYE_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
        
        # Load Helius
        try:
            with open(Path.home() / ".config/helius/credentials.json") as f:
                cls.HELIUS_KEY = json.load(f).get("api_key", "")
        except:
            pass

Config.load()

# ============================================
# DATA FETCHERS
# ============================================
def fetch_dexscreener(address: str) -> dict:
    """Fetch token metadata from DexScreener"""
    try:
        resp = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{address}",
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            pairs = data.get("pairs", [])
            if pairs:
                top = max(pairs, key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0))
                base = top.get("baseToken", {})
                pair_created_ms = top.get("pairCreatedAt", 0)
                age_days = (datetime.now().timestamp() * 1000 - pair_created_ms) / (1000 * 3600 * 24) if pair_created_ms else 0
                return {
                    "symbol": base.get("symbol", "???"),
                    "name": base.get("name", "Unknown"),
                    "price": float(top.get("priceUsd", 0) or 0),
                    "liquidity": float(top.get("liquidity", {}).get("usd", 0) or 0),
                    "volume_24h": float(top.get("volume", {}).get("h24", 0) or 0),
                    "price_change_24h": float(top.get("priceChange", {}).get("h24", 0) or 0),
                    "dex": top.get("dexId", "???"),
                    "age_days": age_days,
                    "market_cap": float(top.get("marketCap", 0) or 0),
                }
    except Exception as e:
        logger.error(f"DexScreener error: {e}")
    return {}

def fetch_helius_holders(address: str) -> list:
    """Fetch top holders from Helius"""
    if not Config.HELIUS_KEY:
        return []
    try:
        rpc = f"https://mainnet.helius-rpc.com/?api-key={Config.HELIUS_KEY}"
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "getTokenLargestAccounts",
            "params": [address]
        }
        resp = requests.post(rpc, json=payload, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("result", {}).get("value", [])[:20]
    except Exception as e:
        logger.error(f"Helius error: {e}")
    return []

# ============================================
# ANALYSIS ENGINES - NOW USING sentinel_test
# ============================================
def run_whale_scorer(address: str, token_data: dict) -> dict:
    """Run whale accumulation scorer"""
    try:
        # Try importing from whale-tracker
        sys.path.insert(0, str(Path.home() / ".openclaw/workspace/skills/whale-accumulation-scorer/scripts"))
        from whale_tracker import WhaleTracker
        tracker = WhaleTracker()
        signal = tracker.analyze_token(address)
        return {
            "score": signal.score,
            "phase": signal.phase.value,
            "buy_sell_ratio": signal.buy_sell_ratio,
            "velocity": signal.accumulation_velocity,
            "tags": signal.signal_tags,
            "actionable": signal.is_actionable,
            "details": signal.details
        }
    except Exception as e:
        logger.warning(f"Whale scorer not available: {e}")
        return {"score": 0, "phase": "unknown", "tags": []}

def run_engine_a(address: str) -> dict:
    """Engine A: 12H EMA50 Reclaim - imports from sentinel_test"""
    try:
        return sentinel_test.run_engine_a(address)
    except Exception as e:
        logger.error(f"Engine A error: {e}")
        return {"signal": None, "strength": 0, "message": f"Error: {str(e)[:50]}"}

def run_engine_b(address: str) -> dict:
    """Engine B: 4H EMA50 + Retest - imports from sentinel_test"""
    try:
        return sentinel_test.run_engine_b(address)
    except Exception as e:
        logger.error(f"Engine B error: {e}")
        return {"signal": None, "strength": 0, "message": f"Error: {str(e)[:50]}"}

def run_engine_c(address: str) -> dict:
    """Engine C: 1H EMA50 Retest - imports from sentinel_test"""
    try:
        return sentinel_test.run_engine_c(address)
    except Exception as e:
        logger.error(f"Engine C error: {e}")
        return {"signal": None, "strength": 0, "message": f"Error: {str(e)[:50]}"}

# ============================================
# CLAUDE SONNET VERDICT
# ============================================
def get_claude_verdict(token_data: dict, whale_data: dict, 
                       engine_a: dict, engine_b: dict, engine_c: dict) -> dict:
    """Get final verdict from Claude Sonnet (not Opus)"""
    if not Config.ANTHROPIC_KEY:
        # Fallback to engine aggregation
        buy_count = sum(1 for e in [engine_a, engine_b, engine_c] if e.get('signal') == 'BUY')
        stalk_count = sum(1 for e in [engine_a, engine_b, engine_c] if e.get('signal') == 'STALK')
        
        if buy_count >= 2:
            return {"verdict": "BUY", "reasoning": "Engine aggregation: 2+ BUY signals", "confidence": 70}
        elif buy_count >= 1 or stalk_count >= 2:
            return {"verdict": "STALK", "reasoning": "Engine aggregation: 1 BUY or 2+ STALK", "confidence": 50}
        else:
            return {"verdict": "PASS", "reasoning": "No clear engine signals", "confidence": 30}
    
    # Build prompt for Claude Sonnet
    prompt = f"""You are ClawBot Sentinel, an expert crypto trading analyst. Analyze this token and give a BUY/STALK/PASS verdict.

TOKEN DATA:
- Symbol: {token_data.get('symbol', '???')}
- Price: ${token_data.get('price', 0):.6f}
- Market Cap: ${token_data.get('market_cap', 0):,.0f}
- Liquidity: ${token_data.get('liquidity', 0):,.0f}
- Volume 24h: ${token_data.get('volume_24h', 0):,.0f}
- Price Change 24h: {token_data.get('price_change_24h', 0):.2f}%
- Age: {token_data.get('age_days', 0):.1f} days

WHALE ANALYSIS:
- Score: {whale_data.get('score', 0):.2f}/1.0
- Phase: {whale_data.get('phase', 'unknown')}
- Buy/Sell Ratio: {whale_data.get('buy_sell_ratio', 0):.2f}
- Signal Tags: {', '.join(whale_data.get('tags', ['none']))}
- Actionable: {whale_data.get('actionable', False)}

TECHNICAL ENGINES:
- Engine A (12H EMA50): {engine_a.get('message', 'N/A')}
- Engine B (4H EMA50 + Volume): {engine_b.get('message', 'N/A')}
- Engine C (1H EMA50 Trend): {engine_c.get('message', 'N/A')}

Engine Signals:
- Engine A: {engine_a.get('signal', 'N/A')} (strength: {engine_a.get('strength', 0)})
- Engine B: {engine_b.get('signal', 'N/A')} (strength: {engine_b.get('strength', 0)})
- Engine C: {engine_c.get('signal', 'N/A')} (strength: {engine_c.get('strength', 0)})

RULES:
- BUY: Strong engine signal (3+ candles above EMA50 on 12H) + whale confluence
- STALK: Engine setup forming, or whale activity present but waiting for confirmation
- PASS: No engine signal, weak liquidity (<$50K), or distribution detected

Respond in this exact format:
VERDICT: BUY|STALK|PASS
REASONING: One sentence explaining why
CONFIDENCE: 0-100"""

    try:
        resp = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': Config.ANTHROPIC_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-3-5-sonnet-20241022',
                'max_tokens': 150,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            content = data.get('content', [{}])[0].get('text', '')
            
            lines = content.strip().split('\n')
            verdict = "PASS"
            reasoning = "No clear signal"
            confidence = 50
            
            for line in lines:
                if line.startswith("VERDICT:"):
                    verdict = line.split(":", 1)[1].strip()
                elif line.startswith("REASONING:"):
                    reasoning = line.split(":", 1)[1].strip()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = int(line.split(":", 1)[1].strip())
                    except:
                        pass
            
            return {
                "verdict": verdict,
                "reasoning": reasoning,
                "confidence": confidence,
                "raw_response": content
            }
        else:
            logger.error(f"Claude API error: {resp.status_code} - {resp.text}")
            return {"verdict": "ERROR", "reasoning": f"API error: {resp.status_code}"}
            
    except Exception as e:
        logger.error(f"Claude error: {e}")
        return {"verdict": "ERROR", "reasoning": str(e)}

# ============================================
# TELEGRAM HANDLER - FIXED ADDRESS REGEX
# ============================================
# FIXED: More permissive regex that handles common Solana address formats
# Also allows addresses that might have been copy-pasted with formatting
SOLANA_ADDRESS_REGEX = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')

async def analyze_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle token analysis request"""
    text = update.message.text.strip()
    logger.info(f"[DEBUG] Received message: {text[:50]}...")
    
    # Check if it's a command (starts with /)
    if text.startswith('/'):
        logger.info("[DEBUG] Message is a command, skipping analysis")
        return  # Let command handlers deal with it
    
    # Check if it's a valid Solana address (strict full-match only)
    if not SOLANA_ADDRESS_REGEX.match(text):
        logger.info(f"[DEBUG] Message '{text}' is not a valid Solana address")
        await update.message.reply_text(
            "Send me a Solana contract address for analysis, or use /help for commands.",
            parse_mode='Markdown'
        )
        return
    
    address = text
    logger.info(f"[DEBUG] Analyzing address: {address}")
    
    # Send "analyzing" message
    analyzing_msg = await update.message.reply_text(f"🔍 Analyzing `{address[:16]}...`\n\nFetching data...", parse_mode='Markdown')
    
    try:
        # Step 1: Fetch data
        await analyzing_msg.edit_text(f"🔍 Analyzing `{address[:16]}...`\n\n📊 Fetching DexScreener data...", parse_mode='Markdown')
        token_data = fetch_dexscreener(address)
        
        await analyzing_msg.edit_text(f"🔍 Analyzing `{address[:16]}...`\n\n🐋 Fetching whale data...", parse_mode='Markdown')
        holders = fetch_helius_holders(address)
        
        # Step 2: Run analysis
        await analyzing_msg.edit_text(f"🔍 Analyzing `{address[:16]}...`\n\n🐋 Running whale scorer...", parse_mode='Markdown')
        whale_data = run_whale_scorer(address, token_data)
        
        await analyzing_msg.edit_text(f"🔍 Analyzing `{address[:16]}...`\n\n📈 Running Engine A (12H EMA50)...", parse_mode='Markdown')
        engine_a = run_engine_a(address)
        
        await analyzing_msg.edit_text(f"🔍 Analyzing `{address[:16]}...`\n\n📈 Running Engine B (4H EMA50)...", parse_mode='Markdown')
        engine_b = run_engine_b(address)
        
        await analyzing_msg.edit_text(f"🔍 Analyzing `{address[:16]}...`\n\n📈 Running Engine C (1H EMA50)...", parse_mode='Markdown')
        engine_c = run_engine_c(address)
        
        # Step 3: Get Claude verdict
        await analyzing_msg.edit_text(f"🔍 Analyzing `{address[:16]}...`\n\n🧠 Getting Claude Sonnet verdict...", parse_mode='Markdown')
        claude_result = get_claude_verdict(token_data, whale_data, engine_a, engine_b, engine_c)
        
        # Format response
        symbol = token_data.get('symbol', '???')
        name = token_data.get('name', 'Unknown')
        price = token_data.get('price', 0)
        liq = token_data.get('liquidity', 0)
        vol = token_data.get('volume_24h', 0)
        age = token_data.get('age_days', 0)
        mc = token_data.get('market_cap', 0)
        
        whale_score = whale_data.get('score', 0)
        whale_phase = whale_data.get('phase', 'unknown')
        tags = ', '.join(whale_data.get('tags', ['none']))
        
        verdict = claude_result.get('verdict', 'PASS')
        reasoning = claude_result.get('reasoning', '')
        confidence = claude_result.get('confidence', 0)
        
        # Emoji for verdict
        verdict_emoji = {"BUY": "🟢", "STALK": "🟡", "PASS": "🔴", "ERROR": "⚠️"}.get(verdict, "⚪")
        
        response = f"""🔍 **{name} (${symbol})**
`{address}`

📊 **Price:** ${price:.6f} | **MC:** ${mc:,.0f} | **Liq:** ${liq:,.0f}
📈 **Vol 24h:** ${vol:,.0f} | **Age:** {age:.1f}d | **Chg 24h:** {token_data.get('price_change_24h', 0):.2f}%

🐋 **Whale Score:** {whale_score:.2f} ({whale_phase})
   Tags: {tags}

📈 **Engines:**
   A (12H): {engine_a.get('phase', engine_a.get('signal', 'N/A'))} - {engine_a.get('message', '')[:40]}
   B (4H): {engine_b.get('signal', 'N/A')} - {engine_b.get('message', '')[:40]}
   C (1H): {engine_c.get('signal', 'N/A')} - {engine_c.get('message', '')[:40]}

{verdict_emoji} **VERDICT: {verdict}** ({confidence}% confidence)
   {reasoning}

[View on DexScreener](https://dexscreener.com/solana/{address})
"""
        
        await analyzing_msg.edit_text(response, parse_mode='Markdown', disable_web_page_preview=True)
        logger.info(f"[DEBUG] Analysis complete: {verdict}")
        
    except Exception as e:
        logger.error(f"Analysis error: {e}", exc_info=True)
        await analyzing_msg.edit_text(f"❌ Error analyzing token: {str(e)[:200]}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    await update.message.reply_text(
        "🤖 **ClawBot Sentinel v2**\n\n"
        "Paste any Solana contract address to get instant analysis:\n"
        "• Whale accumulation scoring\n"
        "• 3-Engine technical analysis (12H/4H/1H EMA50)\n"
        "• Claude Sonnet verdict\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show commands\n"
        "/status - System status\n\n"
        "Example:\n"
        "`63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9`",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    await update.message.reply_text(
        "**Commands:**\n"
        "/start - Start the bot\n"
        "/help - Show this help\n"
        "/status - System status\n\n"
        "**How to use:**\n"
        "Simply paste a Solana contract address (32-44 characters).\n\n"
        "**Example addresses:**\n"
        "• GIGA: `63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9`\n"
        "• BONK: `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`\n"
        "• WIF: `EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm`",
        parse_mode='Markdown'
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    status_text = (
        "🤖 **ClawBot Sentinel v2 Status**\n\n"
        f"✅ Telegram Bot: @{Config.TELEGRAM_TOKEN.split(':')[0] if Config.TELEGRAM_TOKEN else 'N/A'}\n"
        f"{'✅' if Config.ANTHROPIC_KEY else '❌'} Claude Sonnet: {'Ready' if Config.ANTHROPIC_KEY else 'Not configured'}\n"
        f"{'✅' if Config.HELIUS_KEY else '❌'} Helius: {'Ready' if Config.HELIUS_KEY else 'Not configured'}\n"
        f"{'✅' if Config.BIRDEYE_KEY else '⚠️'} Birdeye: {'Ready' if Config.BIRDEYE_KEY else 'Not configured (using fallback)'}\n"
        f"✅ DexScreener: Ready (no key needed)\n\n"
        "**Engines:**\n"
        "• Engine A: 12H EMA50 Reclaim\n"
        "• Engine B: 4H EMA50 + Volume + Retest\n"
        "• Engine C: 1H EMA50 Trend + Retest\n\n"
        "Send a Solana address to start analysis!"
    )
    await update.message.reply_text(status_text, parse_mode='Markdown')

# ============================================
# MAIN
# ============================================
def main():
    if not Config.TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found in keys.env")
        sys.exit(1)
    
    print("🚀 Starting ClawBot Sentinel v2...")
    print(f"   Telegram Bot: @{Config.TELEGRAM_TOKEN.split(':')[0]}")
    print(f"   Claude Sonnet: {'✅' if Config.ANTHROPIC_KEY else '❌'}")
    print(f"   Helius: {'✅' if Config.HELIUS_KEY else '❌'}")
    print(f"   Birdeye: {'✅' if Config.BIRDEYE_KEY else '❌'}")
    print()
    
    # Build application
    application = Application.builder().token(Config.TELEGRAM_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # Add message handler (only for text that's not a command)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_token))
    
    # Start bot
    print("✅ Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
