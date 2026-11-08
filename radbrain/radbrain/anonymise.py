"""Phase 3 — the anonymiser. Fails closed.

Pipeline for one OCR'd/copied report text:
  1. structure: everything before the first section heading (the PACS header with name, DOB, PID, exam date …) is
     dropped; only Fragestellung / Technik / Befund / Beurteilung bodies are kept. Signature lines are parsed for the
     signer (→ B1/B2/B3 via signers.json) and dropped. No heading at all → quarantine.
  2. scrub: signers.json names → their code ([B1] …, Ajit → [AA], staff → [NAME]); IDs, birth dates, dates
     (→ [DATUM], so "Voruntersuchung vom [DATUM]" keeps its meaning), years, times, phone numbers, addresses, ages,
     wards, titled names (Dr./Prof./OA/Herr/Frau …), "Nachname, Vorname", DICOM "NAME^VORNAME", first+last names,
     names in communication sentences ("telefonisch an … mitgeteilt"), listed surnames.
  3. residual check on the scrubbed text: any date/time/long number left, any listed name left, any capitalised or
     ALL-CAPS token the lexicon cannot explain → NOT ok → the caller quarantines the capture.
The lexicon = German word frequencies (wordfreq) + compound splitting + eponym list + abbreviations + the local
allowlist (data dir, grows when Ajit releases a quarantined capture). Medical eponyms (Morbus Crohn, Bankart,
Hill-Sachs, Monteggia, Weber B …) are protected.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import config
from .names import AMBIGUOUS, EPONYMS, FIRST_NAMES, SURNAMES, TITLES

SECTION_ALIASES = {
    "fragestellung": ("fragestellung", "klinische angaben", "klinische angabe", "klinik", "indikation",
                      "rechtfertigende indikation", "anamnese", "klinische fragestellung", "fragestellung/klinik"),
    "technik": ("technik", "untersuchungstechnik", "methode", "methodik", "vergleich", "voruntersuchung",
                "voruntersuchungen", "voraufnahmen", "kontrastmittel"),
    "befund": ("befund", "befunde", "befundbeschreibung"),
    "beurteilung": ("beurteilung", "zusammenfassung", "impression", "empfehlung", "procedere"),
}
_ALIAS = {a: k for k, v in SECTION_ALIASES.items() for a in v}
_HEADING = re.compile(r"^\s*(" + "|".join(sorted((re.escape(a) for a in _ALIAS), key=len, reverse=True)) +
                      r")\s*(?::|\s*$)\s*(.*)$", re.I)
EXAM_LINE = re.compile(r"^\s*(untersuchung|leistung|exam|untersuchungsart|anforderung|modalität)\s*[:]\s*(.+)$", re.I)
SIGNATURE = re.compile(r"(signiert|freigegeben|unterschrieben|vidiert|validiert|befundet\s+(von|durch)|befunder|"
                       r"diktiert|geschrieben\s+(von|durch)|erstellt\s+(von|durch)|vorläufiger befund|"
                       r"mit freundlichen|mit kollegialen|\bmfg\b|\bgez\.|\bi\.\s?a\.|^\s*entwurf\s*(von|durch)?\s*:|"
                       r"^\s*(befundender|befundende|assistenzarzt|assistenzärztin|oberarzt|oberärztin|chefarzt|"
                       r"chefärztin)\s*:)", re.I)
ROLE_ONLY = re.compile(r"^\s*(Prof\.?|Dr\.?|med\.?|PD|\s)*\s*[\wÄÖÜäöüß.\- ]{0,60}\s*[,(]?\s*"
                       r"(Chefarzt|Chefärztin|Oberarzt|Oberärztin|Leitender Oberarzt|Leitende Oberärztin|"
                       r"Facharzt|Fachärztin|Assistenzarzt|Assistenzärztin|Arzt|Ärztin)\)?\s*$", re.I)
TITLE_NAME_LINE = re.compile(r"^\s*((Prof\.|Dr\.|med\.|PD|Priv\.-Doz\.)\s*)+[A-ZÄÖÜ][\wäöüß'-]+(\s+[A-ZÄÖÜ][\wäöüß'-]+)?"
                             r"\s*$")

PLACEHOLDER = re.compile(r"\[(?:B1|B2|B3|AA|NAME|ARZT|ID|GEBURTSDATUM|DATUM|JAHR|ZEIT|TEL|ADRESSE|ALTER|STATION)\]")

MONTHS = r"(Januar|Jänner|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|" \
         r"Jan\.?|Feb\.?|Febr\.?|Mär\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Sept\.?|Okt\.?|Nov\.?|Dez\.?)"
DATE_RX = [
    re.compile(r"(?<![\d.])\d{1,2}\.\s?\d{1,2}\.\s?(\d{4}|\d{2})(?![\d])"),
    re.compile(r"(?<!\d)\d{4}-\d{1,2}-\d{1,2}(?!\d)"),
    re.compile(r"(?<!\d)\d{1,2}/\d{1,2}/(\d{4}|\d{2})(?!\d)"),
    re.compile(r"(?<![\w.])\d{1,2}\.\s?" + MONTHS + r"(\s+\d{2,4})?(?!\w)", re.I),
    re.compile(r"(?<!\w)" + MONTHS + r"\s+\d{4}(?!\d)", re.I),
    re.compile(r"(?<!\d)(0?[1-9]|1[0-2])/(19|20)\d{2}(?!\d)"),
    re.compile(r"(?<=\bvom\s)\d{1,2}\.\d{1,2}\.(?!\d)", re.I),
    re.compile(r"(?<=\bam\s)\d{1,2}\.\d{1,2}\.(?!\d)", re.I),
    re.compile(r"(?<!\d)\d{1,2}\.\d{1,2}\.(?=\s|$|,|;|\))"),
]
YEAR = re.compile(r"(?<![\d.,/-])(19[3-9]\d|20[0-4]\d)(?![\d.,]\d|\s?(mm|cm|ml|HU|mGy|mSv|mg|%))")
TIME_RX = [re.compile(r"(?<![\d.])([01]?\d|2[0-3]):[0-5]\d(:[0-5]\d)?(\s?Uhr|\s?h\b)?"),
           re.compile(r"(?<![\d.])([01]?\d|2[0-3])\.[0-5]\d\s?Uhr"),
           re.compile(r"(?<![\d.])([01]?\d|2[0-3])\s?Uhr(?!\w)")]
ID_LABEL = re.compile(r"\b(PID|Pat\.?\s?-?\s?(Nr|ID)\.?|Patienten-?(nummer|nr\.?|id)|Fall-?\s?(Nr|Nummer)\.?|Fallnummer|"
                      r"Auftrags?-?\s?(Nr|Nummer)\.?|Auftragsnummer|Aufnahme-?\s?(Nr|Nummer)\.?|Accession(\s?No\.?)?|"
                      r"Acc\.?-?\s?Nr\.?|Untersuchungs-?\s?(Nr|Nummer)\.?|Befund-?\s?(Nr|Nummer)\.?|Episoden?-?\s?Nr\.?|"
                      r"Barcode|Versichertennummer|Vers\.-?Nr\.?|KV-?Nr\.?|ID|Akten-?\s?(Nr|zeichen)\.?)"
                      r"\s*[:#.]?\s*[A-Z]{0,4}[-/]?\d[\w/-]*", re.I)
DOB = re.compile(r"\b(geb\.?|geboren(\s+am)?|Geburtsdatum|Geb\.-?Datum|Geb\.?\s?Dat\.?|DOB|\*)\s*[:.]?\s*"
                 r"(\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\.\s?" + MONTHS + r"\s+\d{4})", re.I)
DOB_YEAR = re.compile(r"\b(geb\.?|geboren|Jahrgang|Jg\.)\s*(\d{4})\b", re.I)
PHONE = re.compile(r"(\b(Tel(efon)?|Fax|Durchwahl|DW|Piepser|Pieper|Funk|Mobil|Handy|App\.)\.?\s*[:.]?\s*"
                   r"[+(]?\d[\d\s/()-]{1,18}\d|\+\d{2}[\d\s/()-]{6,18}\d|(?<![\d.])0\d{2,5}[\s/-]\d{2,}[\d\s-]{0,10}\d)",
                   re.I)
STREET = re.compile(r"\b[A-ZÄÖÜ][\wäöüß.-]*(straße|strasse|str\.|weg|gasse|platz|allee|ring|damm|ufer|steige|"
                    r"steig|chaussee)\s*\d+\s?[a-z]?\b", re.I)
POSTCODE = re.compile(r"(?<!\d)\d{5}\s+[A-ZÄÖÜ][a-zäöüß]{2,}(?:[-\s][A-ZÄÖÜ][a-zäöüß]+)*")
AGE_RX = [re.compile(r"(?<![\d.,])\d{1,3}(?=\s?-?\s?jährig)", re.I),
          re.compile(r"(?<![\d.,])\d{1,3}(?=\s?Jahre?\s+alt)", re.I),
          re.compile(r"(?<=Alter)(?P<pre>\s*[:.]?\s*(?:von\s)?)\d{1,3}", re.I),
          re.compile(r"(?<![\d.,])\d{2,3}(?=\s?J\.(?!\w))"),
          re.compile(r"(?<![\d.,])\d{2,3}(?=\s?(?:LJ|Lj\.?|y/?o|yo|years? old)\b)", re.I),
          re.compile(r"(?<=\b[mwdMWD]),?\s?\d{2,3}(?=\b)"),
          re.compile(r"(?<=im\s)\d{1,3}\.(?=\s?Lebensjahr)", re.I)]
WARD = re.compile(r"\b(Station|Stat\.|Intensivstation|Normalstation|Wachstation|Ambulanz)\s+(?!(?:und|oder|mit|bei|"
                  r"ist|wurde|der|die|das|zur|zum)\b)[\wÄÖÜäöüß]{1,14}\b")
LONG_NUMBER = re.compile(r"(?<![\d.,])\d{5,}(?![\d.,]?\d)")
UP = r"[A-ZÀ-ÖØ-ÞĀ-ŽŞİ]"
LET = r"[^\W\d_]"
CAP = UP + r"[a-zß-öø-ÿā-žşığ]" + LET + r"*(?:[-'’]" + UP + LET + r"+)?"
CAPS_WORD = UP + r"{2,}(?:[-'’]" + UP + r"{2,})?"
TITLE_NAME = re.compile(r"\b(" + TITLES + r")(\s*(" + TITLES + r"))*\s+((?:[A-Z]\.\s?)?(" + CAP + "|" + CAPS_WORD + r")"
                        r"(\s+(" + CAP + "|" + CAPS_WORD + r"))?(\s+(" + CAP + "|" + CAPS_WORD + r"))?)")
SURNAME_COMMA = re.compile(r"\b(" + CAP + "|" + CAPS_WORD + r"),\s*(" + CAP + r")\b")
DICOM = re.compile(r"\b[A-ZÄÖÜ][\wÄÖÜäöüß'-]*\^[A-ZÄÖÜ][\wÄÖÜäöüß'-]*(\^[\w'-]*)*")
COMM = re.compile(r"(mitgeteilt|besprochen|informiert|rücksprache|telefonisch|übermittelt|benachrichtigt|"
                  r"weitergeleitet|demonstriert|übergeben|kommuniziert|durchgesagt|zuweise|zuweisend|überweise|"
                  r"angefordert|veranlasst|anwesend|in absprache|nach absprache|auf wunsch)", re.I)
PREP_NAME = re.compile(r"\b(an|mit|von|durch|bei|via|für|zu|den|dem|der|die|Kollegen|Kollegin|Kollege|Herrn|"
                       r"Frau|Herr)\s+(" + CAP + "|" + CAPS_WORD + r")(\s+(" + CAP + "|" + CAPS_WORD + r"))?")
TOKEN = re.compile(r"[^\W\d_][\w'’-]*")
ROLE_NOUNS = {"Station", "Stationsarzt", "Stationsärztin", "Kollege", "Kollegin", "Kollegen", "Zuweiser", "Zuweiserin",
              "Hausarzt", "Hausärztin", "Patient", "Patientin", "Angehörigen", "Angehörige", "Arzt", "Ärztin", "Ärzten",
              "Chirurgie", "Unfallchirurgie", "Neurochirurgie", "Gefäßchirurgie", "Viszeralchirurgie", "Notaufnahme",
              "ZNA", "Intensivstation", "Dienstarzt", "Dienstärztin", "Diensthabenden", "Diensthabende", "Oberarzt",
              "Oberärztin", "Chefarzt", "Chefärztin", "Klinik", "Kardiologie", "Neurologie", "Innere", "Onkologie",
              "Urologie", "Gynäkologie", "Pädiatrie", "Anästhesie", "Pflege", "Team", "Schockraum", "Schockraumteam",
              "Klinikum", "Abteilung", "Ambulanz", "Sekretariat", "Telefon", "Funk", "Pieper", "Einverständnis",
              "Anforderer", "Anfordernden", "Behandlern", "Behandler", "Kollegium", "Intensivmedizin", "Radiologie",
              "Nuklearmedizin", "Strahlentherapie", "Tumorboard", "Konferenz", "Visite", "Befund", "Befunde", "Bild",
              "Bilder", "Aufnahmen", "Untersuchung", "Patienten"}
ROMAN = re.compile(r"^[IVX]{1,5}°?$")
MED_SUFFIX = re.compile(r"(ion|ionen|itis|itiden|ose|osen|om|ome|omen|ie|ien|ung|ungen|ismus|ase|asen|ität|aler|ale|"
                        r"alen|ales|ös|öse|ösen|öser|iv|ive|iven|iver|ektomie|plastik|graphie|grafie|skopie|pathie|"
                        r"algie|ämie|urie|zele|thorax|trauma|schmerz|schmerzen|schwäche|befund|zeichen|ödem|tomie|"
                        r"logie|gramm|plasie|trophie|ektasie|stenose|sklerose|ruptur|fraktur|läsion|blutung|"
                        r"erguss|infarkt|aneurysma|ulkus|phyt|phyten|kel|keln|oid|oide|oids|ikus|icus|alis|aris|"
                        r"ius|ium|ia|us|um)$")
INFLECT = ("", "s", "es", "n", "en", "e", "er", "em", "ern", "ns")

ABBREV = set("""
CT MRT MR KM HU ED DD Z.n. V.a. DSA CTA MRA TOF DWI ADC FLAIR STIR T1 T2 PD SWI GRE TSE TIRM VIBE HASTE MIP MPR VRT
AP PA LAO RAO LWK BWK HWK SWK LWS BWS HWS ISG OSG USG ACG AC TEP HTEP KTEP DHS PFNA PFN VKB HKB ZVK PICC ICD SM PM
EKG COPD TBC CUP NSCLC SCLC HCC CCC RCC AML FNH IPMN PDAC LK LKs LAE AAA PTA PTX SAB ICB SDH EDH NNH ZNS GI KHK
pAVK AVK VSD ASD PFO LV RV LA RA LVEF EF NYHA BMI ASA GFR CRP PCT INR PTT KG HB HK MCV CEA PSA AFP BNP HWZ OP OPs
ITS IMC ZNA NA RTW NEF ICU ER US MRCP ERCP PTCD TIPS TACE TARE SIRT RFA MWA CTO PET SPECT FDG PSMA DOTATATE CEUS
CS CW RC SSP ISP SSC TM RM IS AS MS VS HS BS LS IVC SVC VCI VCS AMS AMI TC TSA ACI ACE ACC ACM ACA ACP VA BA AICA
PICA SCA MCA ICA PCA ACoA PCoA LIMA RIMA ACVB PCI TAVI MKE AKE TKE MVR AVR LMCA LAD RCX RCA PDA RIVA RCX RIVP
ALL PLL LCL MCL MPFL VKB ACL PCL TFCC SL LT DRUG PRUG ECU FCU FCR ECRB ECRL EPL APL EDC FDS FDP ROI ROIs SUV
BI-RADS PI-RADS LI-RADS TI-RADS Lung-RADS O-RADS Bosniak TNM ECOG RECIST mRECIST iRECIST WHO AO OTA ASIF GCS NIHSS
ASPECTS mRS TICI CBF CBV MTT TTP Tmax DSC DCE ASL BOLD fMRT DTI NMR KMA KM-Aufnahme li re bds re. li. bds.
HNO MKG ORL NCT CCT cCT cMRT CTP CTPA LE TVT VTE ST SA CA AD
""".split())


@lru_cache(maxsize=1)
def _words() -> frozenset[str]:
    try:
        from wordfreq import top_n_list
        return frozenset(top_n_list("de", 200000))
    except Exception:  # noqa: BLE001
        return frozenset()


@lru_cache(maxsize=1)
def _medical() -> frozenset[str]:
    p = Path(__file__).with_name("lexicon_med.txt")
    words = set()
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                words.update(w.lower() for w in line.split())
    return frozenset(words)


@lru_cache(maxsize=50000)
def _zipf(token: str) -> float:
    try:
        from wordfreq import zipf_frequency
        return zipf_frequency(token, "de")
    except Exception:  # noqa: BLE001
        return 0.0


def _allowlist_path() -> Path:
    return config.data_dir() / "allowlist.txt"


def allowlist() -> frozenset[str]:
    p = _allowlist_path()
    if not p.exists():
        return frozenset()
    return frozenset(w.strip().lower() for w in p.read_text(encoding="utf-8").split() if w.strip())


def add_to_allowlist(tokens) -> None:
    """Called when Ajit releases a quarantined capture: the unknown words he cleared become known (local only)."""
    cur = set(allowlist())
    new = {t.lower() for t in tokens if t and t.lower() not in cur}
    if new:
        with _allowlist_path().open("a", encoding="utf-8") as f:
            for t in sorted(new):
                f.write(t + "\n")


_LINK = ("", "s", "es", "n", "en", "e", "er", "ns")
_NAMES_LOWER = frozenset(n.lower() for n in (SURNAMES | FIRST_NAMES) - AMBIGUOUS - EPONYMS)


def _known_part(w: str) -> bool:
    w = w.casefold()
    if len(w) < 3:
        return False
    if w in _medical():
        return True
    if w in _NAMES_LOWER:
        return False
    return (len(w) >= 4 and w in _words()) or (len(w) >= 6 and bool(MED_SUFFIX.search(w)))


@lru_cache(maxsize=50000)
def _compound(w: str, depth: int = 0) -> bool:
    """True when w splits into known German/medical parts (Lungenembolie = Lungen+Embolie)."""
    if _known_part(w):
        return True
    if depth >= 3 or len(w) < 7:
        return False
    for i in range(3, len(w) - 2):
        head = w[:i]
        for link in _LINK:
            if link and not head.endswith(link):
                continue
            base = head[: len(head) - len(link)] if link else head
            if _known_part(base) or (len(base) >= 3 and base in _medical()):
                if _compound(w[i:], depth + 1):
                    return True
    return False


def known(token: str) -> bool:
    t = token.strip("-'’")
    if not t or any(ch.isdigit() for ch in t) or ROMAN.match(t) or (len(t) <= 2 and t not in SURNAMES):
        return True
    if t in EPONYMS or t in ABBREV or t.upper() in ABBREV:
        return True
    low = t.lower()
    if low in allowlist() or low in _medical():
        return True
    if "-" in t:
        return all(known(p) for p in t.split("-") if p)
    if t.isupper() and len(t) >= 2:
        return low in _words() and len(t) >= 6 and low not in _NAMES_LOWER   # long caps words: GROSS etc.
    if low in _NAMES_LOWER:
        return False
    return _known_word(low)


@lru_cache(maxsize=100000)
def _known_word(low: str) -> bool:
    low = low.casefold()
    for suf in INFLECT:
        if suf and not low.endswith(suf):
            continue
        base = low[: len(low) - len(suf)] if suf else low
        if len(base) < 3:
            continue
        if base in _medical() or base in _words() or _compound(base):
            return True
    return len(low) >= 7 and bool(MED_SUFFIX.search(low))


def _is_name_token(tok: str) -> bool:
    if tok in EPONYMS:
        return False
    return (tok in SURNAMES or tok in FIRST_NAMES) and tok not in AMBIGUOUS


# ----------------------------------------------------------------------------------------------- structure
@dataclass
class Parsed:
    header: list[str] = field(default_factory=list)
    sections: dict[str, list[str]] = field(default_factory=dict)
    signature: list[str] = field(default_factory=list)
    exam: str = ""
    had_heading: bool = False


def _normalise(raw: str) -> str:
    s = unicodedata.normalize("NFC", raw or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ").replace("​", "")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def parse(raw: str) -> Parsed:
    p = Parsed()
    cur: str | None = None
    for line in _normalise(raw).split("\n"):
        st = line.strip()
        if not st:
            if cur:
                p.sections.setdefault(cur, []).append("")
            continue
        m = _HEADING.match(st)
        if m:
            cur = _ALIAS[m.group(1).lower()]
            p.had_heading = True
            p.sections.setdefault(cur, [])
            if m.group(2).strip():
                p.sections[cur].append(m.group(2).strip())
            continue
        if SIGNATURE.search(st) or ROLE_ONLY.match(st) or (cur and TITLE_NAME_LINE.match(st)):
            p.signature.append(st)
            continue
        if cur is None:
            p.header.append(st)
            em = EXAM_LINE.match(st)
            if em and not p.exam:
                p.exam = em.group(2).strip()
            continue
        p.sections[cur].append(st)
    if not p.exam:   # a header line that names a modality (e.g. "CT Thorax mit KM")
        for h in p.header:
            if re.search(r"\b(CT|MRT|MR|Röntgen|Rö|DSA|Angiographie|Thorax p\.a\.|cCT|CTA)\b", h) and len(h) < 90:
                p.exam = h
                break
    return p


# ----------------------------------------------------------------------------------------------- scrub
def _signer_rx(names: list[str]) -> re.Pattern | None:
    names = sorted({n.strip() for n in names if n and len(n.strip()) >= 2}, key=len, reverse=True)
    if not names:
        return None
    return re.compile(r"(?<![\wÄÖÜäöüß])(" + "|".join(re.escape(n) for n in names) + r")(?![\wÄÖÜäöüß])", re.I)


def find_signer(lines: list[str], sig: config.Signers) -> str | None:
    best = None
    for code in config.CODES:
        rx = _signer_rx(sig.by_code.get(code, []))
        if not rx:
            continue
        for ln in lines:
            if rx.search(ln):
                strong = bool(re.search(r"signiert|freigegeben|vidiert|validiert|unterschrieben", ln, re.I))
                if strong:
                    return code
                best = best or code
    return best


def is_mine(lines: list[str], sig: config.Signers) -> bool:
    rx = _signer_rx(sig.me)
    return bool(rx and any(rx.search(ln) for ln in lines))


def scrub(text: str, sig: config.Signers | None = None, counts: Counter | None = None) -> str:
    sig = sig or config.signers()
    c = counts if counts is not None else Counter()

    def sub(rx, repl, s, kind):
        def f(m):
            c[kind] += 1
            return repl(m) if callable(repl) else repl
        return rx.sub(f, s)

    s = text
    for code in config.CODES:
        rx = _signer_rx(sig.by_code.get(code, []))
        if rx:
            s = sub(rx, f"[{code}]", s, "signer")
    rx = _signer_rx(sig.me)
    if rx:
        s = sub(rx, "[AA]", s, "me")
    rx = _signer_rx(sig.staff)
    if rx:
        s = sub(rx, "[NAME]", s, "staff")
    s = sub(DICOM, "[NAME]", s, "name")
    s = sub(DOB, "[GEBURTSDATUM]", s, "dob")
    s = sub(DOB_YEAR, lambda m: m.group(1) + " [JAHR]", s, "dob")
    s = sub(ID_LABEL, "[ID]", s, "id")
    s = sub(PHONE, "[TEL]", s, "phone")
    s = sub(STREET, "[ADRESSE]", s, "address")
    s = sub(POSTCODE, "[ADRESSE]", s, "address")
    for rx in DATE_RX:
        s = sub(rx, "[DATUM]", s, "date")
    for rx in TIME_RX:
        s = sub(rx, "[ZEIT]", s, "time")
    s = sub(YEAR, "[JAHR]", s, "year")
    for rx in AGE_RX:
        s = sub(rx, lambda m: (m.groupdict().get("pre") or "") + "[ALTER]", s, "age")
    s = sub(WARD, "[STATION]", s, "ward")
    s = sub(LONG_NUMBER, "[ID]", s, "id")

    def title(m):
        lead = m.group(1)
        names = m.group(4).split()
        keep_tail = []
        # "Patient Zustand nach": a Patient/Pat. title only takes tokens that are names or unknown words
        chain = m.group(0)[: m.start(4) - m.start(0)]
        patient_title = re.fullmatch(r"\s*((Pat\.?|Patient(in)?)\s*)+", chain, re.I)
        out = []
        for i, tok in enumerate(names):
            if re.match(r"^[A-Z]\.$", tok):
                out.append(tok)
                continue
            if patient_title or i > 0:
                if not (_is_name_token(tok) or not known(tok) or tok.isupper()):
                    keep_tail = names[i:]
                    break
            out.append(tok)
        if not out:
            return m.group(0)
        c["name"] += 1
        repl = "[ARZT]" if re.search(r"Dr|Prof|PD|OA|OÄ|CA|CÄ|arzt|ärztin|Kolleg|FA|FÄ|AA|AÄ|LOA", m.group(0)) \
            else "[NAME]"
        tail = (" " + " ".join(keep_tail)) if keep_tail else ""
        if patient_title:
            return chain + "[NAME]" + tail
        pat = re.match(r"\s*((Pat\.?|Patient(in)?)\s+)", chain, re.I)   # "Patientin Frau X" -> "Patientin [NAME]"
        return (pat.group(1) if pat else "") + repl + tail
    s = TITLE_NAME.sub(title, s)
    s = sub(SURNAME_COMMA, lambda m: "[NAME]" if (m.group(2) in FIRST_NAMES or not known(m.group(1)))
            and m.group(1) not in EPONYMS else m.group(0), s, "name")

    def first_last(m):
        a, b = m.group(1), m.group(2)
        if a in FIRST_NAMES and a not in AMBIGUOUS and b not in EPONYMS and (not known(b) or _is_name_token(b)
                                                                               or b.isupper()):
            c["name"] += 1
            return "[NAME]"
        return m.group(0)
    s = re.sub(r"\b(" + CAP + r")\s+(" + CAP + "|" + CAPS_WORD + r")\b", first_last, s)

    # names in communication sentences: "telefonisch an Kowalczuk mitgeteilt", "Rücksprache mit Brandstetter"
    def comm_sentence(sent: str) -> str:
        if not COMM.search(sent):
            return sent

        def pn(m):
            toks = [m.group(2)] + ([m.group(4)] if m.group(4) else [])
            first_tok = toks[0]
            if first_tok in ROLE_NOUNS or first_tok in EPONYMS or first_tok.upper() in ABBREV:
                return m.group(0)
            person_prep = m.group(1) in ("an", "mit", "durch", "via", "Herrn", "Herr", "Frau", "Kollegen", "Kollegin",
                                         "Kollege")
            if person_prep:   # "Rücksprache mit Trautwein": only common words / medical terms survive
                if not _is_name_token(first_tok) and not first_tok.isupper() and (
                        first_tok.casefold() in _medical() or _zipf(first_tok) >= 3.2):
                    return m.group(0)
            elif known(first_tok) and not _is_name_token(first_tok) and not first_tok.isupper():
                return m.group(0)
            c["name"] += 1
            tail = toks[1] if len(toks) > 1 else None
            keep = (" " + tail) if tail and (tail in ROLE_NOUNS or (known(tail) and not _is_name_token(tail)
                                                                     and not tail.isupper())) else ""
            return m.group(1) + " [NAME]" + keep
        return PREP_NAME.sub(pn, sent)
    s = "".join(comm_sentence(x) for x in re.split(r"(?<=[.;!?\n])", s))

    def bare(m):
        t = m.group(0)
        if _is_name_token(t):
            c["name"] += 1
            return "[NAME]"
        return t
    s = re.sub(r"(?<![\w\[])" + CAP + r"(?![\w\]])", bare, s)
    return s


# ----------------------------------------------------------------------------------------------- residual
def residual(text: str) -> list[str]:
    """Reasons (kinds only, never the matched text) why the scrubbed text is not safe."""
    s = PLACEHOLDER.sub(" ", text)
    reasons = []
    if any(rx.search(s) for rx in DATE_RX) or YEAR.search(s):
        reasons.append("Datum übrig")
    if any(rx.search(s) for rx in TIME_RX[:2]):
        reasons.append("Uhrzeit übrig")
    if LONG_NUMBER.search(s) or re.search(r"\d{3,}[-/]\d{3,}", s):
        reasons.append("Nummer übrig")
    if DOB.search(s) or re.search(r"\bgeb(\.|oren)\b", s, re.I):
        reasons.append("Geburtsdatum-Hinweis")
    unknown, names = [], []
    for m in TOKEN.finditer(s):
        t = m.group(0)
        if not t[0].isupper():
            continue
        if _is_name_token(t):
            names.append(t)
        elif not known(t):
            unknown.append(t)
    if names:
        reasons.append("Name übrig")
    if unknown:
        reasons.append(f"unbekannte Wörter ({len(unknown)})")
    return reasons


def unknown_tokens(text: str) -> list[str]:
    s = PLACEHOLDER.sub(" ", text)
    return sorted({m.group(0) for m in TOKEN.finditer(s) if m.group(0)[0].isupper() and not known(m.group(0))
                   and not _is_name_token(m.group(0))})


# ----------------------------------------------------------------------------------------------- entry point
@dataclass
class Result:
    ok: bool
    sections: dict[str, str]
    exam: str
    signer: str | None
    author_is_me: bool
    reasons: list[str]
    counts: Counter
    signature: list[str] = field(default_factory=list)     # raw lines, memory only (signers_auto) — never stored

    @property
    def text(self) -> str:
        out = []
        for k in ("fragestellung", "technik", "befund", "beurteilung"):
            if self.sections.get(k):
                out.append(f"{k.capitalize()}:\n{self.sections[k]}")
        return "\n\n".join(out)


def anonymise(raw: str, sig: config.Signers | None = None) -> Result:
    sig = sig or config.signers()
    p = parse(raw)
    counts: Counter = Counter()
    counts["header_lines"] = len(p.header)
    reasons: list[str] = []
    if not p.had_heading or not (p.sections.get("befund") or p.sections.get("beurteilung")):
        reasons.append("keine Abschnitte (Befund/Beurteilung) erkannt")
    signer = find_signer(p.signature, sig) or find_signer(p.header, sig)
    mine = is_mine(p.signature + p.header, sig)
    sections = {}
    for k, lines in p.sections.items():
        body = "\n".join(lines).strip()
        body = re.sub(r"\n{3,}", "\n\n", body)
        sections[k] = scrub(body, sig, counts)
    exam = scrub(p.exam, sig, counts) if p.exam else ""
    for k, v in list(sections.items()) + [("exam", exam)]:
        reasons += residual(v)
    reasons = list(dict.fromkeys(reasons))
    return Result(ok=not reasons, sections=sections, exam=exam, signer=signer, author_is_me=mine, reasons=reasons,
                  counts=counts, signature=list(p.signature))
