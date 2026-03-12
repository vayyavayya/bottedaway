"""Telegram Handler for ClawBot Sentinel"""
import re
import os
from typing import Dict, Optional

class TelegramHandler:
    """Handles incoming Telegram messages for token analysis"""
    
    SOLANA_ADDRESS_PATTERN = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}")
    
    def __init__(self):
        self.workspace_dir = os.path.expanduser("~/.openclaw/workspace")
        
    def is_solana_address(self, text: str) -> bool:
        """Check if text contains a Solana contract address"""
        if not text:
            return False
        matches = self.SOLANA_ADDRESS_PATTERN.findall(text.strip())
        for match in matches:
            if 32 <= len(match) <= 44:
                return True
        return False
    
    def extract_address(self, text: str) -> Optional[str]:
        """Extract the first Solana address from text"""
        matches = self.SOLANA_ADDRESS_PATTERN.findall(text.strip())
        for match in matches:
            if 32 <= len(match) <= 44:
                return match
        return None
    
    def format_analysis_response(self, analysis: Dict) -> str:
        """Format analysis results for Telegram"""
        token = analysis.get("token", {})
        whale = analysis.get("whale", {})
        engines = analysis.get("engines", {})
        verdict = analysis.get("verdict", {})
        
        lines = [
            f"🔍 {token.get('name', 'Unknown')} (${token.get('symbol', '???')})",
            f"📊 Price: ${token.get('price', 0):.6f} | MC: ${token.get('market_cap', 0):,.0f} | Liq: ${token.get('liquidity', 0):,.0f}",
            "",
            f"🐋 Whale Score: {whale.get('score', 0):.2f} ({whale.get('phase', 'unknown')})",
            f"   B/S Ratio: {whale.get('buy_sell_ratio', 0):.2f} | Velocity: {whale.get('velocity', 0):.2f}x",
            f"   Tags: {', '.join(whale.get('tags', ['none']))}",
            "",
            f"📈 Engine A (12H): {engines.get('A', {}).get('phase', 'N/A')}",
            f"📈 Engine B (4H): {engines.get('B', {}).get('phase', 'N/A')}",
            f"📈 Engine C (1H): {engines.get('C', {}).get('phase', 'N/A')}",
            "",
            f"✅ VERDICT: {verdict.get('action', 'PASS')}",
        ]
        
        if verdict.get('reason'):
            lines.append(f"   Reason: {verdict['reason']}")
        
        if verdict.get('action') == 'BUY' and verdict.get('position_size'):
            lines.append(f"   Position: ${verdict['position_size']:,.0f}")
        
        return "\n".join(lines)

if __name__ == "__main__":
    handler = TelegramHandler()
    test = "Check NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump"
    print(f"Address found: {handler.extract_address(test)}")
