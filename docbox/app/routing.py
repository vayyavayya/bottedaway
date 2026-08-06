"""Where a document belongs once the model knows what it is.

Rules first (fast, predictable, yours to edit), then the model's own suggestion,
then the inbox. Nothing leaves the inbox unless the classification is confident
enough — an archive that files things wrongly is worse than a pile.

The rule file is written to `<data>/routing.json` on first run so you can edit
it without touching the code.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from .config import settings

log = logging.getLogger("docbox.routing")

# Confidence below which a document stays in the inbox for a human to look at.
AUTOFILE_FLOOR = 0.55

DEFAULT_RULES: list[dict] = [
    {"name": "payslips",   "doc_type": ["payslip"],              "folder": "Finance/Payslips/{year}"},
    {"name": "tax",        "doc_type": ["tax"],                  "folder": "Finance/Tax/{year}"},
    {"name": "bank",       "doc_type": ["statement"],            "folder": "Finance/Statements/{year}"},
    {"name": "invoices",   "doc_type": ["invoice"],              "folder": "Finance/Invoices/{year}"},
    {"name": "receipts",   "doc_type": ["receipt"],              "folder": "Finance/Receipts/{year}"},
    {"name": "insurance",  "doc_type": ["insurance"],            "folder": "Insurance"},
    {"name": "medical",    "doc_type": ["medical"],              "folder": "Medical/{year}"},
    {"name": "contracts",  "doc_type": ["contract"],             "folder": "Contracts"},
    {"name": "ids",        "doc_type": ["id"],                   "folder": "Personal/IDs"},
    {"name": "travel",     "doc_type": ["ticket"],               "folder": "Travel/{year}"},
    {"name": "manuals",    "doc_type": ["manual", "warranty"],   "folder": "Home/Manuals and Warranties"},
    {"name": "letters",    "doc_type": ["letter"],               "folder": "Correspondence/{year}"},
    # Keyword rules run before type rules of the same specificity is not a thing —
    # order in this list is the priority. Put narrow rules above broad ones.
]

# Rules that beat the doc_type table because the words are unambiguous.
DEFAULT_KEYWORD_RULES: list[dict] = [
    {"name": "rent",      "keywords": ["mietvertrag", "tenancy agreement", "lease agreement"],
     "folder": "Home/Tenancy"},
    {"name": "utilities", "keywords": ["stadtwerke", "electricity bill", "gas bill", "water bill",
                                        "stromrechnung", "gasrechnung"],
     "folder": "Home/Utilities/{year}"},
    {"name": "car",       "keywords": ["kfz", "vehicle registration", "fahrzeugschein", "mot certificate"],
     "folder": "Car"},
]


@dataclass
class Route:
    folder: str
    rule: str
    confident: bool


def rules_path() -> Path:
    return settings.data_dir / "routing.json"


def load_rules() -> dict:
    """Read the user's rules, creating the file with the defaults on first run."""
    path = rules_path()
    if not path.exists():
        payload = {
            "_comment": (
                "Docbox filing rules. Rules are tried top to bottom; the first "
                "match wins. {year} and {yyyymm} expand from the document date. "
                "Set auto_file to false to keep everything in the inbox."
            ),
            "auto_file": True,
            "confidence_floor": AUTOFILE_FLOOR,
            "keyword_rules": DEFAULT_KEYWORD_RULES,
            "rules": DEFAULT_RULES,
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2))
        except OSError as exc:
            log.warning("could not write %s: %s", path, exc)
        return payload

    try:
        loaded = json.loads(path.read_text())
        if not isinstance(loaded, dict):
            raise ValueError("routing.json must contain an object")
        return loaded
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        log.warning("bad routing.json (%s) — using defaults", exc)
        return {
            "auto_file": True,
            "confidence_floor": AUTOFILE_FLOOR,
            "keyword_rules": DEFAULT_KEYWORD_RULES,
            "rules": DEFAULT_RULES,
        }


def _expand(template: str, date: str) -> str:
    """`Finance/Invoices/{year}` -> `Finance/Invoices/2024`."""
    year = date[:4] if len(date) >= 4 and date[:4].isdigit() else "undated"
    yyyymm = date[:6] if len(date) >= 6 and date[:6].isdigit() else year
    return template.replace("{year}", year).replace("{yyyymm}", yyyymm)


def _haystack(analysis) -> str:
    parts = [
        getattr(analysis, "correspondent", "") or "",
        getattr(analysis, "title", "") or "",
        getattr(analysis, "summary", "") or "",
    ]
    return " ".join(parts).lower()


def choose_folder(analysis, text: str = "", current: str | None = None,
                  config: dict | None = None) -> Route:
    """Decide the destination folder for an analysed document."""
    config = config if config is not None else load_rules()
    inbox = settings.inbox_name

    if not config.get("auto_file", True):
        return Route(current or inbox, "auto-file off", False)

    floor = float(config.get("confidence_floor", AUTOFILE_FLOOR))
    confidence = float(getattr(analysis, "confidence", 0.0) or 0.0)
    date = getattr(analysis, "date", "") or ""
    doc_type = (getattr(analysis, "doc_type", "") or "").lower()

    # Not sure enough to move it anywhere: leave it in the pile.
    if confidence < floor or getattr(analysis, "source", "") == "heuristic":
        return Route(current or inbox, "below confidence floor", False)

    blob = f"{_haystack(analysis)} {(text or '')[:2000].lower()}"

    for rule in config.get("keyword_rules", []):
        words = [w.lower() for w in rule.get("keywords", []) if w]
        if any(re.search(rf"\b{re.escape(word)}", blob) for word in words):
            return Route(_expand(rule["folder"], date), rule.get("name", "keyword"), True)

    for rule in config.get("rules", []):
        types = [t.lower() for t in rule.get("doc_type", [])]
        if doc_type and doc_type in types:
            return Route(_expand(rule["folder"], date), rule.get("name", "type"), True)

    return Route(current or inbox, "no rule matched", False)


def known_folders(config: dict | None = None) -> list[str]:
    """Folder templates the rules can produce — shown in the UI as suggestions."""
    config = config if config is not None else load_rules()
    out = []
    for rule in list(config.get("keyword_rules", [])) + list(config.get("rules", [])):
        folder = rule.get("folder", "")
        base = folder.split("/{")[0].split("{")[0].strip("/")
        if base and base not in out:
            out.append(base)
    return out
