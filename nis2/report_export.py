"""NIS2-Modul – Berichtsgenerator für Word (.docx) und PDF.

DIE SPRACHE GEHÖRT DEM MANDANTEN (#1954)
Der Readiness-Report geht an den Mandanten; über seine Sprache entscheidet
deshalb ``firmen.sprache`` und nicht der Bearbeiter, der ihn zufällig erzeugt
(aufgelöst in :func:`export_report_docx` über
``shared.reports.texte.aufloesen``, fail-open auf Deutsch). Ein
``sprache``-Argument übersteuert für diesen einen Lauf.

Drei Dinge bleiben dabei bewusst **unberührt**:

* **Der Dateiname.** ``NIS2_Bericht_<Projekt>_<Datum>.docx`` ist kein
  Dokumentinhalt, sondern eine Kennung, nach der Aufrufer suchen
  (``server/api/nis2.py``). Dasselbe gilt in ``dsgvo/report_export.py``.
* **Die Katalogtexte.** Anforderungstitel und ``-beschreibung``
  (``NIS2_ANFORDERUNGEN``), die Bewertungs-Labels (``BEWERTUNG_SKALA``), die
  Kapitelnamen samt ``referenz`` (``KAPITEL``) und die Einrichtungsklassen
  (``EINRICHTUNGSKLASSEN``) liegen in ``nis2/requirements.py`` und sind
  (noch) nur deutsch vorhanden — siehe Bericht zu #1954. Sie hier zu
  übersetzen wäre eine zweite Quelle für dieselben Begriffe, die Oberfläche
  und Vorlagen-Engine anders lesen würden (#1731/#1735).
* **Die Fundstellen.** ``Art. 21``, ``Anhang I``, ``L 333`` bleiben, wie sie
  sind; nur die Bezeichnung der Rechtsquelle folgt dem Amtsblatt
  (``Richtlinie`` → *Directive*). Die Ziffern nie — die Lehre aus
  #1763/#1792.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from shared.reports import texte as _rt

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

from nis2.requirements import (
    BEWERTUNG_SKALA,
    EINRICHTUNGSKLASSEN,
    KAPITEL,
    NIS2_ANFORDERUNGEN,
    berechne_reifegrad,
)

_NIS2_BLUE = "#1A237E"
_DARK = "#0D1B6E"
_SOFT = "#E8EAF6"
_KAPITEL_FARBEN = {
    "NIS1": ("#1565C0", "#E3F2FD"),
    "NIS2": ("#4A148C", "#F3E5F5"),
    "NIS3": ("#B71C1C", "#FFEBEE"),
    "NIS4": ("#E65100", "#FFF3E0"),
    "NIS5": ("#1B5E20", "#E8F5E9"),
}
_BEWERTUNG_FARBEN = {
    0: "#9E9E9E", 1: "#C62828", 2: "#E65100",
    3: "#F57F17", 4: "#2E7D32", 5: "#1B5E20",
}
_AMPEL_FARBEN = {
    "gruen": "#2e7d32",
    "orange": "#e65100",
    "rot": "#c62828",
}

REFERENZEN = [
    "[1] Europäisches Parlament und Rat der Europäischen Union, "
    "\"Richtlinie (EU) 2022/2555 über Maßnahmen für ein hohes gemeinsames "
    "Cybersicherheitsniveau in der Union (NIS2-Richtlinie),\" "
    "Amtsblatt der EU, L 333, 27. Dezember 2022.",
    "[2] Bundesamt für Sicherheit in der Informationstechnik (BSI), "
    "\"BSI-Grundschutz-Kompendium Edition 2023,\" BSI, Bonn, 2023.",
    "[3] ENISA, \"NIS2 Implementation – Guidance for Operators of Essential Services,\" "
    "ENISA, Athens, 2023.",
    "[4] European Union Agency for Cybersecurity (ENISA), "
    "\"Cybersecurity Risk Management for Operators of Essential Services,\" "
    "ENISA, Athens, 2022.",
    "[5] Bundesamt für Sicherheit in der Informationstechnik (BSI), "
    "\"Umsetzungshinweise zur NIS-2-Richtlinie,\" BSI, Bonn, 2023.",
    "[6] International Organization for Standardization, "
    "\"ISO/IEC 27001:2022 – Information Security Management Systems,\" ISO, Geneva, 2022.",
    "[7] International Organization for Standardization, "
    "\"ISO/IEC 27002:2022 – Information Security Controls,\" ISO, Geneva, 2022.",
    "[8] ENISA, \"Supply Chain Cybersecurity – Good practices for cybersecurity in supply chains,\" "
    "ENISA, Athens, 2021.",
    "[9] Europäische Kommission, \"Durchführungsrechtsakt zur Festlegung technischer und "
    "methodischer Anforderungen für Cybersicherheitsmaßnahmen gemäß Art. 21 NIS2-RL,\" "
    "Brüssel, 2024.",
    "[10] NIS-Kooperationsgruppe, \"Leitfaden für die Meldung erheblicher Vorfälle nach NIS2,\" "
    "NIS-Kooperationsgruppe, 2023.",
]

#: Dieselbe Quellenliste für das englische Dokument (#1954).
#:
#: **Übersetzt sind Urheber und Rolle, nicht die Titel deutschsprachiger
#: Veröffentlichungen** — gleiche Linie wie ``dsgvo.report_export.
#: REFERENZEN_EN``. Ein Titel ist die Kennung eines Dokuments: Wer das
#: „BSI-Grundschutz-Kompendium" oder die „Umsetzungshinweise zur
#: NIS-2-Richtlinie" englisch übersetzt, nennt eine Veröffentlichung, die es
#: nicht gibt, und der Leser findet sie nicht (die Lehre aus #1763/#1792).
#:
#: Übersetzt ist deshalb nur, wo eine **amtliche** englische Fassung existiert:
#: [1] (Amtsblatt, dort amtlich „NIS 2 Directive" — mit Leerzeichen, anders als
#: unser Produktbegriff „NIS2"), [9] und [10] (Rechtsakt bzw. Gremium der
#: Union). [3], [4], [6], [7] und [8] waren schon englisch; [2] und [5]
#: behalten ihren deutschen Titel.
REFERENZEN_EN = [
    "[1] European Parliament and Council of the European Union, "
    "\"Directive (EU) 2022/2555 on measures for a high common level of "
    "cybersecurity across the Union (NIS 2 Directive),\" "
    "Official Journal of the EU, L 333, 27 December 2022.",
    "[2] Federal Office for Information Security (BSI), "
    "\"BSI-Grundschutz-Kompendium Edition 2023,\" BSI, Bonn, 2023.",
    "[3] ENISA, \"NIS2 Implementation – Guidance for Operators of Essential Services,\" "
    "ENISA, Athens, 2023.",
    "[4] European Union Agency for Cybersecurity (ENISA), "
    "\"Cybersecurity Risk Management for Operators of Essential Services,\" "
    "ENISA, Athens, 2022.",
    "[5] Federal Office for Information Security (BSI), "
    "\"Umsetzungshinweise zur NIS-2-Richtlinie,\" BSI, Bonn, 2023.",
    "[6] International Organization for Standardization, "
    "\"ISO/IEC 27001:2022 – Information Security Management Systems,\" ISO, Geneva, 2022.",
    "[7] International Organization for Standardization, "
    "\"ISO/IEC 27002:2022 – Information Security Controls,\" ISO, Geneva, 2022.",
    "[8] ENISA, \"Supply Chain Cybersecurity – Good practices for cybersecurity in supply chains,\" "
    "ENISA, Athens, 2021.",
    "[9] European Commission, \"Implementing act laying down technical and "
    "methodological requirements for cybersecurity measures pursuant to "
    "Art. 21 NIS2 Directive,\" Brussels, 2024.",
    "[10] NIS Cooperation Group, \"Guidance on the notification of "
    "significant incidents under NIS2,\" NIS Cooperation Group, 2023.",
]


def _referenzen(sprache: str) -> list[str]:
    """Die Quellenliste in der Sprache des Dokuments."""
    return REFERENZEN_EN if sprache != "de" else REFERENZEN


#: Die Texte des NIS2-Readiness-Reports je Sprache (#1954).
#:
#: Die deutschen Werte sind zeichengenau die aus 8.3.4 — einschließlich der
#: Halbgeviertstriche („–"), der doppelten Leerzeichen in den Bannern der
#: Lückenanalyse und der Gedankenstriche in „— Keine Einträge erfasst —".
#:
#: Amtliche englische Begriffe der Richtlinie (EU) 2022/2555:
#: ``Einrichtung`` → *entity*, ``erheblicher Sicherheitsvorfall`` →
#: *significant incident*, ``Risikomanagementmaßnahmen`` → *cybersecurity
#: risk-management measures*, ``Aufsichtsbehörde`` → *competent authority*.
#: Die Kürzel N1–N6 und N-GOV sind **Bezeichner** dieses Moduls und bleiben.
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        "titel": "NIS2-Readiness Report",
        "untertitel": "Richtlinie (EU) 2022/2555 – NIS2 Cybersicherheitsrichtlinie",
        # Datumsformat statt eines festen Musters: `%B` wäre von der
        # Server-Locale abhängig und schriebe im englischen Bericht deutsche
        # Monatsnamen. Englisch bekommt ISO 8601 — in einem Dokument, das ein
        # Prüfer liest, ist `03.11.2026` sonst zweideutig.
        "datum_format": "%d.%m.%Y",

        "ampel_gruen": "Weitgehend konform",
        "ampel_orange": "Teilweise konform – Handlungsbedarf",
        "ampel_rot": "Erhebliche Lücken – Dringender Handlungsbedarf",

        "m_projekt": "Projekt:",
        "m_unternehmen": "Unternehmen:",
        "m_klasse": "Einrichtungsklasse:",
        "m_berater": "Berater:",
        "m_erstellt": "Erstellt am:",
        "m_rechtsgrundlage": "Rechtsgrundlage:",
        "rechtsquelle": "Richtlinie (EU) 2022/2555 (NIS2)",
        "gesamtergebnis": "Gesamtergebnis: {pct} – {ampel}",

        "h1": "1. Executive Summary",
        "summary": ("Dieser Bericht dokumentiert den NIS2-Compliance-Status "
                    "der Einrichtung \"{einrichtung}\" gemäß Richtlinie (EU) "
                    "2022/2555. Von {gesamt} Anforderungen wurden {bewertet} "
                    "bewertet. Der Gesamtreifegrad beträgt {pct} ({ampel})."),

        "h2": "2. Bewertungsübersicht nach Kapitel",
        "k_kapitel": "Kapitel",
        "k_referenz": "Referenz",
        "k_reifegrad": "Reifegrad",
        "k_bewertet": "Bewertet",

        "h3": "3. Lückenanalyse – Kritische Anforderungen",
        "l_bewertung": "Bewertung: {wert} – {label}",
        "l_referenz": "Referenz: {ref}",
        "l_massnahme": "Maßnahme: {massnahme}",

        "h4": "4. Detailbewertung aller Anforderungen",
        "d_id": "ID",
        "d_anforderung": "Anforderung",
        "d_bewertung": "Bewertung",
        "d_kommentar": "Kommentar",

        "h5": "5. Pflicht-Dokumentation (Nachweise)",
        "n6_klassifikation": "N6 Entity-Klassifikation: {klasse}",
        "n6_sektor": "Sektor: {sektor}",

        "n1_titel": "N1 Asset-Inventar",
        "n1_asset": "Asset",
        "n1_typ": "Typ",
        "n1_krit": "Krit.",
        "n1_v": "V",
        "n1_i": "I",
        "n1_a": "A",

        "n2_titel": "N2 Risiko-Register",
        "n2_id": "ID",
        "n2_titel_sp": "Titel",
        "n2_auswirkung": "Auswirkung",
        "n2_wkt": "Wkt",
        "n2_score": "Score",
        "n2_status": "Status",

        "n4_titel": "N4 Supply-Chain-Vendoren",
        "n4_vendor": "Vendor",
        "n4_leistung": "Leistung",
        "n4_krit": "Krit.",
        "n4_score": "Score",
        "n4_status": "Status",

        "block_kopf": "{titel} ({anzahl} Einträge)",
        "keine_eintraege": "— Keine Einträge erfasst —",

        "n3_titel": "N3 Incident-Response-Plan",
        "n3_csirt_kontakt": "CSIRT-Kontakt",
        "n3_csirt_email": "CSIRT-Email",
        "n3_early_warning": "24h Early-Warning-SLA",
        "n3_notification": "72h Notification-SLA",
        "n3_final_report": "1M Final-Report-SLA",
        "n3_manager": "Incident-Manager",

        "n5_titel": "N5 Business-Continuity-Plan",
        "n5_rpo": "RPO (Minuten)",
        "n5_rto": "RTO (Minuten)",
        "n5_strategie": "Backup-Strategie",
        "n5_haeufigkeit": "Backup-Häufigkeit",
        "n5_dr": "DR-Standort",
        "n5_test_datum": "Letzter BCP-Test",
        "n5_test_frequenz": "Test-Frequenz",

        "gov_kopf": "N-GOV Governance-Nachweise Art. 20 ({anzahl} Einträge)",
        "gov_keine": "— Keine Governance-Nachweise erfasst —",
        "gov_typ": "Typ",
        "gov_datum": "Datum",
        "gov_gremium": "Gremium",
        "gov_gegenstand": "Gegenstand",
        "gov_review": "Wiedervorlage",

        "h6": "6. Referenzen und Rechtsquellen",
    },
    "en": {
        "titel": "NIS2 readiness report",
        "untertitel": "Directive (EU) 2022/2555 – NIS2 cybersecurity directive",
        "datum_format": "%Y-%m-%d",

        "ampel_gruen": "Largely compliant",
        "ampel_orange": "Partially compliant – action required",
        "ampel_rot": "Significant gaps – urgent action required",

        "m_projekt": "Project:",
        "m_unternehmen": "Company:",
        "m_klasse": "Entity class:",
        "m_berater": "Consultant:",
        "m_erstellt": "Created on:",
        "m_rechtsgrundlage": "Legal basis:",
        "rechtsquelle": "Directive (EU) 2022/2555 (NIS2)",
        "gesamtergebnis": "Overall result: {pct} – {ampel}",

        "h1": "1. Executive summary",
        "summary": ("This report documents the NIS2 compliance status of the "
                    "entity \"{einrichtung}\" pursuant to Directive (EU) "
                    "2022/2555. Of {gesamt} requirements, {bewertet} have "
                    "been assessed. The overall maturity is {pct} ({ampel})."),

        "h2": "2. Assessment overview by chapter",
        "k_kapitel": "Chapter",
        "k_referenz": "Reference",
        "k_reifegrad": "Maturity",
        "k_bewertet": "Assessed",

        "h3": "3. Gap analysis – critical requirements",
        "l_bewertung": "Assessment: {wert} – {label}",
        "l_referenz": "Reference: {ref}",
        "l_massnahme": "Measure: {massnahme}",

        "h4": "4. Detailed assessment of all requirements",
        "d_id": "ID",
        "d_anforderung": "Requirement",
        "d_bewertung": "Assessment",
        "d_kommentar": "Comment",

        "h5": "5. Mandatory documentation (evidence)",
        "n6_klassifikation": "N6 entity classification: {klasse}",
        "n6_sektor": "Sector: {sektor}",

        "n1_titel": "N1 asset inventory",
        "n1_asset": "Asset",
        "n1_typ": "Type",
        "n1_krit": "Crit.",
        # Schutzbedarf V/I/A — im Englischen die übliche Reihung C/I/A
        # (confidentiality, integrity, availability). Die **Spalten bleiben in
        # ihrer Reihenfolge**: `V` ist Vertraulichkeit und wird `C`, nicht an
        # eine andere Stelle gerückt.
        "n1_v": "C",
        "n1_i": "I",
        "n1_a": "A",

        "n2_titel": "N2 risk register",
        "n2_id": "ID",
        "n2_titel_sp": "Title",
        "n2_auswirkung": "Impact",
        "n2_wkt": "Lik.",
        "n2_score": "Score",
        "n2_status": "Status",

        "n4_titel": "N4 supply chain vendors",
        "n4_vendor": "Vendor",
        "n4_leistung": "Service",
        "n4_krit": "Crit.",
        "n4_score": "Score",
        "n4_status": "Status",

        "block_kopf": "{titel} ({anzahl} entries)",
        "keine_eintraege": "— No entries recorded —",

        "n3_titel": "N3 incident response plan",
        "n3_csirt_kontakt": "CSIRT contact",
        "n3_csirt_email": "CSIRT email",
        "n3_early_warning": "24h early warning SLA",
        "n3_notification": "72h notification SLA",
        "n3_final_report": "1M final report SLA",
        "n3_manager": "Incident manager",

        "n5_titel": "N5 business continuity plan",
        "n5_rpo": "RPO (minutes)",
        "n5_rto": "RTO (minutes)",
        "n5_strategie": "Backup strategy",
        "n5_haeufigkeit": "Backup frequency",
        "n5_dr": "DR site",
        "n5_test_datum": "Last BCP test",
        "n5_test_frequenz": "Test frequency",

        "gov_kopf": "N-GOV governance evidence Art. 20 ({anzahl} entries)",
        "gov_keine": "— No governance evidence recorded —",
        "gov_typ": "Type",
        "gov_datum": "Date",
        "gov_gremium": "Body",
        "gov_gegenstand": "Subject",
        "gov_review": "Next review",

        "h6": "6. References and legal sources",
    },
}

_t = _rt.macher(TEXTE)


# #1765: Die alte Inline-Kennzeichnung („🤖 KI-generiert … fachlich zu
# prüfen") steht in Bestandstexten und gehört nicht in ein Dokument. Sie
# wird beim Drucken entfernt; die Herkunft führt `shared/ki_herkunft`.
from shared.ki_herkunft import ohne_marker as _ohne_ki_marker


def _safe_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "-", s or "")
    s = re.sub(r"\s+", "_", s).strip("_")
    return s[:100] or "NIS2_Bericht"


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex_to_word(h: str) -> str:
    return h.lstrip("#").upper()


def _load_font(size: int, bold: bool = False):
    candidates = (
        (["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"] if bold else [])
        + ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _set_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), _hex_to_word(fill))
    tc_pr.append(shd)


def _set_border(cell, color: str = "DDDDDD") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = tc_pr.first_child_found_in("w:tcBorders")
    if tc_borders is None:
        tc_borders = OxmlElement("w:tcBorders")
        tc_pr.append(tc_borders)
    for edge in ("top", "left", "bottom", "right"):
        el = tc_borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            tc_borders.append(el)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), color.lstrip("#"))


def _banner(doc, text: str, bg: str, fg: str = "#FFFFFF", size: int = 14) -> None:
    tbl = doc.add_table(rows=1, cols=1)
    cell = tbl.cell(0, 0)
    _set_shading(cell, bg)
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(size)
    r, g, b = _hex_to_rgb(fg)
    run.font.color.rgb = RGBColor(r, g, b)


def _section_heading(doc, text: str, color: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(14)
    r, g, b = _hex_to_rgb(color)
    run.font.color.rgb = RGBColor(r, g, b)
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)


def _maturity_bar_docx(doc, pct: float, color: str, label: str) -> None:
    bar_tbl = doc.add_table(rows=1, cols=2)
    bar_tbl.autofit = False
    total_w = Inches(5.5)
    filled = Inches(5.5 * pct / 100)
    empty = total_w - filled
    c0 = bar_tbl.cell(0, 0)
    c0.width = filled
    _set_shading(c0, color)
    p0 = c0.paragraphs[0]
    p0.paragraph_format.space_before = Pt(0)
    p0.paragraph_format.space_after = Pt(0)
    r0 = p0.add_run(f"  {pct:.1f}%  {label}")
    r0.bold = True
    r0.font.size = Pt(9)
    rv, gv, bv = _hex_to_rgb(color)
    r0.font.color.rgb = RGBColor(255, 255, 255)
    c1 = bar_tbl.cell(0, 1)
    c1.width = empty if empty > Inches(0) else Inches(0.01)
    _set_shading(c1, "#E0E0E0")
    c1.paragraphs[0].paragraph_format.space_before = Pt(0)
    c1.paragraphs[0].paragraph_format.space_after = Pt(0)


def _gauge_image(pct: float, color: str, size: int = 200) -> Image.Image:
    import math
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r = size // 2 - 10
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#E0E0E0")
    angle = -90 + (pct / 100) * 360
    start_angle = -90
    draw.pieslice([cx - r, cy - r, cx + r, cy + r], start=start_angle, end=angle, fill=color)
    inner_r = int(r * 0.6)
    draw.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r], fill="#FFFFFF")
    font = _load_font(int(size * 0.18), bold=True)
    text = f"{pct:.0f}%"
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        tw, th = int(size * 0.3), int(size * 0.18)
    draw.text((cx - tw // 2, cy - th // 2), text, fill=color, font=font)
    return img


# ── #1954: Katalogeinträge in der Sprache des Dokuments ──────────────────────
# Die Literale werden hier direkt gelesen; ohne diesen Helfer käme die
# englische Fassung (`titel_en`, `label_en`, `referenz_en`) nie an — die
# Übersetzung wäre vorhanden und wirkungslos (der Defekt aus #1735).
# `uebersetze` liefert **Kopien**: Das Modul-Literal wird von mehreren
# Anfragen gleichzeitig gelesen.
def _kat(eintrag: dict, sp: str) -> dict:
    from shared.katalog_sprache import uebersetze

    return uebersetze(eintrag or {}, sp)


def export_report_docx(
    *,
    out_dir: Path,
    projekt_name: str,
    unternehmen: str = "",
    einrichtungsklasse: str = "wesentlich",
    berater: str = "",
    bewertungen_raw: dict[str, dict[str, Any]],
    anforderungen: list[dict[str, Any]] | None = None,
    incl_massnahmen: bool = True,
    incl_details: bool = True,
    incl_referenzen: bool = True,
    pflicht_doku: dict[str, Any] | None = None,
    klassifikator: dict[str, Any] | None = None,
    sprache: str | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = date.today().strftime("%Y%m%d")
    out_path = out_dir / f"NIS2_Bericht_{_safe_filename(projekt_name)}_{ts}.docx"

    # #1954: Die Sprache des Dokuments bestimmt der **Mandant**; ein
    # ausdrücklich übergebener Wert übersteuert für diesen einen Lauf.
    sp = _rt.aufloesen("nis2", projekt_name, sprache)

    anf = anforderungen or NIS2_ANFORDERUNGEN
    ergebnis = berechne_reifegrad(bewertungen_raw, anf)
    pct = ergebnis["prozent"]
    # `label` kommt aus `nis2/requirements.EINRICHTUNGSKLASSEN` und ist (noch)
    # nur deutsch vorhanden — siehe Bericht zu #1954.
    ekl_label = _kat(EINRICHTUNGSKLASSEN.get(einrichtungsklasse, {}),
                     sp).get("label", einrichtungsklasse)

    if pct >= 70:
        ampel_color = _AMPEL_FARBEN["gruen"]
        ampel_text = _t(sp, "ampel_gruen")
    elif pct >= 40:
        ampel_color = _AMPEL_FARBEN["orange"]
        ampel_text = _t(sp, "ampel_orange")
    else:
        ampel_color = _AMPEL_FARBEN["rot"]
        ampel_text = _t(sp, "ampel_rot")

    doc = Document()
    from shared.reports.docx_pdf import set_a4 as _a4
    # Die Dokumentsprache (`w:lang`) wird nur gesetzt, wenn sie vom Standard
    # abweicht: Für Deutsch war sie vor #1954 nicht gesetzt, und „auf Deutsch
    # byte-identisch" ist der Regressionsschutz dieses Vorgangs. `None` heißt im
    # Helfer ausdrücklich „nicht anfassen".
    _a4(doc, sprache=sp if sp != "de" else None)  # #1614 A4
    for section in doc.sections:
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)

    # ── Deckblatt ──────────────────────────────────────────────────────────────
    _banner(doc, _t(sp, "titel"), _NIS2_BLUE, size=22)
    _banner(doc, _t(sp, "untertitel"), _DARK, size=11)
    doc.add_paragraph()

    meta_tbl = doc.add_table(rows=6, cols=2)
    meta_tbl.autofit = False
    meta_data = [
        (_t(sp, "m_projekt"), projekt_name),
        (_t(sp, "m_unternehmen"), unternehmen),
        (_t(sp, "m_klasse"), ekl_label),
        (_t(sp, "m_berater"), berater),
        (_t(sp, "m_erstellt"), date.today().strftime(_t(sp, "datum_format"))),
        (_t(sp, "m_rechtsgrundlage"), _t(sp, "rechtsquelle")),
    ]
    for i, (label, value) in enumerate(meta_data):
        c0, c1 = meta_tbl.cell(i, 0), meta_tbl.cell(i, 1)
        c0.width = Inches(1.8)
        c1.width = Inches(4.2)
        r0 = c0.paragraphs[0].add_run(label)
        r0.bold = True
        r0.font.size = Pt(10)
        r1 = c1.paragraphs[0].add_run(value)
        r1.font.size = Pt(10)

    doc.add_paragraph()
    _banner(doc, _t(sp, "gesamtergebnis", pct=f"{pct:.1f}%", ampel=ampel_text),
            ampel_color, size=13)
    doc.add_paragraph()

    # Gauge-Bild
    gauge = _gauge_image(pct, ampel_color)
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    gauge.save(tmp.name)
    tmp.close()
    try:
        doc.add_picture(tmp.name, width=Inches(2.2))
    finally:
        os.unlink(tmp.name)

    doc.add_page_break()

    # ── Executive Summary ──────────────────────────────────────────────────────
    _section_heading(doc, _t(sp, "h1"), _NIS2_BLUE)
    bewertet = sum(1 for r in anf if int(bewertungen_raw.get(r["id"], {}).get("bewertung", 0)) > 0)
    gesamt = len(anf)
    p = doc.add_paragraph(
        _t(sp, "summary", einrichtung=(unternehmen or projekt_name),
           gesamt=gesamt, bewertet=bewertet, pct=f"{pct:.1f}%",
           ampel=ampel_text)
    )
    p.paragraph_format.space_after = Pt(6)

    # ── Kapitel-Übersicht ──────────────────────────────────────────────────────
    _section_heading(doc, _t(sp, "h2"), _NIS2_BLUE)
    kap_scores = ergebnis["kapitel_scores"]
    overview_tbl = doc.add_table(rows=1 + len(KAPITEL), cols=4)
    overview_tbl.autofit = False
    headers = [_t(sp, "k_kapitel"), _t(sp, "k_referenz"),
               _t(sp, "k_reifegrad"), _t(sp, "k_bewertet")]
    col_widths = [Inches(2.4), Inches(1.6), Inches(1.6), Inches(0.9)]
    for i, (hdr, w) in enumerate(zip(headers, col_widths)):
        c = overview_tbl.cell(0, i)
        c.width = w
        _set_shading(c, _NIS2_BLUE)
        r = c.paragraphs[0].add_run(hdr)
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(255, 255, 255)

    for row_i, (kid, _kinfo_roh) in enumerate(KAPITEL.items(), start=1):
        kinfo = _kat(_kinfo_roh, sp)
        ks = kap_scores.get(kid, {})
        kpct = ks.get("prozent", 0.0)
        kbew = ks.get("bewertet", 0)
        kanz = ks.get("anzahl", 0)
        kfg, _ = _KAPITEL_FARBEN.get(kid, (_NIS2_BLUE, _SOFT))
        bg = "#F5F5F5" if row_i % 2 == 0 else "#FFFFFF"
        row_data = [kinfo["titel"], kinfo["referenz"], f"{kpct:.1f}%", f"{kbew}/{kanz}"]
        for ci, (val, w) in enumerate(zip(row_data, col_widths)):
            c = overview_tbl.cell(row_i, ci)
            c.width = w
            _set_shading(c, bg)
            _set_border(c)
            run = c.paragraphs[0].add_run(val)
            run.font.size = Pt(9)
            if ci == 2:
                run.bold = True
                rv, gv, bv = _hex_to_rgb(kfg)
                run.font.color.rgb = RGBColor(rv, gv, bv)

    doc.add_paragraph()

    # ── Lückenanalyse ──────────────────────────────────────────────────────────
    luecken = ergebnis["luecken"]
    if luecken:
        _section_heading(doc, _t(sp, "h3"), _NIS2_BLUE)
        for req in luecken[:20]:
            bew = bewertungen_raw.get(req["id"], {})
            bval = int(bew.get("bewertung", 0))
            bcolor = _BEWERTUNG_FARBEN.get(bval, "#9E9E9E")
            kfg, _ = _KAPITEL_FARBEN.get(req["kapitel"], (_NIS2_BLUE, _SOFT))
            _banner(doc, f"{req['id']}  –  {req['titel']}", kfg, size=10)
            info_tbl = doc.add_table(rows=2, cols=2)
            info_tbl.autofit = False
            for ci in range(2):
                info_tbl.cell(0, ci).width = Inches(3.0)
                info_tbl.cell(1, ci).width = Inches(3.0)
            c00 = info_tbl.cell(0, 0)
            # `label` aus `nis2/requirements.BEWERTUNG_SKALA` — nur deutsch
            # vorhanden, siehe Bericht zu #1954.
            r00 = c00.paragraphs[0].add_run(
                _t(sp, "l_bewertung", wert=bval,
                   label=_kat(BEWERTUNG_SKALA.get(bval, {}),
                              sp).get('label', '')))
            r00.bold = True
            r00.font.size = Pt(9)
            rv, gv, bv = _hex_to_rgb(bcolor)
            r00.font.color.rgb = RGBColor(rv, gv, bv)
            c01 = info_tbl.cell(0, 1)
            c01.paragraphs[0].add_run(
                _t(sp, "l_referenz", ref=req['ref'])).font.size = Pt(9)
            c10 = info_tbl.cell(1, 0)
            c10.merge(info_tbl.cell(1, 1))
            c10.paragraphs[0].add_run(req["beschreibung"]).font.size = Pt(8)

            if incl_massnahmen and bew.get("massnahme"):
                mp = doc.add_paragraph()
                mr = mp.add_run(_t(sp, "l_massnahme", massnahme=bew['massnahme']))
                mr.italic = True
                mr.font.size = Pt(8)

            doc.add_paragraph()

    # ── Detailbewertungen ──────────────────────────────────────────────────────
    if incl_details:
        _section_heading(doc, _t(sp, "h4"), _NIS2_BLUE)
        by_kap: dict[str, list] = defaultdict(list)
        for req in anf:
            by_kap[req["kapitel"]].append(req)

        for kid, kreqs in by_kap.items():
            kinfo = _kat(KAPITEL[kid], sp)
            kfg, kbg = _KAPITEL_FARBEN.get(kid, (_NIS2_BLUE, _SOFT))
            _banner(doc, f"{kinfo['titel']}  ·  {kinfo['referenz']}", kfg, size=11)

            detail_tbl = doc.add_table(rows=1 + len(kreqs), cols=4)
            detail_tbl.autofit = False
            detail_headers = [_t(sp, "d_id"), _t(sp, "d_anforderung"),
                              _t(sp, "d_bewertung"), _t(sp, "d_kommentar")]
            detail_widths = [Inches(0.7), Inches(2.3), Inches(1.1), Inches(2.0)]
            for ci, (hdr, w) in enumerate(zip(detail_headers, detail_widths)):
                c = detail_tbl.cell(0, ci)
                c.width = w
                _set_shading(c, kfg)
                r = c.paragraphs[0].add_run(hdr)
                r.bold = True
                r.font.size = Pt(9)
                r.font.color.rgb = RGBColor(255, 255, 255)

            for ri, req in enumerate(kreqs, start=1):
                bew = bewertungen_raw.get(req["id"], {})
                bval = int(bew.get("bewertung", 0))
                bcolor = _BEWERTUNG_FARBEN.get(bval, "#9E9E9E")
                row_bg = kbg if ri % 2 == 0 else "#FFFFFF"
                row_data = [
                    req["id"],
                    req["titel"],
                    f"{bval} – "
                    f"{_kat(BEWERTUNG_SKALA.get(bval, {}), sp).get('label', '')}",
                    _ohne_ki_marker(bew.get("kommentar", "")),
                ]
                for ci, (val, w) in enumerate(zip(row_data, detail_widths)):
                    c = detail_tbl.cell(ri, ci)
                    c.width = w
                    _set_shading(c, row_bg)
                    _set_border(c)
                    run = c.paragraphs[0].add_run(val)
                    run.font.size = Pt(8)
                    if ci == 2:
                        run.bold = True
                        rv, gv, bv = _hex_to_rgb(bcolor)
                        run.font.color.rgb = RGBColor(rv, gv, bv)

            doc.add_paragraph()

    # ── Pflicht-Doku-Nachweis (Sprint β) ───────────────────────────────────────
    if pflicht_doku:
        _section_heading(doc, _t(sp, "h5"), _NIS2_BLUE)

        # Klassifikator-Ergebnis
        if klassifikator and klassifikator.get('klasse'):
            # `klasse` ist der **Datenwert** ('wesentlich'|'wichtig'|…) und
            # wird roh in Großbuchstaben gedruckt — schon im deutschen
            # Bericht. Das bleibt so: Ein Datenwert wird nicht übersetzt
            # (BERICHTE.md, Regel 7); gemeldet, nicht geglättet.
            _banner(doc, _t(sp, "n6_klassifikation",
                            klasse=klassifikator['klasse'].upper()),
                    _NIS2_BLUE, size=11)
            if klassifikator.get('begruendung'):
                p = doc.add_paragraph(klassifikator['begruendung'])
                for r in p.runs:
                    r.font.size = Pt(9)
            if klassifikator.get('sektor'):
                doc.add_paragraph(
                    _t(sp, "n6_sektor", sektor=klassifikator['sektor'])
                ).runs[0].font.size = Pt(9)
            doc.add_paragraph()

        sections = [
            (_t(sp, "n1_titel"), pflicht_doku.get('assets') or [], [
                ('asset_name', _t(sp, "n1_asset")), ('asset_typ', _t(sp, "n1_typ")),
                ('kritikalitaet', _t(sp, "n1_krit")), ('schutzbedarf_v', _t(sp, "n1_v")),
                ('schutzbedarf_i', _t(sp, "n1_i")), ('schutzbedarf_a', _t(sp, "n1_a")),
            ]),
            (_t(sp, "n2_titel"), pflicht_doku.get('risiken') or [], [
                ('risiko_id', _t(sp, "n2_id")), ('titel', _t(sp, "n2_titel_sp")),
                ('auswirkung', _t(sp, "n2_auswirkung")), ('eintrittswkt', _t(sp, "n2_wkt")),
                ('risikoscore', _t(sp, "n2_score")), ('status', _t(sp, "n2_status")),
            ]),
            (_t(sp, "n4_titel"), pflicht_doku.get('vendors') or [], [
                ('vendor_name', _t(sp, "n4_vendor")), ('leistung', _t(sp, "n4_leistung")),
                ('kritikalitaet', _t(sp, "n4_krit")), ('assessment_score', _t(sp, "n4_score")),
                ('status', _t(sp, "n4_status")),
            ]),
        ]
        for title, items, cols in sections:
            doc.add_paragraph().add_run(
                _t(sp, "block_kopf", titel=title, anzahl=len(items))).bold = True
            if not items:
                doc.add_paragraph(_t(sp, "keine_eintraege")).runs[0].font.size = Pt(9)
                continue
            tbl = doc.add_table(rows=len(items) + 1, cols=len(cols))
            tbl.style = 'Light Grid Accent 1'
            for ci, (_, hdr) in enumerate(cols):
                c = tbl.cell(0, ci)
                c.paragraphs[0].add_run(hdr).bold = True
            for ri, item in enumerate(items, start=1):
                for ci, (key, _) in enumerate(cols):
                    v = item.get(key, '')
                    tbl.cell(ri, ci).paragraphs[0].add_run(str(v)[:60]).font.size = Pt(8)
            doc.add_paragraph()

        # N3 + N5 als Block-Status
        ir = pflicht_doku.get('incident_response') or {}
        if ir:
            doc.add_paragraph().add_run(_t(sp, "n3_titel")).bold = True
            for k, label in [('csirt_kontakt', _t(sp, "n3_csirt_kontakt")),
                              ('csirt_email', _t(sp, "n3_csirt_email")),
                              ('early_warning_sla', _t(sp, "n3_early_warning")),
                              ('notification_sla', _t(sp, "n3_notification")),
                              ('final_report_sla', _t(sp, "n3_final_report")),
                              ('incident_manager', _t(sp, "n3_manager"))]:
                if ir.get(k):
                    p = doc.add_paragraph(f"  • {label}: {ir[k]}")
                    p.runs[0].font.size = Pt(9)
            doc.add_paragraph()

        bcp = pflicht_doku.get('bcp') or {}
        if bcp:
            doc.add_paragraph().add_run(_t(sp, "n5_titel")).bold = True
            for k, label in [('rpo_minuten', _t(sp, "n5_rpo")),
                              ('rto_minuten', _t(sp, "n5_rto")),
                              ('backup_strategie', _t(sp, "n5_strategie")),
                              ('backup_haeufigkeit', _t(sp, "n5_haeufigkeit")),
                              ('dr_standort', _t(sp, "n5_dr")),
                              ('test_datum', _t(sp, "n5_test_datum")),
                              ('test_frequenz', _t(sp, "n5_test_frequenz"))]:
                if bcp.get(k):
                    p = doc.add_paragraph(f"  • {label}: {bcp[k]}")
                    p.runs[0].font.size = Pt(9)
            doc.add_paragraph()

        # Governance-Nachweise (Art. 20, #1212): Billigungsbeschluss / Review /
        # Schulung als Nachweis-Tabelle im Readiness-Report.
        governance = pflicht_doku.get('governance') or []
        doc.add_paragraph().add_run(
            _t(sp, "gov_kopf", anzahl=len(governance))).bold = True
        if not governance:
            doc.add_paragraph(_t(sp, "gov_keine")).runs[0].font.size = Pt(9)
        else:
            gcols = [('typ', _t(sp, "gov_typ")), ('datum', _t(sp, "gov_datum")),
                     ('gremium', _t(sp, "gov_gremium")),
                     ('gegenstand', _t(sp, "gov_gegenstand")),
                     ('naechster_review', _t(sp, "gov_review"))]
            gtbl = doc.add_table(rows=len(governance) + 1, cols=len(gcols))
            gtbl.style = 'Light Grid Accent 1'
            for ci, (_, hdr) in enumerate(gcols):
                gtbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
            for ri, g in enumerate(governance, start=1):
                for ci, (key, _) in enumerate(gcols):
                    gtbl.cell(ri, ci).paragraphs[0].add_run(
                        str(g.get(key, ''))[:60]).font.size = Pt(8)
            doc.add_paragraph()

    # ── Referenzen ─────────────────────────────────────────────────────────────
    if incl_referenzen:
        _section_heading(doc, _t(sp, "h6"), _NIS2_BLUE)
        for ref in _referenzen(sp):
            p = doc.add_paragraph(ref, style="List Bullet")
            p.paragraph_format.space_after = Pt(3)
            for run in p.runs:
                run.font.size = Pt(9)

    doc.save(str(out_path))
    return out_path


def export_report_pdf(**kwargs) -> Path:
    """#1614: PDF vektoriell aus dem DOCX (A4) statt Rasterbild."""
    from shared.reports.docx_pdf import docx_to_pdf_bytes
    docx_path = export_report_docx(**kwargs)
    pdf_path = Path(docx_path).with_suffix(".pdf")
    pdf_path.write_bytes(docx_to_pdf_bytes(docx_path))
    return pdf_path
