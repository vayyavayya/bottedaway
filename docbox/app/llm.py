"""Reading a document and deciding what it is.

Two kinds of backend:

* **Hosted, OpenAI-compatible** — Nous Research (the default), or anything else
  that speaks `/v1/chat/completions`. Better answers on messy OCR, nothing to
  install, and it costs per call.
* **Local Ollama** — nothing leaves the machine.

Switch with `DOCBOX_LLM_PROVIDER`. Either way, if the model is unreachable or
replies with junk we fall back to heuristics and flag the document rather than
failing the upload.

PRIVACY: with a hosted provider the extracted text of every document — bank
statements, medical letters, payslips — is sent to that provider's API. That is
the trade for the better naming. `DOCBOX_LLM_PROVIDER=ollama` keeps everything
on your own machine.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .config import settings
from .naming import find_date_in_text, normalize_date, slugify

log = logging.getLogger("docbox.llm")

SYSTEM_PROMPT = """You file paper documents for a family archive.
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
  "person": if the document is clearly about one named member of the household,
          their name exactly as it appears in the list below. "" otherwise.
  "summary": one short sentence a person would recognise it by.
  "confidence": 0.0-1.0, how sure you are the fields are right.

Rules: use the document's own language for correspondent, English for doc_type.
Never invent a date that is not in the text. Output JSON only."""

USER_TEMPLATE = """Original filename: {filename}
{household}{hint}
--- DOCUMENT TEXT (may be noisy OCR) ---
{text}
--- END ---

