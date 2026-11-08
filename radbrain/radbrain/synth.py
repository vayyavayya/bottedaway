"""Synthetic German radiology reports with planted FAKE identifiers — the only data used for tests and the demo.

Every report is generated here from templates; no line comes from a real report. Draft = Assistenzarzt style; final =
the draft rewritten by the signer's style rules (STYLE_RULES, the ground truth the miner must rediscover):
house rules are shared by >= 2 of the 3 fake signers, personal rules belong to one.

Identifiers are planted in the PACS-style header and inline (Voruntersuchung vom <date>, "telefonisch an Dr. <name>
um <time> Uhr mitgeteilt", "<age>-jährige Patientin", ward, phone, address, ID numbers, signature lines). Half of
the names come from radbrain.names, half from HELDOUT lists the anonymiser has never seen.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from . import names as N

# fake signers for tests/demo (written into a test signers.json)
FAKE_SIGNERS = {"B1": ["Oberhauser"], "B2": ["Lindqvist"], "B3": ["Okonkwo"]}
FAKE_ME = ["Kerber"]
FAKE_STAFF = ["Brunnhuber"]
OTHER_ASSISTANTS = ["Wendelstein", "Marquardt-Ilić", "Fasching"]

HELDOUT_SURNAMES = ["Brandstetter", "Kowalczuk", "Oyelaran", "Dzhambulatov", "Haberkorn", "Wüstenhagen", "Rüdenauer",
                    "Tschernig", "Zyprian", "Ostermaier", "Kürsatoglu", "Pfannenstiel-Wirth", "Mbeki-Lorenz",
                    "Quandtmeyer", "Szczepaniak", "Vukadinović", "Eichelsdörfer", "Hjelmstad", "Abubakari",
                    "Trautwein", "Gutknecht", "Rademacher", "Leutheusser", "Ćosić", "Nakamura", "Oyelowo",
                    "Ferreira-Klopp", "Steinhilber", "Mutlu", "Bayraktaroğlu", "Wiedemeyer", "Kassabian"]
HELDOUT_FIRST = ["Wiebke", "Gesine", "Arvid", "Thordis", "Jolanta", "Radomir", "Oluwaseun", "Svetozar", "Mechthild",
                 "Hiltrud", "Gunnar", "Eilika", "Bozena", "Tamás", "Ilkka", "Aurelia", "Ottilie", "Kasimir",
                 "Leokadia", "Adewale", "Rosalinde", "Wenzeslaus"]
TOWNS = ["Musterstadt", "Beispielhausen", "Neustadt", "Altdorf", "Bergheim", "Talhausen", "Lindenau", "Am Rhein"]
STREETS = ["Lindenstraße", "Am Mühlberg", "Gartenweg", "Hauptstraße", "Rosenweg", "Bahnhofstr.", "Kirchgasse",
           "Am Sonnenhang"]
WARDS = ["4B", "2A", "C3", "Kardio 1", "ITS2", "7", "UCH", "NCH3"]


def _surnames(rng):
    pool = [n for n in N.SURNAMES if n not in N.AMBIGUOUS and n not in N.EPONYMS]
    return rng.choice(HELDOUT_SURNAMES) if rng.random() < 0.5 else rng.choice(sorted(pool))


def _first(rng):
    pool = [n for n in N.FIRST_NAMES if n not in N.AMBIGUOUS]
    return rng.choice(HELDOUT_FIRST) if rng.random() < 0.5 else rng.choice(sorted(pool))


def _date(rng, y0=2023, y1=2026):
    d, m, y = rng.randint(1, 28), rng.randint(1, 12), rng.randint(y0, y1)
    style = rng.random()
    if style < 0.6:
        return f"{d:02d}.{m:02d}.{y}"
    if style < 0.75:
        return f"{d}.{m}.{str(y)[2:]}"
    if style < 0.9:
        months = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
                  "November", "Dezember"]
        return f"{d}. {months[m - 1]} {y}"
    return f"{y}-{m:02d}-{d:02d}"


def _dob(rng):
    return f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(1932, 2004)}"


def _time(rng):
    return f"{rng.randint(6, 22):02d}:{rng.randint(0, 59):02d}"


def _phone(rng):
    return rng.choice([f"0123 456-{rng.randint(1000, 9999)}", f"{rng.randint(2000, 4999)}",
                       f"+49 123 456 {rng.randint(1000, 9999)}", f"01234 {rng.randint(100000, 999999)}"])


# ------------------------------------------------------------------------------------------------- templates
@dataclass
class Tpl:
    key: str
    exam: str
    frage: str
    technik: str
    befund: list[str]
    beurteilung: list[str]
    thorax: bool = False


def _side(rng):
    return rng.choice(["rechts", "links"])


def templates(rng) -> list[Tpl]:
    s, s2 = _side(rng), _side(rng)
    n = rng.randint(4, 38)
    w = rng.choice(["BWK 12", "LWK 1", "LWK 3", "BWK 8", "LWK 2"])
    seg = rng.choice(["L4/5", "L5/S1", "C5/6", "C6/7", "L3/4"])
    bg_thorax = ["Regelrechte Belüftung der übrigen Lungenabschnitte.", "Herz normal groß.",
                 "Mediastinum mittelständig und nicht verbreitert."]
    bg_abd = ["Leber normal groß mit homogenem Parenchym.", "Milz und Pankreas regelrecht.",
              "Keine pathologisch vergrößerten Lymphknoten."]
    bg_head = ["Regelrechte Weite der inneren und äußeren Liquorräume.", "Keine Mittellinienverlagerung.",
               "Mastoidzellen und Nasennebenhöhlen regelrecht belüftet."]
    return [
        Tpl("pneumonie", "Röntgen Thorax p.a. in 2 Ebenen", "Fieber, Husten. Pneumonie?", "Thorax p.a. und seitlich.",
            [f"Es zeigt sich eine fleckige Verschattung im Unterfeld {s}, möglicherweise einem Infiltrat entsprechend.",
             "Randwinkel beidseits frei."] + bg_thorax,
            [f"Am ehesten pneumonisches Infiltrat im Unterfeld {s}.", "Kein Pleuraerguss."], True),
        Tpl("pleuraerguss", "Röntgen Thorax liegend", "Dyspnoe. Erguss?", "Liegendaufnahme a.p.",
            [f"Es zeigt sich eine homogene Transparenzminderung basal {s}, möglicherweise einem Pleuraerguss "
             "entsprechend.", "Herz grenzwertig groß."] + bg_thorax[:1],
            [f"Pleuraerguss {s}, eher mittelgradig.", "Keine Stauungszeichen."], True),
        Tpl("pneumothorax", "Röntgen Thorax p.a.", "Z.n. ZVK-Anlage. Pneumothorax?", "Thorax p.a. in Exspiration.",
            [f"Es zeigt sich eine apikale Pleuralinie {s} mit einem Saum von ca. {n} mm.", "ZVK-Spitze in der "
             "VCS."] + bg_thorax[1:],
            [f"Schmaler apikaler Pneumothorax {s}.", "ZVK regelrecht einliegend."], True),
        Tpl("lungenembolie", "CT Thorax mit KM (CTPA)", "D-Dimere erhöht, Dyspnoe. LAE?",
            "Spiral-CT nach i.v. KM-Gabe in pulmonalarterieller Phase, Vergleich: CT vom {date2}.",
            [f"Es zeigt sich ein Füllungsdefekt in der Unterlappenarterie {s}, fortgesetzt in die Segmentarterien.",
             "RV/LV-Quotient grenzwertig.", "Kein Pleuraerguss."] + bg_thorax[:1],
            [f"Lungenarterienembolie im Unterlappen {s}, am ehesten akut.", "Möglicherweise beginnende "
             "Rechtsherzbelastung."], True),
        Tpl("rundherd", "CT Thorax nativ", "Rundherd in der Voraufnahme. Verlauf?",
            "Low-dose CT nativ, Vergleich: CT vom {date2}.",
            [f"Es zeigt sich ein solider Rundherd im Oberlappen {s} von {n} mm, im Vergleich zur Voruntersuchung "
             "größenkonstant.", "Keine weiteren Noduli."] + bg_thorax[1:],
            [f"Größenkonstanter Rundherd im Oberlappen {s}, eher benigne.", "Kontrolle nach Fleischner empfohlen."],
            True),
        Tpl("stauung", "Röntgen Thorax liegend", "Dyspnoe, Ödeme. Stauung?", "Liegendaufnahme a.p.",
            ["Es zeigt sich eine Kardiomegalie mit zentraler Gefäßzeichnungsvermehrung.",
             "Kerley-B-Linien beidseits.", "Kleine Pleuraergüsse beidseits."],
            ["Kardiomegalie mit pulmonalvenöser Stauung.", "Möglicherweise interstitielles Ödem."], True),
        Tpl("rippenfraktur", "Röntgen Rippen und Thorax", "Sturz. Rippenfraktur?", "Thorax p.a. und Rippen schräg.",
            [f"Es zeigt sich eine Frakturlinie der 7. Rippe {s} lateral ohne wesentliche Dislokation.",
             "Kein Pneumothorax."] + bg_thorax[1:2],
            [f"Nicht dislozierte Rippenfraktur 7 {s}."], True),
        Tpl("icb", "CT Schädel nativ (cCT)", "Vigilanzminderung. Blutung?", "Spiral-CT nativ.",
            [f"Es zeigt sich eine hyperdense Raumforderung in den Stammganglien {s} von {n} mm mit perifokalem Ödem.",
             "Diskrete Mittellinienverlagerung."] + bg_head[:1],
            [f"Intrazerebrale Blutung in den Stammganglien {s}.", "Am ehesten hypertensive Genese."]),
        Tpl("sab", "CT Schädel nativ (cCT)", "Vernichtungskopfschmerz. SAB?", "Spiral-CT nativ, CTA der hirnversorgenden "
            "Gefäße.", ["Es zeigt sich hyperdenses Material in den basalen Zisternen und der Sylvischen Fissur "
                         f"{s}.", "Beginnende Erweiterung der Temporalhörner."],
            ["Subarachnoidalblutung, eher Fisher Grad 3.", "Möglicherweise beginnender Hydrozephalus."]),
        Tpl("sdh", "CT Schädel nativ (cCT)", "Sturz unter Antikoagulation.", "Spiral-CT nativ.",
            [f"Es zeigt sich eine sichelförmige hyperdense Flüssigkeitsansammlung frontoparietal {s}, maximal {n} mm.",
             "Mittellinienverlagerung um 4 mm."] + bg_head[2:],
            [f"Akutes subdurales Hämatom frontoparietal {s}."]),
        Tpl("ischaemie", "MRT Schädel nativ", "Akute Hemiparese. Ischämie?", "MRT mit DWI, FLAIR, SWI und TOF.",
            [f"Es zeigt sich eine Diffusionsrestriktion im Mediastromgebiet {s} mit korrespondierender ADC-Absenkung.",
             "FLAIR noch ohne Signalanhebung."] + bg_head[:1],
            [f"Akute Ischämie im Mediastromgebiet {s}.", "Am ehesten embolische Genese."]),
        Tpl("schaedelfraktur", "CT Schädel nativ (cCT)", "Sturz auf den Kopf.", "Spiral-CT nativ, Knochenfenster.",
            [f"Es zeigt sich eine nicht dislozierte Kalottenfraktur parietal {s}.", "Keine intrakranielle Blutung."],
            [f"Kalottenfraktur parietal {s} ohne intrakranielle Komplikation."]),
        Tpl("ileus", "CT Abdomen mit KM", "Erbrechen, Stuhlverhalt. Ileus?", "Spiral-CT nach i.v. KM in "
            "portalvenöser Phase.", ["Es zeigen sich dilatierte Dünndarmschlingen bis 4 cm mit Spiegelbildung.",
                                    "Kalibersprung im rechten Unterbauch."] + bg_abd[:1],
            ["Mechanischer Dünndarmileus mit Kalibersprung im rechten Unterbauch.", "Möglicherweise Bride."]),
        Tpl("appendizitis", "CT Abdomen mit KM", "Rechtsseitiger Unterbauchschmerz. Appendizitis?",
            "Spiral-CT nach i.v. KM.", [f"Es zeigt sich eine auf {n % 6 + 9} mm verdickte Appendix mit "
                                        "periappendizitischer Fettgewebsimbibierung.", "Keine freie Luft."],
            ["Akute Appendizitis.", "Kein Abszess."]),
        Tpl("divertikulitis", "CT Abdomen mit KM", "Linksseitiger Unterbauchschmerz.", "Spiral-CT nach i.v. KM.",
            ["Es zeigt sich eine Wandverdickung des Sigmas mit Divertikeln und Fettgewebsimbibierung.",
             "Keine freie Luft, kein Abszess."] + bg_abd[1:2],
            ["Akute Sigmadivertikulitis, eher unkompliziert."]),
        Tpl("freie_luft", "CT Abdomen mit KM", "Akutes Abdomen. Perforation?", "Spiral-CT nach i.v. KM.",
            ["Es zeigt sich freie intraabdominelle Luft subphrenisch und perihepatisch.", "Wenig Aszites."],
            ["Freie intraabdominelle Luft, am ehesten Hohlorganperforation."]),
        Tpl("cholezystitis", "CT Abdomen mit KM", "Oberbauchschmerz rechts, Fieber.", "Spiral-CT nach i.v. KM.",
            ["Es zeigt sich eine wandverdickte Gallenblase mit Konkrementen und perivesikaler Flüssigkeit."] + bg_abd[:1],
            ["Akute Cholezystitis bei Cholezystolithiasis."]),
        Tpl("nierenstein", "CT Abdomen nativ (Low-dose)", "Flankenschmerz. Urolithiasis?", "Low-dose CT nativ.",
            [f"Es zeigt sich ein {n % 7 + 3} mm großes Konkrement im proximalen Harnleiter {s} mit Harnstau II°.",
             f"Niere {s2} unauffällig."],
            [f"Harnleiterstein proximal {s} mit Harnstau II°."]),
        Tpl("pankreatitis", "CT Abdomen mit KM", "Lipase erhöht.", "Spiral-CT nach i.v. KM.",
            ["Es zeigt sich ein ödematös aufgetriebenes Pankreas mit peripankreatischer Flüssigkeit.",
             "Keine Nekrosen."] + bg_abd[:1], ["Akute ödematöse Pankreatitis."]),
        Tpl("leberlaesion", "MRT Leber mit KM", "Unklare Leberläsion im Ultraschall.", "MRT mit Gd-haltigem KM.",
            [f"Es zeigt sich eine T2-hyperintense Läsion im Lebersegment {rng.randint(2, 8)} von {n} mm mit "
             "nodulärem peripherem Enhancement."], ["Leberläsion, am ehesten Hämangiom."]),
        Tpl("aszites", "CT Abdomen mit KM", "Bauchumfangszunahme.", "Spiral-CT nach i.v. KM.",
            ["Es zeigt sich ausgeprägter Aszites in allen Quadranten.", "Leber zirrhotisch umgebaut."],
            ["Ausgeprägter Aszites bei Leberzirrhose."]),
        Tpl("aortenaneurysma", "CT-Angiographie Aorta", "Pulsierender Tumor abdominell.", "CTA in arterieller Phase.",
            [f"Es zeigt sich eine infrarenale Aortenerweiterung auf {n + 30} mm mit randständigem Thrombus.",
             "Kein Hinweis auf Ruptur."], ["Infrarenales Aortenaneurysma ohne Rupturzeichen."]),
        Tpl("dissektion", "CT-Angiographie Aorta", "Thoraxschmerz mit Ausstrahlung in den Rücken.",
            "CTA nativ und arteriell.", ["Es zeigt sich eine Dissektionsmembran ab dem Aortenbogen bis infrarenal.",
                                         "Truncus coeliacus aus dem wahren Lumen."],
            ["Aortendissektion Stanford B.", "Möglicherweise Malperfusion der linken Niere."]),
        Tpl("stenose", "DSA Becken-Bein links", "pAVK IIb links.", "DSA über 4F-Schleuse rechts femoral.",
            [f"Es zeigt sich eine hochgradige Stenose der A. femoralis superficialis {s} über ca. {n} mm.",
             "Gute Kollateralisation."], [f"Hochgradige Stenose der A. femoralis superficialis {s}."]),
        Tpl("bandscheibe", "MRT LWS nativ", "Lumboischialgie. Bandscheibenvorfall?", "MRT sagittal T1, T2, STIR, axial "
            "T2.", [f"Es zeigt sich ein mediolateraler Bandscheibenvorfall in Höhe {seg} {s} mit Kontakt zur Nervenwurzel.",
                    "Übrige Bandscheibenfächer regelrecht."],
            [f"Bandscheibenvorfall {seg} mediolateral {s} mit Wurzelkontakt."]),
        Tpl("wirbelfraktur", "CT BWS/LWS nativ", "Sturz, Rückenschmerz.", "Spiral-CT nativ mit MPR.",
            [f"Es zeigt sich eine Deckplattenimpressionsfraktur {w} mit Höhenminderung um ca. 20 %.",
             "Hinterkante intakt."], [f"Deckplattenimpressionsfraktur {w}, eher stabil."]),
        Tpl("spinalkanalstenose", "MRT LWS nativ", "Claudicatio spinalis.", "MRT sagittal und axial.",
            [f"Es zeigt sich eine absolute Spinalkanalstenose in Höhe {seg} bei Facettengelenksarthrose.",
             "Neuroforamina beidseits eingeengt."], [f"Absolute Spinalkanalstenose {seg}."]),
        Tpl("meniskus", "MRT Knie nativ", "Distorsion. Meniskusläsion?", "MRT PD fs, T1, T2.",
            ["Es zeigt sich eine horizontale Signalanhebung im Hinterhorn des Innenmeniskus mit Kontakt zur Unterfläche.",
             "Kreuzbänder regelrecht."], ["Horizontalriss im Hinterhorn des Innenmeniskus."]),
        Tpl("kreuzband", "MRT Knie nativ", "Distorsionstrauma.", "MRT PD fs, T1, T2.",
            ["Es zeigt sich eine Kontinuitätsunterbrechung des vorderen Kreuzbandes.", "Bone bruise am lateralen "
             "Femurkondylus."], ["Vordere Kreuzbandruptur.", "Möglicherweise begleitende Innenbandzerrung."]),
        Tpl("rotatorenmanschette", "MRT Schulter nativ", "Schulterschmerz, Abduktionsschwäche.", "MRT PD fs, T1.",
            ["Es zeigt sich eine transmurale Ruptur der Supraspinatussehne mit Retraktion um 12 mm.",
             "Goutallier Grad 2."], ["Transmurale Supraspinatussehnenruptur mit Retraktion."]),
        Tpl("schulterluxation", "Röntgen Schulter in 2 Ebenen", "Sturz, Fehlstellung.", "Schulter a.p. und Y-View.",
            [f"Es zeigt sich eine vordere Luxation des Humeruskopfes {s} mit Hill-Sachs-Delle.",
             "Möglicherweise knöcherne Bankart-Läsion."], [f"Vordere Schulterluxation {s} mit Hill-Sachs-Delle."]),
        Tpl("radiusfraktur", "Röntgen Handgelenk in 2 Ebenen", "Sturz auf die ausgestreckte Hand.",
            "Handgelenk d.p. und seitlich.", [f"Es zeigt sich eine distale Radiusfraktur {s} mit dorsaler Abkippung "
                                              "(Colles-Typ).", "Processus styloideus ulnae intakt."],
            [f"Distale Radiusfraktur {s} vom Colles-Typ."]),
        Tpl("skaphoid", "CT Handgelenk nativ", "Tabatière-Druckschmerz.", "Spiral-CT nativ mit MPR.",
            ["Es zeigt sich eine nicht dislozierte Fraktur im mittleren Drittel des Skaphoids."],
            ["Nicht dislozierte Skaphoidfraktur (mittleres Drittel)."]),
        Tpl("schenkelhals", "Röntgen Hüfte in 2 Ebenen", "Sturz, Beinverkürzung.", "Beckenübersicht und Hüfte axial.",
            [f"Es zeigt sich eine Schenkelhalsfraktur {s} mit Varusfehlstellung, eher Garden III."],
            [f"Dislozierte Schenkelhalsfraktur {s} (Garden III)."]),
        Tpl("osg", "Röntgen OSG in 2 Ebenen", "Supinationstrauma.", "OSG a.p. und seitlich.",
            [f"Es zeigt sich eine Fraktur des Außenknöchels {s} in Höhe der Syndesmose (Weber B).",
             "Sprunggelenk kongruent."], [f"Außenknöchelfraktur {s} Weber B."]),
        Tpl("beckenfraktur", "CT Becken nativ", "Hochrasanztrauma.", "Spiral-CT nativ mit MPR.",
            [f"Es zeigt sich eine Fraktur des oberen und unteren Schambeinastes {s}.", "Iliosakralgelenke intakt."],
            [f"Vordere Beckenringfraktur {s}."]),
        Tpl("metastasen", "CT Thorax/Abdomen mit KM (Staging)", "Staging bei Mammakarzinom.",
            "Spiral-CT nach i.v. KM, Vergleich: CT vom {date2}.",
            ["Es zeigen sich neu aufgetretene hypodense Leberläsionen bis 18 mm.",
             f"Osteolyse in {w}."] + bg_thorax[1:2],
            ["Neu aufgetretene hepatische und ossäre Metastasen, am ehesten Progress."], True),
        Tpl("normal_roe", "Röntgen Thorax p.a. in 2 Ebenen", "Präoperativ.", "Thorax p.a. und seitlich.",
            ["Regelrechte Belüftung beider Lungen.", "Randwinkel beidseits frei.", "Herz normal groß."],
            ["Altersentsprechender Normalbefund.", "Ansonsten unauffälliger Befund."], True),
        Tpl("normal_ct", "CT Schädel nativ (cCT)", "Synkope.", "Spiral-CT nativ.",
            ["Keine intrakranielle Blutung.", "Keine Demarkierung einer Ischämie."] + bg_head,
            ["Regelrechter intrakranieller Befund.", "Ansonsten unauffälliger Befund."]),
        Tpl("normal_mrt", "MRT Knie nativ", "Belastungsschmerz.", "MRT PD fs, T1, T2.",
            ["Menisken und Kreuzbänder regelrecht.", "Kein Gelenkerguss.", "Knorpel regelrecht."],
            ["Regelrechter MRT-Befund des Kniegelenks."]),
        Tpl("normal_angio", "DSA Becken-Bein rechts", "Kontrolle nach PTA.", "DSA über 4F-Schleuse links femoral.",
            ["Regelrechte Kontrastierung der Becken- und Beinarterien.", "Keine relevante Stenose."],
            ["Regelrechter angiographischer Befund nach PTA."]),
    ]


# ------------------------------------------------------------------------------------------------- style rules
@dataclass
class StyleRule:
    rid: str
    signers: tuple[str, ...]
    label: str
    section: str                      # befund | beurteilung
    kind: str                         # sub | del | ins | reorder | number


STYLE_RULES = [
    StyleRule("H_ES_ZEIGT", ("B1", "B2", "B3"), "\"Es zeigt sich …\" gestrichen", "befund", "del"),
    StyleRule("H_MOEGL", ("B1", "B2"), "Hedging \"möglicherweise\" gestrichen", "befund", "del"),
    StyleRule("H_KEIN_PTX", ("B1", "B3"), "\"Kein Pneumothorax.\" ergänzt (Thorax)", "befund", "ins"),
    StyleRule("H_EHER", ("B2", "B3"), "\"eher\" → \"am ehesten\"", "beurteilung", "sub"),
    StyleRule("P_B1_VEREINBAR", ("B1",), "\"Am ehesten\" → \"Vereinbar mit\"", "beurteilung", "sub"),
    StyleRule("P_B1_NUMMER", ("B1",), "Beurteilung nummeriert", "beurteilung", "number"),
    StyleRule("P_B1_ANSONSTEN", ("B1",), "\"Ansonsten unauffälliger Befund.\" gestrichen", "beurteilung", "del"),
    StyleRule("P_B2_BDS", ("B2",), "\"beidseits\" → \"bds.\"", "befund", "sub"),
    StyleRule("P_B2_KORREL", ("B2",), "\"Klinische Korrelation empfohlen.\" ergänzt", "beurteilung", "ins"),
    StyleRule("P_B2_MOEGL_BEU", ("B2",), "\"Möglicherweise\" → \"Fraglich\" (Beurteilung)", "beurteilung", "sub"),
    StyleRule("P_B3_UNAUFF", ("B3",), "\"regelrecht\" → \"unauffällig\"", "befund", "sub"),
    StyleRule("P_B3_REORDER", ("B3",), "Beurteilung: Hauptbefund nach vorn (Reihenfolge)", "beurteilung", "reorder"),
]
RULE_P = 0.85


def _apply_befund(lines: list[str], signer: str, rng, thorax: bool, applied: set) -> list[str]:
    out = []
    for ln in lines:
        x = ln
        if "H_ES_ZEIGT" in _active(signer) and rng.random() < RULE_P and re.match(r"Es zeig(t|en) sich ", x):
            x = re.sub(r"^Es zeig(t|en) sich ", "", x)
            x = x[0].upper() + x[1:]
            applied.add("H_ES_ZEIGT")
        if "H_MOEGL" in _active(signer) and "möglicherweise " in x and rng.random() < RULE_P:
            x = x.replace(", möglicherweise einem", ", einem").replace("möglicherweise ", "")
            applied.add("H_MOEGL")
        if "P_B2_BDS" in _active(signer) and "beidseits" in x and rng.random() < RULE_P:
            x = x.replace("beidseits", "bds.").replace("bds..", "bds.")
            applied.add("P_B2_BDS")
        if "P_B3_UNAUFF" in _active(signer) and "egelrecht" in x and rng.random() < RULE_P:
            x = x.replace("Regelrecht", "Unauffällig").replace("regelrecht", "unauffällig")
            applied.add("P_B3_UNAUFF")
        out.append(x)
    if thorax and "H_KEIN_PTX" in _active(signer) and not any("Pneumothorax" in x for x in out) \
            and rng.random() < RULE_P:
        out.append("Kein Pneumothorax.")
        applied.add("H_KEIN_PTX")
    return out


def _apply_beurteilung(lines: list[str], signer: str, rng, applied: set) -> list[str]:
    out = []
    for ln in lines:
        x = ln
        if "P_B1_ANSONSTEN" in _active(signer) and x.startswith("Ansonsten unauffälliger") and rng.random() < RULE_P:
            applied.add("P_B1_ANSONSTEN")
            continue
        if "H_EHER" in _active(signer) and re.search(r"\beher\b", x) and rng.random() < RULE_P:
            x = re.sub(r"\beher\b", "am ehesten", x)
            applied.add("H_EHER")
        if "P_B1_VEREINBAR" in _active(signer) and x.startswith("Am ehesten ") and rng.random() < RULE_P:
            x = "Vereinbar mit " + x[len("Am ehesten "):]
            applied.add("P_B1_VEREINBAR")
        if "P_B2_MOEGL_BEU" in _active(signer) and x.startswith("Möglicherweise ") and rng.random() < RULE_P:
            x = "Fraglich " + x[len("Möglicherweise "):]
            applied.add("P_B2_MOEGL_BEU")
        out.append(x)
    if "P_B3_REORDER" in _active(signer) and len(out) >= 2 and rng.random() < RULE_P:
        out = [out[1], out[0]] + out[2:]
        applied.add("P_B3_REORDER")
    if "P_B2_KORREL" in _active(signer) and rng.random() < RULE_P:
        out.append("Klinische Korrelation empfohlen.")
        applied.add("P_B2_KORREL")
    if "P_B1_NUMMER" in _active(signer) and len(out) >= 1 and rng.random() < RULE_P:
        out = [f"{i + 1}. {x}" for i, x in enumerate(out)]
        applied.add("P_B1_NUMMER")
    return out


def _active(signer: str) -> set[str]:
    return {r.rid for r in STYLE_RULES if signer in r.signers}


# ------------------------------------------------------------------------------------------------- reports
@dataclass
class Synth:
    kind: str                 # pair | final
    signer: str
    entity: str
    draft: str | None
    final: str
    identifiers: list[str] = field(default_factory=list)      # strings that must never survive anonymisation
    author_is_me: bool = False
    applied_rules: list[str] = field(default_factory=list)
    clean_draft: dict = field(default_factory=dict)            # section texts without identifiers (ground truth)
    clean_final: dict = field(default_factory=dict)


def _render(header: list[str], frage: str, technik: str, befund: list[str], beu: list[str], sig: list[str]) -> str:
    parts = header + ["", "Fragestellung:", frage, "", "Technik:", technik, "", "Befund:"] + befund + \
        ["", "Beurteilung:"] + beu + [""] + sig
    return "\n".join(parts)


def make(rng: random.Random, signer: str | None = None, entity: str | None = None, kind: str = "pair",
         plant: bool = True) -> Synth:
    signer = signer or rng.choice(["B1", "B2", "B3"])
    tpls = templates(rng)
    t = next((x for x in tpls if x.key == entity), None) if entity else rng.choice(tpls)
    ids: list[str] = []
    last, first = _surnames(rng), _first(rng)
    dob, pid, fall = _dob(rng), str(rng.randint(10_000_000, 99_999_999)), f"{rng.randint(2023, 2026)}" \
        f"{rng.randint(100000, 999999)}"
    exam_date, exam_time = _date(rng), _time(rng)
    date2 = _date(rng, 2019, 2025)
    ref_last = _surnames(rng)
    ward = rng.choice(WARDS)
    age = rng.randint(19, 94)
    phone = _phone(rng)
    me = rng.random() < 0.5
    author = FAKE_ME[0] if me else rng.choice(OTHER_ASSISTANTS)
    header_style = rng.random()
    if header_style < 0.33:
        header = [f"Patient: {last}, {first}", f"geb. {dob}", f"PID: {pid}", f"Fall-Nr.: {fall}"]
    elif header_style < 0.66:
        header = [f"{last.upper()}^{first.upper()}", f"Geburtsdatum: {dob}", f"Auftragsnummer: {fall}"]
    else:
        header = [f"{first} {last}, * {dob}", f"Pat.-Nr. {pid}"]
    header += [f"Untersuchung: {t.exam}", f"Untersuchungsdatum: {exam_date} {exam_time} Uhr", f"Station: {ward}",
               f"Zuweiser: Dr. med. {ref_last}"]
    if rng.random() < 0.3:
        street, plz, town = rng.choice(STREETS), rng.randint(70000, 79999), rng.choice(TOWNS)
        header.append(f"Anschrift: {street} {rng.randint(1, 120)}, {plz} {town}")
        ids += [f"{street} ", str(plz)]
    ids += [last, first, dob, pid, fall, exam_date, exam_time, ref_last]
    frage = t.frage
    if plant and rng.random() < 0.5:
        frage = f"Die {age}-jährige Patientin stellt sich vor. " + frage
        ids.append(f"{age}-jährig")
    technik = t.technik.replace("{date2}", date2)
    if "{date2}" in t.technik:
        ids.append(date2)
    elif plant and rng.random() < 0.4:
        technik += f" Voruntersuchung vom {date2} zum Vergleich."
        ids.append(date2)
    befund = list(t.befund)
    beu = list(t.beurteilung)
    tail: list[str] = []
    if plant:
        r = rng.random()
        if r < 0.35:
            t2 = _time(rng)
            ttl = rng.choice(["Dr.", "OA Dr.", "Frau Dr.", "Herrn Dr.", "Kollegin", "Kollegen"])
            tail.append(f"Der Befund wurde am {exam_date} um {t2} Uhr telefonisch an {ttl} {ref_last} (Station {ward}, "
                        f"Tel. {phone}) mitgeteilt.")
            ids += [t2, f"Station {ward}", phone.split()[-1]]
        elif r < 0.55:
            nm = _surnames(rng)
            tail.append(f"Rücksprache mit {nm} erfolgt.")
            ids.append(nm)
        elif r < 0.7:
            y = rng.randint(2005, 2024)
            befund.insert(0, f"Z.n. Operation {y} auswärts.")
            ids.append(str(y))
        elif r < 0.8:
            befund.insert(0, f"Patientin Frau {last} ist bekannt.")
    sig_draft = [f"Erstellt von: Dr. {author}, Assistenzarzt", f"Vorläufiger Befund vom {exam_date}"]
    signer_name = FAKE_SIGNERS[signer][0]
    role = {"B1": "Chefarzt", "B2": "Leitender Oberarzt", "B3": "Oberarzt"}[signer]
    sig_final = [f"Elektronisch signiert: Prof. Dr. med. {signer_name}, {role}, {exam_date} {exam_time}"] \
        if signer == "B1" else [f"Elektronisch freigegeben: Dr. med. {signer_name}, {role}, {exam_date}"]
    ids += [author, signer_name]
    applied: set = set()
    befund_final = _apply_befund(befund, signer, rng, t.thorax, applied)
    beu_final = _apply_beurteilung(beu, signer, rng, applied)
    draft = _render(header, frage, technik, befund, beu + tail, sig_draft) if kind == "pair" else None
    final = _render(header, frage, technik, befund_final, beu_final + tail, sig_final)
    return Synth(kind=kind, signer=signer, entity=t.key, draft=draft, final=final, identifiers=list(dict.fromkeys(ids)),
                 author_is_me=me and kind == "pair", applied_rules=sorted(applied),
                 clean_draft={"befund": "\n".join(befund), "beurteilung": "\n".join(beu)},
                 clean_final={"befund": "\n".join(befund_final), "beurteilung": "\n".join(beu_final)})


def corpus(n: int, seed: int = 7, kind_mix: float = 0.7) -> list[Synth]:
    rng = random.Random(seed)
    out = []
    for i in range(n):
        out.append(make(rng, signer=["B1", "B2", "B3"][i % 3], kind="pair" if rng.random() < kind_mix else "final"))
    return out


def write_test_signers(path) -> None:
    import json
    path.write_text(json.dumps({"signers": FAKE_SIGNERS, "me": FAKE_ME, "staff": FAKE_STAFF}, ensure_ascii=False),
                    encoding="utf-8")
