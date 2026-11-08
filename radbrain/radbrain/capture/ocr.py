"""Local OCR backends behind one API: ocr(image) -> str.

Backends
  tesseract  tesseract CLI via stdin/stdout (no temp files), lang deu, grayscale + polarity fix + adaptive upscale + light threshold
  ollama     local vision model (config.models().vision) via POST {ollama}/api/chat, image base64 in memory
  paddle     PaddleOCR (lang german) if installed; skipped gracefully otherwise

Images are never written to disk: encoding for Ollama goes through io.BytesIO, preprocessing stays in PIL.
Nothing here logs or prints recognised text.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageStat

BACKENDS = ("tesseract", "ollama", "paddle")
DEFAULT_BACKEND = "tesseract"

OLLAMA_PROMPT = (
    "Transcribe ALL text in this image exactly, verbatim, character by character. It is a German "
    "radiology report. Preserve the original line breaks, punctuation, capitalisation, umlauts (ä ö ü Ä Ö Ü) "
    "and ß, numbers, units and abbreviations exactly as shown (for example V.a., DD, KM, HU, re./li., Z.n., "
    "i.v., ca., mm, BWK 12, LWK 3). Do not correct, translate, summarise, reorder or explain anything. "
    "Do not add markdown, quotes or commentary. Output only the transcribed text."
)

_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n(.*?)\n?```\s*$", re.S)


class OCRUnavailable(RuntimeError):
    """The requested backend cannot run here (missing binary/package/server)."""


# --------------------------------------------------------------------------------------------- preprocessing
def estimate_line_height(gray: Image.Image) -> float | None:
    """Median height (px) of ink rows runs in a dark-text-on-light image. None if no text-like rows."""
    w, h = gray.size
    if w == 0 or h == 0:
        return None
    # ink = pixels clearly darker than the background; count per row via a 1-px-wide resize of a mask
    mask = gray.point(lambda v: 255 if v < 140 else 0)
    rows = mask.resize((1, h), Image.Resampling.BOX).tobytes()
    runs, cur = [], 0
    for v in rows:
        if v > 2:              # row has >~1% ink
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    runs = [r for r in runs if r >= 3]
    return float(statistics.median(runs)) if runs else None


def _long_run_lines(mask: Image.Image, k: int, vertical: bool) -> list[int]:
    """Indices of columns (vertical=True) or rows containing an ink run of >= ~k..2k px. Done with BOX
    downsampling: a block that averages to (almost) full ink can only come from a continuous run."""
    w, h = mask.size
    hits: set[int] = set()
    for off in (0, k // 2):
        if vertical:
            m = mask.crop((0, off, w, h))
            if m.height < k:
                continue
            small = m.resize((w, max(1, m.height // k)), Image.Resampling.BOX)
            sw, sh = small.size
            px = small.load()
            hits.update(x for x in range(sw) if any(px[x, y] >= 245 for y in range(sh)))
        else:
            m = mask.crop((off, 0, w, h))
            if m.width < k:
                continue
            small = m.resize((max(1, m.width // k), h), Image.Resampling.BOX)
            sw, sh = small.size
            px = small.load()
            hits.update(y for y in range(sh) if any(px[x, y] >= 245 for x in range(sw)))
    return sorted(hits)


def remove_ui_lines(g: Image.Image, line_h: float | None) -> Image.Image:
    """Whiten panel borders, scrollbars and rules (long straight ink runs) that Tesseract reads as | l I ]."""
    lh = line_h or 14.0
    mask = g.point(lambda v: 255 if v < 200 else 0)
    cols = _long_run_lines(mask, max(6, int(1.3 * lh) + 1), vertical=True)
    rows = _long_run_lines(mask, max(20, int(6 * lh)), vertical=False)
    if not cols and not rows:
        return g
    g = g.copy()
    d = ImageDraw.Draw(g)
    for x in cols:
        d.line([(max(0, x - 1), 0), (max(0, x - 1), g.height)], fill=255, width=3)
    for y in rows:
        d.line([(0, max(0, y - 1)), (g.width, max(0, y - 1))], fill=255, width=3)
    return g


def preprocess_for_tesseract(image: Image.Image, *, target_line_px: int = 32, max_scale: float = 3.0,
                             threshold: bool = True, strip_ui: bool = True) -> Image.Image:
    """Grayscale, make text dark-on-light, strip UI lines, upscale small text (~2x for 11-13 px fonts),
    light threshold."""
    g = image.convert("L")
    if ImageStat.Stat(g).mean[0] < 128:          # light-on-dark panel -> invert
        g = ImageOps.invert(g)
    g = ImageOps.autocontrast(g, cutoff=1)
    lh = estimate_line_height(g)
    if strip_ui:
        g = remove_ui_lines(g, lh)
    scale = 1.0
    if lh is not None and lh < target_line_px:
        scale = min(max_scale, max(2.0, target_line_px / lh)) if lh < target_line_px * 0.75 else 1.5
    elif lh is None and max(g.size) < 1200:
        scale = 2.0
    if scale > 1.0:
        g = g.resize((int(g.width * scale), int(g.height * scale)), Image.Resampling.LANCZOS)
    if threshold:
        # "light" threshold: push the near-white background to pure white and the core of glyphs to black,
        # keep anti-aliased edges as gray (hard binarisation hurts upscaled small text)
        g = g.point(lambda v: 255 if v > 200 else (0 if v < 60 else v))
    return g


# --------------------------------------------------------------------------------------------- backends
def ocr_tesseract(image: Image.Image, *, lang: str = "deu", psm: int = 4, preprocess: bool = True,
                  tessdata_dir: str | None = None, timeout: float = 60.0) -> str:
    """Runs the tesseract CLI with the image piped through STDIN as an in-memory BMP and the text read
    from STDOUT. (pytesseract.image_to_string is NOT used: it writes the image to a temp file.)"""
    cmd = tesseract_cmd()
    if not cmd:
        raise OCRUnavailable("tesseract binary not found")
    img = preprocess_for_tesseract(image) if preprocess else image.convert("L")
    buf = io.BytesIO()
    img.save(buf, format="BMP")            # in memory; leptonica parses BMP straight from the buffer
    if img is not image:
        del img
    args = [cmd, "stdin", "stdout", "-l", lang, "--oem", "1", "--psm", str(psm),
            "-c", "preserve_interword_spaces=1"]
    if tessdata_dir:
        args[1:1] = ["--tessdata-dir", tessdata_dir]
    try:
        proc = subprocess.run(args, input=buf.getvalue(), capture_output=True, timeout=timeout,
                              creationflags=_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise OCRUnavailable(f"tesseract failed: {type(e).__name__}") from e
    finally:
        buf.close()
    if proc.returncode != 0:
        raise OCRUnavailable(f"tesseract exit {proc.returncode}")     # stderr not echoed (may quote input)
    txt = proc.stdout.decode("utf-8", errors="replace")
    return _tidy(fix_tesseract_artifacts(txt))


_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0          # CREATE_NO_WINDOW under pythonw
_TESS_CMD: list[str] = []


def tesseract_cmd() -> str | None:
    """tesseract on PATH, else the UB-Mannheim install locations on Windows. Cached."""
    if _TESS_CMD:
        return _TESS_CMD[0]
    found = shutil.which("tesseract")
    if not found and sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
            cand = os.path.join(base, "Tesseract-OCR", "tesseract.exe")
            if os.path.exists(cand):
                found = cand
                break
    if found:
        _TESS_CMD.append(found)
    return found


def tesseract_languages() -> list[str]:
    cmd = tesseract_cmd()
    if not cmd:
        return []
    p = subprocess.run([cmd, "--list-langs"], capture_output=True, timeout=20, creationflags=_NO_WINDOW)
    lines = (p.stdout or b"").decode("utf-8", "replace").splitlines()
    return [ln.strip() for ln in lines[1:] if ln.strip()]


_PIPE_AS_I = re.compile(r"(?:(?<=\s)|^)\|(?=[\s.,;:)]|$)", re.M)
_II_AS_LI = re.compile(r"(?<![A-Za-zÄÖÜäöüß])Ii\.")


def fix_tesseract_artifacts(text: str) -> str:
    """Known l/I/| confusions that cannot be German: a free-standing '|' is a roman 'I' (Grad I, Bosniak I),
    'Ii.' is the side abbreviation 'li.'."""
    text = _PIPE_AS_I.sub("I", text or "")
    return _II_AS_LI.sub("li.", text)


def image_to_b64_png(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")          # in memory only
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    buf.close()
    return data


def ocr_ollama(image: Image.Image, *, model: str | None = None, host: str | None = None,
               timeout: float = 240.0, min_width: int = 1000, prompt: str = OLLAMA_PROMPT) -> str:
    """Verbatim transcription with a local vision model. Upscales narrow crops so small fonts survive the
    model's own resize. Temperature 0, thinking off where supported, <think> blocks stripped anyway."""
    import httpx

    from radbrain import config
    m = config.models()
    model = model or m.vision
    host = (host or m.ollama).rstrip("/")
    img = image.convert("RGB")
    if img.width < min_width:
        f = min(3.0, min_width / max(1, img.width))
        img = img.resize((int(img.width * f), int(img.height * f)), Image.Resampling.LANCZOS)
    b64 = image_to_b64_png(img)
    del img
    body = {"model": model, "stream": False, "think": False, "keep_alive": "30m",
            "options": {"temperature": 0, "top_k": 1, "seed": 0, "num_predict": 4096, "num_ctx": 16384},
            "messages": [{"role": "user", "content": prompt, "images": [b64]}]}
    try:
        r = httpx.post(f"{host}/api/chat", json=body, timeout=timeout)
        if r.status_code == 400 and "think" in r.text.lower():   # model without a thinking switch
            body.pop("think", None)
            r = httpx.post(f"{host}/api/chat", json=body, timeout=timeout)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise OCRUnavailable(f"ollama request failed: {type(e).__name__}") from e
    finally:
        del b64
        body["messages"][0]["images"] = []
    try:
        content = r.json()["message"]["content"]
    except (ValueError, KeyError, TypeError) as e:
        raise OCRUnavailable("ollama returned no message") from e
    return clean_model_output(content)