JSON:"""

VISION_PROMPT = """This is a photo or scan of a document. Read it and reply with a
single JSON object using exactly these fields: date (YYYY-MM-DD or null),
correspondent, doc_type, title (2-6 words), person, summary, confidence (0-1).
Output JSON only."""

DOC_TYPES = {
    "invoice", "receipt", "contract", "letter", "statement", "payslip", "tax",
    "insurance", "medical", "warranty", "id", "ticket", "manual", "report",
    "note", "other",
}

# Defaults per provider. Model names change — `/api/health` lists what the key
# can actually reach, so you never have to trust this table.
PROVIDERS = {
    "nous": {
        "base_url": "https://inference-api.nousresearch.com/v1",
        "model": "Hermes-4-70B",
        "local": False,
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "local": False,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "nousresearch/hermes-4-70b",
        "local": False,
    },
    "ollama": {
        "base_url": "http://127.0.0.1:11434",
        "model": "qwen2.5:3b",
        "local": True,
    },
}


def provider() -> str:
    name = (settings.llm_provider or "nous").lower()
    return name if name in PROVIDERS else "nous"


def base_url() -> str:
    return (settings.llm_base_url or PROVIDERS[provider()]["base_url"]).rstrip("/")


def model_name() -> str:
    return settings.llm_model or PROVIDERS[provider()]["model"]


def is_local() -> bool:
    return bool(PROVIDERS[provider()]["local"])


@dataclass
class Analysis:
    date: str = ""
    title: str = ""
    doc_type: str = ""
    correspondent: str = ""
    person: str = ""
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
        person=_clean_field(payload.get("person"), 60),
        summary=_clean_field(payload.get("summary"), 300),
        confidence=confidence,
        source=source,
        raw=payload,
    )


# -------------------------------------------------------------------- backends


def _headers() -> dict:
    key = settings.llm_api_key
    headers = {"content-type": "application/json"}
    if key:
        headers["authorization"] = f"Bearer {key}"
    if provider() == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/docbox"
        headers["X-Title"] = "Docbox"
    return headers


def _post_with_retries(url: str, payload: dict, timeout: int) -> httpx.Response:
    """Hosted APIs rate-limit and hiccup; a document is worth three tries."""
    last: Exception | None = None
    for attempt in range(3):
        try:
            response = httpx.post(url, json=payload, headers=_headers(), timeout=timeout)
        except httpx.HTTPError as exc:
            last = exc
        else:
            if response.status_code < 400:
                return response
            if response.status_code in {408, 409, 429} or response.status_code >= 500:
                last = httpx.HTTPStatusError(
                    f"{response.status_code}: {response.text[:200]}",
                    request=response.request, response=response,
                )
            else:
                response.raise_for_status()
        if attempt < 2:
            time.sleep(2 ** attempt)
    raise last or httpx.HTTPError("request failed")


def _chat_openai(messages: list[dict], model: str, json_mode: bool = True) -> str:
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 500,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        response = _post_with_retries(f"{base_url()}/chat/completions", payload, settings.llm_timeout)
    except httpx.HTTPStatusError as exc:
        # Not every OpenAI-compatible server implements response_format.
        if json_mode and exc.response is not None and exc.response.status_code == 400:
            log.info("provider rejected response_format; retrying without it")
            return _chat_openai(messages, model, json_mode=False)
        raise
    body = response.json()
    choices = body.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("message") or {}).get("content", "") or ""


def _chat_ollama(messages: list[dict], model: str) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 500},
    }
    response = httpx.post(f"{base_url()}/api/chat", json=payload, timeout=settings.llm_timeout)
    response.raise_for_status()
    return (response.json().get("message") or {}).get("content", "")


def _chat(messages: list[dict], model: str | None = None) -> str:
    model = model or model_name()
    if provider() == "ollama":
        return _chat_ollama(messages, model)
    return _chat_openai(messages, model)


def available() -> bool:
    if not settings.llm_enabled:
        return False
    try:
        if provider() == "ollama":
            return httpx.get(f"{base_url()}/api/tags", timeout=3).status_code == 200
        response = httpx.get(f"{base_url()}/models", headers=_headers(), timeout=8)
        return response.status_code < 400
    except httpx.HTTPError:
        return False


def installed_models() -> list[str]:
    """What this key/host can actually reach — better than trusting a docs page."""
    try:
        if provider() == "ollama":
            response = httpx.get(f"{base_url()}/api/tags", timeout=5)
            response.raise_for_status()
            return [m.get("name", "") for m in response.json().get("models", [])]
        response = httpx.get(f"{base_url()}/models", headers=_headers(), timeout=8)
        response.raise_for_status()
        data = response.json().get("data") or []
        return [m.get("id", "") for m in data if m.get("id")][:60]
    except (httpx.HTTPError, ValueError):
        return []


# ------------------------------------------------------------------- analysis


def household_line() -> str:
    people = settings.household
    if not people:
        return ""
    return f"Household members: {', '.join(people)}.\n"


def analyze_text(text: str, filename: str, hint: str = "") -> Analysis:
    if not settings.llm_enabled:
        return Analysis(source="none", error="llm disabled")
    if not is_local() and not settings.llm_api_key:
        return Analysis(source="none", error=f"no API key set for provider {provider()!r}")

    # An import keeps the folder the document sat in before — real signal.
    hint_line = f"It was filed under: {hint}\n" if hint else ""
    prompt = USER_TEMPLATE.format(
        filename=filename,
        household=household_line(),
        hint=hint_line,
        text=text[: settings.extract_max_chars],
    )
    try:
        raw = _chat([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
    except httpx.HTTPError as exc:
        return Analysis(source="none", error=f"{provider()}: {_short(exc)}")
    payload = extract_json(raw)
    if not payload:
        return Analysis(source="none", error="model returned no JSON")
    return normalize_analysis(payload, "llm")


def analyze_image(path: Path) -> Analysis:
    """Used when OCR found nothing and a vision model is configured."""
    if not settings.llm_enabled:
        return Analysis(source="none", error="llm disabled")
    model = settings.vision_model
    if not model:
        return Analysis(source="none", error="no vision model configured")
    try:
        encoded = base64.b64encode(path.read_bytes()).decode()
    except OSError as exc:
        return Analysis(source="none", error=str(exc))

    try:
        if provider() == "ollama":
            raw = _chat_ollama(
                [{"role": "user", "content": VISION_PROMPT, "images": [encoded]}], model
            )
        else:
            mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            raw = _chat_openai([{
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{encoded}"}},
                ],
            }], model)
    except httpx.HTTPError as exc:
        return Analysis(source="none", error=f"{provider()} vision: {_short(exc)}")

    payload = extract_json(raw)
    if not payload:
        return Analysis(source="none", error="vision model returned no JSON")
    return normalize_analysis(payload, "vision")


def _short(exc: Exception) -> str:
    return re.sub(r"\s+", " ", str(exc))[:160]


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
