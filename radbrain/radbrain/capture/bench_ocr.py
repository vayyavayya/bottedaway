"""Synthetic OCR benchmark: python -m radbrain.capture.bench_ocr [--backends tesseract,ollama] [--out f.json]

~30 fictional German report snippets (written here, no real data) are rendered IN MEMORY to images that
look like a PACS report panel: Arial/Tahoma/Verdana/Segoe UI at 11-13 px plus larger variants, dark-on-light
and light-on-dark, half of them JPEG-recompressed and slightly blurred to mimic Citrix/HDX compression.
Nothing is written to disk except the JSON results (--out).

Metrics per backend
  cer            Levenshtein(hyp, ref) / len(ref), line structure kept (whitespace inside lines collapsed)
  cer_flat       same with all whitespace incl. line breaks collapsed to one space (layout-insensitive)
  abbrev_hit     exact hits of radiology abbreviations (V.a., DD, KM, HU, ED, re., li., Z.n., Lig., BWK 12,
                 LWK 3, i.v., ca., mm) counted per occurrence: sum(min(ref, hyp)) / sum(ref)
  term_hit       same for Pneumothorax / Pleuraerguss / Lungenembolie and other key terms
  umlaut_acc     ä ö ü Ä Ö Ü ß of the reference that survive in the Levenshtein alignment
  sec/image      wall time per image (Ollama: after a warm-up call that loads the model)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import platform
import random
import re
import statistics
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from rapidfuzz.distance import Levenshtein

# ------------------------------------------------------------------------------------------- synthetic text
SNIPPETS: list[str] = [
    "CT Thorax mit KM i.v.:\nZentrale Lungenembolie re. mit Füllungsdefekt in der Pulmonalarterie.\n"
    "Keine Rechtsherzbelastung. Kein Pleuraerguss.",
    "Beurteilung:\n1. V.a. segmentale Lungenembolie li. im Unterlappen.\n2. DD Artefakt bei Atemexkursion.\n"
    "Empfehlung: klinische Korrelation.",
    "Röntgen Thorax p.a. und seitlich:\nKein Pneumothorax. Kleiner Pleuraerguss re. basal, ca. 15 mm.\n"
    "Herz normal groß. Zwerchfell glatt begrenzt.",
    "Z.n. Hemithyreoidektomie li. 2019.\nSchilddrüsenrest re. unauffällig, Größe ca. 12 x 9 mm.\n"
    "Keine suspekten Lymphknoten zervikal.",
    "MRT LWS nativ:\nOsteochondrose LWK 3/4 mit breitbasiger Bandscheibenprotrusion.\n"
    "Keine Spinalkanalstenose. Neuroforamina re./li. frei.",
    "Frische Deckplattenimpressionsfraktur BWK 12, Höhenminderung ca. 20 %.\n"
    "Hinterkante intakt. Kein Hinweis auf Spinalkanaleinengung.",
    "CT Abdomen mit KM i.v. in portalvenöser Phase:\nLeber homogen, keine fokalen Läsionen.\n"
    "Zyste der li. Niere, Dichte 5 HU, ca. 18 mm, Bosniak I.",
    "Hypodense Läsion im Lebersegment VII, ca. 9 mm, 45 HU nativ.\nDD Hämangiom, DD Metastase.\n"
    "Weitere Abklärung mittels MRT empfohlen.",
    "MRT Knie re.:\nKomplette Ruptur des vorderen Kreuzbandes.\nLig. collaterale mediale intakt. "
    "Gelenkerguss mäßig.",
    "Partialruptur des Lig. fibulotalare anterius li.\nKnochenmarködem im Talus. "
    "Keine Fraktur abgrenzbar.",
    "Rezidivierender Pneumothorax re. apikal, Spitzenabstand ca. 25 mm.\n"
    "Z.n. Thoraxdrainage re. Keine Mediastinalverlagerung.",
    "Pleuraerguss beidseits, re. > li., mit Kompressionsatelektase.\nV.a. kardiale Dekompensation.\n"
    "Pulmonalvenöse Stauung Grad II.",
    "ED Mammakarzinom li. 2021, Z.n. BET und Radiatio.\nKein Anhalt für Lokalrezidiv.\n"
    "Keine ossären Metastasen in BWK 12 und LWK 3.",
    "CT Schädel nativ:\nKeine intrakranielle Blutung. Keine frühen Ischämiezeichen.\n"
    "Altersentsprechende Weite der äußeren Liquorräume.",
    "Mikroangiopathische Marklagerläsionen beidseits, Fazekas Grad 1.\nKein Nachweis einer Raumforderung.\n"
    "Ventrikelsystem mittelständig.",
    "CT-Angiographie Hals:\nHochgradige Stenose der A. carotis interna li. ca. 80 %.\n"
    "Re. geringgradige Plaques ohne hämodynamische Relevanz.",
    "Lungenembolie bis in die Subsegmentarterien beidseits.\nRV/LV-Quotient 1,1. Keine Infarktpneumonie.\n"
    "Kleiner Pleuraerguss li. dorsobasal.",
    "Rundherd im Oberlappen re., ca. 7 mm, glatt begrenzt.\nDD Granulom. Verlaufskontrolle in 6 Monaten.\n"
    "Kein Pneumothorax nach Punktion.",
    "Sonographie Abdomen:\nGallenblase mit Konkrement ca. 14 mm, Wand nicht verdickt.\n"
    "Ductus hepatocholedochus 5 mm, nicht erweitert.",
    "Akute Appendizitis mit periappendizitischer Flüssigkeit.\nAppendix-Durchmesser ca. 11 mm. "
    "Keine freie Luft.\nV.a. beginnende Perforation.",
    "Röntgen Hand li. in 2 Ebenen:\nDistale Radiusfraktur Typ Colles mit Dorsalabkippung ca. 25°.\n"
    "Begleitende Fraktur des Proc. styloideus ulnae.",
    "Z.n. Hüft-TEP re. Prothese regelrecht positioniert.\nKein Lockerungssaum. "
    "Heterotope Ossifikationen Grad I nach Brooker.",
    "MRT Schulter re.:\nTransmurale Ruptur der Supraspinatussehne, Retraktion ca. 15 mm.\n"
    "Fettige Atrophie Goutallier Grad 2. Erguss in der Bursa.",
    "CT Thorax nativ:\nEmphysem zentrilobulär, Betonung der Oberlappen.\n"
    "Keine Infiltrate. Kein Pleuraerguss. Kein Pneumothorax.",
    "Nierenstein im proximalen Ureter re., ca. 6 mm, 950 HU.\nHarnstau Grad II re.\n"
    "Li. Niere unauffällig.",
    "Gefäßstatus: Aortenaneurysma infrarenal, max. Durchmesser ca. 52 mm.\n"
    "Teilthrombosiert. Keine Hinweise auf Ruptur.\nDD entzündliches Aneurysma unwahrscheinlich.",
    "MRT Becken mit KM i.v.:\nUterus myomatosus, größtes Myom ca. 38 mm, intramural.\n"
    "Ovarien beidseits unauffällig. Kein Aszites.",
    "Spondylodese LWK 3 bis LWK 5, Schraubenlage regelrecht.\nKeine Lockerung. "
    "Anschlussdegeneration LWK 2/3.",
    "Mediastinale Lymphknoten bis ca. 14 mm Kurzachse.\nV.a. Lymphom, DD Sarkoidose.\n"
    "Histologische Sicherung empfohlen.",
    "Vergleich mit der Voruntersuchung vom 03.04.2025:\nGrößenregredienter Pleuraerguss re., "
    "Lungenembolie nicht mehr nachweisbar.\nSchließlich unveränderter Befund in BWK 12.",
]

ABBREVS = ["V.a.", "DD", "KM", "HU", "ED", "re.", "li.", "Z.n.", "Lig.", "BWK 12", "LWK 3", "i.v.", "ca.", "mm"]
TERMS = ["Pneumothorax", "Pleuraerguss", "Lungenembolie", "Läsion", "Größe", "Füllungsdefekt", "Höhenminderung"]
SPECIAL = set("äöüÄÖÜß")
_B = r"[A-Za-z0-9ÄÖÜäöüß]"

# ------------------------------------------------------------------------------------------- rendering
FONT_CANDIDATES = {
    "Segoe UI": [r"C:\Windows\Fonts\segoeui.ttf"],
    "Arial": [r"C:\Windows\Fonts\arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"],
    "Tahoma": [r"C:\Windows\Fonts\tahoma.ttf", "/System/Library/Fonts/Supplemental/Tahoma.ttf"],
    "Verdana": [r"C:\Windows\Fonts\verdana.ttf", "/System/Library/Fonts/Supplemental/Verdana.ttf"],
}


def available_fonts() -> dict[str, str]:
    out = {}
    for name, paths in FONT_CANDIDATES.items():
        for p in paths:
            if os.path.exists(p):
                out[name] = p
                break
    return out


def load_font(name: str, size: int, fonts: dict[str, str]):
    if name in fonts:
        return ImageFont.truetype(fonts[name], size)
    return ImageFont.load_default(size)


def render_panel(text: str, *, font, dark: bool = False, compressed: bool = False, jpeg_q: int = 45,
                 blur: float = 0.5, pad: int = 10, line_gap: float = 1.35) -> Image.Image:
    """A report panel: border, padding, a fake scrollbar on the right. Returns an in-memory RGB image."""
    bg, fg, border, bar = ((30, 32, 36), (214, 214, 214), (70, 70, 76), (55, 57, 62)) if dark else \
        ((255, 255, 255), (20, 20, 20), (160, 160, 160), (225, 225, 225))
    lines = text.split("\n")
    asc, desc = font.getmetrics()
    lh = int((asc + desc) * line_gap)
    tw = max(int(font.getlength(ln)) for ln in lines)
    w, h = tw + 2 * pad + 16, lh * len(lines) + 2 * pad
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=border)
    d.rectangle([w - 13, 1, w - 2, h - 2], fill=bar)                    # scrollbar track
    d.rectangle([w - 11, 4, w - 4, max(12, h // 3)], fill=border)       # scrollbar thumb
    for i, ln in enumerate(lines):
        d.text((pad, pad + i * lh), ln, font=font, fill=fg)
    if compressed:
        if blur:
            img = img.filter(ImageFilter.GaussianBlur(blur))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=jpeg_q)      # in memory, mimics Citrix lossy codec
        buf.seek(0)
        img = Image.open(buf).convert("RGB")
        buf.close()
    return img


STYLE_SIZES = [11, 12, 13, 12, 11, 13, 16, 12, 20, 14]


def make_samples(n: int, seed: int = 7) -> list[dict]:
    fonts = available_fonts()
    font_names = [f for f in ("Segoe UI", "Arial", "Tahoma", "Verdana") if f in fonts] or ["default"]
    rnd = random.Random(seed)
    samples = []
    for i in range(n):
        text = SNIPPETS[i % len(SNIPPETS)]
        size = STYLE_SIZES[i % len(STYLE_SIZES)]
        fname = font_names[i % len(font_names)]
        dark = (i % 3 == 2)
        compressed = (i % 2 == 1)
        q = rnd.choice([35, 45, 55]) if compressed else None
        blur = rnd.choice([0.4, 0.6]) if compressed else 0.0
        samples.append({"i": i, "text": text, "style": {"font": fname, "px": size, "dark": dark,
                                                         "compressed": compressed, "jpeg_q": q, "blur": blur}})
    return samples


def render_sample(s: dict) -> Image.Image:
    st = s["style"]
    font = load_font(st["font"], st["px"], available_fonts())
    return render_panel(s["text"], font=font, dark=st["dark"], compressed=st["compressed"],
                        jpeg_q=st["jpeg_q"] or 45, blur=st["blur"])


# ------------------------------------------------------------------------------------------- metrics
def norm_lines(t: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in (t or "").replace("\r", "").split("\n")]
    return "\n".join(ln for ln in lines if ln)


def norm_flat(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def cer(hyp: str, ref: str) -> float:
    return Levenshtein.distance(hyp, ref) / max(1, len(ref))


def count_token(text: str, tok: str) -> int:
    pat = (r"(?<!" + _B + r")" if tok[0].isalnum() else "") + re.escape(tok).replace(r"\ ", r"\s+") + \
          (r"(?!" + _B + r")" if tok[-1].isalnum() else "")
    return len(re.findall(pat, text))


def token_hits(hyp: str, ref: str, toks: list[str]) -> tuple[int, int]:
    hit = tot = 0
    for t in toks:
        r = count_token(ref, t)
        if r:
            tot += r
            hit += min(r, count_token(hyp, t))
    return hit, tot


def special_char_hits(hyp: str, ref: str) -> tuple[int, int]:
    tot = sum(1 for c in ref if c in SPECIAL)
    hit = 0
    for op in Levenshtein.opcodes(ref, hyp):
        if op.tag == "equal":
            hit += sum(1 for c in ref[op.src_start:op.src_end] if c in SPECIAL)
    return hit, tot


def score(hyp: str, ref: str) -> dict:
    h, r = norm_lines(hyp), norm_lines(ref)
    a_hit, a_tot = token_hits(h, r, ABBREVS)
    t_hit, t_tot = token_hits(h, r, TERMS)
    u_hit, u_tot = special_char_hits(norm_flat(h), norm_flat(r))
    return {"cer": round(cer(h, r), 4), "cer_flat": round(cer(norm_flat(h), norm_flat(r)), 4),
            "abbrev": [a_hit, a_tot], "terms": [t_hit, t_tot], "umlaut": [u_hit, u_tot],
            "exact": h == r}


# ------------------------------------------------------------------------------------------- runner
def make_backend(name: str, args):
    from radbrain.capture import ocr as ocrmod
    if name == "tesseract":
        return lambda img: ocrmod.ocr_tesseract(img, psm=args.psm)
    if name == "tesseract_raw":
        return lambda img: ocrmod.ocr_tesseract(img, psm=args.psm, preprocess=False)
    if name == "ollama":
        return lambda img: ocrmod.ocr_ollama(img, model=args.ollama_model, host=args.ollama_url,
                                             min_width=args.ollama_min_width)
    if name == "paddle":
        return ocrmod.ocr_paddle
    raise SystemExit(f"unknown backend {name}")


def summarise(rows: list[dict]) -> dict:
    ok = [r for r in rows if "error" not in r]
    if not ok:
        return {"n": len(rows), "failures": len(rows)}

    def rate(key):
        h = sum(r[key][0] for r in ok)
        t = sum(r[key][1] for r in ok)
        return {"rate": round(h / t, 4) if t else None, "hits": h, "total": t}

    secs = sorted(r["sec"] for r in ok)
    out = {"n": len(rows), "failures": len(rows) - len(ok),
           "cer_mean": round(statistics.mean(r["cer"] for r in ok), 4),
           "cer_median": round(statistics.median(r["cer"] for r in ok), 4),
           "cer_max": round(max(r["cer"] for r in ok), 4),
           "cer_flat_mean": round(statistics.mean(r["cer_flat"] for r in ok), 4),
           "exact_samples": sum(1 for r in ok if r["exact"]),
           "abbrev_hit": rate("abbrev"), "term_hit": rate("terms"), "umlaut_acc": rate("umlaut"),
           "sec_mean": round(statistics.mean(secs), 3), "sec_median": round(statistics.median(secs), 3),
           "sec_p95": round(secs[min(len(secs) - 1, int(0.95 * len(secs)))], 3)}
    groups = {
        "small_11_13px": [r for r in ok if r["style"]["px"] <= 13],
        "large_14px_plus": [r for r in ok if r["style"]["px"] >= 14],
        "dark_on_light": [r for r in ok if not r["style"]["dark"]],
        "light_on_dark": [r for r in ok if r["style"]["dark"]],
        "clean": [r for r in ok if not r["style"]["compressed"]],
        "jpeg_blur": [r for r in ok if r["style"]["compressed"]],
    }
    out["cer_by_style"] = {k: {"n": len(v), "cer_mean": round(statistics.mean(x["cer"] for x in v), 4)}
                           for k, v in groups.items() if v}
    return out


def run(args) -> dict:
    samples = make_samples(args.n, args.seed)
    backends = [b.strip() for b in args.backends.split(",") if b.strip()]
    result = {"tool": "radbrain.capture.bench_ocr", "host": platform.system(),
              "python": sys.version.split()[0], "n_samples": len(samples), "fonts": sorted(available_fonts()),
              "backends": {}, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    for name in backends:
        if name == "paddle":
            import importlib.util
            if not importlib.util.find_spec("paddleocr"):
                result["backends"]["paddle"] = {"skipped": "paddleocr not installed"}
                continue
        fn = make_backend(name, args)
        meta = {}
        if name == "ollama":
            meta["model"] = args.ollama_model
            t0 = time.perf_counter()
            try:
                fn(render_panel("Test Größe ca. 5 mm", font=load_font("Arial", 16, available_fonts())))
                meta["warmup_sec"] = round(time.perf_counter() - t0, 2)
            except Exception as e:
                result["backends"][name] = {"skipped": f"warm-up failed: {e}"}
                continue
        rows = []
        for s in samples:
            img = render_sample(s)
            t0 = time.perf_counter()
            try:
                hyp = fn(img)
                row = {"i": s["i"], "style": s["style"], "sec": round(time.perf_counter() - t0, 3),
                       **score(hyp, s["text"])}
            except Exception as e:
                row = {"i": s["i"], "style": s["style"], "error": f"{type(e).__name__}: {e}"[:200],
                       "sec": round(time.perf_counter() - t0, 3)}
            finally:
                del img
            if args.verbose:
                print(f"[{name}] #{s['i']:02d} {s['style']['px']}px dark={s['style']['dark']} "
                      f"jpeg={s['style']['compressed']} cer={row.get('cer')} {row['sec']}s", file=sys.stderr)
            rows.append(row)
        result["backends"][name] = {**meta, "summary": summarise(rows), "samples": rows}
    result["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backends", default="tesseract,ollama",
                    help="comma list of tesseract, tesseract_raw (no preprocessing), ollama, paddle")
    ap.add_argument("--ollama-model", default=None, help="vision model (default: config.models().vision)")
    ap.add_argument("--ollama-url", default=None, help="default: config.models().ollama")
    ap.add_argument("--ollama-min-width", type=int, default=1000, help="upscale narrower crops to this width")
    ap.add_argument("--psm", type=int, default=4)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None, help="write the JSON results here as well")
    ap.add_argument("--summary-only", action="store_true", help="omit per-sample rows from stdout")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    if args.ollama_model is None:
        from radbrain import config
        args.ollama_model = config.models().vision
    res = run(args)
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    shown = res if not args.summary_only else {**res, "backends": {
        k: {kk: vv for kk, vv in v.items() if kk != "samples"} for k, v in res["backends"].items()}}
    print(json.dumps(shown, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
