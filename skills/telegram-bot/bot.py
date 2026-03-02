#!/usr/bin/env python3
"""
Polyclaw Telegram Bot - Trading Command Interface
Commands:
- /scan — Run Polymarket scanner, return top 5 opportunities
- /analyze <market_id> — Deep-analyze a specific Polymarket market
- /crypto <symbol> — Analyze a crypto token
- /portfolio — Show current positions and P&L
- /alerts — Show recent alerts from all monitors
- /status — System health check (all cron jobs, agent status)

Push Alerts (automatic):
- Edge >10% from research pipeline
- Whale tracker major accumulation
- Price monitor >15% move
- Daily brief at 8am

Setup:
- Token in ~/.config/telegram/bot_token
- Hardcoded BigBrother's Telegram user ID for security
"""

import os
import sys
import json
import asyncio
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Hardcoded BigBrother's Telegram user ID for security
# Only this user can interact with the bot
AUTHORIZED_USER_ID = 123456789  # TODO: Replace with actual user ID

# Paths
WORKSPACE = Path("/Users/pterion2910/.openclaw/workspace")
CONFIG_DIR = Path.home() / ".config" / "telegram"
TOKEN_FILE = CONFIG_DIR / "bot_token"

# Analysis output directories
POLYMARKET_ANALYSIS_DIR = WORKSPACE / "analysis" / "polymarket"
CRYPTO_ANALYSIS_DIR = WORKSPACE / "analysis" / "crypto"
WHALE_TRACKER_DIR = WORKSPACE / "skills" / "whale-tracker"
PRICE_MONITOR_DIR = WORKSPACE / "skills" / "price-monitor"

# Alert tracking
ALERTS_LOG = WORKSPACE / "skills" / "telegram-bot" / "data" / "alerts.json"
DAILY_BRIEF_SENT = WORKSPACE / "skills" / "telegram-bot" / "data" / "daily_brief_sent.txt"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# SECURITY
# ============================================================================

def is_authorized(user_id: int) -> bool:
    """Check if user is authorized to use this bot."""
    return user_id == AUTHORIZED_USER_ID

async def check_auth(update: Update) -> bool:
    """Check authorization and send error if not authorized."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text(
            "🚫 Unauthorized access. This bot is private."
        )
        logger.warning(f"Unauthorized access attempt from user {user_id}")
        return False
    return True

# ============================================================================
# COMMAND HANDLERS
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not await check_auth(update):
        return
    
    welcome_msg = """🤖 **Polyclaw Trading Bot**

Your command center for Polymarket and crypto analysis.

**Available Commands:**
📊 `/scan` — Top 5 Polymarket opportunities
🔍 `/analyze <market_id>` — Deep market analysis
💎 `/crypto <symbol>` — Crypto token analysis
💼 `/portfolio` — Current positions & P&L
🚨 `/alerts` — Recent alerts from monitors
⚙️ `/status` — System health check

**Push Alerts Enabled:**
• Research edge >10%
• Whale accumulation signals
• Price moves >15%
• Daily brief at 8am

