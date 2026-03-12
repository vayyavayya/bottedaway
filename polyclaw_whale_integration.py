#!/usr/bin/env python3
"""
Polyclaw + Whale Accumulation Scorer Integration
When scanning crypto-related Polymarket markets, cross-reference whale signals
"""

import json
import os
import sys
import re

# Paths
POLYCLAW_DIR = os.path.expanduser("~/.openclaw/workspace/skills/polyclaw")
WHALE_DIR = os.path.expanduser("~/.openclaw/workspace/skills/whale-accumulation-scorer")

sys.path.insert(0, os.path.join(WHALE_DIR, 'scripts'))

def extract_token_symbols(question, description=""):
    """Extract potential token symbols from market text"""
    text = f"{question} {description}".upper()
    
    # Common crypto keywords that might precede token symbols
    crypto_keywords = [
        r"(\w+)\s+(?:PRICE|TOKEN|COIN)",
        r"(?:PRICE OF|VALUE OF)\s+(\w+)",
        r"(\w+)\s+(?:ABOVE|BELOW|OVER|UNDER)",
        r"(\w+)\s+(?:REACH|HIT|BREAK)",
        r"(?:WILL)\s+(\w+)\s+(?:BE|CLOSE|END|HIT)"
    ]
    
    symbols = set()
    
    # Pattern matching
    for pattern in crypto_keywords:
        matches = re.findall(pattern, text)
        for match in matches:
            if len(match) >= 2 and len(match) <= 10:
                symbols.add(match)
    
    # Common token symbol pattern (all caps, 2-10 chars)
    all_caps = re.findall(r'\b[A-Z]{2,10}\b', text)
    common_tokens = {'BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'DOGE', 'SHIB', 'PEPE', 
                     'BONK', 'WIF', 'JUP', 'JTO', 'PYTH', 'RENDER', 'HNT',
                     'LINK', 'AAVE', 'UNI', 'MKR', 'LDO', 'ARB', 'OP', 'MATIC',
                     'ATOM', 'DOT', 'AVAX', 'NEAR', 'FTM', 'SUI', 'APT', 'SEI'}
    
    for token in all_caps:
        if token in common_tokens:
            symbols.add(token)
    
    return list(symbols)

def get_token_address(symbol):
    """Get token address from symbol (would need a token database)"""
    # Common Solana tokens
    token_map = {
        "BTC": "9n4nbM75f5Ui33ZbPYXn59EwSgE8CGsSgAeTSHFP2Q7J",  # Wrapped BTC on Solana
        "ETH": "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",  # Wrapped ETH
        "SOL": "So11111111111111111111111111111111111111112",  # Native SOL
        "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
        "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
    }
    return token_map.get(symbol.upper())

def analyze_polymarket_with_whale_data(market_data):
    """
    Analyze a Polymarket market and cross-reference with whale accumulation data
    """
    from whale_tracker import WhaleTracker
    
    question = market_data.get('question', '')
    description = market_data.get('description', '')
    
    # Extract potential token symbols
    symbols = extract_token_symbols(question, description)
    
    if not symbols:
        return {
            "market_id": market_data.get('id'),
            "question": question,
            "whale_analysis": None,
            "note": "No crypto tokens detected in market text"
        }
    
    tracker = WhaleTracker()
    token_analyses = []
    
    for symbol in symbols:
        address = get_token_address(symbol)
        if address:
            try:
                signal = tracker.analyze_token(address)
                token_analyses.append({
                    "symbol": symbol,
                    "address": address[:16] + "...",
                    "score": signal.score,
                    "phase": signal.phase.value,
                    "actionable": signal.is_actionable,
                    "whales": signal.num_whales_accumulating,
                    "buy_sell_ratio": signal.buy_sell_ratio
                })
            except Exception as e:
                token_analyses.append({
                    "symbol": symbol,
                    "error": str(e)
                })
    
    # Determine if whale signal supports the market thesis
    accumulation_signals = [t for t in token_analyses if t.get('actionable')]
    
    return {
        "market_id": market_data.get('id'),
        "question": question,
        "detected_tokens": symbols,
        "token_analyses": token_analyses,
        "whale_confluence": len(accumulation_signals) > 0,
        "accumulation_count": len(accumulation_signals),
        "recommendation": "STRONG" if len(accumulation_signals) >= 2 else ("MODERATE" if len(accumulation_signals) == 1 else "NEUTRAL")
    }

def enhance_polymarket_research(research_results):
    """
    Enhance existing Polymarket research with whale accumulation data
    Call this after research.py produces results
    """
    enhanced = []
    
    for result in research_results:
        # Get market data from result
        market_data = {
            'id': result.get('market_id'),
            'question': result.get('question'),
            'description': result.get('description', '')
        }
        
        # Add whale analysis
        whale_data = analyze_polymarket_with_whale_data(market_data)
        
        # Merge with existing research
        enhanced_result = {**result, 'whale_analysis': whale_data}
        
        # Boost signal if whale confluence exists
        if whale_data.get('whale_confluence') and result.get('signal', {}).get('edge_percent', 0) > 3:
            enhanced_result['signal']['edge_percent'] += 2  # Boost for whale confirmation
            enhanced_result['whale_boost'] = True
        
        enhanced.append(enhanced_result)
    
    return enhanced

if __name__ == "__main__":
    # Test with a sample crypto market
    test_market = {
        "id": "test-market-123",
        "question": "Will Bitcoin close above $100K by end of March 2026?",
        "description": "This market resolves to YES if the price of BTC exceeds $100,000..."
    }
    
    print("=" * 80)
    print("POLYCLAW + WHALE SCORER INTEGRATION TEST")
    print("=" * 80)
    print(f"\nMarket: {test_market['question']}")
    
    result = analyze_polymarket_with_whale_data(test_market)
    
    print(f"\nDetected tokens: {result['detected_tokens']}")
    print(f"Whale confluence: {result['whale_confluence']}")
    print(f"Recommendation: {result['recommendation']}")
    
    if result['token_analyses']:
        print("\nToken analyses:")
        for ta in result['token_analyses']:
            if 'error' in ta:
                print(f"  {ta['symbol']}: ERROR - {ta['error']}")
            else:
                print(f"  {ta['symbol']}: score={ta['score']:.2f}, phase={ta['phase']}, whales={ta['whales']}")
    
    print("\n" + "=" * 80)
