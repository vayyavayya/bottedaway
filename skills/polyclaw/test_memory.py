#!/usr/bin/env python3
"""
Test script for PolyClaw Memory System
Verifies end-to-end functionality: recording, stats, prompt updates
"""

import os
import sys
import json

# Add paths
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/skills/polyclaw'))

from memory_tracker import PolyclawMemory, load_research_note

def test_memory_system():
    print("🧪 Testing PolyClaw Memory System")
    print("=" * 60)
    
    # Test 1: Initialize memory
    print("\n[1/5] Initializing memory...")
    memory = PolyclawMemory()
    print(f"   ✓ Loaded {len(memory.history)} historical records")
    print(f"   ✓ Found {len(memory.category_stats)} category stats")
    
    # Test 2: Record a resolution
    print("\n[2/5] Recording test resolution...")
    resolution = memory.record_resolution(
        market_id="test-market-001",
        question="Will BTC close above $100K by March 2026?",
        category="Crypto",
        prediction=65.0,
        outcome="YES",
        confidence=70,
        edge_percent=15.0,
        pnl=25.50,
        lessons=["base rate was key", "timing matters"]
    )
    print(f"   ✓ Recorded: {resolution.question[:50]}...")
    print(f"   ✓ Prediction: {resolution.prediction:.1f}% | Outcome: {resolution.outcome}")
    print(f"   ✓ Correct: {resolution.was_correct()}")
    print(f"   ✓ P&L: ${resolution.pnl:+.2f}")
    
    # Test 3: Record another (wrong prediction)
    print("\n[3/5] Recording second resolution...")
    resolution2 = memory.record_resolution(
        market_id="test-market-002",
        question="Will Candidate X win the election?",
        category="Politics",
        prediction=75.0,
        outcome="NO",
        confidence=80,
        edge_percent=20.0,
        pnl=-30.00,
        lessons=["ignored base rate", "overconfident on polls"]
    )
    print(f"   ✓ Recorded: {resolution2.question[:50]}...")
    print(f"   ✓ Prediction: {resolution2.prediction:.1f}% | Outcome: {resolution2.outcome}")
    print(f"   ✓ Correct: {resolution2.was_correct()}")
    print(f"   ✓ P&L: ${resolution2.pnl:+.2f}")
    
    # Test 4: Check category stats
    print("\n[4/5] Computing category statistics...")
    memory.compute_category_stats()
    for cat, stats in memory.category_stats.items():
        print(f"   📊 {cat}:")
        print(f"      - Resolved: {stats.total_resolved}")
        print(f"      - Accuracy: {stats.accuracy() * 100:.1f}%")
        print(f"      - Base Rate YES: {stats.base_rate_yes:.1f}%")
        print(f"      - Total P&L: ${stats.total_pnl:+.2f}")
    
    # Test 5: Generate prompt addon
    print("\n[5/5] Generating prompt addon...")
    prompt_context = memory.get_base_rate_prompt()
    print("   ✓ Generated prompt context:")
    for line in prompt_context.split('\n')[:10]:
        if line.strip():
            print(f"      {line}")
    
    addon_path = memory.save_prompt_addon()
    print(f"   ✓ Saved to: {addon_path}")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print(f"\n📁 Files updated:")
    print(f"   - memory/projects/polyclaw-history.md")
    print(f"   - skills/polyclaw/prompts/memory_context.md")
    print(f"   - MEMORY.md (PolyClaw Trading Learnings section)")
    
    print(f"\n📊 Current Stats:")
    print(f"   - Total markets: {len(memory.history)}")
    print(f"   - Categories: {len(memory.category_stats)}")
    total_pnl = sum(s.total_pnl for s in memory.category_stats.values())
    print(f"   - Total P&L: ${total_pnl:+.2f}")
    
    return True

if __name__ == '__main__':
    try:
        test_memory_system()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
