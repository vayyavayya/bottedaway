#!/usr/bin/env python3
"""
POLYCLAW Memory Tracker - Long-term memory system for prediction market outcomes

Records market resolutions, updates base rates, extracts lessons learned,
and feeds insights back into ClawAnalyst prompts.

Usage:
    python memory_tracker.py resolve <market_id> <outcome> [--pnl <amount>]
    python memory_tracker.py stats [--category <cat>]
    python memory_tracker.py export [--format json|markdown]
    python memory_tracker.py update-prompts
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# Paths
WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
HISTORY_FILE = os.path.join(WORKSPACE, 'memory', 'projects', 'polyclaw-history.md')
MEMORY_FILE = os.path.join(WORKSPACE, 'MEMORY.md')
ANALYSIS_DIR = os.path.join(WORKSPACE, 'analysis', 'polymarket')
PROMPTS_DIR = os.path.join(WORKSPACE, 'skills', 'polyclaw', 'prompts')

# Ensure directories exist
os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
os.makedirs(PROMPTS_DIR, exist_ok=True)


@dataclass
class MarketResolution:
    """Single market resolution record"""
    market_id: str
    question: str
    category: str
    prediction: float  # Our estimated probability (0-100)
    outcome: str  # "YES", "NO", "CANCELLED", "UNRESOLVED"
    pnl: Optional[float]  # Profit/loss from trade
    confidence: int  # Our confidence at prediction time
    edge_percent: float  # Edge we thought we had
    timestamp: str  # When resolved
    lessons: List[str]  # Lessons learned from this trade
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def was_correct(self) -> bool:
        """Check if our prediction was directionally correct"""
        if self.outcome == "CANCELLED" or self.outcome == "UNRESOLVED":
            return False
        if self.outcome == "YES":
            return self.prediction > 50
        return self.prediction < 50


@dataclass  
class CategoryStats:
    """Statistics for a market category"""
    category: str
    total_resolved: int
    correct_predictions: int
    incorrect_predictions: int
    base_rate_yes: float  # % of markets that resolve YES
    avg_edge_when_correct: float
    avg_edge_when_wrong: float
    avg_pnl: float
    total_pnl: float
    
    def accuracy(self) -> float:
        if self.total_resolved == 0:
            return 0.0
        return self.correct_predictions / self.total_resolved


class PolyclawMemory:
    """Long-term memory system for Polymarket trading"""
    
    def __init__(self):
        self.history: List[MarketResolution] = []
        self.category_stats: Dict[str, CategoryStats] = {}
        self.load_history()
        self.compute_category_stats()
    
    def load_history(self):
        """Parse history from markdown file"""
        if not os.path.exists(HISTORY_FILE):
            return
        
        # Parse the markdown to extract resolution records
        # Records are stored as JSON blocks in markdown
        with open(HISTORY_FILE, 'r') as f:
            content = f.read()
        
        # Extract JSON blocks between ```json markers
        import re
        json_blocks = re.findall(r'```json\n(.*?)\n```', content, re.DOTALL)
        
        for block in json_blocks:
            try:
                data = json.loads(block.strip())
                if 'market_id' in data:
                    self.history.append(MarketResolution(**data))
            except:
                pass
    
    def save_history(self):
        """Save history to markdown file"""
        content = self._generate_history_content()
        with open(HISTORY_FILE, 'w') as f:
            f.write(content)
    
    def _generate_history_content(self) -> str:
        """Generate the full markdown content"""
        lines = [
            "# PolyClaw Trading History",
            "",
            "Historical record of prediction market resolutions, outcomes, and learnings.",
            "Auto-generated from memory tracker system.",
            "",
            "---",
            "",
            "## 📊 Category Base Rates",
            "",
        ]
        
        # Add category statistics
        if self.category_stats:
            lines.append("| Category | Resolved | Accuracy | Base Rate YES | Avg P&L |")
            lines.append("|----------|----------|----------|---------------|---------|")
            
            for cat, stats in sorted(self.category_stats.items()):
                acc_pct = f"{stats.accuracy() * 100:.1f}%"
                base_yes = f"{stats.base_rate_yes:.1f}%"
                pnl = f"${stats.total_pnl:+.2f}"
                lines.append(f"| {cat} | {stats.total_resolved} | {acc_pct} | {base_yes} | {pnl} |")
        else:
            lines.append("*No resolved markets yet*")
        
        lines.extend([
            "",
            "---",
            "",
            "## 🎯 Resolved Markets",
            "",
            "### Legend",
            "- **Prediction**: Our estimated probability (0-100%)",
            "- **Outcome**: What actually happened",
            "- **✅/❌**: Whether our prediction was directionally correct",
            "- **P&L**: Profit/loss from trading this market",
            "",
        ])
        
        # Group by category
        by_category = {}
        for rec in self.history:
            cat = rec.category or "Uncategorized"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(rec)
        
        for cat in sorted(by_category.keys()):
            lines.append(f"### {cat}")
            lines.append("")
            
            for rec in by_category[cat]:
                emoji = "✅" if rec.was_correct() else "❌"
                pnl_str = f"${rec.pnl:+.2f}" if rec.pnl is not None else "N/A"
                
                lines.append(f"**{rec.question[:80]}{'...' if len(rec.question) > 80 else ''}**")
                lines.append(f"- Date: {rec.timestamp}")
                lines.append(f"- Our Prediction: {rec.prediction:.1f}% | Outcome: {rec.outcome} {emoji}")
                lines.append(f"- Edge: {rec.edge_percent:.1f}% | Confidence: {rec.confidence}%")
                lines.append(f"- P&L: {pnl_str}")
                if rec.lessons:
                    lines.append(f"- Lessons: {', '.join(rec.lessons)}")
                lines.append("")
                
                # Embed JSON for programmatic access
                lines.append("```json")
                lines.append(json.dumps(rec.to_dict(), indent=2))
                lines.append("```")
                lines.append("")
        
        return "\n".join(lines)
    
    def compute_category_stats(self):
        """Compute base rates and stats per category"""
        cat_data: Dict[str, List[MarketResolution]] = {}
        
        for rec in self.history:
            cat = rec.category or "Uncategorized"
            if cat not in cat_data:
                cat_data[cat] = []
            cat_data[cat].append(rec)
        
        for cat, records in cat_data.items():
            resolved = [r for r in records if r.outcome in ("YES", "NO")]
            if not resolved:
                continue
            
            correct = sum(1 for r in resolved if r.was_correct())
            incorrect = len(resolved) - correct
            yes_count = sum(1 for r in resolved if r.outcome == "YES")
            
            edges_correct = [r.edge_percent for r in resolved if r.was_correct()]
            edges_wrong = [r.edge_percent for r in resolved if not r.was_correct()]
            pnls = [r.pnl for r in resolved if r.pnl is not None]
            
            self.category_stats[cat] = CategoryStats(
                category=cat,
                total_resolved=len(resolved),
                correct_predictions=correct,
                incorrect_predictions=incorrect,
                base_rate_yes=(yes_count / len(resolved)) * 100,
                avg_edge_when_correct=sum(edges_correct) / len(edges_correct) if edges_correct else 0,
                avg_edge_when_wrong=sum(edges_wrong) / len(edges_wrong) if edges_wrong else 0,
                avg_pnl=sum(pnls) / len(pnls) if pnls else 0,
                total_pnl=sum(pnls) if pnls else 0
            )
    
    def record_resolution(
        self,
        market_id: str,
        question: str,
        category: str,
        prediction: float,
        outcome: str,
        confidence: int,
        edge_percent: float,
        pnl: Optional[float] = None,
        lessons: Optional[List[str]] = None
    ) -> MarketResolution:
        """Record a new market resolution"""
        
        resolution = MarketResolution(
            market_id=market_id,
            question=question,
            category=category,
            prediction=prediction,
            outcome=outcome,
            pnl=pnl,
            confidence=confidence,
            edge_percent=edge_percent,
            timestamp=datetime.now().strftime('%Y-%m-%d'),
            lessons=lessons or []
        )
        
        self.history.append(resolution)
        self.compute_category_stats()
        self.save_history()
        self._update_memory_md(lessons or [], resolution)
        
        return resolution
    
    def _update_memory_md(self, lessons: List[str], resolution: MarketResolution):
        """Update MEMORY.md with learnings"""
        if not os.path.exists(MEMORY_FILE):
            return
        
        with open(MEMORY_FILE, 'r') as f:
            content = f.read()
        
        # Find or create PolyClaw section
        polyclaw_section = "## PolyClaw Trading Learnings"
        
        new_entry = f"""