def clean_model_output(text: str) -> str:
    text = _THINK_RE.sub("", text or "")
    if "</think>" in text:                      # unbalanced: keep what follows the last close tag
        text = text.rsplit("</think>", 1)[1]
    text = text.strip()
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1)
    return _tidy(text)


_PADDLE = None


def ocr_paddle(image: Image.Image) -> str:
    """PaddleOCR (2.x .ocr() or 3.x .predict()). Lines are re-ordered top-to-bottom, left-to-right."""
    global _PADDLE
    try:
        import numpy as np
        from paddleocr import PaddleOCR
    except Exception as e:
        raise OCRUnavailable("paddleocr not installed") from e
    if _PADDLE is None:
        try:
            _PADDLE = PaddleOCR(lang="german", use_angle_cls=False, show_log=False)
        except TypeError:          # 3.x dropped show_log / use_angle_cls
            _PADDLE = PaddleOCR(lang="german", use_textline_orientation=False)
    arr = np.array(image.convert("RGB"))
    items: list[tuple[float, float, str]] = []
    if hasattr(_PADDLE, "predict"):
        try:
            for res in _PADDLE.predict(arr):
                d = res if isinstance(res, dict) else getattr(res, "json", {}).get("res", {})
                for box, txt in zip(d.get("rec_polys", d.get("dt_polys", [])), d.get("rec_texts", [])):
                    ys = [p[1] for p in box]
                    xs = [p[0] for p in box]
                    items.append((float(min(ys)), float(min(xs)), str(txt)))
        except Exception:
            items = []
    if not items:
        res = _PADDLE.ocr(arr)
        for page in res or []:
            for line in page or []:
                box, (txt, _conf) = line[0], line[1]
                items.append((float(min(p[1] for p in box)), float(min(p[0] for p in box)), str(txt)))
    del arr
    return _tidy(_join_lines(items))


