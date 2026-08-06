"""Filename rules: `YYYYMMDD-some-content.ext`.

Pure functions, no I/O — this is the part worth unit-testing.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata

MAX_SLUG = 60

# Characters that are legal on disk but painful in URLs, shells and iOS Files.
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")

_TRANSLIT = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "ae", "Ö": "oe", "Ü": "ue",
    "å": "a", "æ": "ae", "ø": "oe", "é": "e", "è": "e", "ê": "e",
    "à": "a", "á": "a", "â": "a", "ç": "c", "ñ": "n", "ó": "o", "ô": "o",
}

STOPWORDS = {
    "the", "a", "an", "of", "for", "and", "to", "in", "on", "at", "with",
    "der", "die", "das", "und", "von", "für", "fur", "den", "dem", "des",
}

# Dates we can find in raw document text, most-specific pattern first.
_DATE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(20\d{2}|19\d{2})-(\d{1,2})-(\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(20\d{2}|19\d{2})/(\d{1,2})/(\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})\.(\d{1,2})\.((?:20|19)\d{2})\b"), "dmy"),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/((?:20|19)\d{2})\b"), "dmy_slash"),
    (re.compile(r"\b(\d{1,2})-(\d{1,2})-((?:20|19)\d{2})\b"), "dmy"),
]

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "januar": 1, "februar": 2, "maerz": 3, "märz": 3, "mai": 5, "juni": 6,
    "juli": 7, "oktober": 10, "dezember": 12,
}

_MONTH_NAME_RE = re.compile(
    r"\b(\d{1,2})[.\s]+([A-Za-zäöüÄÖÜ]{3,9})[.,\s]+((?:20|19)\d{2})\b"
)
_MONTH_FIRST_RE = re.compile(
    r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+((?:20|19)\d{2})\b"
)


def transliterate(text: str) -> str:
    out = []
    for ch in text:
        if ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
        else:
            out.append(ch)
    normalized = unicodedata.normalize("NFKD", "".join(out))
    return "".join(c for c in normalized if not unicodedata.combining(c))


def slugify(text: str, max_len: int = MAX_SLUG, drop_stopwords: bool = True) -> str:
    """`Rechnung Stadtwerke März 2024` -> `rechnung-stadtwerke-maerz-2024`."""
    ascii_text = transliterate(text or "").lower()
    words = [w for w in _SLUG_STRIP.split(ascii_text) if w]
    if drop_stopwords and len(words) > 2:
        kept = [w for w in words if w not in STOPWORDS]
        if kept:
            words = kept
    slug = ""
    for word in words:
        candidate = f"{slug}-{word}" if slug else word
        if len(candidate) > max_len:
            break
        slug = candidate
    if not slug:
        # Everything was stripped (e.g. CJK-only title); keep a stable fallback.
        slug = "document"
    return slug.strip("-")


def normalize_date(value: str | None) -> str:
    """Accept anything date-ish, return `YYYYMMDD` or ''."""
    if not value:
        return ""
    raw = str(value).strip()
    if re.fullmatch(r"\d{8}", raw):  # already YYYYMMDD
        return _build(int(raw[0:4]), int(raw[4:6]), int(raw[6:8]))
    found = find_date_in_text(raw)
    if found:
        return found
    digits = re.sub(r"[^0-9]", "", raw)
    if len(digits) == 8:  # e.g. "2024 03 17" with odd separators
        return _build(int(digits[0:4]), int(digits[4:6]), int(digits[6:8]))
    return ""


def _plausible(day: dt.date) -> bool:
    return dt.date(1970, 1, 1) <= day <= dt.date.today() + dt.timedelta(days=370)


def _build(year: int, month: int, day: int) -> str:
    try:
        parsed = dt.date(year, month, day)
    except ValueError:
        return ""
    return parsed.strftime("%Y%m%d") if _plausible(parsed) else ""


def find_date_in_text(text: str) -> str:
    """Best-effort date scrape, used when the model gives us nothing usable."""
    if not text:
        return ""
    window = text[:4000]

    for pattern, kind in _DATE_PATTERNS:
        for match in pattern.finditer(window):
            a, b, c = match.groups()
            if kind == "ymd":
                got = _build(int(a), int(b), int(c))
            elif kind == "dmy_slash":
                # Ambiguous: 03/04/2024. Prefer D/M unless the first number can't be a day.
                got = _build(int(c), int(b), int(a)) or _build(int(c), int(a), int(b))
            else:
                got = _build(int(c), int(b), int(a))
            if got:
                return got

    for match in _MONTH_NAME_RE.finditer(window):
        day, month_name, year = match.groups()
        month = _MONTHS.get(transliterate(month_name).lower()[:3]) or _MONTHS.get(month_name.lower())
        if month:
            got = _build(int(year), month, int(day))
            if got:
                return got

    for match in _MONTH_FIRST_RE.finditer(window):
        month_name, day, year = match.groups()
        month = _MONTHS.get(month_name.lower()[:3])
        if month:
            got = _build(int(year), month, int(day))
            if got:
                return got
    return ""


def build_filename(date: str, title: str, ext: str, extra: str = "") -> str:
    """`20240317-stadtwerke-rechnung.pdf`."""
    date_part = normalize_date(date) or dt.date.today().strftime("%Y%m%d")
    parts = [p for p in (extra, title) if p and p.strip()]
    slug = slugify(" ".join(parts))
    ext = (ext or "").lower().lstrip(".")
    suffix = f".{ext}" if ext else ""
    return f"{date_part}-{slug}{suffix}"


def dedupe_filename(name: str, taken: set[str]) -> str:
    """Append `-2`, `-3`, ... before the extension until the name is free."""
    if name not in taken:
        return name
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    counter = 2
    while True:
        candidate = f"{stem}-{counter}{'.' + ext if ext else ''}"
        if candidate not in taken:
            return candidate
        counter += 1


_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._\- ()]+")


def safe_filename(name: str) -> str:
    """Sanitize a user- or scanner-supplied name for on-disk use."""
    cleaned = _UNSAFE_NAME.sub("-", transliterate(name or "").strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-. ")
    cleaned = cleaned.replace("..", ".")
    if not cleaned:
        cleaned = "file"
    return cleaned[:120]


def safe_folder(name: str, default: str = "Inbox") -> str:
    """Single-level folder name; no traversal, no separators."""
    cleaned = (name or "").strip().strip("/")
    if not cleaned or cleaned in {".", ".."}:
        return default
    cleaned = cleaned.split("/")[0].split("\\")[0]
    cleaned = _UNSAFE_NAME.sub("-", transliterate(cleaned)).strip("-. ")
    return cleaned[:60] or default


def looks_machine_generated(name: str) -> bool:
    """Scanner output like `IMG_0042.pdf`, `Scan 12 Mar 2024.pdf`, `20240312_113355.jpg`."""
    stem = name.rsplit(".", 1)[0].strip().lower()
    if not stem:
        return True
    patterns = (
        r"^img[_\- ]?\d+$",
        r"^dsc[_\- ]?\d+$",
        r"^scan[_\- ]?\d*$",
        r"^scan[ _-].*",
        r"^document[_\- ]?\d*$",
        r"^doc[_\- ]?\d+$",
        r"^photo[_\- ]?\d*$",
        r"^\d{6,}([_\- ]\d+)*$",
        r"^[0-9a-f]{16,}$",
        r"^untitled.*",
        r"^unbenannt.*",
        r"^file[_\- ]?\d*$",
        r"^pdf[_\- ]?\d+.*",
        r"^[a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12}$",
    )
    return any(re.match(p, stem) for p in patterns)
