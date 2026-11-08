"""Local models only: the Ollama on the PC (127.0.0.1). No cloud endpoint is ever configured here.

DECISION (DECISIONS.md #3): RadBrain does NOT go through Triage. Triage routes to Claude (cloud) and the hard rule for
this project is that report text never leaves the PC; so the engine talks to the PC's own Ollama only.
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from urllib.parse import urlparse

import httpx

from . import config

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _base() -> str:
    url = config.models().ollama.rstrip("/")
    host = urlparse(url).hostname or ""
    if host not in LOCAL_HOSTS:
        raise RuntimeError("RadBrain only talks to a local Ollama (127.0.0.1); refusing " + host)
    return url


def available(timeout: float = 3.0) -> dict:
    try:
        r = httpx.get(_base() + "/api/tags", timeout=timeout)
        names = [m["name"] for m in r.json().get("models", [])]
        m = config.models()
        return {"ok": True, "models": names, "llm": _has(names, m.llm), "embed": _has(names, m.embed)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": type(e).__name__, "llm": False, "embed": False, "models": []}


def _has(names, want):
    return any(n == want or n.split(":")[0] == want.split(":")[0] and (":" not in want or n == want) for n in names)


def chat_json(system: str, user: str, *, timeout: float = 600, temperature: float = 0.2) -> dict | None:
    m = config.models()
    try:
        r = httpx.post(_base() + "/api/chat", timeout=timeout, json={
            "model": m.llm, "stream": False, "format": "json", "think": False,
            "options": {"temperature": temperature, "num_ctx": 16384},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        txt = r.json()["message"]["content"]
        txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
        return json.loads(txt)
    except Exception:  # noqa: BLE001
        return None


def embed(texts: list[str], timeout: float = 120) -> list[list[float]] | None:
    m = config.models()
    try:
        r = httpx.post(_base() + "/api/embed", timeout=timeout, json={"model": m.embed, "input": texts})
        r.raise_for_status()
        return r.json()["embeddings"]
    except Exception:  # noqa: BLE001
        return None


def cosine(a, b) -> float:
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


@lru_cache(maxsize=4096)
def ngrams(s: str) -> frozenset:
    s = " " + re.sub(r"\s+", " ", (s or "").casefold()) + " "
    return frozenset(s[i:i + 3] for i in range(len(s) - 2))


def lexical_sim(a: str, b: str) -> float:
    """Fallback when the embedding model is not reachable: character-trigram Jaccard."""
    x, y = ngrams(a), ngrams(b)
    return len(x & y) / max(1, len(x | y))
