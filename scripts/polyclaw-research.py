#!/usr/bin/env python3
"""
Perplexity Deep Research for PolyClaw
Analyzes Polymarket trends with AI-powered research before trading decisions.
"""

import os
import sys
import json
import requests
from typing import Optional, Dict, List

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "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")
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

def perplexity_research(query: str, model: str = "sonar-pro") -> Optional[Dict]:
    """
    Run deep research query via Perplexity API.
    
    Models:
    - sonar-pro: Best for research (citations, comprehensive)
    - sonar: Fast, good for quick checks
    """
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a research analyst specializing in prediction markets. Provide comprehensive analysis with citations. Focus on: 1) Current events impacting the market, 2) Historical precedents, 3) Expert opinions, 4) Key risk factors. Be objective and highlight uncertainties."
            },
            {
                "role": "user",
                "content": query
            }
        ],
        "temperature": 0.2,
        "max_tokens": 2000
    }
    
    try:
        resp = requests.post(PERPLEXITY_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[Perplexity] Error: {e}")
        return None

def research_market(question: str, current_price: float, volume: str) -> str:
    """
    Deep research on a specific Polymarket question.
    Use this BEFORE making trading decisions.
    """
    query = f"""Analyze this Polymarket prediction market:

Market Question: "{question}"
Current Price: YES ${current_price:.2f}
24h Volume: {volume}

Provide comprehensive analysis including:
1. Current news/events affecting this outcome
2. Historical precedents or similar situations
3. Expert predictions or consensus
4. Key factors that could swing the outcome
5. Timeline of critical events
6. Confidence level assessment
7. Risk factors and unknowns

Format as structured analysis with citations."""

    result = perplexity_research(query)
    
    if not result or "choices" not in result:
        return "[Error] Could not fetch research data"
    
    content = result["choices"][0]["message"]["content"]
    citations = result.get("citations", [])
    
    output = f"""═══════════════════════════════════════════════════════════
📊 PERPLEXITY DEEP RESEARCH
═══════════════════════════════════════════════════════════

🎯 Market: {question}
💰 Current: YES ${current_price:.2f} | Volume: {volume}

{content}

"""
    
    if citations:
        output += "\n📚 Sources:\n"
        for i, cite in enumerate(citations[:5], 1):
            output += f"   {i}. {cite}\n"
    
    output += "\n═══════════════════════════════════════════════════════════\n"
    output += "⚠️  This is research, not financial advice. Verify independently.\n"
    output += "═══════════════════════════════════════════════════════════\n"
    
    return output

def compare_markets(market1: Dict, market2: Dict) -> str:
    """
    Research relationship between two markets for hedging analysis.
    """
    query = f"""Compare these two prediction markets for logical relationships:

Market A: "{market1['question']}"
Market B: "{market2['question']}"

Determine:
1. If Market A resolves YES, does Market B necessarily resolve YES? (Implication)
2. If Market A resolves NO, does Market B necessarily resolve NO? (Contrapositive)
3. Are there overlapping factors or causal chains?
4. What's the logical coverage percentage between them?

Provide strict logical analysis only - reject correlations without logical necessity."""

    result = perplexity_research(query, model="sonar-pro")
    
    if not result or "choices" not in result:
        return "[Error] Could not fetch comparison data"
    
    return result["choices"][0]["message"]["content"]

def scan_trending_news(topic: str = "prediction markets") -> str:
    """
    Get latest news affecting prediction markets.
    """
    query = f"""What are the latest developments affecting {topic} today?

Focus on:
- Breaking news that could impact active prediction markets
- Political developments
- Economic indicators
- Sports outcomes
- Crypto/web3 events

Provide specific events with timestamps and potential market impacts."""

    result = perplexity_research(query)
    
    if not result or "choices" not in result:
        return "[Error] Could not fetch news"
    
    return result["choices"][0]["message"]["content"]

def main():
    """CLI interface for Perplexity research."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Perplexity Deep Research for PolyClaw")
    parser.add_argument("--research", "-r", help="Research a specific market question")
    parser.add_argument("--price", "-p", type=float, default=0.5, help="Current YES price")
    parser.add_argument("--volume", "-v", default="Unknown", help="24h volume")
    parser.add_argument("--news", "-n", action="store_true", help="Get trending news")
    parser.add_argument("--compare", "-c", nargs=2, metavar="QUESTION", help="Compare two markets")
    
    args = parser.parse_args()
    
    if args.news:
        print(scan_trending_news())
    elif args.compare:
        market1 = {"question": args.compare[0]}
        market2 = {"question": args.compare[1]}
        print(compare_markets(market1, market2))
    elif args.research:
        print(research_market(args.research, args.price, args.volume))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
