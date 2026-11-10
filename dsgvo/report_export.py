"""DSGVO-Modul – Berichtsgenerator für Word (.docx) und PDF."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

from dsgvo.requirements import (
    BEWERTUNG_SKALA,
    DSGVO_ANFORDERUNGEN,
    KAPITEL,
    ORGANISATIONSTYPEN,
    berechne_reifegrad,
)
from shared.reports import texte as _rt

_EU_BLUE = "#003399"
_DARK = "#1a237e"
_SOFT = "#e8eaf6"
_KAPITEL_FARBEN = {
    "GDS1": ("#1565C0", "#E3F2FD"),
    "GDS2": ("#4A148C", "#F3E5F5"),
    "GDS3": ("#00695C", "#E0F2F1"),
    "GDS4": ("#BF360C", "#FBE9E7"),
    "GDS5": ("#E65100", "#FFF3E0"),
    "GDS6": ("#2C3E50", "#ECF0F1"),
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
    "\"Verordnung (EU) 2016/679 des Europäischen Parlaments und des Rates zum Schutz "
    "natürlicher Personen bei der Verarbeitung personenbezogener Daten, zum freien "
    "Datenverkehr und zur Aufhebung der Richtlinie 95/46/EG (DSGVO),\" "
    "Amtsblatt der EU, L 119, 4. Mai 2016.",
    "[2] Erwägungsgründe der Verordnung (EU) 2016/679, Erwägungsgründe 1–173.",
    "[3] Bundesbeauftragte für den Datenschutz und die Informationsfreiheit (BfDI), "
    "\"Kurzpapiere der DSK zu verschiedenen Themengebieten der DSGVO,\" BfDI, Bonn, 2018.",
    "[4] Datenschutzkonferenz (DSK), \"Orientierungshilfe zu Auftragsverarbeitungsverträgen,\" "
    "DSK, Berlin, 2019.",
    "[5] Artikel-29-Datenschutzgruppe / EDPB, \"Leitlinien zur Datenschutz-Folgenabschätzung (DSFA),\" "
    "WP248 rev.01, Brüssel, 2017.",
    "[6] European Data Protection Board (EDPB), \"Guidelines 01/2022 on data subject rights – "
    "Right of access,\" EDPB, Brussels, 2022.",
    "[7] EDPB, \"Guidelines 05/2022 on the use of cookies and similar tracking technologies,\" "
    "EDPB, Brussels, 2023.",
    "[8] Europäische Kommission, \"Angemessenheitsbeschlüsse – Liste der Drittländer mit "
    "angemessenem Datenschutzniveau.\" [Online]. "
    "Available: https://ec.europa.eu/info/law/law-topic/data-protection",
    "[9] Bundesamt für Sicherheit in der Informationstechnik (BSI), "
    "\"BSI-Grundschutz-Kompendium,\" BSI, Bonn, 2023.",
    "[10] International Organization for Standardization, "
    "\"ISO/IEC 27701:2019 – Privacy Information Management,\" ISO, Geneva, 2019.",
]

#: Dieselbe Quellenliste für das englische Dokument (#1954).
#:
#: **Übersetzt sind Urheber und Rolle, nicht die Titel deutschsprachiger
#: Veröffentlichungen.** Ein Titel ist die Kennung eines Dokuments: Wer die
#: „Kurzpapiere der DSK" oder die „Orientierungshilfe zu
#: Auftragsverarbeitungsverträgen" englisch übersetzt, nennt eine
#: Veröffentlichung, die es nicht gibt, und der Leser findet sie nicht — die
#: Lehre aus #1763/#1792, dort mit Fundstellen. Übersetzt wird deshalb nur,
#: wo eine **amtliche** englische Fassung existiert: [1] (Amtsblatt), [2],
#: [5] (WP248 ist im Original englisch), [8]. [6], [7] und [10] waren schon
#: englisch; [3], [4] und [9] behalten ihren Titel.
REFERENZEN_EN = [
    "[1] European Parliament and Council of the European Union, "
    "\"Regulation (EU) 2016/679 of the European Parliament and of the Council "
    "on the protection of natural persons with regard to the processing of "
    "personal data, on the free movement of such data and repealing Directive "
    "95/46/EC (GDPR),\" Official Journal of the EU, L 119, 4 May 2016.",
    "[2] Recitals of Regulation (EU) 2016/679, recitals 1–173.",
    "[3] Federal Commissioner for Data Protection and Freedom of Information "
    "(BfDI), \"Kurzpapiere der DSK zu verschiedenen Themengebieten der DSGVO,\" "
    "BfDI, Bonn, 2018.",
    "[4] Datenschutzkonferenz (DSK), \"Orientierungshilfe zu "
    "Auftragsverarbeitungsverträgen,\" DSK, Berlin, 2019.",
    "[5] Article 29 Data Protection Working Party / EDPB, \"Guidelines on Data "
    "Protection Impact Assessment (DPIA),\" WP248 rev.01, Brussels, 2017.",
    "[6] European Data Protection Board (EDPB), \"Guidelines 01/2022 on data subject rights – "
    "Right of access,\" EDPB, Brussels, 2022.",
    "[7] EDPB, \"Guidelines 05/2022 on the use of cookies and similar tracking technologies,\" "
    "EDPB, Brussels, 2023.",
    "[8] European Commission, \"Adequacy decisions – list of third countries "
    "with an adequate level of data protection.\" [Online]. "
    "Available: https://ec.europa.eu/info/law/law-topic/data-protection",
    "[9] Federal Office for Information Security (BSI), "
    "\"BSI-Grundschutz-Kompendium,\" BSI, Bonn, 2023.",
    "[10] International Organization for Standardization, "
    "\"ISO/IEC 27701:2019 – Privacy Information Management,\" ISO, Geneva, 2019.",
]

#: Die Texte des DSGVO-Gesamtberichts je Sprache (#1954).
#:
#: Der Bericht geht an den Mandanten, also entscheidet ``firmen.sprache`` über
#: seine Sprache (``shared/reports/texte``). Die deutschen Werte sind
#: zeichengenau die aus 8.3.4 — einschließlich der doppelten Leerzeichen in den
#: Bannern, des Halbgeviertstrichs als Platzhalter („–") und des
#: Großbuchstaben-ẞ in „MAẞNAHMENPLAN".
#:
#: Fundstellen bleiben unangetastet; auf Englisch heißt die Verordnung (EU)
#: 2016/679 amtlich „GDPR", die DSFA „DPIA" und der AVV „DPA" (Begriffsliste
#: #1954). Auch die inkonsistente Schreibweise der Spannen („Art. 12-22" mit
#: Bindestrich, „Art. 15–22" mit Halbgeviertstrich) ist übernommen statt
#: begradigt: Sie ist Bestand, und Begradigen wäre eine inhaltliche Änderung.
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        # ── DSMS-Anhang ────────────────────────────────────────────────────
        "dsms_banner": "DSMS-GESAMTBERICHT  –  DATENSCHUTZ-MANAGEMENTSYSTEM",
        "dsms_abschnitt": "{titel}  ({anzahl})",
        "dsms_tom": "TOM-Katalog nach Schutzzielen (Art. 25/32)",
        "dsms_tom_ziel": "Schutzziel",
        "dsms_tom_titel": "Maßnahme",
        "dsms_tom_ist": "Ist",
        "dsms_tom_soll": "Soll",
        "dsms_tom_verantwortlich": "Verantwortlich",
        "dsms_br": "Betroffenenrechte & Fristen (Art. 12-22)",
        "dsms_br_id": "ID",
        "dsms_br_typ": "Typ",
        "dsms_br_eingang": "Eingang",
        "dsms_br_frist": "Frist",
        "dsms_br_status": "Status",
        "dsms_tr": "Drittlandtransfers & TIA (Art. 44-49)",
        "dsms_tr_id": "ID",
        "dsms_tr_empfaenger": "Empfänger",
        "dsms_tr_drittland": "Drittland",
        "dsms_tr_grundlage": "Grundlage",
        "dsms_tr_tia": "TIA",
        "dsms_lk": "Löschkonzept / Aufbewahrungsfristen (Art. 17)",
        "dsms_lk_id": "ID",
        "dsms_lk_kategorie": "Datenkategorie",
        "dsms_lk_frist": "Frist",
        "dsms_lk_klasse": "Klasse",
        "dsms_lk_status": "Status",
        "dsms_ew": "Einwilligungs-Nachweise (Art. 7)",
        "dsms_ew_id": "ID",
        "dsms_ew_zweck": "Zweck",
        "dsms_ew_zeitpunkt": "Zeitpunkt",
        "dsms_ew_kanal": "Kanal",
        "dsms_ew_status": "Status",
        "dsms_dsb": "Datenschutzbeauftragter (Art. 37-39)",
        "dsb_typ": "Typ",
        "dsb_name": "Name",
        "dsb_bestelldatum": "Bestelldatum",
        "dsb_email": "Kontakt-E-Mail",
        "dsb_veroeffentlicht": "Kontakt veröffentlicht",
        "dsb_gemeldet": "Bei Aufsicht gemeldet",

        # ── Deckblatt ──────────────────────────────────────────────────────
        "titel": "DSGVO-COMPLIANCE-BERICHT",
        "untertitel": ("Verordnung (EU) 2016/679 – Datenschutz-Grundverordnung"
                       "  ·  Compliance-Assessment"),
        "m_projekt": "Projekt:",
        "m_unternehmen": "Unternehmen:",
        "m_organisationstyp": "Organisationstyp:",
        "m_berater": "Berater:",
        "m_berichtsdatum": "Berichtsdatum:",
        "rechtsgrundlage_banner": "Rechtsgrundlage: {wert}",

        # ── 1 Management Summary ───────────────────────────────────────────
        "h1": "1  MANAGEMENT SUMMARY",
        "kpi_reifegrad": "Gesamt-Reifegrad",
        "kpi_bewertet": "Bewertet",
        "kpi_frist": "Frist",
        "kpi_frist_wert": "DSGVO gilt seit 25.05.2018",
        "reifegrad_je_kapitel": "Reifegrad je Kapitel",
        "kapitel_balken": "{titel}  ({pct}%)",
        "kritisch_banner": "⚠  Kritische Lücken (Gewichtung 3 / nicht erfüllt)",
        "kritisch_zeile": "{id} – {titel}  [{ref}]",

        # ── 2 Rechtlicher Rahmen ───────────────────────────────────────────
        "h2": "2  RECHTLICHER RAHMEN",
        "r_rechtsgrundlage": "Rechtsgrundlage",
        "r_rechtsgrundlage_wert": (
            "Verordnung (EU) 2016/679 des Europäischen Parlaments und des Rates "
            "zum Schutz natürlicher Personen bei der Verarbeitung personenbezogener Daten "
            "(Datenschutz-Grundverordnung – DSGVO). Gültig seit 25. Mai 2018."),
        "r_geltungsbereich": "Geltungsbereich",
        "r_geltungsbereich_wert": (
            "Die DSGVO gilt für alle Verantwortlichen und Auftragsverarbeiter, die "
            "personenbezogene Daten von Personen in der EU verarbeiten, unabhängig vom Sitz."),
        "r_bussgeld": "Maximale Bußgelder",
        "r_bussgeld_wert": ("Bis zu 20 Mio. € oder 4 % des weltweiten "
                            "Jahresumsatzes (Art. 83 DSGVO)."),
        "r_meldepflicht": "Meldepflicht Datenpannen",
        "r_meldepflicht_wert": "72 Stunden an Aufsichtsbehörde (Art. 33 DSGVO).",
        "r_betroffenenrechte": "Betroffenenrechte",
        "r_betroffenenrechte_wert": ("Auskunft, Berichtigung, Löschung, "
                                     "Einschränkung, Portabilität, Widerspruch."),
        "r_organisationstyp": "Organisationstyp",

        # ── 3 Methodik ─────────────────────────────────────────────────────
        "h3": "3  METHODIK DER BEWERTUNG",
        "methodik": (
            "Die vorliegende DSGVO-Compliance-Bewertung basiert auf einer strukturierten "
            "Gap-Analyse der Anforderungen der Verordnung (EU) 2016/679. "
            "Die Anforderungen wurden direkt aus dem Verordnungstext extrahiert und in sechs "
            "Domänen gegliedert: Grundsätze & Rechtmäßigkeit, Betroffenenrechte, Pflichten des "
            "Verantwortlichen, Technische & Organisatorische Maßnahmen, Meldepflichten & DSFA "
            "sowie Datenschutzbeauftragter & Drittlandtransfer.\n\n"
            "Jede Anforderung wurde nach einer sechsstufigen Reifegradskala (0–5) bewertet. "
            "Die Gewichtung (1–3) spiegelt die regulatorische Priorität und das "
            "Bußgeldrisiko wider."),
        "bewertungsskala": "Bewertungsskala",
        "s_wert": "Wert",
        "s_bezeichnung": "Bezeichnung",
        "s_anteil": "Reifegrad-Anteil",
        "s_prozent": "{pct} %",

        # ── 4 Anforderungen ───────────────────────────────────────────────
        "h4": "4  KAPITELWEISE ANFORDERUNGSBEWERTUNG",
        "kapitel_banner": "{titel}  ·  Reifegrad: {pct}%",
        "referenz_banner": "Referenz: {wert}",
        "a_id": "ID",
        "a_anforderung": "Anforderung",
        "a_referenz": "Referenz",
        "a_bewertung": "Bewertung",
        "a_kommentar": "Kommentar",

        # ── 5 Maßnahmenplan ───────────────────────────────────────────────
        "h5": "5  MAẞNAHMENPLAN",
        "massnahmen_intro": (
            "Die folgenden Maßnahmen adressieren Anforderungen mit Bewertung < 4. "
            "Priorisierung: Gewichtung 3 = kritisch (hohes Bußgeldrisiko), "
            "2 = wichtig, 1 = empfohlen."),
        "ma_id": "ID",
        "ma_anforderung": "Anforderung",
        "ma_aktuell": "Aktuell",
        "ma_massnahme": "Maßnahme",
        "ma_verantwortlich": "Verantw. / Termin",

        # ── Anhang ────────────────────────────────────────────────────────
        "anhang_banner": "ANHANG  –  WISSENSCHAFTLICHE QUELLENANGABEN",
        "quellen_intro": ("Die vorliegende Bewertung stützt sich auf folgende "
                          "normative und informative Quellen:"),
        "disclaimer_banner": "Disclaimer",
        "disclaimer": (
            "Dieser Bericht gibt den Compliance-Stand zum Zeitpunkt der Bewertung wieder. "
            "Er ersetzt keine rechtliche Beratung durch einen Datenschutzjuristen. "
            "Bußgeldentscheidungen liegen im Ermessen der zuständigen "
            "Datenschutzaufsichtsbehörde."),

        # ── Pflicht-Dokumentation ─────────────────────────────────────────
        "pflicht_titel": "Pflicht-Dokumentation (Nachweise)",
        "pflicht_zeile": "{titel} — {anzahl} Einträge",
        "leer": "— Keine Einträge erfasst —",
        "d1": "D1 — Verarbeitungstätigkeiten (Art. 30)",
        "d1_id": "ID",
        "d1_name": "Name",
        "d1_zweck": "Zweck",
        "d1_rechtsgrundlage": "Rechtsgrundlage",
        "d2": "D2 — Technische/Organisatorische Maßnahmen (Art. 32)",
        "d2_kategorie": "Kategorie",
        "d2_massnahme": "Maßnahme",
        "d2_status": "Status",
        "d3": "D3 — Datenschutz-Folgenabschätzung (Art. 35)",
        "d3_id": "ID",
        "d3_titel": "Titel",
        "d3_restrisiko": "Restrisiko",
        "d3_status": "Status",
        "d4": "D4 — AVV-Tracker (Art. 28)",
        "d4_vendor": "Vendor",
        "d4_leistung": "Leistung",
        "d4_avv": "AVV",
        "d4_drittland": "Drittland-Garantie",
        "d5": "D5 — Datenpannen-Register (Art. 33-34)",
        "d5_id": "ID",
        "d5_titel": "Titel",
        "d5_festgestellt": "Festgestellt",
        "d5_risiko": "Risiko",
        "d5_status": "Status",

        #: Platzhalter für eine leere Angabe — ein Halbgeviertstrich, kein
        #: ``None`` (Regel 8 von #1954).
        "platzhalter": "–",
    },
    "en": {
        # ── DSMS-Anhang ────────────────────────────────────────────────────
        "dsms_banner": "DSMS OVERALL REPORT  –  DATA PROTECTION MANAGEMENT SYSTEM",
        "dsms_abschnitt": "{titel}  ({anzahl})",
        "dsms_tom": "TOM catalogue by protection goals (Art. 25/32)",
        "dsms_tom_ziel": "Protection goal",
        "dsms_tom_titel": "Measure",
        "dsms_tom_ist": "Actual",
        "dsms_tom_soll": "Target",
        "dsms_tom_verantwortlich": "Responsible",
        "dsms_br": "Data subject rights & deadlines (Art. 12-22)",
        "dsms_br_id": "ID",
        "dsms_br_typ": "Type",
        "dsms_br_eingang": "Received",
        "dsms_br_frist": "Deadline",
        "dsms_br_status": "Status",
        "dsms_tr": "Third-country transfers & TIA (Art. 44-49)",
        "dsms_tr_id": "ID",
        "dsms_tr_empfaenger": "Recipient",
        "dsms_tr_drittland": "Third country",
        "dsms_tr_grundlage": "Basis",
        "dsms_tr_tia": "TIA",
        "dsms_lk": "Erasure concept / retention periods (Art. 17)",
        "dsms_lk_id": "ID",
        "dsms_lk_kategorie": "Category of data",
        "dsms_lk_frist": "Period",
        "dsms_lk_klasse": "Class",
        "dsms_lk_status": "Status",
        "dsms_ew": "Records of consent (Art. 7)",
        "dsms_ew_id": "ID",
        "dsms_ew_zweck": "Purpose",
        "dsms_ew_zeitpunkt": "Time",
        "dsms_ew_kanal": "Channel",
        "dsms_ew_status": "Status",
        "dsms_dsb": "Data protection officer (Art. 37-39)",
        "dsb_typ": "Type",
        "dsb_name": "Name",
        "dsb_bestelldatum": "Date of designation",
        "dsb_email": "Contact email",
        "dsb_veroeffentlicht": "Contact published",
        "dsb_gemeldet": "Notified to the supervisory authority",

        # ── Deckblatt ──────────────────────────────────────────────────────
        "titel": "GDPR COMPLIANCE REPORT",
        "untertitel": ("Regulation (EU) 2016/679 – General Data Protection "
                       "Regulation  ·  Compliance assessment"),
        "m_projekt": "Project:",
        "m_unternehmen": "Company:",
        "m_organisationstyp": "Type of organisation:",
        "m_berater": "Consultant:",
        "m_berichtsdatum": "Report date:",
        "rechtsgrundlage_banner": "Legal basis: {wert}",

        # ── 1 Management Summary ───────────────────────────────────────────
        "h1": "1  MANAGEMENT SUMMARY",
        "kpi_reifegrad": "Overall maturity",
        "kpi_bewertet": "Assessed",
        "kpi_frist": "Deadline",
        "kpi_frist_wert": "GDPR applicable since 25 May 2018",
        "reifegrad_je_kapitel": "Maturity by chapter",
        "kapitel_balken": "{titel}  ({pct}%)",
        "kritisch_banner": "⚠  Critical gaps (weighting 3 / not met)",
        "kritisch_zeile": "{id} – {titel}  [{ref}]",

        # ── 2 Rechtlicher Rahmen ───────────────────────────────────────────
        "h2": "2  LEGAL FRAMEWORK",
        "r_rechtsgrundlage": "Legal basis",
        "r_rechtsgrundlage_wert": (
            "Regulation (EU) 2016/679 of the European Parliament and of the "
            "Council on the protection of natural persons with regard to the "
            "processing of personal data (General Data Protection Regulation – "
            "GDPR). Applicable since 25 May 2018."),
        "r_geltungsbereich": "Scope",
        "r_geltungsbereich_wert": (
            "The GDPR applies to all controllers and processors that process "
            "personal data of persons in the EU, irrespective of their place of "
            "establishment."),
        "r_bussgeld": "Maximum administrative fines",
        "r_bussgeld_wert": ("Up to EUR 20 million or 4 % of total worldwide "
                            "annual turnover (Art. 83 GDPR)."),
        "r_meldepflicht": "Duty to notify personal data breaches",
        "r_meldepflicht_wert": ("72 hours to the supervisory authority "
                                "(Art. 33 GDPR)."),
        "r_betroffenenrechte": "Data subject rights",
        "r_betroffenenrechte_wert": ("Access, rectification, erasure, "
                                     "restriction, portability, objection."),
        "r_organisationstyp": "Type of organisation",

        # ── 3 Methodik ─────────────────────────────────────────────────────
        "h3": "3  ASSESSMENT METHODOLOGY",
        "methodik": (
            "This GDPR compliance assessment is based on a structured gap "
            "analysis of the requirements of Regulation (EU) 2016/679. "
            "The requirements were taken directly from the text of the "
            "regulation and grouped into six domains: principles & lawfulness, "
            "data subject rights, obligations of the controller, technical & "
            "organisational measures, notification duties & DPIA, and data "
            "protection officer & third-country transfers.\n\n"
            "Each requirement was assessed on a six-level maturity scale (0–5). "
            "The weighting (1–3) reflects the regulatory priority and the risk "
            "of an administrative fine."),
        "bewertungsskala": "Assessment scale",
        "s_wert": "Value",
        "s_bezeichnung": "Designation",
        "s_anteil": "Share of maturity",
        "s_prozent": "{pct} %",

        # ── 4 Anforderungen ───────────────────────────────────────────────
        "h4": "4  REQUIREMENT ASSESSMENT BY CHAPTER",
        "kapitel_banner": "{titel}  ·  Maturity: {pct}%",
        "referenz_banner": "Reference: {wert}",
        "a_id": "ID",
        "a_anforderung": "Requirement",
        "a_referenz": "Reference",
        "a_bewertung": "Assessment",
        "a_kommentar": "Comment",

        # ── 5 Maßnahmenplan ───────────────────────────────────────────────
        "h5": "5  ACTION PLAN",
        "massnahmen_intro": (
            "The following measures address requirements assessed below 4. "
            "Prioritisation: weighting 3 = critical (high risk of an "
            "administrative fine), 2 = important, 1 = recommended."),
        "ma_id": "ID",
        "ma_anforderung": "Requirement",
        "ma_aktuell": "Current",
        "ma_massnahme": "Measure",
        "ma_verantwortlich": "Owner / due date",

        # ── Anhang ────────────────────────────────────────────────────────
        "anhang_banner": "ANNEX  –  ACADEMIC REFERENCES",
        "quellen_intro": ("This assessment draws on the following normative "
                          "and informative sources:"),
        "disclaimer_banner": "Disclaimer",
        "disclaimer": (
            "This report reflects the compliance status at the time of the "
            "assessment. It does not replace legal advice from a data "
            "protection lawyer. Decisions on administrative fines are at the "
            "discretion of the competent data protection supervisory "
            "authority."),

        # ── Pflicht-Dokumentation ─────────────────────────────────────────
        "pflicht_titel": "Mandatory documentation (evidence)",
        "pflicht_zeile": "{titel} — {anzahl} entries",
        "leer": "— No entries recorded —",
        "d1": "D1 — Processing activities (Art. 30)",
        "d1_id": "ID",
        "d1_name": "Name",
        "d1_zweck": "Purpose",
        "d1_rechtsgrundlage": "Legal basis",
        "d2": "D2 — Technical/organisational measures (Art. 32)",
        "d2_kategorie": "Category",
        "d2_massnahme": "Measure",
        "d2_status": "Status",
        "d3": "D3 — Data protection impact assessment (Art. 35)",
        "d3_id": "ID",
        "d3_titel": "Title",
        "d3_restrisiko": "Residual risk",
        "d3_status": "Status",
        "d4": "D4 — DPA tracker (Art. 28)",
        "d4_vendor": "Vendor",
        "d4_leistung": "Service",
        "d4_avv": "DPA",
        "d4_drittland": "Third-country safeguard",
        "d5": "D5 — Personal data breach register (Art. 33-34)",
        "d5_id": "ID",
        "d5_titel": "Title",
        "d5_festgestellt": "Detected",
        "d5_risiko": "Risk",
        "d5_status": "Status",

        "platzhalter": "–",
    },
}

_t = _rt.macher(TEXTE)


def _referenzen(sprache: str) -> list[str]:
    """Die Quellenliste in der Sprache des Dokuments."""
    return REFERENZEN_EN if sprache != "de" else REFERENZEN


# #1765: Die alte Inline-Kennzeichnung („🤖 KI-generiert … fachlich zu
# prüfen") steht in Bestandstexten und gehört nicht in ein Dokument. Sie
# wird beim Drucken entfernt; die Herkunft führt `shared/ki_herkunft`.
from shared.ki_herkunft import ohne_marker as _ohne_ki_marker


def _safe_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "-", s or "")
    s = re.sub(r"\s+", "_", s).strip("_")
    return s[:100] or "DSGVO_Bericht"


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


# ── DSMS-Gesamtbericht (#1113) ───────────────────────────────────────────────
# Spalten-Definition je DSMS-Bereich: (Kontext-Key, Überschrift, [(feld, label)])
#
# #1954: Überschrift und Spaltenetiketten stehen als **Katalogschlüssel** hier,
# der Text in ``TEXTE``. Die Struktur (Reihenfolge, Felder, Spaltenzahl) ist
# unverändert; nur die Beschriftung wird jetzt in der Sprache des Mandanten
# aufgelöst.
_DSMS_DOCX_SECTIONS = [
    ("tom_katalog", "dsms_tom",
     [("ziel", "dsms_tom_ziel"), ("titel", "dsms_tom_titel"),
      ("status", "dsms_tom_ist"), ("soll", "dsms_tom_soll"),
      ("verantwortlich", "dsms_tom_verantwortlich")]),
    ("betroffenenrechte", "dsms_br",
     [("antrag_id", "dsms_br_id"), ("typ", "dsms_br_typ"),
      ("eingang_datum", "dsms_br_eingang"),
      ("frist_datum", "dsms_br_frist"), ("status", "dsms_br_status")]),
    ("transfers", "dsms_tr",
     [("transfer_id", "dsms_tr_id"), ("empfaenger", "dsms_tr_empfaenger"),
      ("drittland", "dsms_tr_drittland"), ("grundlage", "dsms_tr_grundlage"),
      ("tia_status", "dsms_tr_tia")]),
    ("loeschregeln", "dsms_lk",
     [("regel_id", "dsms_lk_id"), ("datenkategorie", "dsms_lk_kategorie"),
      ("aufbewahrungsfrist", "dsms_lk_frist"), ("loeschklasse", "dsms_lk_klasse"),
      ("status", "dsms_lk_status")]),
    ("einwilligungen", "dsms_ew",
     [("einwilligung_id", "dsms_ew_id"), ("zweck", "dsms_ew_zweck"),
      ("zeitpunkt", "dsms_ew_zeitpunkt"), ("kanal", "dsms_ew_kanal"),
      ("status", "dsms_ew_status")]),
]


def _add_dsms_sections_docx(doc, dsms: dict[str, Any], sp: str = "de") -> None:
    """Hängt den DSMS-Gesamtbericht (zusätzliche Bereiche) an das DOCX an.

    Leere Bereiche werden übersprungen, damit ein Bericht ohne die jeweiligen
    Daten kompakt bleibt.
    """
    has_any = (
        any(dsms.get(k) for k, _, _ in _DSMS_DOCX_SECTIONS)
        or bool((dsms.get("dsb") or {}).get("vorhanden"))
    )
    if not has_any:
        return

    doc.add_page_break()
    _banner(doc, _t(sp, "dsms_banner"), _EU_BLUE)

    for key, titel_key, cols in _DSMS_DOCX_SECTIONS:
        items = dsms.get(key) or []
        if not items:
            continue
        _section_heading(doc, _t(sp, "dsms_abschnitt", titel=_t(sp, titel_key),
                                 anzahl=len(items)), _EU_BLUE)
        tbl = doc.add_table(rows=1, cols=len(cols))
        tbl.style = "Light Grid Accent 1"
        for ci, (_, hdr_key) in enumerate(cols):
            cell = tbl.cell(0, ci)
            _set_shading(cell, _EU_BLUE)
            run = cell.paragraphs[0].add_run(_t(sp, hdr_key))
            run.bold = True
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(255, 255, 255)
        for it in items:
            row = tbl.add_row().cells
            for ci, (fld, _) in enumerate(cols):
                val = it.get(fld, "")
                if isinstance(val, bool):
                    val = "✓" if val else "✗"
                run = row[ci].paragraphs[0].add_run(str(val)[:80])
                run.font.size = Pt(8)
        doc.add_paragraph()

    # DSB (Einzelobjekt)
    dsb = dsms.get("dsb") or {}
    if dsb.get("vorhanden"):
        _section_heading(doc, _t(sp, "dsms_dsb"), _EU_BLUE)
        pairs = [
            (_t(sp, "dsb_typ"), dsb.get("typ", "")),
            (_t(sp, "dsb_name"), dsb.get("name", "")),
            (_t(sp, "dsb_bestelldatum"), dsb.get("bestelldatum", "")),
            (_t(sp, "dsb_email"), dsb.get("kontakt_email", "")),
            (_t(sp, "dsb_veroeffentlicht"),
             "✓" if dsb.get("kontakt_veroeffentlicht") else "✗"),
            (_t(sp, "dsb_gemeldet"),
             "✓" if dsb.get("gemeldet_aufsicht") else "✗"),
        ]
        tbl = doc.add_table(rows=len(pairs), cols=2)
        for ri, (label, value) in enumerate(pairs):
            c0, c1 = tbl.cell(ri, 0), tbl.cell(ri, 1)
            _set_shading(c0, _EU_BLUE)
            _set_shading(c1, _SOFT)
            r0 = c0.paragraphs[0].add_run(label)
            r0.bold = True
            r0.font.size = Pt(9)
            r0.font.color.rgb = RGBColor(255, 255, 255)
            c1.paragraphs[0].add_run(
                str(value or _t(sp, "platzhalter"))).font.size = Pt(9)
        doc.add_paragraph()


# ── #1954: Katalogeinträge in der Sprache des Dokuments ──────────────────────
# `DSGVO_ANFORDERUNGEN`, `KAPITEL` und `BEWERTUNG_SKALA` sind Modul-Literale
# und werden hier direkt gelesen. Ohne diese drei Helfer käme die englische
# Fassung (`titel_en`, `referenz_en`, `label_en`) nie an — die Übersetzung
# wäre vorhanden und wirkungslos, der Defekt aus #1735.
#
# `uebersetze` liefert **Kopien**; das Modul-Literal bleibt unberührt, denn
# mehrere Anfragen lesen es gleichzeitig.
def _reqs(sp: str) -> list[dict]:
    """Die Anforderungen in der Sprache ``sp``."""
    from shared.katalog_sprache import uebersetze_viele

    return uebersetze_viele(DSGVO_ANFORDERUNGEN, sp)


def _kap(kap_info: dict, sp: str) -> dict:
    """Ein Kapitel in der Sprache ``sp``."""
    from shared.katalog_sprache import uebersetze

    return uebersetze(kap_info, sp)


def _skala(bval: int, sp: str) -> dict:
    """Ein Eintrag der Bewertungsskala in der Sprache ``sp``."""
    from shared.katalog_sprache import uebersetze

    return uebersetze(BEWERTUNG_SKALA.get(bval, BEWERTUNG_SKALA[0]), sp)


def export_report_docx(
    *,
    out_dir: Path,
    projekt_name: str,
    unternehmen: str = "",
    organisationstyp: str = "verantwortlicher",
    berater: str = "",
    bewertungen_raw: dict[str, dict[str, Any]],
    incl_massnahmen: bool = True,
    incl_details: bool = True,
    incl_referenzen: bool = True,
    pflicht_doku: dict[str, Any] | None = None,
    dsms: dict[str, Any] | None = None,
    sprache: str | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"DSGVO_Bericht_{_safe_filename(projekt_name)}_{date.today().isoformat()}.docx"

    # #1954: Die Sprache des Dokuments bestimmt der **Mandant**; ein
    # ausdrücklich übergebener Wert übersteuert für diesen einen Lauf.
    sp = _rt.aufloesen("dsgvo", projekt_name, sprache)
    platzhalter = _t(sp, "platzhalter")

    bewertungen = {rid: d["bewertung"] for rid, d in bewertungen_raw.items()}
    reife = berechne_reifegrad(bewertungen)
    org_info = ORGANISATIONSTYPEN.get(organisationstyp, ORGANISATIONSTYPEN["verantwortlicher"])
    ampel_farbe = _AMPEL_FARBEN.get(reife["ampel"], "#9e9e9e")

    doc = Document()
    from shared.reports.docx_pdf import set_a4 as _a4
    # Die Dokumentsprache (`w:lang`) wird nur gesetzt, wenn sie vom Standard
    # abweicht: Für Deutsch war sie vor #1954 nicht gesetzt, und „auf Deutsch
    # byte-identisch" ist der Regressionsschutz dieses Vorgangs. `None` heißt im
    # Helfer ausdrücklich „nicht anfassen".
    _a4(doc, sprache=sp if sp != "de" else None)  # #1614 A4
    sec = doc.sections[0]
    sec.top_margin = Inches(0.7)
    sec.bottom_margin = Inches(0.7)
    sec.left_margin = Inches(0.85)
    sec.right_margin = Inches(0.85)

    _banner(doc, _t(sp, "titel"), _EU_BLUE, size=24)
    _banner(doc, _t(sp, "untertitel"), "#001A66", size=11)

    meta_tbl = doc.add_table(rows=5, cols=2)
    meta_pairs = [
        (_t(sp, "m_projekt"), projekt_name),
        (_t(sp, "m_unternehmen"), unternehmen or platzhalter),
        # `org_info['label']` kommt aus `dsgvo/requirements.py` und ist (noch)
        # nur deutsch vorhanden — siehe Bericht zu #1954.
        (_t(sp, "m_organisationstyp"), org_info["label"]),
        (_t(sp, "m_berater"), berater or platzhalter),
        (_t(sp, "m_berichtsdatum"), date.today().strftime("%d.%m.%Y")),
    ]
    for i, (label, value) in enumerate(meta_pairs):
        c0, c1 = meta_tbl.cell(i, 0), meta_tbl.cell(i, 1)
        _set_shading(c0, _EU_BLUE)
        _set_shading(c1, _SOFT)
        r0 = c0.paragraphs[0].add_run(label)
        r0.bold = True; r0.font.size = Pt(10); r0.font.color.rgb = RGBColor(255, 255, 255)
        c1.paragraphs[0].add_run(value).font.size = Pt(10)

    doc.add_paragraph()
    _banner(doc, _t(sp, "rechtsgrundlage_banner", wert=org_info["referenz"]),
            "#E8EAF6", "#003399", size=9)

    doc.add_page_break()
    _banner(doc, _t(sp, "h1"), _EU_BLUE)

    summary_tbl = doc.add_table(rows=1, cols=3)
    kpis = [
        (_t(sp, "kpi_reifegrad"), f"{reife['gesamt_pct']:.0f}%", ampel_farbe),
        (_t(sp, "kpi_bewertet"),
         f"{reife['bewertete_count']}/{reife['gesamt_count']}", "#1565c0"),
        (_t(sp, "kpi_frist"), _t(sp, "kpi_frist_wert"), "#bf360c"),
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
        b.bold = True; b.font.size = Pt(16); b.font.color.rgb = RGBColor(255, 255, 255)

    doc.add_paragraph()
    _section_heading(doc, _t(sp, "reifegrad_je_kapitel"), _EU_BLUE)
    for kap_id, _kap_roh in KAPITEL.items():
        kap_info = _kap(_kap_roh, sp)
        kap_pct = reife["kapitel_pct"].get(kap_id, 0.0)
        kap_farbe, _ = _KAPITEL_FARBEN.get(kap_id, (_EU_BLUE, _SOFT))
        _maturity_bar_docx(doc, kap_pct, kap_farbe,
                           _t(sp, "kapitel_balken", titel=kap_info["titel"],
                              pct=f"{kap_pct:.0f}"))

    doc.add_paragraph()
    kritisch = [
        r for r in _reqs(sp)
        if bewertungen.get(r["id"], 0) in (0, 1) and r["gewichtung"] == 3
    ]
    if kritisch:
        _banner(doc, _t(sp, "kritisch_banner"), "#BF360C", size=10)
        for req in kritisch[:5]:
            p = doc.add_paragraph(style="List Bullet")
            run = p.add_run(_t(sp, "kritisch_zeile", id=req["id"],
                               titel=req["titel"], ref=req["ref"]))
            run.font.size = Pt(9)

    doc.add_page_break()
    _banner(doc, _t(sp, "h2"), _EU_BLUE)
    rechtlich = [
        (_t(sp, "r_rechtsgrundlage"), _t(sp, "r_rechtsgrundlage_wert")),
        (_t(sp, "r_geltungsbereich"), _t(sp, "r_geltungsbereich_wert")),
        (_t(sp, "r_bussgeld"), _t(sp, "r_bussgeld_wert")),
        (_t(sp, "r_meldepflicht"), _t(sp, "r_meldepflicht_wert")),
        (_t(sp, "r_betroffenenrechte"), _t(sp, "r_betroffenenrechte_wert")),
        (_t(sp, "r_organisationstyp"), org_info["label"]),
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
        c1.paragraphs[0].add_run(value).font.size = Pt(9)

    doc.add_page_break()
    _banner(doc, _t(sp, "h3"), _EU_BLUE)
    meth_text = _t(sp, "methodik")
    doc.add_paragraph(meth_text).runs[0].font.size = Pt(10)

    doc.add_paragraph()
    _section_heading(doc, _t(sp, "bewertungsskala"), _EU_BLUE)
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
        # `info['label']` kommt aus `dsgvo/requirements.BEWERTUNG_SKALA` und ist
        # (noch) nur deutsch vorhanden — siehe Bericht zu #1954.
        scale_tbl.cell(row_i, 1).paragraphs[0].add_run(info["label"]).font.size = Pt(9)
        scale_tbl.cell(row_i, 2).paragraphs[0].add_run(
            _t(sp, "s_prozent", pct=info["reife_pct"])).font.size = Pt(9)

    if incl_details:
        doc.add_page_break()
        _banner(doc, _t(sp, "h4"), _EU_BLUE)
        by_kapitel: dict[str, list] = defaultdict(list)
        for req in _reqs(sp):
            by_kapitel[req["kapitel"]].append(req)

        for kap_id, reqs in by_kapitel.items():
            kap_info = _kap(KAPITEL[kap_id], sp)
            kap_farbe, kap_soft = _KAPITEL_FARBEN.get(kap_id, (_EU_BLUE, _SOFT))
            kap_pct = reife["kapitel_pct"].get(kap_id, 0.0)
            _banner(doc, _t(sp, "kapitel_banner", titel=kap_info["titel"],
                            pct=f"{kap_pct:.0f}"), kap_farbe)
            _banner(doc, _t(sp, "referenz_banner", wert=kap_info["referenz"]),
                    kap_soft, kap_farbe, size=9)
            doc.add_paragraph()

            req_tbl = doc.add_table(rows=1, cols=5)
            for i, hdr in enumerate((_t(sp, "a_id"), _t(sp, "a_anforderung"),
                                     _t(sp, "a_referenz"), _t(sp, "a_bewertung"),
                                     _t(sp, "a_kommentar"))):
                cell = req_tbl.cell(0, i)
                _set_shading(cell, kap_farbe)
                run = cell.paragraphs[0].add_run(hdr)
                run.bold = True; run.font.size = Pt(8); run.font.color.rgb = RGBColor(255, 255, 255)
            for i, w in enumerate([0.7, 2.2, 1.6, 1.0, 2.0]):
                req_tbl.columns[i].width = Inches(w)

            for ridx, req in enumerate(reqs):
                rid = req["id"]
                bew_data = bewertungen_raw.get(rid, {})
                bval = bew_data.get("bewertung", 0)
                binfo = _skala(bval, sp)
                bfarbe = _BEWERTUNG_FARBEN.get(bval, "#9E9E9E")
                row_bg = kap_soft if ridx % 2 == 0 else "#FFFFFF"
                kommentar = _ohne_ki_marker(bew_data.get("kommentar", "")) or platzhalter

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

    if incl_massnahmen:
        doc.add_page_break()
        _banner(doc, _t(sp, "h5"), _EU_BLUE)
        doc.add_paragraph(_t(sp, "massnahmen_intro")).runs[0].font.size = Pt(10)
        doc.add_paragraph()

        massnahmen = sorted(
            [r for r in _reqs(sp)
             if bewertungen.get(r["id"], 0) < 4 and bewertungen.get(r["id"], 0) > 0
             or bewertungen.get(r["id"], 0) == 0],
            key=lambda r: (-r["gewichtung"], bewertungen.get(r["id"], 0)),
        )
        ma_tbl = doc.add_table(rows=1, cols=5)
        for i, hdr in enumerate((_t(sp, "ma_id"), _t(sp, "ma_anforderung"),
                                 _t(sp, "ma_aktuell"), _t(sp, "ma_massnahme"),
                                 _t(sp, "ma_verantwortlich"))):
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
            binfo = _skala(bval, sp)
            bfarbe = _BEWERTUNG_FARBEN.get(bval, "#9E9E9E")
            massnahme = bew_data.get("massnahme", "") or req["hinweise"][:120]
            verantw = bew_data.get("verantwortlich", "")
            ziel = bew_data.get("zieldatum", "")

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
            row[4].paragraphs[0].add_run(f"{verantw}\n{ziel}".strip()).font.size = Pt(8)

    if incl_referenzen:
        doc.add_page_break()
        _banner(doc, _t(sp, "anhang_banner"), _EU_BLUE)
        doc.add_paragraph(_t(sp, "quellen_intro")).runs[0].font.size = Pt(10)
        doc.add_paragraph()
        for ref in _referenzen(sp):
            p = doc.add_paragraph(style="List Number")
            p.add_run(ref).font.size = Pt(9)
        doc.add_paragraph()
        _banner(doc, _t(sp, "disclaimer_banner"), "#455a64", size=9)
        disclaimer_p = doc.add_paragraph(_t(sp, "disclaimer"))
        disclaimer_p.runs[0].font.size = Pt(9)
        disclaimer_p.runs[0].italic = True

    # Pflicht-Doku-Section (Sprint δ)
    if pflicht_doku:
        _section_heading(doc, _t(sp, "pflicht_titel"), "#1565C0")
        for title, items, cols in [
            (_t(sp, "d1"), pflicht_doku.get('vvt') or [],
             [('vvt_id', _t(sp, "d1_id")), ('name', _t(sp, "d1_name")),
              ('zweck', _t(sp, "d1_zweck")),
              ('rechtsgrundlage', _t(sp, "d1_rechtsgrundlage"))]),
            (_t(sp, "d2"), pflicht_doku.get('tom') or [],
             [('kategorie', _t(sp, "d2_kategorie")),
              ('massnahme', _t(sp, "d2_massnahme")),
              ('umsetzungsstatus', _t(sp, "d2_status"))]),
            (_t(sp, "d3"), pflicht_doku.get('dpia') or [],
             [('dpia_id', _t(sp, "d3_id")), ('titel', _t(sp, "d3_titel")),
              ('restrisiko', _t(sp, "d3_restrisiko")),
              ('status', _t(sp, "d3_status"))]),
            (_t(sp, "d4"), pflicht_doku.get('avv') or [],
             [('auftragsverarbeiter', _t(sp, "d4_vendor")),
              ('leistung', _t(sp, "d4_leistung")),
              ('avv_vorhanden', _t(sp, "d4_avv")),
              ('drittland_garantie', _t(sp, "d4_drittland"))]),
            (_t(sp, "d5"), pflicht_doku.get('datenpannen') or [],
             [('panne_id', _t(sp, "d5_id")), ('titel', _t(sp, "d5_titel")),
              ('festgestellt_am', _t(sp, "d5_festgestellt")),
              ('risikoeinschaetzung', _t(sp, "d5_risiko")),
              ('status', _t(sp, "d5_status"))]),
        ]:
            doc.add_paragraph().add_run(
                _t(sp, "pflicht_zeile", titel=title, anzahl=len(items))).bold = True
            if not items:
                doc.add_paragraph(_t(sp, "leer")).runs[0].font.size = Pt(9)
                continue
            tbl = doc.add_table(rows=len(items) + 1, cols=len(cols))
            tbl.style = 'Light Grid Accent 1'
            for ci, (_, hdr) in enumerate(cols):
                tbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
            for ri, it in enumerate(items, start=1):
                for ci, (key, _) in enumerate(cols):
                    val = it.get(key, '')
                    if isinstance(val, bool):
                        val = '✓' if val else '✗'
                    tbl.cell(ri, ci).paragraphs[0].add_run(str(val)[:60]).font.size = Pt(8)
            doc.add_paragraph()

    # DSMS-Gesamtbericht (#1113) — zusätzliche Bereiche, leere übersprungen
    if dsms:
        _add_dsms_sections_docx(doc, dsms, sp)

    doc.save(str(out_path))
    return out_path


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