def _join_lines(items: list[tuple[float, float, str]]) -> str:
    if not items:
        return ""
    items.sort()
    lines: list[list[tuple[float, float, str]]] = []
    for it in items:
        if lines and abs(it[0] - lines[-1][0][0]) < 8:
            lines[-1].append(it)
        else:
            lines.append([it])
    return "\n".join(" ".join(t for _, _, t in sorted(ln, key=lambda x: x[1])) for ln in lines)


def _tidy(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\f", "")
    lines = [ln.rstrip() for ln in text.split("\n")]
    # drop leading/trailing blank lines, collapse runs of >1 blank line
    out: list[str] = []
    for ln in lines:
        if not ln and (not out or not out[-1]):
            continue
        out.append(ln)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


# --------------------------------------------------------------------------------------------- dispatch
def get_backend(name: str, **kwargs) -> Callable[[Image.Image], str]:
    name = (name or DEFAULT_BACKEND).lower()
    fn = {"tesseract": ocr_tesseract, "ollama": ocr_ollama, "paddle": ocr_paddle}.get(name)
    if fn is None:
        raise ValueError(f"unknown OCR backend {name!r}; choose from {BACKENDS}")
    if kwargs:
        return lambda img: fn(img, **kwargs)
    return fn


def best_backend() -> str:
    """settings.json key "ocr" in the data dir (default "tesseract")."""
    from radbrain import config
    p = config.data_dir() / "settings.json"
    if p.exists():
        try:
            v = str(json.loads(p.read_text(encoding="utf-8")).get("ocr") or "").lower()
            if v in BACKENDS:
                return v
        except (ValueError, OSError):
            pass
    return DEFAULT_BACKEND


def ocr(image: Image.Image, backend: str | None = None, **kwargs) -> str:
    """The one entry point: ocr(image) -> text, using best_backend() unless one is given."""
    return get_backend(backend or best_backend(), **kwargs)(image)


def available_backends() -> dict[str, str]:
    """{backend: "ok" | reason} without running OCR on anything real."""
    out: dict[str, str] = {}
    try:
        if not tesseract_cmd():
            out["tesseract"] = "tesseract binary not found"
        else:
            out["tesseract"] = "ok" if "deu" in tesseract_languages() else "deu traineddata missing"
    except Exception as e:
        out["tesseract"] = f"unavailable: {type(e).__name__}"
    try:
        import httpx

        from radbrain import config
        m = config.models()
        tags = httpx.get(f"{m.ollama.rstrip('/')}/api/tags", timeout=3).json()
        names = {t["name"] for t in tags.get("models", [])}
        out["ollama"] = "ok" if (m.vision in names or f"{m.vision}:latest" in names) else f"model {m.vision} not pulled"
    except Exception as e:
        out["ollama"] = f"unavailable: {type(e).__name__}"
    try:
        import importlib.util
        out["paddle"] = "ok" if importlib.util.find_spec("paddleocr") else "not installed"
    except Exception:
        out["paddle"] = "not installed"
    return out


# light sharpening helper some callers use for Citrix-compressed crops
def unsharp(image: Image.Image) -> Image.Image:
    return image.filter(ImageFilter.UnsharpMask(radius=1, percent=80, threshold=2))
