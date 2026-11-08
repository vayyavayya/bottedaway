"""Modality, region and the ~40-entity pathology checklist (Phase 6), with the rules used for auto-tagging.

Tagging is rules first (fast, deterministic, testable); the local LLM is only asked when the rules find no
modality/region (radbrain.sections.tag(..., llm=True)).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MODALITIES = ("Röntgen", "CT", "MRT", "Angio")

_MOD_RULES: list[tuple[str, re.Pattern]] = [
    ("Angio", re.compile(r"\b(DSA|Angiographie|Angiografie|Katheterangiographie|PTA|Stent(implantation|einlage)|"
                         r"Embolisation|digitale Subtraktions)", re.I)),
    ("MRT", re.compile(r"\b(MRT|MR[- ]|MRI\b|Magnetresonanz|Kernspin|T1w?|T2w?|STIR|FLAIR|DWI|ADC|TOF|Gadolinium|Gd\b)",
                       re.I)),
    ("CT", re.compile(r"\b(CT|Computertomogra|CTA\b|Angio-?CT|HU\b|Hounsfield|Spiral-?CT|Multislice|MSCT|cCT|CCT|"
                      r"Low-?dose|Kontrastmittelphase|portalvenös|arteriell(e|en)? Phase)", re.I)),
    ("Röntgen", re.compile(r"\b(Röntgen|Rö\.?|Thorax (p\.?a\.?|a\.?p\.?|in 2 Ebenen|liegend)|in (zwei|2) Ebenen|"
                           r"Aufnahme|Übersichtsaufnahme|Liegendaufnahme|seitlich|konventionell)", re.I)),
]

REGIONS = ("Thorax", "Abdomen", "Becken", "Schädel", "Wirbelsäule", "Schulter", "Ellenbogen", "Hand", "Hüfte",
           "Knie", "Sprunggelenk/Fuß", "Gefäße")

_REGION_RULES: list[tuple[str, re.Pattern]] = [
    ("Gefäße", re.compile(r"\b(Aorta|Aorten|Becken-?Bein|A\. (femoralis|poplitea|iliaca|carotis|renalis)|Karotis|"
                          r"Carotis|Arteria|Stenose|Verschluss|Dissektion|Aneurysma|CTA|DSA)", re.I)),
    ("Schädel", re.compile(r"\b(Schädel|Kopf|cCT|CCT|cMRT|Hirn|zerebral|cerebral|intrakraniell|Ventrikel|ICB|SAB|"
                           r"Kalotte|Mittellinie|Stammganglien|Kleinhirn|Sella|NNH|Nasennebenhöhle)", re.I)),
    ("Wirbelsäule", re.compile(r"\b(HWS|BWS|LWS|Wirbelsäule|HWK|BWK|LWK|SWK|Bandscheibe|Spinalkanal|Neuroforam|"
                               r"Myelon|Spondyl|Facetten|Os sacrum|ISG)", re.I)),
    ("Schulter", re.compile(r"\b(Schulter|Humeruskopf|Glenoid|Rotatorenmanschette|Supraspinatus|AC-Gelenk|"
                            r"Akromion|Acromion|Labrum|Bankart|Hill-Sachs|Clavicula|Klavikula)", re.I)),
    ("Ellenbogen", re.compile(r"\b(Ellenbogen|Olecranon|Olekranon|Radiusköpfchen|Capitulum|Monteggia)", re.I)),
    ("Hand", re.compile(r"\b(Hand|Handgelenk|Skaphoid|Scaphoid|Kahnbein|Metakarpal|Fingers?|distale[rn]? Radius|"
                        r"Radius(fraktur)?|Ulna|Karpal|Colles|Smith-Fraktur)", re.I)),
    ("Hüfte", re.compile(r"\b(Hüfte|Hüftgelenk|Schenkelhals|Femurkopf|pertrochantär|Acetabulum|Azetabulum|Coxarthrose|"
                         r"Hüft-TEP)", re.I)),
    ("Knie", re.compile(r"\b(Knie|Meniskus|Menisken|Kreuzband|VKB|HKB|Patella|Tibiaplateau|Femurkondyle|Gonarthrose|"
                        r"Innenband|Außenband)", re.I)),
    ("Sprunggelenk/Fuß", re.compile(r"\b(Sprunggelenk|OSG|USG|Malleolus|Weber|Fuß|Calcaneus|Kalkaneus|Achillessehne|"
                                    r"Metatarsal|Lisfranc|Talus)", re.I)),
    ("Becken", re.compile(r"\b(Becken|Os pubis|Schambein|Sitzbein|Iliosakral|Symphyse|Os ilium|Beckenring)", re.I)),
    ("Abdomen", re.compile(r"\b(Abdomen|Leber|Milz|Pankreas|Niere|Nieren|Gallenblase|Darm|Kolon|Colon|Dünndarm|Ileus|"
                           r"Appendix|Appendizitis|Divertik|Harnleiter|Ureter|Aszites|freie Luft|Retroperitoneum|"
                           r"Magen|Cholezyst|Nephrolith|Urolith)", re.I)),
    ("Thorax", re.compile(r"\b(Thorax|Lunge|Lungen|pulmonal|Pleura|Pneumo|Mediastinum|Herz|kardial|Infiltrat|"
                          r"Rundherd|Hili?|Zwerchfell|Rippe|Sinus phrenicocostalis|Lungenembolie|Stauung)", re.I)),
]


@dataclass(frozen=True)
class Entity:
    key: str
    label: str
    modalities: tuple[str, ...]
    region: str
    pattern: re.Pattern


def _e(key, label, mods, region, rx):
    return Entity(key, label, tuple(mods), region, re.compile(rx, re.I))


R, C, M, A = "Röntgen", "CT", "MRT", "Angio"
ENTITIES: list[Entity] = [
    _e("pneumonie", "Pneumonie", (R, C), "Thorax", r"pneumoni|infiltrat|konsolidierung"),
    _e("pleuraerguss", "Pleuraerguss", (R, C), "Thorax", r"pleuraergu|ergüsse|ergussbildung|erguss\b"),
    _e("pneumothorax", "Pneumothorax", (R, C), "Thorax", r"pneumothorax|\bPTX\b"),
    _e("lungenembolie", "Lungenembolie", (C,), "Thorax", r"lungenarterienembol|lungenembol|\bLAE\b|\bLE\b|"
                                                           r"füllungsdefekt"),
    _e("rundherd", "Rundherd/Nodulus", (R, C), "Thorax", r"rundherd|nodul|noduli|fleischner"),
    _e("stauung", "Herzinsuffizienz/Stauung", (R, C), "Thorax", r"stauung|kardiomegal|herzinsuff|kerley|"
                                                                r"interstitielle[sn]? ödem"),
    _e("rippenfraktur", "Rippenfraktur", (R, C), "Thorax", r"rippenfraktur|rippen(serien)?fraktur"),
    _e("icb", "ICB", (C, M), "Schädel", r"\bICB\b|intrazerebrale[rn]? blutung|parenchymblutung|hämatom.{0,20}"
                                       r"(intrazerebral|parenchym)"),
    _e("sab", "SAB", (C, M), "Schädel", r"\bSAB\b|subarachnoidal"),
    _e("sdh", "Subdurales Hämatom", (C, M), "Schädel", r"subdural|\bSDH\b|epidural|\bEDH\b"),
    _e("ischaemie", "Ischämie/Infarkt", (C, M), "Schädel", r"isch(ä|ae)mie|infarkt|diffusionsrestrik|"
                                                            r"demarkier|early sign"),
    _e("schaedelfraktur", "Schädel-/Gesichtsfraktur", (R, C), "Schädel", r"kalottenfraktur|schädelfraktur|"
                                                                          r"mittelgesichtsfraktur|orbitabodenfraktur"),
    _e("ileus", "Ileus", (R, C), "Abdomen", r"\bileus|spiegelbildung|dilatierte.{0,30}darmschlingen|kalibersprung"),
    _e("appendizitis", "Appendizitis", (C,), "Abdomen", r"appendizitis|appendicitis"),
    _e("divertikulitis", "Divertikulitis", (C,), "Abdomen", r"divertikulitis"),
    _e("freie_luft", "Freie Luft/Perforation", (R, C), "Abdomen", r"freie (intraabdominelle |abdominelle )?luft|"
                                                                   r"pneumoperitoneum|perforation"),
    _e("cholezystitis", "Cholezystitis", (C,), "Abdomen", r"cholezystitis|cholecystitis"),
    _e("nierenstein", "Nieren-/Harnleiterstein", (C,), "Abdomen", r"nephrolith|urolith|harnleiterstein|"
                                                                  r"nierenstein|konkrement"),
    _e("pankreatitis", "Pankreatitis", (C,), "Abdomen", r"pankreatitis"),
    _e("leberlaesion", "Leberläsion", (C, M), "Abdomen", r"leberläsion|leberherd|hämangiom|leberzyste|\bHCC\b"),
    _e("aszites", "Aszites", (C,), "Abdomen", r"aszites"),
    _e("aortenaneurysma", "Aortenaneurysma", (C, A), "Gefäße", r"aortenaneurysma|\bAAA\b|aneurysma"),
    _e("dissektion", "Aortendissektion", (C,), "Gefäße", r"dissektion|dissekat|intimaflap|stanford"),
    _e("stenose", "Stenose/Verschluss", (C, A), "Gefäße", r"stenose|verschluss|okklusion|\bpAVK\b"),
    _e("bandscheibe", "Bandscheibenvorfall", (M, C), "Wirbelsäule", r"bandscheibenvorfall|bandscheibenprotrusion|"
                                                                    r"prolaps|protrusion|sequester|\bBSV\b"),
    _e("wirbelfraktur", "Wirbelkörperfraktur", (R, C, M), "Wirbelsäule", r"(wirbelkörper|deckplatten|grundplatten|"
                                                                         r"BWK.{0,8}|LWK.{0,8}|HWK.{0,8})"
                                                                         r"(fraktur|impression|sinterung)|"
                                                                         r"sinterungsfraktur"),
    _e("spinalkanalstenose", "Spinalkanalstenose", (M, C), "Wirbelsäule", r"spinalkanalstenose|"
                                                                           r"neuroforam.{0,20}(stenose|einengung)"),
    _e("meniskus", "Meniskusläsion", (M,), "Knie", r"meniskus|menisken|korbhenkel"),
    _e("kreuzband", "Kreuzbandruptur", (M,), "Knie", r"kreuzband|\bVKB\b|\bHKB\b"),
    _e("rotatorenmanschette", "Rotatorenmanschette", (M,), "Schulter", r"rotatorenmanschette|supraspinatus|"
                                                                        r"infraspinatus"),
    _e("schulterluxation", "Schulterluxation", (R, M), "Schulter", r"(schulter|humerus).{0,20}luxation|"
                                                                    r"bankart|hill-sachs"),
    _e("luxation", "Luxation (sonst.)", (R, C), "", r"luxation"),
    _e("radiusfraktur", "Distale Radiusfraktur", (R, C), "Hand", r"radiusfraktur|distale[rn]? radius|colles|"
                                                                 r"smith-fraktur"),
    _e("skaphoid", "Skaphoidfraktur", (R, C, M), "Hand", r"skaphoid|scaphoid|kahnbein"),
    _e("schenkelhals", "Schenkelhals-/proximale Femurfraktur", (R, C), "Hüfte", r"schenkelhals|pertrochantär|"
                                                                                r"femurfraktur|garden"),
    _e("osg", "Sprunggelenksfraktur", (R, C), "Sprunggelenk/Fuß", r"weber|malleolarfraktur|sprunggelenksfraktur|"
                                                                  r"außenknöchel|innenknöchel"),
    _e("beckenfraktur", "Beckenfraktur", (R, C), "Becken", r"beckenfraktur|beckenring|schambeinast|"
                                                           r"acetabulumfraktur|azetabulumfraktur"),
    _e("metastasen", "Metastasen", (C, M), "", r"metasta|filiae|filia\b"),
    _e("arthrose", "Arthrose/degenerativ", (R, M), "", r"arthrose|osteochondrose|spondylose|degenerativ"),
    _e("normal_roe", "Normalbefund Röntgen", (R,), "", r"$^"),
    _e("normal_ct", "Normalbefund CT", (C,), "", r"$^"),
    _e("normal_mrt", "Normalbefund MRT", (M,), "", r"$^"),
    _e("normal_angio", "Normalbefund Angio", (A,), "", r"$^"),
]
BY_KEY = {e.key: e for e in ENTITIES}
NORMAL_KEY = {R: "normal_roe", C: "normal_ct", M: "normal_mrt", A: "normal_angio"}

# a finding is "negated" when it is only mentioned to be excluded
_NEG = re.compile(r"\b(kein(e[nmrs]?)?|ohne|ausschluss( einer| eines)?|kein (sicherer |direkter )?(nachweis|anhalt)"
                  r"( für| auf)?( eine[nrs]?)?)\b[^.;,\n]{0,40}$", re.I)
_NEG_AFTER = re.compile(r"^[^.;\n]{0,40}\b(nicht (nachweisbar|abgrenzbar|sicher abgrenzbar|erkennbar|darstellbar)|"
                        r"ausgeschlossen|auszuschließen)\b", re.I)


def modality(text: str) -> str | None:
    head = text[:400]
    for name, rx in _MOD_RULES:          # the exam title in the first lines decides when present
        if rx.search(head):
            return name
    for name, rx in _MOD_RULES:
        if rx.search(text):
            return name
    return None


def region(text: str) -> str | None:
    head = text[:400]
    scores: dict[str, int] = {}
    for name, rx in _REGION_RULES:
        n = len(rx.findall(text)) + 3 * len(rx.findall(head))
        if n:
            scores[name] = n
    return max(scores, key=scores.get) if scores else None


def pathologies(beurteilung: str, befund: str = "", mod: str | None = None) -> list[str]:
    """Entities asserted (not negated) in the Beurteilung, falling back to the Befund. Normal → per-modality normal."""
    found: list[str] = []
    src = beurteilung or befund
    for sent in re.split(r"(?<=[.;\n])\s+|\n", src):
        for e in ENTITIES:
            m = e.pattern.search(sent)
            if m and not _NEG.search(sent[:m.start()]) and not _NEG_AFTER.search(sent[m.end():]):
                if e.key not in found:
                    found.append(e.key)
    if not found and mod in NORMAL_KEY:
        found.append(NORMAL_KEY[mod])
    return found


def label(key: str) -> str:
    e = BY_KEY.get(key)
    return e.label if e else key
