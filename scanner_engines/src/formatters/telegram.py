"""Format alerts for Telegram."""
from typing import Dict, Any

def alert_to_telegram_text(alert: Dict[str, Any]) -> str:
    """Convert alert dict to Telegram message text with Naomi rules."""
    pattern = alert.get("pattern", "?")
    chain = alert.get("chain", "?")
    address = alert.get("address", "?")[:12] + "..."
    symbol = alert.get("symbol", "UNKNOWN")
    timeframe = alert.get("timeframe", "?")
    price = alert.get("price", 0)
    ema50 = alert.get("ema50", 0)
    reason = alert.get("reason", "")
    
    mc = alert.get("mc", 0)
    mc_text = f"\n💰 Market Cap: ${mc:,.0f}" if mc > 0 else ""
    
    # NAOMI: Add MC range indicator
    naomi_status = ""
    if mc > 0:
        if 100_000 <= mc <= 500_000:
            naomi_status = "\n✅ NAOMI: In sweet spot ($100K-$500K)"
        elif mc < 100_000:
            naomi_status = "\n⚠️ NAOMI: Below $100K (higher risk)"
        else:
            naomi_status = "\n⚠️ NAOMI: Above $500K (may be topped)"
    
    emoji = {"A": "📊", "B": "📈", "C": "🚀"}.get(pattern, "📢")
    
    # NAOMI: Due diligence links
    dd_links = ""
    if chain == "base":
        dd_links = f"\n🔍 BaseScan: https://basescan.org/token/{alert.get('address', '')}"
    elif chain == "solana":
        dd_links = f"\n🔍 Solscan: https://solscan.io/token/{alert.get('address', '')}"
    dd_links += f"\n📊 Bubble Maps: https://app.bubblemaps.io/{chain}/token/{alert.get('address', '')}"
    
    text = f"""{emoji} Pattern {pattern} Alert

🔗 {symbol} ({chain})
📍 {address}
⏱️ Timeframe: {timeframe}
💵 Price: ${price:.6f}
📉 EMA50: ${ema50:.6f}{mc_text}{naomi_status}{dd_links}

📝 {reason}

💡 NAOMI RULES:
   • Wait for dip, never buy top
   • Check liquidity locked
   • Track whales on {chain.title()}Scan
   • Use Bubble Maps for dev dumps
   • Exit: 2x → 5x → 10x
   
🎯 "Take profits before someone else takes them from you"

#Pattern{pattern} #{symbol}"""
    
    return text
