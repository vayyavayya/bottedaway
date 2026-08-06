"""Local LLM naming via Ollama.

Nothing leaves the house: the model runs on the same machine as the library.
If Ollama is down or the reply is junk, we fall back to heuristics and mark the
document for review rather than failing the upload.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .config import settings
from .naming import find_date_in_text, normalize_date, slugify

SYSTEM_PROMPT = """You file paper documents for a two-person household archive.
You are given the OCR text of one document. Reply with a single JSON object and nothing else.

Fields:
  "date": the date the document itself carries (invoice date, letter date, statement
          date, appointment date) as "YYYY-MM-DD". Not today's date. null if absent.
  "correspondent": the company, authority or person that issued it, short and plain
          (e.g. "Stadtwerke Munich", "Dr Meyer", "HSBC"). "" if unclear.
  "doc_type": one of invoice, receipt, contract, letter, statement, payslip, tax,
          insurance, medical, warranty, id, ticket, manual, report, note, other.
  "title": 2-6 words describing what this specific document is, no dates, no filler.
          Examples: "electricity bill march", "rental contract flat", "mri results".
  "summary": one short sentence a person would recognise it by.
  "confidence": 0.0-1.0, how sure you are the fields are right.

Rules: use the document's own language for correspondent, English for doc_type.
Never invent a date that is not in the text. Output JSON only."""

USER_TEMPLATE = """Original filename: {filename}
{hint}
--- DOCUMENT TEXT (may be noisy OCR) ---
{text}
--- END ---

JSON:"""

VISION_PROMPT = """This is a photo or scan of a document. Read it and reply with a
single JSON object using exactly these fields: date (YYYY-MM-DD or null),
correspondent, doc_type, title (2-6 words), summary, confidence (0-1).
Output JSON only."""

DOC_TYPES = {
    "invoice", "receipt", "contract", "letter", "statement", "payslip", "tax",
    "insurance", "medical", "warranty", "id", "ticket", "manual", "report",
    "note", "other",
}


@dataclass
class Analysis:
    date: str = ""
    title: str = ""
    doc_type: str = ""
    correspondent: str = ""
    summary: str = ""
    confidence: float = 0.0
    source: str = "none"  # llm | vision | heuristic | none
    error: str = ""
    raw: dict = field(default_factory=dict)


# --------------------------------------------------------------------- parsing


def extract_json(raw: str) -> dict:
    """Models wrap JSON in prose or fences more often than they should."""
    if not raw:
        return {}
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    while start != -1:
        depth, in_string, escaped = 0, False, False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start : index + 1])
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return {}


def _clean_field(value: object, max_len: int = 80) -> str:
    if value is None or isinstance(value, (list, dict, bool)):
        return ""
    text = str(value).strip().strip('"').strip()
    if text.lower() in {"null", "none", "n/a", "na", "unknown", "unclear", ""}:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text[:max_len]


def normalize_analysis(payload: dict, source: str = "llm") -> Analysis:
    """Turn a raw model dict into something we can safely build a filename from."""
    doc_type = _clean_field(payload.get("doc_type") or payload.get("type"), 24).lower()
    if doc_type not in DOC_TYPES:
        doc_type = "other" if doc_type else ""

    try:
        confidence = float(payload.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = min(max(confidence, 0.0), 1.0)

    return Analysis(
        date=normalize_date(_clean_field(payload.get("date") or payload.get("document_date"), 32)),
        title=_clean_field(payload.get("title") or payload.get("subject"), 80),
        doc_type=doc_type,
        correspondent=_clean_field(payload.get("correspondent") or payload.get("sender"), 60),
        summary=_clean_field(payload.get("summary"), 300),
        confidence=confidence,
        source=source,
        raw=payload,
    )


# ---------------------------------------------------------------------- ollama


def available() -> bool:
    if not settings.llm_enabled:
        return False
    try:
        response = httpx.get(f"{settings.ollama_url}/api/tags", timeout=3)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def installed_models() -> list[str]:
    try:
        response = httpx.get(f"{settings.ollama_url}/api/tags", timeout=5)
        response.raise_for_status()
        return [m.get("name", "") for m in response.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return []


def _chat(messages: list[dict], model: str) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 400},
    }
    response = httpx.post(
        f"{settings.ollama_url}/api/chat",
        json=payload,
        timeout=settings.llm_timeout,
    )
    response.raise_for_status()
    body = response.json()
    return (body.get("message") or {}).get("content", "")


def analyze_text(text: str, filename: str, hint: str = "") -> Analysis:
    if not settings.llm_enabled:
        return Analysis(source="none", error="llm disabled")
    # An import keeps the folder the document sat in before — real signal.
    hint_line = f"It was filed under: {hint}\n" if hint else ""
    prompt = USER_TEMPLATE.format(
        filename=filename, hint=hint_line, text=text[: settings.extract_max_chars]
    )
    try:
        raw = _chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            settings.llm_model,
        )
    except httpx.HTTPError as exc:
        return Analysis(source="none", error=f"ollama: {exc}")
    payload = extract_json(raw)
    if not payload:
        return Analysis(source="none", error="model returned no JSON")
    return normalize_analysis(payload, "llm")


def analyze_image(path: Path) -> Analysis:
    """Used when OCR found nothing and a vision model is configured."""
    if not (settings.llm_enabled and settings.vision_model):
        return Analysis(source="none", error="no vision model configured")
    try:
        encoded = base64.b64encode(path.read_bytes()).decode()
    except OSError as exc:
        return Analysis(source="none", error=str(exc))
    try:
        raw = _chat(
            [{"role": "user", "content": VISION_PROMPT, "images": [encoded]}],
            settings.vision_model,
        )
    except httpx.HTTPError as exc:
        return Analysis(source="none", error=f"ollama vision: {exc}")
    payload = extract_json(raw)
    if not payload:
        return Analysis(source="none", error="vision model returned no JSON")
    return normalize_analysis(payload, "vision")


# ------------------------------------------------------------------ heuristics


_NOISE_LINE = re.compile(r"^[\W_\d]{0,3}$")


def heuristic(text: str, filename: str) -> Analysis:
    """No model, bad model, or empty reply — still better than `IMG_0042.pdf`."""
    date = find_date_in_text(text)
    title = ""
    for line in (text or "").splitlines():
        candidate = line.strip()
        if len(candidate) < 4 or _NOISE_LINE.match(candidate):
            continue
        if len(slugify(candidate)) < 4:
            continue
        title = candidate[:60]
        break
    if not title:
        stem = Path(filename).stem
        title = stem if len(slugify(stem)) > 3 else "scan"
    return Analysis(date=date, title=title, source="heuristic", confidence=0.2)
