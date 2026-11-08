"""Paths and settings. The data dir lives OUTSIDE the repo and holds everything derived from reports.

Windows (the 5090 PC): %LOCALAPPDATA%\\RadBrain
macOS (build/test box only, synthetic data): ~/Library/Application Support/RadBrain
Override for tests: RADBRAIN_DATA.

signers.json (in the data dir, filled by Ajit, never committed, never printed):
{
  "signers": {"B1": ["<surname as on the signature line>", "..."], "B2": [...], "B3": [...]},
  "me": ["<Ajit's own name variants as draft author>"],
  "staff": ["<other names that may appear: colleagues, MTRs>"]
}
Only the codes ever leave this module: names are used for matching and for scrubbing, never logged.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

CODES = ("B1", "B2", "B3")
ROLES = {"B1": "Chefarzt", "B2": "Leitender Oberarzt", "B3": "Oberarzt"}
TARGET_PAIRS = 500
TARGET_FINALS = 1000
LIVE_AT_PAIRS = 300          # Phase 7: the engine is "live" for a signer from this many real pairs
REMINE_EVERY = 25            # Phase 5: re-mine after every 25 new pairs
SATURATION_WINDOW = 20       # Phase 6: saturated when the last 20 captures of an entity added no new rule


def data_dir() -> Path:
    env = os.environ.get("RADBRAIN_DATA")
    if env:
        p = Path(env)
    elif sys.platform == "win32":
        p = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "RadBrain"
    else:
        p = Path.home() / "Library" / "Application Support" / "RadBrain"
    p.mkdir(parents=True, exist_ok=True)
    for sub in ("quarantine", "rulebooks", "logs"):
        (p / sub).mkdir(exist_ok=True)
    return p


def db_path() -> Path:
    return data_dir() / "library.sqlite"


def quarantine_dir() -> Path:
    return data_dir() / "quarantine"


@dataclass
class Signers:
    by_code: dict[str, list[str]] = field(default_factory=dict)
    me: list[str] = field(default_factory=list)
    staff: list[str] = field(default_factory=list)

    @property
    def configured(self) -> bool:
        return any(self.by_code.get(c) for c in CODES)

    def all_names(self) -> list[str]:
        out = list(self.me) + list(self.staff)
        for c in CODES:
            out += self.by_code.get(c, [])
        return [n for n in out if n and n.strip()]


def _load_signers(path: Path) -> Signers:
    if not path.exists():
        return Signers()
    raw = json.loads(path.read_text(encoding="utf-8"))
    sig = raw.get("signers") or {}
    return Signers(by_code={c: [str(n) for n in sig.get(c, [])] for c in CODES},
                   me=[str(n) for n in raw.get("me", [])], staff=[str(n) for n in raw.get("staff", [])])


@lru_cache(maxsize=4)
def _signers_cached(path: str, mtime: float) -> Signers:
    return _load_signers(Path(path))


def signers() -> Signers:
    p = data_dir() / "signers.json"
    return _signers_cached(str(p), p.stat().st_mtime if p.exists() else 0.0)


def write_signers_template() -> Path:
    """Creates an empty signers.json for Ajit to fill in (never overwrites)."""
    p = data_dir() / "signers.json"
    if not p.exists():
        p.write_text(json.dumps({"signers": {c: [] for c in CODES}, "me": [], "staff": [],
                                 "_help": "B1 = Chefarzt, B2 = Leitender Oberarzt, B3 = Oberarzt. Put the surname as it "
                                          "appears on the signature line (variants allowed). 'me' = your own name as "
                                          "draft author. 'staff' = any other names that may appear in reports."},
                                indent=2, ensure_ascii=False), encoding="utf-8")
    return p


@dataclass
class Models:
    ollama: str = "http://127.0.0.1:11434"
    llm: str = "qwen3.6:27b"
    embed: str = "bge-m3"
    vision: str = "qwen3.6:27b"


def models() -> Models:
    """settings.json in the data dir overrides the defaults (the Mac test box uses qwen3.5:9b)."""
    p = data_dir() / "settings.json"
    m = Models()
    if p.exists():
        raw = json.loads(p.read_text(encoding="utf-8"))
        for k in ("ollama", "llm", "embed", "vision"):
            if raw.get(k):
                setattr(m, k, raw[k])
    if os.environ.get("RADBRAIN_OLLAMA"):
        m.ollama = os.environ["RADBRAIN_OLLAMA"]
    if os.environ.get("RADBRAIN_LLM"):
        m.llm = os.environ["RADBRAIN_LLM"]
    return m
