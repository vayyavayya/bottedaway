#!/usr/bin/env python3
"""
Whale Tracker - Autonomous whale monitoring system
Monitors curated wallets, detects new buys, scores via Engines A/B/C, generates reports
"""

import os
import sys
import json
import time
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import logging

# Configuration
MIN_LIQUIDITY_USD = 25000
MIN_VOL_USD = 50000
MAX_TOP10_PCT = 35
WHALE_CONFIRM_MIN_WALLETS = 2
AUTO_ADD_MIN_COMMON_TOKENS = 5
AUTO_REMOVE_INACTIVE_DAYS = 45
AUTO_REMOVE_LOSER_DAYS = 30

DATA_DIR = Path(__file__).parent.parent / "data"
WHALES_DIR = DATA_DIR / "whales"
SNAPSHOTS_DIR = WHALES_DIR / "snapshots"
REPORTS_DIR = DATA_DIR / "reports"

# Ensure directories exist
for d in [WHALES_DIR, SNAPSHOTS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Wallet:
    address: str
    label: Optional[str]
    added_at: str
    source: str
    confidence: float
    notes: str


@dataclass
class TokenBuy:
    token_address: str
    token_symbol: Optional[str]
    token_name: Optional[str]
    wallet_address: str
    wallet_label: Optional[str]
    timestamp: str
    amount: float
    value_usd: Optional[float]
    dex: Optional[str]
    pool: Optional[str]
    tx_hash: str
    tx_link: str


@dataclass
class TokenEnrichment:
    token_address: str
    age_days: Optional[float]
    liquidity_usd: Optional[float]
    volume_24h: Optional[float]
    top10_pct: Optional[float]
    top1_pct: Optional[float]
    mint_authority: Optional[bool]
    freeze_authority: Optional[bool]
    lp_locked: Optional[bool]
    deployer_dumped: Optional[bool]
    whale_confirmation_count: int = 0


@dataclass
class EngineScores:
    A_score: float
    A_notes: str
    B_score: float
    B_notes: str
    C_score: float
    C_notes: str
    composite: float
    risk_flag: bool


@dataclass
class ScoredToken:
    token_address: str
    token_symbol: Optional[str]
    buys: List[TokenBuy]
    enrichment: TokenEnrichment
    scores: EngineScores
    status: str  # PASS, WATCH, REJECT
    reject_reasons: List[str]


class WhaleTracker:
    def __init__(self):
        self.whales_file = WHALES_DIR / "whales.json"
        self.candidates_file = WHALES_DIR / "candidates.json"
        self.last_run_file = WHALES_DIR / "last_run.json"
        self.network = "solana"
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"Accept": "application/json"},
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def load_whales(self) -> List[Wallet]:
        """Load canonical watchlist"""
        if not self.whales_file.exists():
            default = {"network": "solana", "watchlist": []}
            self.whales_file.write_text(json.dumps(default, indent=2))
            return []
        
        data = json.loads(self.whales_file.read_text())
        self.network = data.get("network", "solana")
        return [Wallet(**w) for w in data.get("watchlist", [])]
    
    def save_whales(self, wallets: List[Wallet]):
        """Save canonical watchlist"""
        data = {
            "network": self.network,
            "watchlist": [asdict(w) for w in wallets]
        }
        self.whales_file.write_text(json.dumps(data, indent=2))
    
    def add_wallet(self, address: str, label: Optional[str] = None, notes: str = ""):
        """Add new wallet to watchlist"""
        wallets = self.load_whales()
        
        # De-duplicate
        if any(w.address == address for w in wallets):
            logger.info(f"Wallet {address[:8]}... already in watchlist")
            return
        
        wallets.append(Wallet(
            address=address,
            label=label,
            added_at=datetime.now().strftime("%Y-%m-%d"),
            source="manual",
            confidence=0.5,
            notes=notes
        ))
        
        self.save_whales(wallets)
        logger.info(f"Added wallet {address[:8]}... to watchlist")
    
    def check_last_run(self) -> bool:
        """Check if 24h have passed since last run"""
        if not self.last_run_file.exists():
            return True
        
        data = json.loads(self.last_run_file.read_text())
        last_run = datetime.fromisoformat(data.get("last_run_iso", "2000-01-01"))
        return datetime.now() - last_run >= timedelta(hours=24)
    
    def update_last_run(self):
        """Update last run timestamp"""
        self.last_run_file.write_text(json.dumps({
            "last_run_iso": datetime.now().isoformat()
        }))
    
    async def fetch_wallet_transactions(self, wallet: Wallet) -> List[Dict]:
        """Fetch recent transactions for a wallet"""
        # Use Helius or Solscan API
        api_key = os.getenv("HELIUS_API_KEY") or os.getenv("SOLSCAN_API_KEY")
        
        if api_key and os.getenv("HELIUS_API_KEY"):
            url = f"https://api.helius.xyz/v0/addresses/{wallet.address}/transactions"
            params = {"api-key": api_key, "limit": 100}
        else:
            # Fallback to public Solscan API (rate limited)
            url = f"https://api.solscan.io/account/transactions"
            params = {"address": wallet.address, "limit": 50}
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data if isinstance(data, list) else data.get("data", [])
                else:
                    logger.warning(f"API error for {wallet.address[:8]}: {resp.status}")
                    return []
        except Exception as e:
            logger.error(f"Fetch error for {wallet.address[:8]}: {e}")
            return []
    
    def extract_swap_events(self, txs: List[Dict], wallet: Wallet) -> List[TokenBuy]:
        """Extract token swap/buy events from transactions"""
        buys = []
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        for tx in txs:
            # Parse timestamp
            ts_str = tx.get("timestamp") or tx.get("blockTime")
            if not ts_str:
                continue
                
            try:
                if isinstance(ts_str, (int, float)):
                    tx_time = datetime.fromtimestamp(ts_str)
                else:
                    tx_time = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            except:
                continue
            
            if tx_time < cutoff_time:
                continue
            
            # Look for swap events (simplified - real impl would parse instructions)
            token_changes = tx.get("tokenChanges", [])
            for change in token_changes:
                if change.get("changeType") == "inc" and change.get("amount", 0) > 0:
                    buys.append(TokenBuy(
                        token_address=change.get("tokenAddress", "UNKNOWN"),
                        token_symbol=change.get("tokenSymbol"),
                        token_name=change.get("tokenName"),
                        wallet_address=wallet.address,
                        wallet_label=wallet.label,
                        timestamp=tx_time.isoformat(),
                        amount=change.get("amount", 0),
                        value_usd=change.get("valueUSD"),
                        dex=tx.get("source"),
                        pool=None,
                        tx_hash=tx.get("signature", tx.get("txHash", "")),
                        tx_link=f"https://solscan.io/tx/{tx.get('signature', '')}"
                    ))
        
        return buys
    
    async def enrich_token(self, token_address: str, all_buys: List[TokenBuy]) -> TokenEnrichment:
        """Enrich token data with market info"""
        # Count whale confirmations
        wallet_count = len(set(b.wallet_address for b in all_buys if b.token_address == token_address))
        
        # Fetch from DexScreener
        try:
            async with self.session.get(
                f"https://api.dexscreener.com/latest/dex/tokens/solana/{token_address}"
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        best = max(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0) or 0)
                        liq = best.get("liquidity", {}).get("usd")
                        vol = best.get("volume", {}).get("h24")
                        
                        # Calculate age from pair created
                        created = best.get("pairCreatedAt")
                        age_days = None
                        if created:
                            age_days = (datetime.now() - datetime.fromtimestamp(created/1000)).days
                        
                        return TokenEnrichment(
                            token_address=token_address,
                            age_days=age_days,
                            liquidity_usd=liq,
                            volume_24h=vol,
                            top10_pct=None,  # Would need additional API
                            top1_pct=None,
                            mint_authority=None,
                            freeze_authority=None,
                            lp_locked=None,
                            deployer_dumped=None,
                            whale_confirmation_count=wallet_count
                        )
        except Exception as e:
            logger.error(f"Enrichment error for {token_address[:8]}: {e}")
        
        return TokenEnrichment(
            token_address=token_address,
            whale_confirmation_count=wallet_count
        )
    
    def score_engine_a(self, enrichment: TokenEnrichment, buys: List[TokenBuy]) -> tuple[float, str]:
        """Engine A: Market Structure"""
        score = 50.0
        notes = []
        
        # Age scoring (4-10 days is sweet spot)
        if enrichment.age_days is not None:
            if 4 <= enrichment.age_days <= 10:
                score += 20
                notes.append(f"Sweet spot age: {enrichment.age_days}d")
            elif enrichment.age_days < 4:
                score -= 15
                notes.append(f"Too fresh: {enrichment.age_days}d")
            elif enrichment.age_days > 30:
                score -= 10
                notes.append(f"Aging: {enrichment.age_days}d")
        
        # Whale confirmation boost
        if enrichment.whale_confirmation_count >= WHALE_CONFIRM_MIN_WALLETS:
            score += 15
            notes.append(f"Whale cluster: {enrichment.whale_confirmation_count}")
        
        return min(100, max(0, score)), "; ".join(notes) or "No strong signals"
    
    def score_engine_b(self, enrichment: TokenEnrichment) -> tuple[float, str]:
        """Engine B: Flow + Liquidity"""
        score = 50.0
        notes = []
        
        # Liquidity scoring
        if enrichment.liquidity_usd:
            if enrichment.liquidity_usd >= 100000:
                score += 25
                notes.append(f"Strong liquidity: ${enrichment.liquidity_usd:,.0f}")
            elif enrichment.liquidity_usd >= MIN_LIQUIDITY_USD:
                score += 10
                notes.append(f"Adequate liquidity: ${enrichment.liquidity_usd:,.0f}")
            else:
                score -= 20
                notes.append(f"Low liquidity: ${enrichment.liquidity_usd:,.0f}")
        
        # Volume scoring
        if enrichment.volume_24h:
            if enrichment.volume_24h >= MIN_VOL_USD * 2:
                score += 15
                notes.append(f"Good volume: ${enrichment.volume_24h:,.0f}")
            elif enrichment.volume_24h >= MIN_VOL_USD:
                score += 5
                notes.append(f"Min volume: ${enrichment.volume_24h:,.0f}")
            else:
                score -= 15
                notes.append(f"Low volume: ${enrichment.volume_24h:,.0f}")
        
        return min(100, max(0, score)), "; ".join(notes) or "Insufficient data"
    
    def score_engine_c(self, enrichment: TokenEnrichment) -> tuple[float, str]:
        """Engine C: Risk / Rug Surface"""
        score = 50.0
        notes = []
        risk_flag = False
        
        # Holder concentration
        if enrichment.top10_pct is not None:
            if enrichment.top10_pct > MAX_TOP10_PCT:
                score -= 30
                risk_flag = True
                notes.append(f"High top10: {enrichment.top10_pct:.1f}%")
            elif enrichment.top10_pct > 25:
                score -= 10
                notes.append(f"Elevated top10: {enrichment.top10_pct:.1f}%")
            else:
                score += 10
                notes.append(f"Good distribution: {enrichment.top10_pct:.1f}%")
        
        # Authorities
        if enrichment.mint_authority:
            score -= 20
            risk_flag = True
            notes.append("Mint authority enabled")
        
        if enrichment.freeze_authority:
            score -= 15
            notes.append("Freeze authority enabled")
        
        # LP status
        if enrichment.lp_locked:
            score += 10
            notes.append("LP locked")
        elif enrichment.lp_locked is False:
            score -= 15
            risk_flag = True
            notes.append("LP unlocked")
        
        return min(100, max(0, score)), "; ".join(notes) or "No red flags", risk_flag
    
    def apply_strategy_filters(
        self, 
        enrichment: TokenEnrichment, 
        scores: EngineScores
    ) -> tuple[str, List[str]]:
        """Apply hard strategy gates"""
        reject_reasons = []
        
        # Gate 1: Liquidity
        if enrichment.liquidity_usd is not None and enrichment.liquidity_usd < MIN_LIQUIDITY_USD:
            reject_reasons.append(f"LIQUIDITY < ${MIN_LIQUIDITY_USD:,}")
        
        # Gate 2: Volume
        if enrichment.volume_24h is not None and enrichment.volume_24h < MIN_VOL_USD:
            reject_reasons.append(f"VOLUME < ${MIN_VOL_USD:,}")
        
        # Gate 3: Concentration
        if enrichment.top10_pct is not None and enrichment.top10_pct > MAX_TOP10_PCT:
            reject_reasons.append(f"TOP10 > {MAX_TOP10_PCT}%")
        
        # Gate 4: Structure (simplified - would need chart data)
        if scores.A_score < 40:
            reject_reasons.append("WEAK_STRUCTURE")
        
        # Determine status
        if reject_reasons:
            if scores.composite >= 70 and enrichment.whale_confirmation_count >= 2:
                return "WATCH", reject_reasons  # High potential but needs confirmation
            return "REJECT", reject_reasons
        
        if scores.composite >= 60:
            return "PASS", []
        
        return "WATCH", ["LOW_COMPOSITE"]
    
    async def run_analysis(self) -> List[ScoredToken]:
        """Main analysis pipeline"""
        wallets = self.load_whales()
        if not wallets:
            logger.warning("No wallets in watchlist")
            return []
        
        logger.info(f"Analyzing {len(wallets)} wallets...")
        
        # Collect all transactions
        all_buys: List[TokenBuy] = []
        for wallet in wallets:
            txs = await self.fetch_wallet_transactions(wallet)
            buys = self.extract_swap_events(txs, wallet)
            all_buys.extend(buys)
            logger.info(f"  {wallet.label or wallet.address[:8]}...: {len(buys)} buys")
            await asyncio.sleep(0.5)  # Rate limit
        
        # Group by token
        token_buys = defaultdict(list)
        for buy in all_buys:
            token_buys[buy.token_address].append(buy)
        
        logger.info(f"Found {len(token_buys)} unique tokens")
        
        # Enrich and score each token
        scored_tokens: List[ScoredToken] = []
        for token_address, buys in token_buys.items():
            # Enrich
            enrichment = await self.enrich_token(token_address, all_buys)
            
            # Score engines
            a_score, a_notes = self.score_engine_a(enrichment, buys)
            b_score, b_notes = self.score_engine_b(enrichment)
            c_score, c_notes, risk_flag = self.score_engine_c(enrichment)
            
            composite = 0.40 * a_score + 0.35 * b_score + 0.25 * c_score
            
            scores = EngineScores(
                A_score=a_score,
                A_notes=a_notes,
                B_score=b_score,
                B_notes=b_notes,
                C_score=c_score,
                C_notes=c_notes,
                composite=composite,
                risk_flag=risk_flag
            )
            
            # Apply filters
            status, reject_reasons = self.apply_strategy_filters(enrichment, scores)
            
            scored_tokens.append(ScoredToken(
                token_address=token_address,
                token_symbol=buys[0].token_symbol,
                buys=buys,
                enrichment=enrichment,
                scores=scores,
                status=status,
                reject_reasons=reject_reasons
            ))
            
            await asyncio.sleep(0.2)
        
        return scored_tokens
    
    def generate_html_report(self, tokens: List[ScoredToken], date_str: str) -> str:
        """Generate HTML report"""
        pass_tokens = [t for t in tokens if t.status == "PASS"]
        watch_tokens = [t for t in tokens if t.status == "WATCH"]
        reject_tokens = [t for t in tokens if t.status == "REJECT"]
        
        # Sort by composite score
        pass_tokens.sort(key=lambda x: x.scores.composite, reverse=True)
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>WhaleTracker Daily — {date_str}</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #0a0a0f; color: #e0e0e0; }}
        h1 {{ color: #00ff88; border-bottom: 2px solid #00ff88; padding-bottom: 10px; }}
        h2 {{ color: #00ccff; margin-top: 30px; }}
        .summary {{ background: #1a1a2e; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .token {{ background: #16162a; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #333; }}
        .token.pass {{ border-left-color: #00ff88; }}
        .token.watch {{ border-left-color: #ffaa00; }}
        .token.reject {{ border-left-color: #ff4444; }}
        .score {{ font-size: 24px; font-weight: bold; color: #00ff88; }}
        .score.low {{ color: #ff4444; }}
        .score.mid {{ color: #ffaa00; }}
        .meta {{ color: #888; font-size: 14px; }}
        .wallets {{ background: #0f0f1a; padding: 10px; border-radius: 4px; margin: 10px 0; }}
        .wallet {{ display: inline-block; background: #252540; padding: 4px 8px; margin: 2px; border-radius: 4px; font-size: 12px; }}
        .reject-reason {{ color: #ff6666; font-size: 12px; }}
        a {{ color: #00ccff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ color: #00ccff; }}
    </style>
</head>
<body>
    <h1>🐋 WhaleTracker Daily — {date_str}</h1>
    
    <div class="summary">
        <h3>Summary</h3>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Wallets Scanned</td><td>{len(self.load_whales())}</td></tr>
            <tr><td>New Tokens Detected</td><td>{len(tokens)}</td></tr>
            <tr><td>✅ PASS</td><td>{len(pass_tokens)}</td></tr>
            <tr><td>⚠️ WATCH</td><td>{len(watch_tokens)}</td></tr>
            <tr><td>❌ REJECT</td><td>{len(reject_tokens)}</td></tr>
        </table>
    </div>
"""
        
        # PASS section
        if pass_tokens:
            html += "<h2>✅ PASS (High Conviction)</h2>"
            for t in pass_tokens:
                score_class = "low" if t.scores.composite < 50 else "mid" if t.scores.composite < 70 else ""
                html += f"""
    <div class="token pass">
        <div class="score {score_class}">{t.scores.composite:.1f}</div>
        <strong>{t.token_symbol or 'UNKNOWN'} ({t.token_address[:8]}...)</strong>
        <div class="meta">
            Age: {t.enrichment.age_days or '?'}d | 
            Liquidity: ${t.enrichment.liquidity_usd or 0:,.0f} | 
            Volume 24h: ${t.enrichment.volume_24h or 0:,.0f}
        </div>
        <div class="wallets">
            Wallets: {' '.join(f'<span class="wallet">{b.wallet_label or b.wallet_address[:6]}@{b.timestamp[11:16]}</span>' for b in t.buys)}
        </div>
        <div>
            A: {t.scores.A_score:.0f} | B: {t.scores.B_score:.0f} | C: {t.scores.C_score:.0f}
            {'⚠️ RISK FLAG' if t.scores.risk_flag else ''}
        </div>
        <div><a href="https://dexscreener.com/solana/{t.token_address}" target="_blank">DexScreener</a> | <a href="https://solscan.io/token/{t.token_address}" target="_blank">Solscan</a></div>
    </div>
"""
        
        # WATCH section
        if watch_tokens:
            html += "<h2>⚠️ WATCH (Needs Confirmation)</h2>"
            for t in watch_tokens[:5]:  # Limit to top 5
                html += f"""
    <div class="token watch">
        <div class="score">{t.scores.composite:.1f}</div>
        <strong>{t.token_symbol or 'UNKNOWN'} ({t.token_address[:8]}...)</strong>
        <div class="reject-reason">Reasons: {', '.join(t.reject_reasons)}</div>
    </div>
"""
        
        # REJECT section (collapsed)
        if reject_tokens:
            html += f"<h2>❌ REJECTED ({len(reject_tokens)} tokens)</h2>"
            html += "<details><summary>View rejected tokens</summary>"
            for t in reject_tokens[:10]:  # Show first 10
                html += f"""
    <div class="token reject">
        <strong>{t.token_symbol or 'UNKNOWN'}</strong>
        <span class="reject-reason">{', '.join(t.reject_reasons)}</span>
    </div>
"""
            html += "</details>"
        
        html += """
</body>
</html>
"""
        return html
    
    async def post_to_telegram(self, tokens: List[ScoredToken], date_str: str):
        """Post summary to Telegram"""
        bot_token = os.getenv("WHALE_TELEGRAM_BOT_TOKEN")
        channel = os.getenv("WHALE_TELEGRAM_CHANNEL", "@whalesarebitches")
        
        if not bot_token:
            logger.warning("WHALE_TELEGRAM_BOT_TOKEN not set - skipping Telegram post")
            print("\n" + "="*60)
            print("DRY RUN: Missing WHALE_TELEGRAM_BOT_TOKEN")
            print("="*60)
            return False
        
        pass_tokens = sorted([t for t in tokens if t.status == "PASS"], 
                           key=lambda x: x.scores.composite, reverse=True)[:3]
        watch_count = len([t for t in tokens if t.status == "WATCH"])
        
        message = f"""🐋 <b>WhaleTracker Daily — {date_str}</b>

<b>Top Picks:</b>
"""
        for i, t in enumerate(pass_tokens, 1):
            rationale = t.scores.A_notes[:50] if len(t.scores.A_notes) < 50 else t.scores.A_notes[:47] + "..."
            message += f"""
{i}. <b>{t.token_symbol or 'UNKNOWN'}</b> — {t.scores.composite:.0f}/100
   {rationale}"""
        
        message += f"""

⚠️ <b>WATCH:</b> {watch_count} tokens need confirmation

<a href="https://github.com/vayyavayya/bottedaway/tree/main/skills/whale-tracker/data/reports">View Full Report</a>
"""
        
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            async with self.session.post(url, json={
                "chat_id": channel,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }) as resp:
                if resp.status == 200:
                    logger.info("Telegram post sent successfully")
                    return True
                else:
                    logger.error(f"Telegram API error: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Telegram post failed: {e}")
            return False
    
    async def run(self, force: bool = False):
        """Main entry point"""
        if not force and not self.check_last_run():
            logger.info("Less than 24h since last run - skipping (use --force to override)")
            return
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"Starting WhaleTracker run for {date_str}")
        
        # Run analysis
        tokens = await self.run_analysis()
        
        # Save snapshot
        snapshot_file = SNAPSHOTS_DIR / f"{date_str}.json"
        snapshot_file.write_text(json.dumps({
            "date": date_str,
            "wallets_scanned": len(self.load_whales()),
            "tokens_found": len(tokens),
            "tokens": [{
                "address": t.token_address,
                "symbol": t.token_symbol,
                "status": t.status,
                "composite": t.scores.composite,
                "buys": len(t.buys)
            } for t in tokens]
        }, indent=2))
        
        # Generate report
        html = self.generate_html_report(tokens, date_str)
        (REPORTS_DIR / f"{date_str}.html").write_text(html)
        (REPORTS_DIR / "latest.html").write_text(html)
        
        logger.info(f"Report saved to {REPORTS_DIR / date_str}.html")
        
        # Post to Telegram
        await self.post_to_telegram(tokens, date_str)
        
        # Update last run
        self.update_last_run()
        
        # Summary
        print("\n" + "="*60)
        print(f"WHALETRACKER COMPLETE — {date_str}")
        print("="*60)
        print(f"Wallets: {len(self.load_whales())}")
        print(f"Tokens: {len(tokens)}")
        print(f"  PASS: {len([t for t in tokens if t.status == 'PASS'])}")
        print(f"  WATCH: {len([t for t in tokens if t.status == 'WATCH'])}")
        print(f"  REJECT: {len([t for t in tokens if t.status == 'REJECT'])}")
        print(f"Report: {REPORTS_DIR / date_str}.html")
        print("="*60)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Whale Tracker - Smart money monitoring")
    parser.add_argument("--add-wallet", help="Add wallet address to watchlist")
    parser.add_argument("--label", help="Label for wallet")
    parser.add_argument("--notes", help="Notes about wallet", default="")
    parser.add_argument("--force", action="store_true", help="Force run regardless of last run time")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    
    args = parser.parse_args()
    
    tracker = WhaleTracker()
    
    if args.add_wallet:
        tracker.add_wallet(args.add_wallet, args.label, args.notes)
        return
    
    if args.dry_run:
        print("DRY RUN MODE")
        wallets = tracker.load_whales()
        print(f"Would scan {len(wallets)} wallets:")
        for w in wallets:
            print(f"  - {w.label or w.address[:16]}... ({w.source})")
        return
    
    asyncio.run(run_tracker(tracker, args.force))


async def run_tracker(tracker: WhaleTracker, force: bool):
    async with tracker:
        await tracker.run(force)


if __name__ == "__main__":
    main()
