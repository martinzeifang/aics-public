"""CRA-Modul – Berichtsgenerator für Word (.docx) und PDF.

Erzeugt einen wissenschaftlich strukturierten CRA-Readiness-Bericht mit:
  - Deckblatt, Management Summary, Rechtlichem Rahmen
  - Methodik (Bewertungsskala, Quellenangaben)
  - Kapitelweise Anforderungsbewertung
  - Maßnahmenplan
  - Anhang mit Vollreferenzen

Quellenangaben orientieren sich an IEEE-Zitierstandard.

**Die Sprache gehört dem Mandanten (#1954).** Der Bericht geht an den
Mandanten; über seine Sprache entscheidet deshalb ``firmen.sprache`` und nicht
der Bearbeiter, der ihn zufällig erzeugt (aufgelöst in
:func:`export_report_docx` über ``shared.reports.texte.aufloesen``, fail-open
auf Deutsch).

Was dabei **deutsch bleibt und warum** — es sind durchgereichte Katalogwerte,
keine Prosa dieses Renderers:

* Anforderungstitel, ``ref`` und Kapitelangaben aus :mod:`cra.requirements`
  (``titel``, ``ref``, ``KAPITEL[...]``, ``BEWERTUNG_SKALA[...]['label']``,
  — seit #1954 über ``shared/katalog_sprache`` in beiden Sprachen,
  ``PRODUKTKLASSEN[...]``). Eine Fundstelle in einer Nachweisakte liest sich
  wie eine Feststellung und wird nicht nebenbei übersetzt (#1763/#1792/#1913).
* ``risiko_label`` der verknüpften Risikobewertung (inkl. ``unbewertet``) —
  ein Datenwert aus einem anderen Modul.
* :data:`REFERENZEN` — Literaturangaben zitieren Werktitel in ihrer
  Originalsprache; sie werden nicht übersetzt.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

from cra.requirements import (
    BEWERTUNG_SKALA,
    CRA_ANFORDERUNGEN,
    KAPITEL,
    PRODUKTKLASSEN,
    berechne_reifegrad,
)
from cra.db import load_owasp_checks
from cra.owasp_proactive_controls import OWASP_PC_V3
from shared.reports import texte as _rt

# ── Farb-Palette ──────────────────────────────────────────────────────────────
_EU_BLUE    = "#003399"
_DARK       = "#1a237e"
_SOFT       = "#e8eaf6"
_KAPITEL_FARBEN = {
    "AI1":   ("#1565C0", "#E3F2FD"),
    "AI2":   ("#4A148C", "#F3E5F5"),
    "ART13": ("#00695C", "#E0F2F1"),
    "ART14": ("#BF360C", "#FBE9E7"),
    "IMPL":  ("#2C3E50", "#ECF0F1"),
}
_BEWERTUNG_FARBEN = {
    0: "#9E9E9E", 1: "#C62828", 2: "#E65100",
    3: "#F57F17", 4: "#2E7D32", 5: "#1B5E20",
}
_AMPEL_FARBEN = {
    "gruen":  "#2e7d32",
    "orange": "#e65100",
    "rot":    "#c62828",
}

# ── Wissenschaftliche Quellenangaben (IEEE) ───────────────────────────────────
REFERENZEN = [
    "[1] European Parliament and Council of the European Union, "
    "\"Verordnung (EU) 2024/2847 of the European Parliament and of the Council "
    "on Horizontal Cybersecurity Requirements for Products with Digital Elements "
    "(Cyber Resilience Act),\" Official Journal of the European Union, L 2847, "
    "20 November 2024.",
    "[2] European Union Agency for Cybersecurity (ENISA), "
    "\"ENISA Threat Landscape 2024,\" ENISA, Heraklion, 2024.",
    "[3] International Organization for Standardization, "
    "\"ISO/IEC 27001:2022 – Information Security Management Systems – Requirements,\" "
    "ISO, Geneva, 2022.",
    "[4] International Organization for Standardization, "
    "\"ISO/IEC 27005:2022 – Guidance on Managing Information Security Risks,\" "
    "ISO, Geneva, 2022.",
    "[5] International Organization for Standardization and SAE International, "
    "\"ISO/SAE 21434:2021 – Road Vehicles – Cybersecurity Engineering,\" "
    "ISO, Geneva, 2021.",
    "[6] International Electrotechnical Commission, "
    "\"IEC 62443-3-2:2020 – Security for Industrial Automation and Control Systems – "
    "Part 3-2: Security Risk Assessment for System Design,\" IEC, Geneva, 2020.",
    "[7] European Commission, Directorate-General for Communications Networks, "
    "Content and Technology, \"The Cyber Resilience Act – Summary of the Legislative Text,\" "
    "European Commission, Brussels, 2024. [Online]. "
    "Available: https://digital-strategy.ec.europa.eu/en/policies/cra-summary",
    "[8] Bundesamt für Sicherheit in der Informationstechnik (BSI), "
    "\"Cyber Resilience Act – Informationen und Empfehlungen,\" BSI, Bonn, 2024. "
    "[Online]. Available: https://www.bsi.bund.de/cra",
    "[9] NTIA, \"The Minimum Elements for a Software Bill of Materials (SBOM),\" "
    "U.S. Department of Commerce, Washington, DC, 2021.",
    "[10] International Organization for Standardization, "
    "\"ISO/IEC 29147:2018 – Vulnerability Disclosure,\" ISO, Geneva, 2018.",
]


#: Die Prosa des Readiness-Berichts je Sprache (#1954).
#:
#: **Nummern und Fundstellen bleiben**, nur die Bezeichnung der Anlage wird
#: übersetzt („Anhang I Teil I" → „Annex I Part I"). Die Daten im rechtlichen
#: Rahmen sind gegen den amtlichen Text geprüft (Art. 71 „Inkrafttreten und
#: Geltungsbeginn": in Kraft am zwanzigsten Tag nach der Veröffentlichung vom
#: 20.11.2024, Geltungsbeginn 11.12.2027, Art. 14 ab 11.9.2026).
#:
#: Das **Datumsformat** steht im Katalog, weil ``05.11.2026`` englisch als
#: 11. Mai gelesen wird; englisch wird ISO geschrieben und nicht ``%d %B %Y``
#: (``%B`` hängt an der Locale des Containers).
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        "banner_titel": "CRA-READINESS-BERICHT",
        "banner_untertitel": "Cyber Resilience Act  ·  Verordnung (EU) 2024/2847",
        "m_projekt": "Projekt:",
        "m_unternehmen": "Unternehmen:",
        "m_produkt": "Produkt / Software:",
        "m_produktklasse": "Produktklasse:",
        "m_berater": "Berater:",
        "m_datum": "Berichtsdatum:",
        "leer": "–",
        "datumsformat": "%d.%m.%Y",
        "weg_banner": ("Konformitätsbewertungsweg: {weg}  ·  "
                       "Referenz: {referenz}"),

        "h1_summary": "1  MANAGEMENT SUMMARY",
        "kpi_reifegrad": "Gesamt-Reifegrad",
        "kpi_bewertet": "Bewertet",
        "kpi_fristen": "Fristen",
        "kpi_fristen_wert": "Sep 2026 · Dez 2027",
        "h_reifegrad_kapitel": "Reifegrad je Kapitel",
        "kapitel_balken": "{titel}  ({pct}%)",
        "h_kritisch": "⚠  Kritische Lücken (Gewichtung 3 / nicht erfüllt)",
        "kritisch_zeile": "{id} – {titel}  [{ref}]",

        "h2_recht": "2  RECHTLICHER RAHMEN",
        "r_rechtsgrundlage": "Rechtsgrundlage",
        "r_rechtsgrundlage_wert": (
            "Verordnung (EU) 2024/2847 des Europäischen Parlaments und des Rates "
            "über horizontale Cybersicherheitsanforderungen für Produkte mit "
            "digitalen Elementen (Cyber Resilience Act – CRA). "
            "Veröffentlicht im Amtsblatt der EU am 20. November 2024."),
        "r_geltungsbereich": "Geltungsbereich",
        "r_geltungsbereich_wert": (
            "Der CRA gilt für alle Hersteller, Importeure und Händler von Hard- und "
            "Softwareprodukten mit digitalen Elementen, die auf dem EU-Markt "
            "bereitgestellt werden (Art. 2 CRA). Ausgenommen sind u.a. "
            "Medizinprodukte (MDR/IVDR), Luftfahrt, Kfz (UN ECE R155/R156)."),
        "r_inkrafttreten": "Inkrafttreten",
        "r_inkrafttreten_wert": "10. Dezember 2024 (Art. 71 CRA)",
        "r_meldepflichten": "Meldepflichten (Art. 14)",
        "r_meldepflichten_wert": "11. September 2026",
        "r_anwendung": "Vollständige Anwendung",
        "r_anwendung_wert": "11. Dezember 2027",
        "r_produktklasse": "Produktklasse (dieses Projekts)",
        "r_weg": "Konformitätsbewertungsweg",
        "r_klasse_referenz": "Referenz der Produktklasse",

        "h3_methodik": "3  METHODIK DER BEWERTUNG",
        "methodik_text": (
            "Die vorliegende Readiness-Bewertung basiert auf einer strukturierten "
            "Gap-Analyse der CRA-Anforderungen aus Verordnung (EU) 2024/2847. "
            "Die Anforderungen wurden direkt aus dem Verordnungstext extrahiert und "
            "in fünf Domänen gegliedert: Produktsicherheitsanforderungen (Anhang I Teil I), "
            "Schwachstellenhandhabung (Anhang I Teil II), Herstellerpflichten (Art. 13), "
            "Meldepflichten (Art. 14) sowie organisatorische Implementierungsbereitschaft.\n\n"
            "Jede Anforderung wurde nach einer sechsstufigen Reifegradskala (0–5) bewertet, "
            "die sich an der IEC 62264 und CMMI-Maturity-Levels orientiert. "
            "Die Gewichtung (1–3) spiegelt die regulatorische Priorität wider: "
            "Anforderungen mit Gewichtung 3 sind direkt sanktionsrelevant."),
        "h_skala": "Bewertungsskala",
        "s_wert": "Wert",
        "s_bezeichnung": "Bezeichnung",
        "s_anteil": "Reifegrad-Anteil",
        "s_prozent": "{pct} %",

        "h4_kapitel": "4  KAPITELWEISE ANFORDERUNGSBEWERTUNG",
        "kap_banner": "{titel}  ·  Reifegrad: {pct}%",
        "kap_referenz": "Referenz: {referenz}  ·  {beschreibung}…",
        "t_id": "ID",
        "t_anforderung": "Anforderung",
        "t_referenz": "Referenz",
        "t_bewertung": "Bewertung",
        "t_kommentar": "Kommentar",

        "h5_massnahmen": "5  MAẞNAHMENPLAN",
        "massnahmen_text": (
            "Die folgenden Maßnahmen adressieren Anforderungen mit Bewertung < 4. "
            "Priorisierung: Gewichtung 3 = kritisch, 2 = wichtig, 1 = empfohlen."),
        "t_aktuell": "Aktuell",
        "t_massnahme": "Maßnahme",
        "t_verantwortlich": "Verantw. / Termin",

        "h6_owasp": "6  OWASP PROACTIVE CONTROLS – NACHWEISE",
        "owasp_text": (
            "Übersicht der OWASP Proactive Controls (C1–C10) und deren "
            "Implementierungsstatus. Evidence zeigt verfügbare Nachweise "
            "(Quellen, Evidenzpakete)."),
        "t_titel": "Titel",
        "t_status": "Status",
        "t_evidence": "Evidence",
        "owasp_evidence": "{anzahl} Einträge",
        "owasp_evidence_leer": "—",

        "h7_risiko": "7  RISIKOABSCHÄTZUNG (MODUL RISIKOBEWERTUNG)",
        "risiko_text": (
            "Die CRA-Cybersicherheits-Risikoabschätzung (Anhang I, Anforderung "
            "AI1-01) wird im Modul Risikobewertung geführt und hier als Nachweis "
            "referenziert."),
        "risiko_fehlt_banner": ("⚠  Keine verknüpfte Risikoabschätzung – "
                                "Nachweis fehlt"),
        "risiko_fehlt_text": (
            "Diesem CRA-Projekt ist kein Risikobewertungs-Projekt zugeordnet. "
            "Der Nachweis der Risikoabschätzung nach AI1-01 ist damit unvollständig. "
            "Bitte im Tab „Risikoanalyse“ ein Risikobewertungs-Projekt verknüpfen."),
        "risiko_verknuepft": ("Verknüpftes Projekt: {projekt}  ·  "
                              "Framework: {framework}"),
        "risiko_gesamt": "Risiken gesamt",
        "risiko_offen": "offen",
        "risiko_geloest": "gelöst",
        "risiko_verteilung": "Verteilung nach Risiko-Level:  {verteilung}",
        "h_top": "Top-Risiken (nach Risikowert)",
        "t_risiko": "Risiko",
        "t_level": "Level",
        "t_wert": "Wert",

        "h_anhang": "ANHANG  –  WISSENSCHAFTLICHE QUELLENANGABEN",
        "anhang_text": ("Die vorliegende Bewertung stützt sich auf folgende "
                        "normative und informative Quellen:"),
        "h_disclaimer": "Disclaimer",
        "disclaimer_text": (
            "Dieser Bericht gibt den Readiness-Stand zum Zeitpunkt der Bewertung wieder. "
            "Er ersetzt keine rechtliche Beratung und keine formale Konformitätsbewertung "
            "nach Verordnung (EU) 2024/2847. Für wichtige Produkte der Klasse II und "
            "kritische Produkte "
            "ist zwingend eine akkreditierte Konformitätsbewertungsstelle einzubeziehen."),
    },
    "en": {
        "banner_titel": "CRA READINESS REPORT",
        "banner_untertitel": ("Cyber Resilience Act  ·  "
                              "Regulation (EU) 2024/2847"),
        "m_projekt": "Project:",
        "m_unternehmen": "Company:",
        "m_produkt": "Product / software:",
        "m_produktklasse": "Product class:",
        "m_berater": "Consultant:",
        "m_datum": "Report date:",
        "leer": "–",
        "datumsformat": "%Y-%m-%d",
        "weg_banner": ("Conformity assessment route: {weg}  ·  "
                       "Reference: {referenz}"),

        "h1_summary": "1  MANAGEMENT SUMMARY",
        "kpi_reifegrad": "Overall maturity",
        "kpi_bewertet": "Assessed",
        "kpi_fristen": "Deadlines",
        "kpi_fristen_wert": "Sep 2026 · Dec 2027",
        "h_reifegrad_kapitel": "Maturity by chapter",
        "kapitel_balken": "{titel}  ({pct}%)",
        "h_kritisch": ("⚠  Critical gaps (weighting 3 / not fulfilled)"),
        "kritisch_zeile": "{id} – {titel}  [{ref}]",

        "h2_recht": "2  LEGAL FRAMEWORK",
        "r_rechtsgrundlage": "Legal basis",
        "r_rechtsgrundlage_wert": (
            "Regulation (EU) 2024/2847 of the European Parliament and of the "
            "Council on horizontal cybersecurity requirements for products with "
            "digital elements (Cyber Resilience Act – CRA). Published in the "
            "Official Journal of the EU on 20 November 2024."),
        "r_geltungsbereich": "Scope",
        "r_geltungsbereich_wert": (
            "The CRA applies to all manufacturers, importers and distributors of "
            "hardware and software products with digital elements made available "
            "on the EU market (Art. 2 CRA). Excluded are, among others, medical "
            "devices (MDR/IVDR), civil aviation and motor vehicles "
            "(UN ECE R155/R156)."),
        "r_inkrafttreten": "Entry into force",
        "r_inkrafttreten_wert": "10 December 2024 (Art. 71 CRA)",
        "r_meldepflichten": "Reporting obligations (Art. 14)",
        "r_meldepflichten_wert": "11 September 2026",
        "r_anwendung": "Full application",
        "r_anwendung_wert": "11 December 2027",
        "r_produktklasse": "Product class (of this project)",
        "r_weg": "Conformity assessment route",
        "r_klasse_referenz": "Reference of the product class",

        "h3_methodik": "3  ASSESSMENT METHODOLOGY",
        "methodik_text": (
            "This readiness assessment is based on a structured gap analysis of "
            "the CRA requirements set out in Regulation (EU) 2024/2847. The "
            "requirements were taken directly from the text of the Regulation "
            "and grouped into five domains: product security requirements "
            "(Annex I Part I), vulnerability handling (Annex I Part II), "
            "obligations of manufacturers (Art. 13), reporting obligations "
            "(Art. 14) and organisational readiness for implementation.\n\n"
            "Each requirement was rated on a six-level maturity scale (0–5) "
            "modelled on IEC 62264 and the CMMI maturity levels. The weighting "
            "(1–3) reflects the regulatory priority: requirements with "
            "weighting 3 are directly relevant to penalties."),
        "h_skala": "Rating scale",
        "s_wert": "Value",
        "s_bezeichnung": "Designation",
        "s_anteil": "Share of maturity",
        "s_prozent": "{pct} %",

        "h4_kapitel": "4  REQUIREMENT ASSESSMENT BY CHAPTER",
        "kap_banner": "{titel}  ·  Maturity: {pct}%",
        "kap_referenz": "Reference: {referenz}  ·  {beschreibung}…",
        "t_id": "ID",
        "t_anforderung": "Requirement",
        "t_referenz": "Reference",
        "t_bewertung": "Rating",
        "t_kommentar": "Comment",

        "h5_massnahmen": "5  ACTION PLAN",
        "massnahmen_text": (
            "The following measures address requirements rated below 4. "
            "Prioritisation: weighting 3 = critical, 2 = important, "
            "1 = recommended."),
        "t_aktuell": "Current",
        "t_massnahme": "Measure",
        "t_verantwortlich": "Owner / due date",

        # „OWASP Proactive Controls" ist der Eigenname des Katalogs und bleibt.
        "h6_owasp": "6  OWASP PROACTIVE CONTROLS – EVIDENCE",
        "owasp_text": (
            "Overview of the OWASP Proactive Controls (C1–C10) and their "
            "implementation status. Evidence shows the available records "
            "(sources, evidence packages)."),
        "t_titel": "Title",
        "t_status": "Status",
        "t_evidence": "Evidence",
        "owasp_evidence": "{anzahl} entries",
        "owasp_evidence_leer": "—",

        "h7_risiko": "7  RISK ASSESSMENT (RISK ASSESSMENT MODULE)",
        "risiko_text": (
            "The CRA cybersecurity risk assessment (Annex I, requirement "
            "AI1-01) is maintained in the risk assessment module and "
            "referenced here as evidence."),
        "risiko_fehlt_banner": ("⚠  No linked risk assessment – evidence "
                                "missing"),
        "risiko_fehlt_text": (
            "No risk assessment project is linked to this CRA project. The "
            "evidence of the risk assessment required by AI1-01 is therefore "
            "incomplete. Please link a risk assessment project on the "
            "“Risikoanalyse” tab."),
        "risiko_verknuepft": ("Linked project: {projekt}  ·  "
                              "Framework: {framework}"),
        "risiko_gesamt": "Risks in total",
        "risiko_offen": "open",
        "risiko_geloest": "resolved",
        "risiko_verteilung": "Distribution by risk level:  {verteilung}",
        "h_top": "Top risks (by risk score)",
        "t_risiko": "Risk",
        "t_level": "Level",
        "t_wert": "Score",

        "h_anhang": "ANNEX  –  SCIENTIFIC REFERENCES",
        "anhang_text": ("This assessment draws on the following normative and "
                        "informative sources:"),
        "h_disclaimer": "Disclaimer",
        "disclaimer_text": (
            "This report reflects the readiness status at the time of the "
            "assessment. It is no substitute for legal advice and no substitute "
            "for a formal conformity assessment under Regulation (EU) "
            "2024/2847. For important products of class II and for critical "
            "products, an accredited conformity assessment body must be "
            "involved."),
    },
}

_t = _rt.macher(TEXTE)


# #1765: Die alte Inline-Kennzeichnung („🤖 KI-generiert … fachlich zu
# prüfen") steht in Bestandstexten und gehört nicht in ein Dokument. Sie
# wird beim Drucken entfernt; die Herkunft führt `shared/ki_herkunft`.
from shared.ki_herkunft import bericht_text as _ki_bericht_text
from shared.ki_herkunft import fuer_projekt as _ki_herkunft_karte
from shared.ki_herkunft import ohne_marker as _ohne_ki_marker


def _safe_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "-", s or "")
    s = re.sub(r"\s+", "_", s).strip("_")
    return s[:100] or "CRA_Bericht"


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex_to_word(h: str) -> str:
    return h.lstrip("#").upper()


def _blend(c1: tuple, c2: tuple, t: float) -> tuple:
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


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


# ── DOCX helpers ──────────────────────────────────────────────────────────────

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
    filled_w = max(int(pct / 100 * 120), 2)
    empty_w = 120 - filled_w

    bar_tbl.columns[0].width = Inches(filled_w / 120 * 5.5)
    bar_tbl.columns[1].width = Inches(empty_w / 120 * 5.5)

    c1 = bar_tbl.cell(0, 0)
    _set_shading(c1, color)
    p = c1.paragraphs[0]
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)
    if pct >= 15:
        run = p.add_run(f" {pct:.0f}%")
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(255, 255, 255)

    c2 = bar_tbl.cell(0, 1)
    _set_shading(c2, "E0E0E0")

    lp = doc.add_paragraph(label)
    lp.runs[0].font.size = Pt(9)
    lp.paragraph_format.space_before = Pt(0)
    lp.paragraph_format.space_after = Pt(6)


# ── DOCX-Export ───────────────────────────────────────────────────────────────

def build_rb_risk_summary(db_path: Path | None, projekt_name: str) -> dict[str, Any]:
    """#888: Summary der verknüpften Risikoabschätzung (Modul Risikobewertung).

    Liefert immer ein Dict; ``linked=False`` wenn kein RB-Projekt verknüpft ist
    (der Report weist die fehlende Nachweis-Verknüpfung dann ausdrücklich aus —
    keine stillen Lücken). Bezug: AI1-01 (Nachweisbarkeit der Risikoabschätzung)."""
    result: dict[str, Any] = {
        'linked': False, 'rb_projekt': '', 'framework': '',
        'total': 0, 'offen': 0, 'geloest': 0, 'by_label': {}, 'top': [],
    }
    if not db_path:
        return result
    try:
        from cra.db import load_projekt
        p = load_projekt(db_path, projekt_name) or {}
        meta = p.get('meta') if isinstance(p.get('meta'), dict) else {}
        rb_name = (meta.get('linked_risk_projekt') or '').strip()
        if not rb_name:
            return result
        rb_db = Path('data/db/risikobewertung.sqlite')
        from risikobewertung.db import load_projekt as rb_load, load_risiken
        rb_proj = rb_load(rb_db, rb_name) or {}
        risiken = load_risiken(rb_db, rb_name)
        by_label: dict[str, int] = {}
        for r in risiken:
            lbl = r.get('risiko_label') or 'unbewertet'
            by_label[lbl] = by_label.get(lbl, 0) + 1
        geloest = sum(1 for r in risiken if r.get('is_resolved'))
        top = sorted(
            risiken, key=lambda r: (r.get('risikowert') or 0), reverse=True,
        )[:5]
        result.update({
            'linked': True,
            'rb_projekt': rb_name,
            'framework': rb_proj.get('framework', ''),
            'total': len(risiken),
            'offen': len(risiken) - geloest,
            'geloest': geloest,
            'by_label': by_label,
            'top': [{
                'name': r.get('risk_name', ''),
                'label': r.get('risiko_label', ''),
                'wert': r.get('risikowert'),
            } for r in top],
        })
    except Exception:
        # Fehler beim Laden darf den Report nicht abbrechen.
        return result
    return result


# ── #1954: Katalogeinträge in der Sprache des Dokuments ──────────────────────
# `CRA_ANFORDERUNGEN`, `KAPITEL`, `BEWERTUNG_SKALA` und `PRODUKTKLASSEN` sind
# Modul-Literale und werden hier direkt gelesen. Ohne diese Helfer käme die
# englische Fassung nie an — die Übersetzung wäre vorhanden und wirkungslos
# (der Defekt aus #1735). `uebersetze` liefert **Kopien**; das Literal bleibt
# unberührt, denn mehrere Anfragen lesen es gleichzeitig.
def _reqs(sp: str) -> list[dict]:
    from shared.katalog_sprache import uebersetze_viele

    return uebersetze_viele(CRA_ANFORDERUNGEN, sp)


def _kat(eintrag: dict, sp: str) -> dict:
    from shared.katalog_sprache import uebersetze

    return uebersetze(eintrag, sp)


def export_report_docx(
    *,
    out_dir: Path,
    projekt_name: str,
    unternehmen: str = "",
    produkt: str = "",
    produktklasse: str = "default",
    berater: str = "",
    bewertungen_raw: dict[str, dict[str, Any]],
    db_path: Path | None = None,
    incl_massnahmen: bool = True,
    incl_details: bool = True,
    incl_owasp: bool = True,
    incl_referenzen: bool = True,
    sprache: str | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Der **Dateiname** bleibt deutsch: Er ist kein Dokumentinhalt — der
    # Download-Name setzt `shared/reports/api.py`, und das Berichts-Center
    # liest hier nur die Bytes. Ein sprachabhängiger Pfad wäre eine zweite
    # Stelle, an der die Sprache wirkt, ohne im Dokument sichtbar zu sein.
    out_path = out_dir / f"CRA_Bericht_{_safe_filename(projekt_name)}_{date.today().isoformat()}.docx"

    sp = _rt.aufloesen("cra", projekt_name, sprache)
    leer = _t(sp, "leer")
    bewertungen = {rid: d["bewertung"] for rid, d in bewertungen_raw.items()}
    reife = berechne_reifegrad(bewertungen)
    pk_info = _kat(PRODUKTKLASSEN.get(produktklasse,
                                      PRODUKTKLASSEN["default"]), sp)
    ampel_farbe = _AMPEL_FARBEN.get(reife["ampel"], "#9e9e9e")

    doc = Document()
    from shared.reports.docx_pdf import set_a4 as _a4; _a4(doc, sprache=sp)  # #1614 A4
    sec = doc.sections[0]
    sec.top_margin = Inches(0.7)
    sec.bottom_margin = Inches(0.7)
    sec.left_margin = Inches(0.85)
    sec.right_margin = Inches(0.85)

    # ── 1. Deckblatt ──────────────────────────────────────────────────────────
    _banner(doc, _t(sp, "banner_titel"), _EU_BLUE, size=24)
    _banner(doc, _t(sp, "banner_untertitel"), "#001A66", size=11)

    meta_tbl = doc.add_table(rows=6, cols=2)
    meta_pairs = [
        (_t(sp, "m_projekt"), projekt_name),
        (_t(sp, "m_unternehmen"), unternehmen or leer),
        (_t(sp, "m_produkt"), produkt or leer),
        # `pk_info["label"]` kommt aus `cra/requirements.py` und wird nur
        # durchgereicht (siehe Modul-Docstring).
        (_t(sp, "m_produktklasse"), pk_info["label"]),
        (_t(sp, "m_berater"), berater or leer),
        (_t(sp, "m_datum"), date.today().strftime(_t(sp, "datumsformat"))),
    ]
    for i, (label, value) in enumerate(meta_pairs):
        c0, c1 = meta_tbl.cell(i, 0), meta_tbl.cell(i, 1)
        _set_shading(c0, _EU_BLUE)
        _set_shading(c1, _SOFT)
        p0, p1 = c0.paragraphs[0], c1.paragraphs[0]
        r0 = p0.add_run(label)
        r0.bold = True; r0.font.size = Pt(10); r0.font.color.rgb = RGBColor(255, 255, 255)
        p1.add_run(value).font.size = Pt(10)

    doc.add_paragraph()
    _banner(
        doc,
        _t(sp, "weg_banner", weg=pk_info['konformitaet'],
           referenz=pk_info['referenz']),
        "#E8EAF6", "#003399", size=9,
    )

    # ── 2. Management Summary ──────────────────────────────────────────────────
    doc.add_page_break()
    _banner(doc, _t(sp, "h1_summary"), _EU_BLUE)

    summary_tbl = doc.add_table(rows=1, cols=3)
    kpis = [
        (_t(sp, "kpi_reifegrad"), f"{reife['gesamt_pct']:.0f}%", ampel_farbe),
        (_t(sp, "kpi_bewertet"),
         f"{reife['bewertete_count']}/{reife['gesamt_count']}", "#1565c0"),
        (_t(sp, "kpi_fristen"), _t(sp, "kpi_fristen_wert"), "#bf360c"),
    ]
    for i, (label, value, color) in enumerate(kpis):
        cell = summary_tbl.cell(0, i)
        _set_shading(cell, color)
        _set_border(cell, "FFFFFF")
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(6)
        a = p.add_run(label + "\n")
        a.font.size = Pt(9); a.font.color.rgb = RGBColor(220, 220, 220)
        b = p.add_run(value)
        b.bold = True; b.font.size = Pt(20); b.font.color.rgb = RGBColor(255, 255, 255)

    doc.add_paragraph()
    _section_heading(doc, _t(sp, "h_reifegrad_kapitel"), _EU_BLUE)

    for kap_id, _kap_roh in KAPITEL.items():
        kap_info = _kat(_kap_roh, sp)
        kap_pct = reife["kapitel_pct"].get(kap_id, 0.0)
        kap_farbe, _ = _KAPITEL_FARBEN.get(kap_id, (_EU_BLUE, _SOFT))
        _maturity_bar_docx(doc, kap_pct, kap_farbe,
                           _t(sp, "kapitel_balken",
                              titel=kap_info['titel'].split('–')[0].strip(),
                              pct=f"{kap_pct:.0f}"))

    doc.add_paragraph()
    kritisch = [
        r for r in _reqs(sp)
        if bewertungen.get(r["id"], 0) in (0, 1) and r["gewichtung"] == 3
    ]
    if kritisch:
        _banner(doc, _t(sp, "h_kritisch"), "#BF360C", size=10)
        for req in kritisch[:5]:
            p = doc.add_paragraph(style="List Bullet")
            run = p.add_run(_t(sp, "kritisch_zeile", id=req['id'],
                               titel=req['titel'], ref=req['ref']))
            run.font.size = Pt(9)

    # ── 3. Rechtlicher Rahmen ──────────────────────────────────────────────────
    doc.add_page_break()
    _banner(doc, _t(sp, "h2_recht"), _EU_BLUE)

    rechtlich = [
        (_t(sp, "r_rechtsgrundlage"), _t(sp, "r_rechtsgrundlage_wert")),
        (_t(sp, "r_geltungsbereich"), _t(sp, "r_geltungsbereich_wert")),
        (_t(sp, "r_inkrafttreten"), _t(sp, "r_inkrafttreten_wert")),
        (_t(sp, "r_meldepflichten"), _t(sp, "r_meldepflichten_wert")),
        (_t(sp, "r_anwendung"), _t(sp, "r_anwendung_wert")),
        (_t(sp, "r_produktklasse"), pk_info["label"]),
        (_t(sp, "r_weg"), pk_info["konformitaet"]),
        (_t(sp, "r_klasse_referenz"), pk_info["referenz"]),
    ]
    for label, value in rechtlich:
        tbl = doc.add_table(rows=1, cols=2)
        tbl.columns[0].width = Inches(2.0)
        tbl.columns[1].width = Inches(4.5)
        c0, c1 = tbl.cell(0, 0), tbl.cell(0, 1)
        _set_shading(c0, _EU_BLUE); _set_shading(c1, _SOFT)
        _set_border(c0, "FFFFFF"); _set_border(c1, "CCCCCC")
        r0 = c0.paragraphs[0].add_run(label)
        r0.bold = True; r0.font.size = Pt(9); r0.font.color.rgb = RGBColor(255, 255, 255)
        r1 = c1.paragraphs[0].add_run(value)
        r1.font.size = Pt(9)

    # ── 4. Methodik ────────────────────────────────────────────────────────────
    doc.add_page_break()
    _banner(doc, _t(sp, "h3_methodik"), _EU_BLUE)

    meth_text = _t(sp, "methodik_text")
    doc.add_paragraph(meth_text).runs[0].font.size = Pt(10)

    doc.add_paragraph()
    _section_heading(doc, _t(sp, "h_skala"), _EU_BLUE)
    scale_tbl = doc.add_table(rows=1 + len(BEWERTUNG_SKALA), cols=3)
    for i, header in enumerate((_t(sp, "s_wert"), _t(sp, "s_bezeichnung"),
                                _t(sp, "s_anteil"))):
        cell = scale_tbl.cell(0, i)
        _set_shading(cell, _EU_BLUE)
        run = cell.paragraphs[0].add_run(header)
        run.bold = True; run.font.size = Pt(9); run.font.color.rgb = RGBColor(255, 255, 255)

    for row_i, (val, info) in enumerate(BEWERTUNG_SKALA.items(), start=1):
        farbe = _BEWERTUNG_FARBEN.get(val, "#9E9E9E")
        c0 = scale_tbl.cell(row_i, 0)
        _set_shading(c0, farbe)
        r0 = c0.paragraphs[0].add_run(str(val))
        r0.bold = True; r0.font.size = Pt(10); r0.font.color.rgb = RGBColor(255, 255, 255)
        # `info["label"]` ist die Skalen-Bezeichnung aus `cra/requirements.py`
        # und wird nur durchgereicht (siehe Modul-Docstring).
        scale_tbl.cell(row_i, 1).paragraphs[0].add_run(info["label"]).font.size = Pt(9)
        scale_tbl.cell(row_i, 2).paragraphs[0].add_run(
            _t(sp, "s_prozent", pct=info['reife_pct'])
        ).font.size = Pt(9)

    # ── 5. Kapitelweise Bewertung ──────────────────────────────────────────────
    if incl_details:
        doc.add_page_break()
        _banner(doc, _t(sp, "h4_kapitel"), _EU_BLUE)

        by_kapitel: dict[str, list] = defaultdict(list)
        for req in _reqs(sp):
            by_kapitel[req["kapitel"]].append(req)

        for kap_id, reqs in by_kapitel.items():
            kap_info = _kat(KAPITEL[kap_id], sp)
            kap_farbe, kap_soft = _KAPITEL_FARBEN.get(kap_id, (_EU_BLUE, _SOFT))
            kap_pct = reife["kapitel_pct"].get(kap_id, 0.0)

            _banner(doc, _t(sp, "kap_banner", titel=kap_info['titel'],
                            pct=f"{kap_pct:.0f}"), kap_farbe)
            _banner(
                doc,
                _t(sp, "kap_referenz", referenz=kap_info['referenz'],
                   beschreibung=kap_info['beschreibung'][:120]),
                kap_soft, kap_farbe, size=9,
            )
            doc.add_paragraph()

            req_tbl = doc.add_table(rows=1, cols=5)
            for i, hdr in enumerate((_t(sp, "t_id"), _t(sp, "t_anforderung"),
                                     _t(sp, "t_referenz"), _t(sp, "t_bewertung"),
                                     _t(sp, "t_kommentar"))):
                cell = req_tbl.cell(0, i)
                _set_shading(cell, kap_farbe)
                run = cell.paragraphs[0].add_run(hdr)
                run.bold = True; run.font.size = Pt(8); run.font.color.rgb = RGBColor(255, 255, 255)

            widths = [0.7, 2.2, 1.6, 1.0, 2.0]
            for i, w in enumerate(widths):
                req_tbl.columns[i].width = Inches(w)

            # #1765: Welche Bewertungen sind ungepruefte KI-Entwuerfe? Einmal
            # je Bericht geladen, nicht je Zeile.
            try:
                _ki = _ki_herkunft_karte("cra", projekt_name, "requirement")
            except Exception:  # noqa: BLE001 — ein Bericht scheitert nicht daran
                _ki = {}

            for ridx, req in enumerate(reqs):
                rid = req["id"]
                bew_data = bewertungen_raw.get(rid, {})
                bval = bew_data.get("bewertung", 0)
                binfo = _kat(BEWERTUNG_SKALA.get(bval,
                                                 BEWERTUNG_SKALA[0]), sp)
                bfarbe = _BEWERTUNG_FARBEN.get(bval, "#9E9E9E")
                row_bg = kap_soft if ridx % 2 == 0 else "#FFFFFF"
                # #1765: Ein ungeprüfter Entwurf wird hier gedruckt, aber als
                # solcher ausgewiesen — der interne Bericht ist der Ort, an dem
                # der Vorbehalt hingehört. In die Konformitätsunterlagen und in
                # die Kundenfassung kommt er gar nicht.
                kommentar = _ki_bericht_text(bew_data.get("kommentar", ""),
                                             _ki.get(rid)) or leer

                row = req_tbl.add_row().cells
                for cell in row:
                    _set_border(cell, "DDDDDD")

                _set_shading(row[0], kap_soft)
                row[0].paragraphs[0].add_run(rid).font.size = Pt(8)
                _set_shading(row[1], row_bg)
                r = row[1].paragraphs[0].add_run(req["titel"])
                r.font.size = Pt(8); r.bold = True
                _set_shading(row[2], row_bg)
                row[2].paragraphs[0].add_run(req["ref"]).font.size = Pt(7)
                _set_shading(row[3], bfarbe)
                r3 = row[3].paragraphs[0].add_run(binfo["label"])
                r3.font.size = Pt(8); r3.bold = True; r3.font.color.rgb = RGBColor(255, 255, 255)
                _set_shading(row[4], row_bg)
                row[4].paragraphs[0].add_run(kommentar[:200]).font.size = Pt(8)

            doc.add_paragraph()

    # ── 6. Maßnahmenplan ──────────────────────────────────────────────────────
    if incl_massnahmen:
        doc.add_page_break()
        _banner(doc, _t(sp, "h5_massnahmen"), _EU_BLUE)
        doc.add_paragraph(_t(sp, "massnahmen_text")).runs[0].font.size = Pt(10)
        doc.add_paragraph()

        massnahmen = [
            r for r in _reqs(sp)
            if bewertungen.get(r["id"], 0) < 4 and bewertungen.get(r["id"], 0) > 0
               or bewertungen.get(r["id"], 0) == 0
        ]
        massnahmen.sort(key=lambda r: (-r["gewichtung"], bewertungen.get(r["id"], 0)))

        ma_tbl = doc.add_table(rows=1, cols=5)
        for i, hdr in enumerate((_t(sp, "t_id"), _t(sp, "t_anforderung"),
                                 _t(sp, "t_aktuell"), _t(sp, "t_massnahme"),
                                 _t(sp, "t_verantwortlich"))):
            cell = ma_tbl.cell(0, i)
            _set_shading(cell, _EU_BLUE)
            run = cell.paragraphs[0].add_run(hdr)
            run.bold = True; run.font.size = Pt(8); run.font.color.rgb = RGBColor(255, 255, 255)
        for i, w in enumerate([0.7, 2.0, 1.0, 2.5, 1.3]):
            ma_tbl.columns[i].width = Inches(w)

        for ridx, req in enumerate(massnahmen[:30]):
            rid = req["id"]
            bew_data = bewertungen_raw.get(rid, {})
            bval = bew_data.get("bewertung", 0)
            binfo = _kat(BEWERTUNG_SKALA.get(bval, BEWERTUNG_SKALA[0]), sp)
            bfarbe = _BEWERTUNG_FARBEN.get(bval, "#9E9E9E")
            massnahme = bew_data.get("massnahme", "") or req["hinweise"][:120]
            verantw = bew_data.get("verantwortlich", "")
            ziel = bew_data.get("zieldatum", "")
            verantw_text = f"{verantw}\n{ziel}".strip()

            row = ma_tbl.add_row().cells
            row_bg = "#FFF3E0" if req["gewichtung"] == 3 else ("#F3E5F5" if req["gewichtung"] == 2 else "#F5F5F5")
            for cell in row:
                _set_border(cell, "DDDDDD")
                _set_shading(cell, row_bg)

            row[0].paragraphs[0].add_run(rid).font.size = Pt(8)
            r = row[1].paragraphs[0].add_run(req["titel"])
            r.font.size = Pt(8); r.bold = (req["gewichtung"] == 3)
            _set_shading(row[2], bfarbe)
            r2 = row[2].paragraphs[0].add_run(binfo["label"])
            r2.font.size = Pt(8); r2.font.color.rgb = RGBColor(255, 255, 255)
            row[3].paragraphs[0].add_run(massnahme[:200]).font.size = Pt(8)
            row[4].paragraphs[0].add_run(verantw_text).font.size = Pt(8)

    # ── 6b. OWASP Proactive Controls – Nachweise ────────────────────────────
    if incl_owasp and db_path:
        doc.add_page_break()
        _banner(doc, _t(sp, "h6_owasp"), _EU_BLUE)
        doc.add_paragraph(_t(sp, "owasp_text")).runs[0].font.size = Pt(10)
        doc.add_paragraph()

        owasp_checks = load_owasp_checks(db_path, projekt_name)
        owasp_by_id = {oc["id"]: oc for oc in OWASP_PC_V3}

        ow_tbl = doc.add_table(rows=1, cols=4)
        for i, hdr in enumerate((_t(sp, "t_id"), _t(sp, "t_titel"),
                                 _t(sp, "t_status"), _t(sp, "t_evidence"))):
            cell = ow_tbl.cell(0, i)
            _set_shading(cell, _EU_BLUE)
            run = cell.paragraphs[0].add_run(hdr)
            run.bold = True; run.font.size = Pt(8); run.font.color.rgb = RGBColor(255, 255, 255)
        for i, w in enumerate([0.8, 3.5, 1.5, 1.5]):
            ow_tbl.columns[i].width = Inches(w)

        for oc in OWASP_PC_V3:
            check = owasp_checks.get(oc["id"], {})
            status = check.get("status", 0)
            binfo = BEWERTUNG_SKALA.get(status, BEWERTUNG_SKALA[0])
            bfarbe = _BEWERTUNG_FARBEN.get(status, "#9E9E9E")
            evidence_json = check.get("evidence_json", [])
            evidence_text = (_t(sp, "owasp_evidence", anzahl=len(evidence_json))
                             if evidence_json else _t(sp, "owasp_evidence_leer"))

            row = ow_tbl.add_row().cells
            row_bg = "#F5F5F5"
            for cell in row:
                _set_border(cell, "DDDDDD")
                _set_shading(cell, row_bg)

            row[0].paragraphs[0].add_run(oc["id"]).font.size = Pt(8)
            # `title` ist der englische Originalname des OWASP-Katalogs und
            # bleibt in jeder Sprache stehen (Entscheidung zu
            # `cra/owasp_proactive_controls.py`).
            r = row[1].paragraphs[0].add_run(oc["title"])
            r.font.size = Pt(8); r.bold = True
            _set_shading(row[2], bfarbe)
            r2 = row[2].paragraphs[0].add_run(binfo["label"])
            r2.font.size = Pt(8); r2.font.color.rgb = RGBColor(255, 255, 255)
            row[3].paragraphs[0].add_run(evidence_text).font.size = Pt(8)

    # ── 6c. Risikoabschätzung (Modul Risikobewertung) — Nachweis AI1-01 (#888) ──
    rb_sum = build_rb_risk_summary(db_path, projekt_name)
    doc.add_page_break()
    _banner(doc, _t(sp, "h7_risiko"), _EU_BLUE)
    doc.add_paragraph(_t(sp, "risiko_text")).runs[0].font.size = Pt(10)
    if not rb_sum["linked"]:
        _banner(doc, _t(sp, "risiko_fehlt_banner"), "#BF360C", size=10)
        doc.add_paragraph(_t(sp, "risiko_fehlt_text")).runs[0].font.size = Pt(10)
    else:
        _section_heading(
            doc, _t(sp, "risiko_verknuepft", projekt=rb_sum['rb_projekt'],
                    framework=rb_sum['framework'] or leer), _EU_BLUE)
        kpi_tbl = doc.add_table(rows=1, cols=3)
        for i, (lbl, val) in enumerate([
            (_t(sp, "risiko_gesamt"), str(rb_sum["total"])),
            (_t(sp, "risiko_offen"), str(rb_sum["offen"])),
            (_t(sp, "risiko_geloest"), str(rb_sum["geloest"])),
        ]):
            c = kpi_tbl.cell(0, i)
            _set_shading(c, _SOFT)
            rp = c.paragraphs[0]
            r0 = rp.add_run(f"{val}\n"); r0.bold = True; r0.font.size = Pt(16)
            rp.add_run(lbl).font.size = Pt(9)
        doc.add_paragraph()
        if rb_sum["by_label"]:
            # `k` ist das `risiko_label` der Risikobewertung — ein Datenwert
            # aus einem anderen Modul und deshalb unverändert.
            verteilung = "  ·  ".join(f"{k}: {v}" for k, v in rb_sum["by_label"].items())
            doc.add_paragraph(
                _t(sp, "risiko_verteilung", verteilung=verteilung)
            ).runs[0].font.size = Pt(9)
        if rb_sum["top"]:
            _section_heading(doc, _t(sp, "h_top"), _EU_BLUE)
            top_tbl = doc.add_table(rows=1, cols=3)
            hdr = [_t(sp, "t_risiko"), _t(sp, "t_level"), _t(sp, "t_wert")]
            for i, h in enumerate(hdr):
                c = top_tbl.cell(0, i); _set_shading(c, _EU_BLUE)
                rr = c.paragraphs[0].add_run(h); rr.bold = True
                rr.font.size = Pt(9); rr.font.color.rgb = RGBColor(255, 255, 255)
            for t in rb_sum["top"]:
                row = top_tbl.add_row().cells
                row[0].paragraphs[0].add_run(str(t["name"])).font.size = Pt(9)
                row[1].paragraphs[0].add_run(str(t["label"] or leer)).font.size = Pt(9)
                row[2].paragraphs[0].add_run(str(t["wert"] if t["wert"] is not None else leer)).font.size = Pt(9)

    # ── 8. Anhang: Referenzen ──────────────────────────────────────────────────
    if incl_referenzen:
        doc.add_page_break()
        _banner(doc, _t(sp, "h_anhang"), _EU_BLUE)
        doc.add_paragraph(_t(sp, "anhang_text")).runs[0].font.size = Pt(10)
        doc.add_paragraph()

        for ref in REFERENZEN:
            p = doc.add_paragraph(style="List Number")
            run = p.add_run(ref)
            run.font.size = Pt(9)

        doc.add_paragraph()
        _banner(doc, _t(sp, "h_disclaimer"), "#455a64", size=9)
        disclaimer_p = doc.add_paragraph(_t(sp, "disclaimer_text"))
        disclaimer_p.runs[0].font.size = Pt(9)
        disclaimer_p.runs[0].italic = True

    doc.save(str(out_path))
    return out_path


# ── PDF-Export ────────────────────────────────────────────────────────────────

def export_report_pdf(**kwargs) -> Path:
    """#1614: PDF vektoriell aus dem DOCX (A4) statt Rasterbild."""
    from shared.reports.docx_pdf import docx_to_pdf_bytes
    docx_path = export_report_docx(**kwargs)
    pdf_path = Path(docx_path).with_suffix(".pdf")
    pdf_path.write_bytes(docx_to_pdf_bytes(docx_path))
    return pdf_path
def _fit_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for para in str(text).splitlines() or [""]:
        words = para.split() or [""]
        cur = ""
        for word in words:
            trial = (cur + " " + word).strip()
            if draw.textlength(trial, font=font) <= max_width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        lines.append(cur)
    return lines or [""]
