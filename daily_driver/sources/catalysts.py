"""
Catalyst scan — overnight news / social / narrative anomalies.

Answers workflow step 3 of the morning routine: "Any overnight catalysts?"

Uses Perplexity's chat API when ``PERPLEXITY_API_KEY`` is set (it can search
recent news and X/Twitter). Without a key the source reports
``available=False`` and the workflow prints a manual-check reminder listing the
tickers to eyeball — it never invents headlines.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

PPLX_URL = "https://api.perplexity.ai/chat/completions"
TIMEOUT = 40


class Catalysts:
    def __init__(self, perplexity_key: Optional[str] = None, model: str = "sonar"):
        self.key = perplexity_key or os.getenv("PERPLEXITY_API_KEY", "")
        self.model = model
        self.available = bool(self.key) and requests is not None

    def scan(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Return a compact catalyst read for the given symbols. Shape:

            {"available": bool, "summary": str, "items": [{symbol, note}], "raw": str}
        """
        symbols = [s for s in dict.fromkeys(s.upper() for s in symbols) if s]
        if not symbols:
            return {"available": True, "summary": "No positions or watchlist to scan.",
                    "items": [], "raw": ""}
        if not self.available:
            return {
                "available": False,
                "summary": "Catalyst scan not configured (set PERPLEXITY_API_KEY). "
                           "Manually check X / news for: " + ", ".join(symbols),
                "items": [],
                "raw": "",
            }
        return self._perplexity_scan(symbols)

    def _perplexity_scan(self, symbols: List[str]) -> Dict[str, Any]:
        prompt = (
            "You are a crypto trading desk analyst. For each ticker, report only "
            "material catalysts from the last ~18 hours: major news, notable X/Twitter "
            "chatter, listings, hacks/exploits, or on-chain anomalies. If nothing "
            "material, say 'quiet'. Be terse — one line per ticker. "
            "Return STRICT JSON: {\"items\":[{\"symbol\":\"..\",\"note\":\"..\"}]}. "
            f"Tickers: {', '.join(symbols)}."
        )
        try:
            resp = requests.post(
                PPLX_URL,
                headers={"Authorization": f"Bearer {self.key}",
                         "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                return {"available": False,
                        "summary": f"Catalyst API error (HTTP {resp.status_code}).",
                        "items": [], "raw": resp.text[:400]}
            content = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:  # network / shape errors degrade gracefully
            return {"available": False, "summary": f"Catalyst scan failed: {e}",
                    "items": [], "raw": ""}

        items = _extract_items(content)
        material = [i for i in items if i.get("note", "").strip().lower() not in ("quiet", "")]
        summary = (f"{len(material)} material catalyst(s) across {len(symbols)} ticker(s)."
                   if material else "Quiet overnight — no material catalysts.")
        return {"available": True, "summary": summary, "items": items, "raw": content}


def _extract_items(content: str) -> List[Dict[str, str]]:
    """Best-effort parse of the model's JSON, tolerating code fences / prose."""
    text = content.strip()
    # Strip common ```json fences.
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            items = data.get("items", [])
            return [{"symbol": str(i.get("symbol", "")).upper(),
                     "note": str(i.get("note", "")).strip()} for i in items if isinstance(i, dict)]
        except (json.JSONDecodeError, AttributeError):
            pass
    return []