### {resolution.timestamp} - {resolution.question[:50]}...
- **Outcome**: {resolution.outcome} ({'✅ Correct' if resolution.was_correct() else '❌ Wrong'})
- **Our Prediction**: {resolution.prediction:.1f}% | **Actual**: {resolution.outcome}
- **P&L**: ${resolution.pnl:+.2f}"""
        
        if lessons:
            new_entry += "\n- **Lessons**: " + "; ".join(lessons)
        
        if polyclaw_section in content:
            # Insert after section header
            parts = content.split(polyclaw_section, 1)
            new_content = parts[0] + polyclaw_section + new_entry + parts[1]
        else:
            # Add new section at end
            new_content = content + f"\n\n{polyclaw_section}\n{new_entry}"
        
        with open(MEMORY_FILE, 'w') as f:
            f.write(new_content)
    
    def get_base_rate_prompt(self) -> str:
        """Generate base rate context for ClawAnalyst prompts"""
        lines = [
            "### Historical Base Rates (from PolyClaw memory):",
            "",
        ]
        
        for cat, stats in sorted(self.category_stats.items()):
            lines.append(f"- **{cat}**: {stats.base_rate_yes:.1f}% resolve YES (n={stats.total_resolved}, {stats.accuracy() * 100:.0f}% prediction accuracy)")
        
        if not self.category_stats:
            lines.append("*No historical data available yet*")
        
        lines.append("")
        lines.append("### Recent Lessons:")
        
        # Get last 5 lessons
        recent_lessons = []
        for rec in reversed(self.history[-10:]):
            recent_lessons.extend(rec.lessons)
        
        recent_lessons = list(dict.fromkeys(recent_lessons))[:5]  # Unique, max 5
        
        if recent_lessons:
            for lesson in recent_lessons:
                lines.append(f"- {lesson}")
        else:
            lines.append("*Building lesson database...*")
        
        return "\n".join(lines)
    
    def generate_analyst_prompt_addon(self) -> str:
        """Generate the prompt addon file for ClawAnalyst"""
        content = f"""# Auto-generated from PolyClaw Memory Tracker
# Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

{self.get_base_rate_prompt()}

### Calibration Notes:
"""
        
        # Add calibration insights
        if self.category_stats:
            for cat, stats in self.category_stats.items():
                if stats.total_resolved >= 5:  # Only for categories with enough data
                    if stats.accuracy() < 0.5:
                        content += f"\n- **{cat}**: We tend to be OVERCONFIDENT (only {stats.accuracy() * 100:.0f}% accuracy). Consider adjusting estimates down by 10-15%."
                    elif stats.accuracy() > 0.7:
                        content += f"\n- **{cat}**: We have EDGE in this category ({stats.accuracy() * 100:.0f}% accuracy). Trust our process."
        
        return content
    
    def save_prompt_addon(self):
        """Save the prompt addon to file"""
        addon_path = os.path.join(PROMPTS_DIR, 'memory_context.md')
        content = self.generate_analyst_prompt_addon()
        with open(addon_path, 'w') as f:
            f.write(content)
        return addon_path


def load_research_note(market_id: str) -> Optional[Dict]:
    """Load research note for a market"""
    # Find most recent research file for this market
    pattern = f"research_{market_id}_*.json"
    import glob
    files = glob.glob(os.path.join(ANALYSIS_DIR, pattern))
    
    if not files:
        return None
    
    # Get most recent
    files.sort(reverse=True)
    
    with open(files[0], 'r') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description='POLYCLAW Memory Tracker - Record resolutions and update learnings'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Record resolution
    resolve_parser = subparsers.add_parser('resolve', help='Record a market resolution')
    resolve_parser.add_argument('market_id', help='Market ID')
    resolve_parser.add_argument('outcome', choices=['YES', 'NO', 'CANCELLED', 'UNRESOLVED'])
    resolve_parser.add_argument('--pnl', type=float, help='Profit/loss from trade')
    resolve_parser.add_argument('--category', help='Override category (auto-detected from research)')
    resolve_parser.add_argument('--lessons', help='Comma-separated lessons learned')
    
    # Show stats
    stats_parser = subparsers.add_parser('stats', help='Show category statistics')
    stats_parser.add_argument('--category', help='Filter by category')
    
    # Export
    export_parser = subparsers.add_parser('export', help='Export data')
    export_parser.add_argument('--format', choices=['json', 'markdown'], default='json')
    
    # Update prompts
    subparsers.add_parser('update-prompts', help='Generate analyst prompt addons')
    
    args = parser.parse_args()
    
    if args.command == 'resolve':
        memory = PolyclawMemory()
        
        # Try to load from research note
        research = load_research_note(args.market_id)
        
        if research:
            question = research['market']['question']
            category = args.category or research['market'].get('category', 'Uncategorized')
            prediction = research['step1_forecasting'].get('p_yes_estimate', 50)
            confidence = research['step1_forecasting'].get('confidence', 50)
            edge = research['step4_signals'].get('edge_percent', 0)
        else:
            # Manual entry required
            question = input("Market question: ")
            category = args.category or input("Category: ")
            prediction = float(input("Our prediction (0-100): "))
            confidence = int(input("Confidence (0-100): "))
            edge = float(input("Edge %: "))
        
        lessons = args.lessons.split(',') if args.lessons else []
        
        resolution = memory.record_resolution(
            market_id=args.market_id,
            question=question,
            category=category,
            prediction=prediction,
            outcome=args.outcome,
            pnl=args.pnl,
            confidence=confidence,
            edge_percent=edge,
            lessons=lessons
        )
        
        print(f"\n✅ Recorded resolution")
        print(f"   Market: {resolution.question[:60]}...")
        print(f"   Prediction: {resolution.prediction:.1f}% | Outcome: {resolution.outcome}")
        print(f"   {'✅ Correct' if resolution.was_correct() else '❌ Wrong'}")
        if resolution.pnl is not None:
            print(f"   P&L: ${resolution.pnl:+.2f}")
        
        # Update prompts
        addon_path = memory.save_prompt_addon()
        print(f"   Updated prompts: {addon_path}")
    
    elif args.command == 'stats':
        memory = PolyclawMemory()
        
        if args.category:
            stats = memory.category_stats.get(args.category)
            if stats:
                print(f"\n📊 {args.category} Statistics")
                print(f"   Resolved: {stats.total_resolved}")
                print(f"   Accuracy: {stats.accuracy() * 100:.1f}%")
                print(f"   Base Rate YES: {stats.base_rate_yes:.1f}%")
                print(f"   Total P&L: ${stats.total_pnl:+.2f}")
            else:
                print(f"No data for category: {args.category}")
        else:
            print("\n📊 Category Statistics")
            print("-" * 60)
            for cat, stats in sorted(memory.category_stats.items()):
                print(f"\n{cat}:")
                print(f"   Resolved: {stats.total_resolved} | Accuracy: {stats.accuracy() * 100:.1f}%")
                print(f"   Base Rate YES: {stats.base_rate_yes:.1f}%")
                print(f"   Avg P&L: ${stats.avg_pnl:+.2f} | Total: ${stats.total_pnl:+.2f}")
    
    elif args.command == 'export':
        memory = PolyclawMemory()
        
        if args.format == 'json':
            data = {
                'resolutions': [r.to_dict() for r in memory.history],
                'category_stats': {k: asdict(v) for k, v in memory.category_stats.items()},
                'exported_at': datetime.now().isoformat()
            }
            print(json.dumps(data, indent=2))
        else:
            print(memory._generate_history_content())
    
    elif args.command == 'update-prompts':
        memory = PolyclawMemory()
        addon_path = memory.save_prompt_addon()
        print(f"✅ Updated analyst prompts: {addon_path}")
        print("\n" + memory.get_base_rate_prompt())
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