Type any command to get started!"""
    
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run Polymarket scanner and return top 5 opportunities."""
    if not await check_auth(update):
        return
    
    await update.message.reply_text("🔍 Scanning Polymarket for opportunities...")
    
    try:
        # Run the scanner
        scanner_path = WORKSPACE / "skills" / "polyclaw" / "scanner.py"
        result = subprocess.run(
            [sys.executable, str(scanner_path)],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            logger.error(f"Scanner failed: {result.stderr}")
            await update.message.reply_text("❌ Scanner error. Check logs.")
            return
        
        # Load results
        today = datetime.now().strftime('%Y-%m-%d')
        scan_file = POLYMARKET_ANALYSIS_DIR / f"scan_{today}.json"
        
        if not scan_file.exists():
            # Try latest
            scan_file = WORKSPACE / "skills" / "polyclaw" / "data" / "markets_latest.json"
        
        with open(scan_file, 'r') as f:
            data = json.load(f)
        
        top_markets = data.get('top_markets', [])[:5]
        
        if not top_markets:
            await update.message.reply_text("📭 No markets found in scan.")
            return
        
        # Format top 5
        message = "📊 **Top 5 Polymarket Opportunities**\n\n"
        
        for i, m in enumerate(top_markets, 1):
            question = m.get('question', 'Unknown')[:60]
            if len(m.get('question', '')) > 60:
                question += "..."
            
            score = m.get('total_score', 0)
            yes_price = m.get('yes_price', 0)
            no_price = m.get('no_price', 0)
            volume = m.get('volume_24h', 0)
            liquidity = m.get('liquidity', 0)
            market_id = m.get('market_id', '')
            
            message += f"**{i}.** {question}\n"
            message += f"   📈 Score: `{score}` | Yes: `{yes_price:.2f}` No: `{no_price:.2f}`\n"
            message += f"   💰 Vol: `${volume:,.0f}` | Liq: `${liquidity:,.0f}`\n"
            message += f"   🔍 `/analyze {market_id}`\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏱️ Scanner timed out. Try again.")
    except Exception as e:
        logger.error(f"Scan error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deep-analyze a specific Polymarket market."""
    if not await check_auth(update):
        return
    
    if not context.args:
        await update.message.reply_text(
            "Usage: `/analyze <market_id>`\n"
            "Get market ID from `/scan` or Polymarket URL."
        )
        return
    
    market_id = context.args[0].strip()
    
    await update.message.reply_text(f"🔬 Analyzing market: `{market_id}`...", parse_mode='Markdown')
    
    try:
        # Run research pipeline
        research_path = WORKSPACE / "skills" / "polyclaw" / "research.py"
        
        result = subprocess.run(
            [sys.executable, str(research_path), market_id, "--model", "kimi"],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=WORKSPACE / "skills" / "polyclaw"
        )
        
        # Load the analysis output
        analysis_file = POLYMARKET_ANALYSIS_DIR / f"{market_id}_research.json"
        
        if not analysis_file.exists():
            # Check for partial output
            today = datetime.now().strftime('%Y-%m-%d')
            analysis_file = POLYMARKET_ANALYSIS_DIR / f"{market_id}_{today}_research.json"
        
        if analysis_file.exists():
            with open(analysis_file, 'r') as f:
                analysis = json.load(f)
            
            # Format analysis summary
            question = analysis.get('market', {}).get('question', 'Unknown')
            forecast = analysis.get('forecasting', {})
            resolution = analysis.get('resolution', {})
            
            edge = forecast.get('edge_percent', 0)
            signal = forecast.get('trading_signal', 'HOLD')
            confidence = forecast.get('confidence', 0)
            
            message = f"🔍 **Market Analysis**\n\n"
            message += f"**{question[:100]}**\n\n"
            message += f"📊 **Signal:** `{signal}`\n"
            message += f"🎯 **Edge:** `{edge:.1f}%`\n"
            message += f"🎲 **Confidence:** `{confidence}%`\n\n"
            
            # Edge highlight
            if edge > 10:
                message += "⚡ **HIGH EDGE DETECTED** ⚡\n\n"
            
            # Forecast summary
            p_yes = forecast.get('p_yes_estimate', 0)
            market_yes = analysis.get('market', {}).get('yes_price', 0)
            
            message += f"**Forecast:**\n"
            message += f"• P(Yes) Estimate: `{p_yes}%`\n"
            message += f"• Market Yes: `{market_yes:.2f}`\n"
            message += f"• Base Rate: `{forecast.get('base_rate', 'N/A')[:50]}`\n\n"
            
            # Resolution clarity
            clarity = resolution.get('clarity_score', 0)
            message += f"**Resolution Clarity:** `{clarity}/100`\n"
            
            if resolution.get('ambiguity_risks'):
                message += "⚠️ **Risks:**\n"
                for risk in resolution['ambiguity_risks'][:2]:
                    message += f"• {risk[:60]}\n"
            
            message += f"\n_Full analysis saved to analysis directory_"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
            # Check for high edge and trigger alert
            if edge > 10:
                await send_edge_alert(context.bot, analysis)
        else:
            await update.message.reply_text(
                "⚠️ Analysis started but output file not found.\n"
                f"Check logs: `{result.stderr[-200:] if result.stderr else 'No output'}`"
            )
            
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏱️ Analysis timed out. Market may be complex.")
    except Exception as e:
        logger.error(f"Analyze error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def crypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analyze a crypto token."""
    if not await check_auth(update):
        return
    
    if not context.args:
        await update.message.reply_text(
            "Usage: `/crypto <symbol>`\n"
            "Examples: `/crypto PUNCH`, `/crypto SOL`"
        )
        return
    
    symbol = context.args[0].upper().strip()
    
    await update.message.reply_text(f"💎 Analyzing {symbol}...")
    
    try:
        # Run crypto analysis
        analyzer_path = WORKSPACE / "skills" / "crypto-analyst" / "analyze.py"
        
        result = subprocess.run(
            [sys.executable, str(analyzer_path), symbol],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Load analysis result
        analysis_files = list(CRYPTO_ANALYSIS_DIR.glob(f"analysis_{symbol}_*.json"))
        
        if analysis_files:
            # Get most recent
            analysis_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            with open(analysis_files[0], 'r') as f:
                data = json.load(f)
            
            analysis = data.get('analysis', {})
            market = data.get('market_data', {})
            
            signal = analysis.get('signal', 'UNKNOWN').upper()
            confidence = analysis.get('confidence', 0)
            entry = analysis.get('entry_price', 0)
            stop = analysis.get('stop_loss', 0)
            target = analysis.get('take_profit', 0)
            
            # Signal emoji
            signal_emoji = {
                'BUY': '🟢',
                'SELL': '🔴',
                'HOLD': '🟡'
            }.get(signal, '⚪')
            
            message = f"{signal_emoji} **{symbol} Analysis**\n\n"
            message += f"**Signal:** `{signal}` (Confidence: {confidence}%)\n\n"
            message += f"💰 **Price:** `${market.get('price', 0):.8f}`\n"
            message += f"📈 24h Change: `{market.get('price_change_24h', 0):.2f}%`\n"
            message += f"💎 Market Cap: `${market.get('market_cap', 0):,.0f}`\n"
            message += f"📊 Volume 24h: `${market.get('volume_24h', 0):,.0f}`\n\n"
            
            if entry and stop and target:
                message += f"**Trade Levels:**\n"
                message += f"• Entry: `${entry:.8f}`\n"
                message += f"• Stop: `${stop:.8f}`\n"
                message += f"• Target: `${target:.8f}`\n\n"
                
                # R/R calculation
                if entry > 0 and stop > 0 and target > 0:
                    risk = entry - stop
                    reward = target - entry
                    rr = reward / risk if risk > 0 else 0
                    message += f"🎯 R/R Ratio: `{rr:.2f}`\n\n"
            
            # Key reasoning
            reasoning = analysis.get('reasoning', '')
            if reasoning:
                message += f"**Analysis:**\n{reasoning[:200]}...\n\n"
            
            message += f"_Full report: `{analysis_files[0].name}`_"
            
            await update.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                f"⚠️ Analysis complete but no output file found for {symbol}.\n"
                f"Output: `{result.stdout[-300:] if result.stdout else 'No output'}`"
            )
            
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏱️ Analysis timed out. Try again.")
    except Exception as e:
        logger.error(f"Crypto analyze error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current positions and P&L."""
    if not await check_auth(update):
        return
    
    await update.message.reply_text("💼 Loading portfolio...")
    
    try:
        # Check Polymarket positions
        # This would integrate with actual trading data
        polymarket_positions = []
        crypto_positions = []
        
        # Load from analysis directory for recent activity
        recent_analysis = list(POLYMARKET_ANALYSIS_DIR.glob("*_research.json"))
        recent_analysis.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        message = "💼 **Portfolio Overview**\n\n"
        
        # Polymarket Section
        message += "**📊 Polymarket Positions**\n"
        
        # TODO: Integrate with actual position data from polymarket integration
        message += "_No active positions tracked (integration pending)_\n\n"
        
        # Crypto Section  
        message += "**💎 Crypto Positions**\n"
        
        # Check price monitor data
        price_data_file = PRICE_MONITOR_DIR / "data" / "punch_last_price.txt"
        if price_data_file.exists():
            with open(price_data_file, 'r') as f:
                current_price = float(f.read().strip())
            message += f"• PUNCH: ${current_price:.8f}\n"
        else:
            message += "_No positions tracked_\n"
        
        message += "\n**📈 Recent Analysis Activity**\n"
        
        # Recent Polymarket analysis
        if recent_analysis:
            message += "_Polymarket:_\n"
            for f in recent_analysis[:3]:
                try:
                    with open(f, 'r') as fp:
                        data = json.load(fp)
                    question = data.get('market', {}).get('question', 'Unknown')[:40]
                    message += f"• {question}...\n"
                except:
                    pass
        
        # Recent crypto analysis
        recent_crypto = list(CRYPTO_ANALYSIS_DIR.glob("analysis_*.json"))
        recent_crypto.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        if recent_crypto:
            message += "\n_Crypto:_\n"
            for f in recent_crypto[:3]:
                symbol = f.name.split('_')[1]
                message += f"• {symbol}\n"
        
        message += "\n_Use `/scan` and `/crypto` for new opportunities_"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Portfolio error: {e}")
        await update.message.reply_text(f"❌ Error loading portfolio: {str(e)[:200]}")


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent alerts from all monitors."""
    if not await check_auth(update):
        return
    
    await update.message.reply_text("🚨 Loading recent alerts...")
    
    try:
        alerts_data = {"alerts": [], "generated_at": datetime.now().isoformat()}
        
        # Load from alerts log if exists
        if ALERTS_LOG.exists():
            try:
                with open(ALERTS_LOG, 'r') as f:
                    alerts_data = json.load(f)
            except:
                pass
        
        alerts = alerts_data.get('alerts', [])
        
        message = "🚨 **Recent Alerts**\n\n"
        
        if not alerts:
            message += "_No alerts recorded yet.\n"
            message += "Alerts trigger on:_\n"
            message += "• Research edge >10%\n"
            message += "• Whale accumulation detected\n"
            message += "• Price moves >15%\n\n"
        else:
            # Show last 10 alerts
            for alert in alerts[-10:]:
                alert_type = alert.get('type', 'UNKNOWN')
                timestamp = alert.get('timestamp', '')
                msg = alert.get('message', '')
                
                emoji = {
                    'EDGE': '⚡',
                    'WHALE': '🐋',
                    'PRICE': '📈',
                    'DAILY': '📰'
                }.get(alert_type, '🔔')
                
                # Format time
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime('%m/%d %H:%M')
                except:
                    time_str = timestamp[:16] if timestamp else 'Unknown'
                
                message += f"{emoji} [{time_str}] {msg[:80]}\n"
        
        # Check whale tracker for recent activity
        whale_snapshots = list((WHALE_TRACKER_DIR / "data" / "snapshots").glob("*.json"))
        if whale_snapshots:
            whale_snapshots.sort(reverse=True)
            message += f"\n🐋 **Whale Tracker:** {len(whale_snapshots)} snapshots available\n"
        
        # Check price monitor
        price_log = PRICE_MONITOR_DIR / "data" / "punch_monitor.log"
        if price_log.exists():
            # Get last few lines
            try:
                result = subprocess.run(
                    ['tail', '-5', str(price_log)],
                    capture_output=True,
                    text=True
                )
                if result.stdout:
                    message += "\n📈 **Price Monitor (last 5):**\n"
                    for line in result.stdout.strip().split('\n')[-3:]:
                        message += f"`{line[:60]}`\n"
            except:
                pass
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Alerts error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """System health check - all cron jobs and agent status."""
    if not await check_auth(update):
        return
    
    await update.message.reply_text("⚙️ Running system health check...")
    
    try:
        message = "⚙️ **System Health Check**\n\n"
        
        # Check cron jobs
        message += "**📅 Cron Jobs**\n"
        try:
            result = subprocess.run(
                ['crontab', '-l'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                cron_lines = [l for l in result.stdout.split('\n') if l.strip() and not l.startswith('#')]
                message += f"• Active jobs: `{len(cron_lines)}`\n"
                
                # Check for specific jobs
                if 'whale' in result.stdout.lower():
                    message += "• ✅ Whale tracker scheduled\n"
                if 'price' in result.stdout.lower() or 'punch' in result.stdout.lower():
                    message += "• ✅ Price monitor scheduled\n"
                if 'polymarket' in result.stdout.lower() or 'polyclaw' in result.stdout.lower():
                    message += "• ✅ Polymarket scheduled\n"
            else:
                message += "• ⚠️ No crontab found\n"
        except Exception as e:
            message += f"• ❌ Cron check failed: {e}\n"
        
        message += "\n**🔧 Skills Status**\n"
        
        # Check each skill
        skills = [
            ('polyclaw', 'Polymarket Scanner'),
            ('crypto-analyst', 'Crypto Analyst'),
            ('whale-tracker', 'Whale Tracker'),
            ('price-monitor', 'Price Monitor'),
        ]
        
        for skill_dir, skill_name in skills:
            skill_path = WORKSPACE / "skills" / skill_dir
            if skill_path.exists():
                message += f"• ✅ {skill_name}\n"
            else:
                message += f"• ❌ {skill_name} (missing)\n"
        
        message += "\n**📊 Analysis Data**\n"
        
        # Count analysis files
        poly_count = len(list(POLYMARKET_ANALYSIS_DIR.glob("*.json"))) if POLYMARKET_ANALYSIS_DIR.exists() else 0
        crypto_count = len(list(CRYPTO_ANALYSIS_DIR.glob("*.json"))) if CRYPTO_ANALYSIS_DIR.exists() else 0
        
        message += f"• Polymarket analysis: `{poly_count}` files\n"
        message += f"• Crypto analysis: `{crypto_count}` files\n"
        
        # Bot status
        message += "\n**🤖 Bot Status**\n"
        message += "• ✅ Telegram bot running\n"
        message += f"• PID: `{os.getpid()}`\n"
        message += f"• Uptime: Check logs for start time\n"
        
        # Check disk space
        try:
            result = subprocess.run(
                ['df', '-h', str(WORKSPACE)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 5:
                        message += f"\n💾 **Disk:** `{parts[4]}` used\n"
        except:
            pass
        
        message += "\n✅ System check complete"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Status error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


# ============================================================================
# PUSH ALERT FUNCTIONS
# ============================================================================

async def send_edge_alert(bot, analysis: Dict):
    """Send alert when research finds edge >10%."""
    try:
        forecast = analysis.get('forecasting', {})
        market = analysis.get('market', {})
        
        edge = forecast.get('edge_percent', 0)
        signal = forecast.get('trading_signal', 'HOLD')
        confidence = forecast.get('confidence', 0)
        question = market.get('question', 'Unknown')
        
        message = "⚡ **HIGH EDGE ALERT** ⚡\n\n"
        message += f"**{question[:100]}**\n\n"
        message += f"🎯 **Edge:** `{edge:.1f}%`\n"
        message += f"📊 **Signal:** `{signal}`\n"
        message += f"🎲 **Confidence:** `{confidence}%`\n\n"
        
        p_yes = forecast.get('p_yes_estimate', 0)
        market_yes = market.get('yes_price', 0)
        
        message += f"• P(Yes) Estimate: `{p_yes}%`\n"
        message += f"• Market Yes Price: `{market_yes:.2f}`\n"
        message += f"• Expected Value: `+{edge:.1f}%`\n\n"
        
        # Add reasoning
        reasoning = forecast.get('reasoning', '')
        if reasoning:
            message += f"**Reasoning:**\n{reasoning[:150]}...\n\n"
        
        message += f"🔍 `/analyze {market.get('market_id', '')}` for full details"
        
        await bot.send_message(
            chat_id=AUTHORIZED_USER_ID,
            text=message,
            parse_mode='Markdown'
        )
        
        # Log the alert
        log_alert('EDGE', f"Edge {edge:.1f}% on {question[:50]}")
        
    except Exception as e:
        logger.error(f"Edge alert error: {e}")


async def send_whale_alert(bot, whale_data: Dict):
    """Send alert when whale tracker detects major accumulation."""
    try:
        token = whale_data.get('token', 'Unknown')
        buyers = whale_data.get('buyer_count', 0)
        confidence = whale_data.get('confidence', 0)
        
        message = "🐋 **WHALE ACCUMULATION ALERT** 🐋\n\n"
        message += f"**Token:** `{token}`\n"
        message += f"👥 **Whale Buyers:** `{buyers}`\n"
        message += f"🎯 **Confidence:** `{confidence}%`\n\n"
        
        if whale_data.get('details'):
            message += "**Details:**\n"
            for detail in whale_data['details'][:3]:
                message += f"• {detail}\n"
        
        await bot.send_message(
            chat_id=AUTHORIZED_USER_ID,
            text=message,
            parse_mode='Markdown'
        )
        
        log_alert('WHALE', f"{buyers} whales accumulating {token}")
        
    except Exception as e:
        logger.error(f"Whale alert error: {e}")


async def send_price_alert(bot, symbol: str, change_pct: float, price: float):
    """Send alert when price monitor detects >15% move."""
    try:
        direction = "📈" if change_pct > 0 else "📉"
        
        message = f"{direction} **PRICE ALERT** {direction}\n\n"
        message += f"**{symbol}** moved **{change_pct:+.2f}%**\n\n"
        message += f"💰 Current Price: `${price:.8f}`\n"
        message += f"⏱️ Time: `{datetime.now().strftime('%H:%M:%S')}`\n\n"
        
        if change_pct > 15:
            message += "⚠️ Significant upward movement detected\n"
        elif change_pct < -15:
            message += "🔻 Significant downward movement detected\n"
        
        message += f"\n`/crypto {symbol}` for full analysis"
        
        await bot.send_message(
            chat_id=AUTHORIZED_USER_ID,
            text=message,
            parse_mode='Markdown'
        )
        
        log_alert('PRICE', f"{symbol} moved {change_pct:+.2f}%")
        
    except Exception as e:
        logger.error(f"Price alert error: {e}")


async def send_daily_brief(bot):
    """Send daily brief at 8am with top opportunities."""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        
        message = f"📰 **Daily Brief - {today}**\n\n"
        
        # Top Polymarket opportunities
        message += "**📊 Top Polymarket Opportunities**\n"
        
        scan_file = POLYMARKET_ANALYSIS_DIR / f"scan_{today}.json"
        if not scan_file.exists():
            scan_file = WORKSPACE / "skills" / "polyclaw" / "data" / "markets_latest.json"
        
        if scan_file.exists():
            with open(scan_file, 'r') as f:
                data = json.load(f)
            
            for m in data.get('top_markets', [])[:3]:
                question = m.get('question', 'Unknown')[:50]
                score = m.get('total_score', 0)
                yes_price = m.get('yes_price', 0)
                message += f"• {question}... (Score: {score}, Yes: {yes_price:.2f})\n"
        else:
            message += "_No scan data available. Run /scan to update_\n"
        
        # Whale tracker summary
        message += "\n**🐋 Whale Tracker**\n"
        whale_dir = WHALE_TRACKER_DIR / "data" / "snapshots"
        if whale_dir.exists():
            snapshots = list(whale_dir.glob("*.json"))
            if snapshots:
                message += f"• {len(snapshots)} daily snapshots\n"
                message += "• Check /alerts for recent activity\n"
            else:
                message += "_No whale data yet_\n"
        
        # Price monitor
        message += "\n**💎 Price Monitor**\n"
        price_file = PRICE_MONITOR_DIR / "data" / "punch_last_price.txt"
        if price_file.exists():
            with open(price_file, 'r') as f:
                price = float(f.read().strip())
            message += f"• PUNCH: ${price:.8f}\n"
        
        message += "\n_Good luck with today's trades! 🚀_"
        
        await bot.send_message(
            chat_id=AUTHORIZED_USER_ID,
            text=message,
            parse_mode='Markdown'
        )
        
        # Mark as sent
        with open(DAILY_BRIEF_SENT, 'w') as f:
            f.write(today)
        
        log_alert('DAILY', f"Daily brief sent for {today}")
        
    except Exception as e:
        logger.error(f"Daily brief error: {e}")


def log_alert(alert_type: str, message: str):
    """Log alert to alerts.json."""
    try:
        ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
        
        alerts_data = {"alerts": [], "generated_at": datetime.now().isoformat()}
        if ALERTS_LOG.exists():
            try:
                with open(ALERTS_LOG, 'r') as f:
                    alerts_data = json.load(f)
            except:
                pass
        
        alerts_data['alerts'].append({
            'type': alert_type,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only last 100 alerts
        alerts_data['alerts'] = alerts_data['alerts'][-100:]
        
        with open(ALERTS_LOG, 'w') as f:
            json.dump(alerts_data, f, indent=2)
            
    except Exception as e:
        logger.error(f"Log alert error: {e}")


# ============================================================================
# BACKGROUND MONITORING
# ============================================================================

async def monitor_task(context: ContextTypes.DEFAULT_TYPE):
    """Background task to check for alerts."""
    try:
        now = datetime.now()
        
        # Check if daily brief should be sent (at 8am)
        if now.hour == 8 and now.minute < 5:
            today = now.strftime('%Y-%m-%d')
            should_send = True
            
            if DAILY_BRIEF_SENT.exists():
                with open(DAILY_BRIEF_SENT, 'r') as f:
                    if f.read().strip() == today:
                        should_send = False
            
            if should_send:
                await send_daily_brief(context.bot)
        
        # Check price monitor for significant moves
        await check_price_alerts(context.bot)
        
        # Check whale tracker
        await check_whale_alerts(context.bot)
        
    except Exception as e:
        logger.error(f"Monitor task error: {e}")


async def check_price_alerts(bot):
    """Check price monitor for >15% moves."""
    try:
        # Read current and previous prices
        price_file = PRICE_MONITOR_DIR / "data" / "punch_last_price.txt"
        history_file = PRICE_MONITOR_DIR / "data" / "price_history.json"
        
        if not price_file.exists():
            return
        
        with open(price_file, 'r') as f:
            current_price = float(f.read().strip())
        
        # Load history
        history = []
        if history_file.exists():
            with open(history_file, 'r') as f:
                history = json.load(f)
        
        # Check last hour's price
        if history:
            last_hour = now = datetime.now() - timedelta(hours=1)
            recent = [h for h in history if datetime.fromisoformat(h['time']) > last_hour]
            
            if recent:
                old_price = recent[0]['price']
                change_pct = ((current_price - old_price) / old_price) * 100
                
                if abs(change_pct) > 15:
                    await send_price_alert(bot, 'PUNCH', change_pct, current_price)
        
        # Update history
        history.append({
            'time': datetime.now().isoformat(),
            'price': current_price
        })
        
        # Keep last 24 hours
        cutoff = datetime.now() - timedelta(hours=24)
        history = [h for h in history if datetime.fromisoformat(h['time']) > cutoff]
        
        with open(history_file, 'w') as f:
            json.dump(history, f)
            
    except Exception as e:
        logger.error(f"Price check error: {e}")


async def check_whale_alerts(bot):
    """Check whale tracker for new accumulation signals."""
    try:
        # Check latest whale snapshot
        whale_dir = WHALE_TRACKER_DIR / "data" / "snapshots"
        if not whale_dir.exists():
            return
        
        snapshots = list(whale_dir.glob("*.json"))
        if not snapshots:
            return
        
        # Get most recent
        snapshots.sort(reverse=True)
        latest = snapshots[0]
        
        # Check if already alerted on this snapshot
        alerted_file = WORKSPACE / "skills" / "telegram-bot" / "data" / "last_whale_alert.txt"
        if alerted_file.exists():
            with open(alerted_file, 'r') as f:
                if f.read().strip() == latest.name:
                    return  # Already alerted
        
        with open(latest, 'r') as f:
            data = json.load(f)
        
        # Look for major accumulation signals
        for token_data in data.get('tokens', []):
            if token_data.get('buyer_count', 0) >= 3 and token_data.get('confidence', 0) > 70:
                await send_whale_alert(bot, token_data)
                
                # Mark as alerted
                with open(alerted_file, 'w') as f:
                    f.write(latest.name)
                break
                
    except Exception as e:
        logger.error(f"Whale check error: {e}")


# ============================================================================
# MAIN
# ============================================================================

def get_token() -> str:
    """Get bot token from file or environment."""
    # Try file first
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'r') as f:
            return f.read().strip()
    
    # Try environment
    token = os.environ.get('WHALE_TELEGRAM_BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
    if token:
        return token
    
    raise ValueError(
        f"Bot token not found. Please set it in {TOKEN_FILE} "
        "or set WHALE_TELEGRAM_BOT_TOKEN environment variable."
    )


def main():
    """Start the bot."""
    print("🤖 Starting Polyclaw Telegram Bot...")
    
    # Ensure data directory exists
    (WORKSPACE / "skills" / "telegram-bot" / "data").mkdir(parents=True, exist_ok=True)
    
    # Get token
    try:
        token = get_token()
        print("✅ Token loaded")
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("scan", scan_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("crypto", crypto_command))
    application.add_handler(CommandHandler("portfolio", portfolio_command))
    application.add_handler(CommandHandler("alerts", alerts_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # Schedule background monitoring
    job_queue = application.job_queue
    job_queue.run_repeating(monitor_task, interval=300, first=60)  # Every 5 minutes
    
    print("✅ Bot configured")
    print(f"✅ Authorized user: {AUTHORIZED_USER_ID}")
    print("🚀 Starting polling...")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()