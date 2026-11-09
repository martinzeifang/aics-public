"""DSGVO TOM-Generator – Technische und organisatorische Maßnahmen (Art. 32 DSGVO).

Generates a structured TOM draft DOCX from DSGVO project data and approved evidence mappings.
Each claim is either cited (evidence) or flagged as [ANNAHME – Nachweis ausstehend].
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from shared.reports import texte as _rt


# ── Colour palette ────────────────────────────────────────────────────────────

_EU_BLUE   = "#003399"
_DARK      = "#1a237e"
_DRAFT_BG  = "#FFF9C4"
_DRAFT_FG  = "#5D4037"
_CITE_BG   = "#E8F5E9"
_OPEN_BG   = "#FFF3E0"
_ASSUM_BG  = "#FCE4EC"

_KATEGORIE_FARBEN: dict[str, tuple[str, str]] = {
    "A": ("#1565C0", "#E3F2FD"),  # Zutrittskontrolle
    "B": ("#1565C0", "#E3F2FD"),  # Zugangskontrolle
    "C": ("#4A148C", "#F3E5F5"),  # Zugriffskontrolle
    "D": ("#4A148C", "#F3E5F5"),  # Weitergabekontrolle
    "E": ("#00695C", "#E0F2F1"),  # Eingabekontrolle
    "F": ("#00695C", "#E0F2F1"),  # Auftragskontrolle
    "G": ("#BF360C", "#FBE9E7"),  # Verfügbarkeitskontrolle
    "H": ("#E65100", "#FFF3E0"),  # Trennungskontrolle
    "I": ("#2C3E50", "#ECF0F1"),  # Pseudonymisierung & Verschlüsselung
    "J": ("#2C3E50", "#ECF0F1"),  # Überprüfung & Evaluierung
}


# ── TOM-Abschnitte ────────────────────────────────────────────────────────────

# #1954: Je Abschnitt zusätzlich ``titel_en``, ``untertitel_en``, ``art_en`` und
# ``beschreibung_en``/``massnahmen_hinweise_en``. Die Übersetzung steht **bei
# ihrem Abschnitt**: Wer einen Maßnahmen-Hinweis ergänzt, sieht die Lücke im
# selben Atemzug (Begründung im Dateikopf von ``shared/reports/texte``).
#
# Die deutschen Schlüssel sind unverändert — ``id``, ``kategorie`` und
# ``dsgvo_req_ids`` sind Bezeichner und werden nie übersetzt. ``art_en``
# übersetzt **nicht die Fundstelle**, nur ihre Schreibweise: ``Abs. 1`` → ``(1)``,
# ``lit. b`` → ``point (b)``, DSGVO → GDPR; die Ziffern bleiben unangetastet
# (Lehre aus #1763/#1792).
#
# ``massnahmen_hinweise_en`` ist **parallel zur deutschen Liste** — gleiche
# Länge, gleiche Reihenfolge. Das ist Absicht und keine Bequemlichkeit: Die
# Zuordnung zu einem Nachweis läuft über den deutschen Hinweis (siehe
# :func:`build_tom_abschnitt`), und eine Liste anderer Länge würde die
# Entsprechung stillschweigend verschieben.
TOM_ABSCHNITTE: list[dict[str, Any]] = [
    {
        "id": "TOM-A",
        "titel": "Zutrittskontrolle",
        "untertitel": "Schutz vor unbefugtem physischen Zutritt",
        "art": "Art. 32 Abs. 1 lit. b DSGVO",
        "beschreibung": (
            "Maßnahmen, die verhindern, dass Unbefugte Zutritt zu Datenverarbeitungsanlagen "
            "erhalten, mit denen personenbezogene Daten verarbeitet oder genutzt werden."
        ),
        "massnahmen_hinweise": [
            "Zutrittskontrollsystem (Schlüssel, Chipkarte, PIN, Biometrie)",
            "Videoüberwachung sensibler Bereiche (Serverraum, Archiv)",
            "Besucherregistrierung und -begleitung",
            "Alarmanlage / Einbruchmeldeanlage",
            "Sicherheitspersonal / Pforte",
        ],
        "titel_en": "Physical access control",
        "untertitel_en": "Protection against unauthorised physical access",
        "art_en": "Art. 32(1), point (b) GDPR",
        "beschreibung_en": (
            "Measures to prevent unauthorised persons from gaining access to data "
            "processing facilities with which personal data are processed or used."
        ),
        "massnahmen_hinweise_en": [
            "Access control system (key, chip card, PIN, biometrics)",
            "Video surveillance of sensitive areas (server room, archive)",
            "Visitor registration and escorting",
            "Alarm system / intruder alarm system",
            "Security staff / reception",
        ],
        "dsgvo_req_ids": ["GDS4-02"],
        "kategorie": "A",
    },
    {
        "id": "TOM-B",
        "titel": "Zugangskontrolle",
        "untertitel": "Schutz vor unbefugter Systemnutzung",
        "art": "Art. 32 Abs. 1 lit. b DSGVO",
        "beschreibung": (
            "Maßnahmen, die verhindern, dass Datenverarbeitungssysteme von Unbefugten "
            "genutzt werden können."
        ),
        "massnahmen_hinweise": [
            "Passwortrichtlinie (Mindestlänge, Komplexität, Ablauf)",
            "Mehr-Faktor-Authentifizierung (MFA) für privilegierte Zugänge",
            "Bildschirmschoner mit automatischer Sperrung",
            "Zentrales Identity & Access Management (IAM)",
            "Protokollierung fehlgeschlagener Anmeldeversuche",
        ],
        "titel_en": "System access control",
        "untertitel_en": "Protection against unauthorised use of systems",
        "art_en": "Art. 32(1), point (b) GDPR",
        "beschreibung_en": (
            "Measures to prevent data processing systems from being used by "
            "unauthorised persons."
        ),
        "massnahmen_hinweise_en": [
            "Password policy (minimum length, complexity, expiry)",
            "Multi-factor authentication (MFA) for privileged access",
            "Screen saver with automatic locking",
            "Central identity & access management (IAM)",
            "Logging of failed login attempts",
        ],
        "dsgvo_req_ids": ["GDS4-02", "GDS4-05"],
        "kategorie": "B",
    },
    {
        "id": "TOM-C",
        "titel": "Zugriffskontrolle",
        "untertitel": "Datenzugriff auf das Notwendige begrenzen",
        "art": "Art. 32 Abs. 1 lit. b DSGVO",
        "beschreibung": (
            "Maßnahmen, die gewährleisten, dass die zur Nutzung berechtigten Personen "
            "ausschließlich auf die ihrer Zugriffsberechtigung unterliegenden Daten "
            "zugreifen können (Need-to-Know-Prinzip)."
        ),
        "massnahmen_hinweise": [
            "Rollenbasierte Zugriffskontrolle (RBAC)",
            "Rechtevergabe nach dem Minimalprinzip (Least Privilege)",
            "Regelmäßige Überprüfung und Entzug nicht mehr benötigter Rechte",
            "Trennung von Produktions- und Testsystemen",
            "Protokollierung von Datenzugriffen bei besonders sensiblen Daten",
        ],
        "titel_en": "Data access control",
        "untertitel_en": "Limiting access to data to what is necessary",
        "art_en": "Art. 32(1), point (b) GDPR",
        "beschreibung_en": (
            "Measures to ensure that persons authorised to use a data processing "
            "system have access exclusively to the data covered by their access "
            "authorisation (need-to-know principle)."
        ),
        "massnahmen_hinweise_en": [
            "Role-based access control (RBAC)",
            "Granting of rights on a minimum basis (least privilege)",
            "Regular review and withdrawal of rights that are no longer needed",
            "Separation of production and test systems",
            "Logging of data access for particularly sensitive data",
        ],
        "dsgvo_req_ids": ["GDS4-02", "GDS4-05"],
        "kategorie": "C",
    },
    {
        "id": "TOM-D",
        "titel": "Weitergabekontrolle",
        "untertitel": "Schutz bei Übermittlung personenbezogener Daten",
        "art": "Art. 32 Abs. 1 lit. b DSGVO",
        "beschreibung": (
            "Maßnahmen, die gewährleisten, dass überprüft werden kann, an welche Stellen "
            "personenbezogene Daten übermittelt worden sind oder werden können."
        ),
        "massnahmen_hinweise": [
            "Verschlüsselung bei der Übertragung (TLS 1.2+ / SFTP / HTTPS)",
            "Protokollierung von Datenweitergaben",
            "Auftragsverarbeitungsverträge (AVV) mit Dienstleistern",
            "Anonymisierung / Pseudonymisierung vor Weitergabe",
            "Verbot unverschlüsselter E-Mail-Übertragung sensibler Daten",
        ],
        "titel_en": "Transfer control",
        "untertitel_en": "Protection during transmission of personal data",
        "art_en": "Art. 32(1), point (b) GDPR",
        "beschreibung_en": (
            "Measures to ensure that it can be verified to which bodies personal "
            "data have been or may be transmitted."
        ),
        "massnahmen_hinweise_en": [
            "Encryption in transit (TLS 1.2+ / SFTP / HTTPS)",
            "Logging of data disclosures",
            "Data processing agreements (DPA) with service providers",
            "Anonymisation / pseudonymisation before disclosure",
            "Prohibition of unencrypted email transmission of sensitive data",
        ],
        "dsgvo_req_ids": ["GDS4-01", "GDS4-02"],
        "kategorie": "D",
    },
    {
        "id": "TOM-E",
        "titel": "Eingabekontrolle",
        "untertitel": "Protokollierung und Nachvollziehbarkeit",
        "art": "Art. 32 Abs. 1 lit. b DSGVO",
        "beschreibung": (
            "Maßnahmen, die gewährleisten, dass nachträglich überprüft werden kann, "
            "ob und von wem personenbezogene Daten eingegeben, verändert oder entfernt worden sind."
        ),
        "massnahmen_hinweise": [
            "Protokollierung von Dateneingaben, -änderungen und -löschungen",
            "Audit-Logs (manipulationssicher, zentral gespeichert)",
            "Benutzer-ID in allen protokollierten Aktionen",
            "Mindestaufbewahrungsfrist für Logs (mind. 6 Monate)",
            "Regelmäßige Auswertung der Protokolldaten",
        ],
        "titel_en": "Input control",
        "untertitel_en": "Logging and traceability",
        "art_en": "Art. 32(1), point (b) GDPR",
        "beschreibung_en": (
            "Measures to ensure that it can subsequently be verified whether and "
            "by whom personal data have been entered, altered or removed."
        ),
        "massnahmen_hinweise_en": [
            "Logging of data entries, changes and deletions",
            "Audit logs (tamper-proof, stored centrally)",
            "User ID in every logged action",
            "Minimum retention period for logs (at least 6 months)",
            "Regular evaluation of the log data",
        ],
        "dsgvo_req_ids": ["GDS4-04"],
        "kategorie": "E",
    },
    {
        "id": "TOM-F",
        "titel": "Auftragskontrolle",
        "untertitel": "Weisungsgemäße Verarbeitung durch Auftragsverarbeiter",
        "art": "Art. 28, Art. 32 Abs. 4 DSGVO",
        "beschreibung": (
            "Maßnahmen, die gewährleisten, dass personenbezogene Daten, die im Auftrag "
            "verarbeitet werden, nur entsprechend den Weisungen des Auftraggebers "
            "verarbeitet werden können."
        ),
        "massnahmen_hinweise": [
            "Schriftliche Auftragsverarbeitungsverträge (AVV) nach Art. 28 DSGVO",
            "Dokumentation und Überprüfung aller Auftragsverarbeiter",
            "Weisungsbefugnis schriftlich festhalten",
            "Recht auf Audit-/Kontrollbesuche beim Auftragsverarbeiter",
            "Sub-Auftragsverarbeiter genehmigungspflichtig",
        ],
        "titel_en": "Instruction control",
        "untertitel_en": "Processing by processors in accordance with instructions",
        "art_en": "Art. 28, Art. 32(4) GDPR",
        "beschreibung_en": (
            "Measures to ensure that personal data processed on behalf of the "
            "controller can be processed only in accordance with the controller's "
            "instructions."
        ),
        "massnahmen_hinweise_en": [
            "Written data processing agreements (DPA) under Art. 28 GDPR",
            "Documentation and review of all processors",
            "Right to issue instructions recorded in writing",
            "Right to audit and inspection visits at the processor",
            "Sub-processors subject to prior authorisation",
        ],
        "dsgvo_req_ids": ["GDS4-05"],
        "kategorie": "F",
    },
    {
        "id": "TOM-G",
        "titel": "Verfügbarkeitskontrolle",
        "untertitel": "Schutz vor unbeabsichtigtem Datenverlust",
        "art": "Art. 32 Abs. 1 lit. b, c DSGVO",
        "beschreibung": (
            "Maßnahmen, die gewährleisten, dass personenbezogene Daten gegen zufällige "
            "Zerstörung oder Verlust geschützt sind und die Verfügbarkeit "
            "rasch wiederhergestellt werden kann."
        ),
        "massnahmen_hinweise": [
            "Regelmäßige Datensicherungen (Backup) nach 3-2-1-Regel",
            "Regelmäßige Tests der Wiederherstellbarkeit",
            "Dokumentierte RTO (Recovery Time Objective) und RPO (Recovery Point Objective)",
            "Redundante Systeme / Failover",
            "Notfallplan für datenschutzrelevante Systeme",
        ],
        "titel_en": "Availability control",
        "untertitel_en": "Protection against accidental loss of data",
        "art_en": "Art. 32(1), points (b) and (c) GDPR",
        "beschreibung_en": (
            "Measures to ensure that personal data are protected against accidental "
            "destruction or loss and that availability can be restored rapidly."
        ),
        "massnahmen_hinweise_en": [
            "Regular backups following the 3-2-1 rule",
            "Regular tests of restorability",
            "Documented RTO (recovery time objective) and RPO (recovery point objective)",
            "Redundant systems / failover",
            "Contingency plan for systems relevant to data protection",
        ],
        "dsgvo_req_ids": ["GDS4-02", "GDS4-03"],
        "kategorie": "G",
    },
    {
        "id": "TOM-H",
        "titel": "Trennungskontrolle",
        "untertitel": "Zweckgebundene Trennung von Daten",
        "art": "Art. 5 Abs. 1 lit. b, Art. 32 Abs. 1 DSGVO",
        "beschreibung": (
            "Maßnahmen, die gewährleisten, dass zu unterschiedlichen Zwecken erhobene "
            "Daten getrennt verarbeitet werden können."
        ),
        "massnahmen_hinweise": [
            "Logische Trennung von Daten unterschiedlicher Mandanten / Zwecke",
            "Physische Trennung von Produktions-, Test- und Entwicklungsumgebungen",
            "Datenbankschemas oder -instanzen nach Verarbeitungszweck",
            "Keine Nutzung von Produktivdaten in Testumgebungen",
        ],
        "titel_en": "Separation control",
        "untertitel_en": "Purpose-bound separation of data",
        "art_en": "Art. 5(1), point (b), Art. 32(1) GDPR",
        "beschreibung_en": (
            "Measures to ensure that data collected for different purposes can be "
            "processed separately."
        ),
        "massnahmen_hinweise_en": [
            "Logical separation of data of different clients / purposes",
            "Physical separation of production, test and development environments",
            "Database schemas or instances by purpose of processing",
            "No use of production data in test environments",
        ],
        "dsgvo_req_ids": ["GDS4-02"],
        "kategorie": "H",
    },
    {
        "id": "TOM-I",
        "titel": "Pseudonymisierung und Verschlüsselung",
        "untertitel": "Technische Schutzmaßnahmen für Daten im Ruhezustand und bei Übertragung",
        "art": "Art. 32 Abs. 1 lit. a DSGVO",
        "beschreibung": (
            "Maßnahmen zur Pseudonymisierung und Verschlüsselung personenbezogener Daten "
            "als geeignetes Mittel zur Risikominimierung, soweit für den Verarbeitungskontext geeignet."
        ),
        "massnahmen_hinweise": [
            "Verschlüsselung ruhender Daten (AES-256 oder gleichwertig)",
            "Verschlüsselung bei der Übertragung (TLS 1.2+ / TLS 1.3)",
            "Schlüsselverwaltungskonzept (Key Management)",
            "Pseudonymisierung personenbezogener Daten in Analysesystemen",
            "Anonymisierung, wenn eine Identifizierung nicht mehr erforderlich ist",
        ],
        "titel_en": "Pseudonymisation and encryption",
        "untertitel_en": "Technical safeguards for data at rest and in transit",
        "art_en": "Art. 32(1), point (a) GDPR",
        "beschreibung_en": (
            "Measures for the pseudonymisation and encryption of personal data as "
            "an appropriate means of minimising risk, where appropriate for the "
            "context of the processing."
        ),
        "massnahmen_hinweise_en": [
            "Encryption of data at rest (AES-256 or equivalent)",
            "Encryption in transit (TLS 1.2+ / TLS 1.3)",
            "Key management concept",
            "Pseudonymisation of personal data in analytics systems",
            "Anonymisation where identification is no longer necessary",
        ],
        "dsgvo_req_ids": ["GDS4-01"],
        "kategorie": "I",
    },
    {
        "id": "TOM-J",
        "titel": "Überprüfung und Evaluierung",
        "untertitel": "Regelmäßige Wirksamkeitsprüfung der Maßnahmen",
        "art": "Art. 32 Abs. 1 lit. d DSGVO",
        "beschreibung": (
            "Ein Verfahren zur regelmäßigen Überprüfung, Bewertung und Evaluierung der "
            "Wirksamkeit der technischen und organisatorischen Maßnahmen zur Gewährleistung "
            "der Sicherheit der Verarbeitung."
        ),
        "massnahmen_hinweise": [
            "Jährliche Datenschutz-Folgenabschätzung (DSFA) für risikoreiche Verarbeitungen",
            "Regelmäßige interne Datenschutzaudits",
            "Penetrationstests und Schwachstellenscans",
            "Datenschutzkontrolle bei Systemänderungen (Privacy by Design / by Default)",
            "Kontinuierliches Datenschutzmanagementsystem (DSMS)",
        ],
        "titel_en": "Review and evaluation",
        "untertitel_en": "Regular testing of the effectiveness of the measures",
        "art_en": "Art. 32(1), point (d) GDPR",
        "beschreibung_en": (
            "A process for regularly testing, assessing and evaluating the "
            "effectiveness of the technical and organisational measures for "
            "ensuring the security of the processing."
        ),
        "massnahmen_hinweise_en": [
            "Annual data protection impact assessment (DPIA) for high-risk processing",
            "Regular internal data protection audits",
            "Penetration tests and vulnerability scans",
            "Data protection review for system changes (privacy by design / by default)",
            "Continuous data protection management system (DSMS)",
        ],
        "dsgvo_req_ids": ["GDS4-04"],
        "kategorie": "J",
    },
]

# TOM-ID → Abschnitt-Lookup
_TOM_BY_ID = {s["id"]: s for s in TOM_ABSCHNITTE}

# DSGVO-Anforderungs-ID → TOM-IDs
_DSGVO_REQ_TO_TOM: dict[str, list[str]] = {}
for _s in TOM_ABSCHNITTE:
    for _rid in _s["dsgvo_req_ids"]:
        _DSGVO_REQ_TO_TOM.setdefault(_rid, []).append(_s["id"])


#: Die Rahmentexte des TOM-Entwurfs je Sprache (#1954).
#:
#: Das Dokument ist der TOM-Nachweis **des Mandanten** (Art. 32 Abs. 1 lit. d
#: verlangt seine Überprüfbarkeit), also entscheidet ``firmen.sprache`` über
#: seine Sprache. Die deutschen Werte sind zeichengenau die aus 8.3.4 —
#: einschließlich der doppelten Leerzeichen („⚠  ENTWURF", „1  Einleitung",
#: „  |  ", „  –  ") und des Geviertstrichs „—" als Platzhalter (anders als in
#: ``report_export.py``, wo ein Halbgeviertstrich „–" steht; beides ist Bestand
#: und wird nicht begradigt).
#:
#: **Die Statusmarken werden übersetzt, die Statuswerte nicht.** Gedruckt wird
#: ``[NACHWEIS]``/``[ANNAHME]``/``[OFFEN]``; intern heißen die Zustände
#: ``cited``/``assumed``/``open`` und bleiben so (Regel 7) — sie werden
#: verglichen, die Marken nur gelesen. Die Legende in der Einleitung nennt
#: dieselben Marken wie die Tabelle, also müssen beide zusammen wechseln.
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        "entwurf_banner": ("⚠  ENTWURF – Nicht rechtsverbindlich. Vor Verwendung "
                           "rechtlich prüfen lassen."),
        "titel": "Verzeichnis technischer und organisatorischer Maßnahmen (TOM)",
        "untertitel": "gemäß Art. 32 Verordnung (EU) 2016/679 (DSGVO)",

        "m_organisation": "Organisation",
        "m_projekt": "Projekt",
        "m_erstellt_am": "Erstellt am",
        "m_erstellt_von": "Erstellt von",
        "m_status": "Status",
        "m_status_wert": "ENTWURF",
        "m_rechtsgrundlage": "Rechtsgrundlage",
        "m_rechtsgrundlage_wert": "Art. 32 Abs. 1 DSGVO",
        "platzhalter": "—",

        "h1": "1  Einleitung",
        "einleitung": (
            "{organisation} hat gemäß Art. 32 Abs. 1 DSGVO geeignete technische und "
            "organisatorische Maßnahmen (TOM) getroffen, um ein dem Risiko angemessenes "
            "Schutzniveau bei der Verarbeitung personenbezogener Daten zu gewährleisten. "
            "Dieses Dokument beschreibt die implementierten bzw. geplanten Maßnahmen je "
            "Schutzkategorie."),
        "legende": (
            "Hinweis: Mit [NACHWEIS] markierte Maßnahmen sind durch Belege aus dem "
            "Evidence-Archiv gestützt. Mit [ANNAHME] markierte Maßnahmen basieren auf "
            "der Reifegradbeurteilung, sind jedoch noch nicht durch dokumentarische "
            "Nachweise belegt. Mit [OFFEN] markierte Maßnahmen sind noch nicht "
            "abschließend dokumentiert."),

        "h2": "2  Technische und organisatorische Maßnahmen",
        "abschnitt_banner": "2.{nr}  {id} – {titel}",
        "abschnitt_referenz": "{art}  |  {untertitel}",
        "reifegrad": "Reifegrad: {wert}/5  –  {label}",

        "t_status": "Status",
        "t_massnahme": "Maßnahme",
        "t_nachweis": "Nachweis / Hinweis",
        "marke_nachweis": "[NACHWEIS]",
        "marke_annahme": "[ANNAHME]",
        "marke_offen": "[OFFEN]",
        "zitat": "{datei} §{abschnitt}",
        "annahme_hinweis": "Basiert auf Reifegradbewertung",

        "h3": "3  Offene Punkte und fehlende Nachweise",
        "offen_intro": ("Folgende Maßnahmen sind noch nicht abschließend durch "
                        "Dokumente oder interne Nachweise belegt und sollten "
                        "priorisiert adressiert werden:"),
        "o_kategorie": "TOM-Kategorie",
        "o_massnahme": "Offene Maßnahme",
        "alles_belegt": ("Alle Maßnahmen sind entweder durch Nachweise belegt oder "
                         "auf Basis der Reifegradbewertung als umgesetzt eingestuft."),

        "h4": "4  Zusammenfassung der Nachweisabdeckung",
        "c_gesamt": "Maßnahmen gesamt",
        "c_nachweis": "[NACHWEIS] – belegt",
        "c_annahme": "[ANNAHME] – Reifegrad",
        "c_offen": "[OFFEN] – fehlend",
        "c_anteil": "{anzahl} ({pct}%)",

        "disclaimer": (
            "Rechtlicher Hinweis: Dieses Dokument wurde automatisiert erstellt und "
            "stellt einen unverbindlichen Entwurf dar. Es ersetzt keine rechtliche "
            "oder datenschutzfachliche Prüfung. Bitte lassen Sie dieses Dokument vor "
            "der Verwendung durch einen qualifizierten Datenschutzbeauftragten oder "
            "Rechtsanwalt prüfen."),

        # Reifegrad-Bezeichnungen dieses Dokuments. **Nicht** dieselben wie
        # `dsgvo/requirements.BEWERTUNG_SKALA` für dieselben Werte 0–5 — das ist
        # Bestand und im Bericht zu #1954 als Widerspruch vermerkt.
        "b_0": "Nicht bewertet",
        "b_1": "Nicht vorhanden",
        "b_2": "Initial",
        "b_3": "Geplant",
        "b_4": "Umgesetzt",
        "b_5": "Optimiert",
    },
    "en": {
        "entwurf_banner": ("⚠  DRAFT – Not legally binding. Have it reviewed "
                           "legally before use."),
        "titel": "Record of technical and organisational measures (TOM)",
        "untertitel": ("pursuant to Art. 32 of Regulation (EU) 2016/679 (GDPR)"),

        "m_organisation": "Organisation",
        "m_projekt": "Project",
        "m_erstellt_am": "Created on",
        "m_erstellt_von": "Created by",
        "m_status": "Status",
        "m_status_wert": "DRAFT",
        "m_rechtsgrundlage": "Legal basis",
        "m_rechtsgrundlage_wert": "Art. 32(1) GDPR",
        "platzhalter": "—",

        "h1": "1  Introduction",
        "einleitung": (
            "{organisation} has taken appropriate technical and organisational "
            "measures (TOM) pursuant to Art. 32(1) GDPR in order to ensure a level "
            "of protection appropriate to the risk when processing personal data. "
            "This document describes the measures implemented or planned for each "
            "protection category."),
        "legende": (
            "Note: measures marked [EVIDENCE] are supported by records from the "
            "evidence archive. Measures marked [ASSUMPTION] are based on the "
            "maturity assessment but are not yet supported by documentary evidence. "
            "Measures marked [OPEN] have not yet been conclusively documented."),

        "h2": "2  Technical and organisational measures",
        "abschnitt_banner": "2.{nr}  {id} – {titel}",
        "abschnitt_referenz": "{art}  |  {untertitel}",
        "reifegrad": "Maturity: {wert}/5  –  {label}",

        "t_status": "Status",
        "t_massnahme": "Measure",
        "t_nachweis": "Evidence / note",
        "marke_nachweis": "[EVIDENCE]",
        "marke_annahme": "[ASSUMPTION]",
        "marke_offen": "[OPEN]",
        "zitat": "{datei} §{abschnitt}",
        "annahme_hinweis": "Based on the maturity assessment",

        "h3": "3  Open points and missing evidence",
        "offen_intro": ("The following measures are not yet conclusively supported "
                        "by documents or internal evidence and should be addressed "
                        "as a priority:"),
        "o_kategorie": "TOM category",
        "o_massnahme": "Open measure",
        "alles_belegt": ("All measures are either supported by evidence or "
                         "classified as implemented on the basis of the maturity "
                         "assessment."),

        "h4": "4  Summary of evidence coverage",
        "c_gesamt": "Total measures",
        "c_nachweis": "[EVIDENCE] – supported",
        "c_annahme": "[ASSUMPTION] – maturity",
        "c_offen": "[OPEN] – missing",
        "c_anteil": "{anzahl} ({pct}%)",

        "disclaimer": (
            "Legal note: this document was generated automatically and constitutes "
            "a non-binding draft. It does not replace a legal or data protection "
            "review. Please have this document reviewed by a qualified data "
            "protection officer or lawyer before use."),

        "b_0": "Not assessed",
        "b_1": "Not in place",
        "b_2": "Initial",
        "b_3": "Planned",
        "b_4": "Implemented",
        "b_5": "Optimised",
    },
}

_t = _rt.macher(TEXTE)


def abschnitt_text(abschnitt: dict[str, Any], feld: str, sprache: str) -> Any:
    """Ein Abschnittsfeld in der gewünschten Sprache; ohne Übersetzung deutsch.

    Der Rückfall ist kein Versehen: Ein neuer Hinweis erscheint sofort in jedem
    Dokument — auf Deutsch, bis ihn jemand übersetzt. Fehlte er, wäre eine halbe
    Übersetzung ein **unvollständiger Nachweis**, und das ist schlimmer als ein
    deutscher Satz darin (siehe ``shared/reports/texte.macher``).
    """
    if sprache != "de":
        wert = abschnitt.get(f"{feld}_en")
        if wert:
            return wert
    return abschnitt.get(feld)


# ── DOCX helpers ──────────────────────────────────────────────────────────────

def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex_word(h: str) -> str:
    return h.lstrip("#").upper()


def _set_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), _hex_word(fill))
    tc_pr.append(shd)


def _set_border(cell, color: str = "DDDDDD") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = OxmlElement("w:tcBorders")
    tc_pr.append(tc_borders)
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        tc_borders.append(el)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), color.lstrip("#"))


def _banner(doc, text: str, bg: str, fg: str = "#FFFFFF", size: int = 13) -> None:
    tbl = doc.add_table(rows=1, cols=1)
    cell = tbl.cell(0, 0)
    _set_shading(cell, bg)
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(size)
    r, g, b = _hex_rgb(fg)
    run.font.color.rgb = RGBColor(r, g, b)


def _heading(doc, text: str, level: int = 2, color: str = "#003399") -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(13 if level == 2 else 11)
    r, g, b = _hex_rgb(color)
    run.font.color.rgb = RGBColor(r, g, b)
    p.paragraph_format.space_before = Pt(10 if level == 2 else 6)
    p.paragraph_format.space_after = Pt(3)


def _body(doc, text: str, size: int = 10, italic: bool = False) -> None:
    p = doc.add_paragraph(text)
    run = p.runs[0] if p.runs else p.add_run(text)
    run.font.size = Pt(size)
    run.italic = italic
    p.paragraph_format.space_after = Pt(3)


def _label_value_row(table, label: str, value: str, bg: str = "FFFFFF") -> None:
    row = table.add_row()
    lc, vc = row.cells[0], row.cells[1]
    _set_shading(lc, "F5F5F5")
    _set_shading(vc, bg)
    _set_border(lc)
    _set_border(vc)
    lp = lc.paragraphs[0]
    lr = lp.add_run(label)
    lr.bold = True
    lr.font.size = Pt(9)
    vp = vc.paragraphs[0]
    vr = vp.add_run(value)
    vr.font.size = Pt(9)


def _safe_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "-", s or "")
    s = re.sub(r"\s+", "_", s).strip("_")
    return s[:80] or "TOM_Entwurf"


# ── TOM-Abschnitt-Inhalt zusammenstellen ─────────────────────────────────────

def _bewertung_label(val: int, sprache: str = "de") -> str:
    if val in (0, 1, 2, 3, 4, 5):
        return _t(sprache, f"b_{val}")
    return str(val)


def build_tom_abschnitt(
    *,
    abschnitt: dict[str, Any],
    bewertungen: dict[str, dict[str, Any]],
    approved_mappings: dict[str, list[dict[str, Any]]],
    doc_index: dict[str, str],
    sprache: str = "de",
) -> dict[str, Any]:
    """Build render-ready content for one TOM section.

    Returns a dict with keys:
    - abschnitt: the section metadata
    - massnahmen: list of {'text': str, 'status': 'cited'|'assumed'|'open', 'citations': [...]}
    - bewertung: rating dict (may be None)
    - has_evidence: bool
    - open_items: list[str]
    """
    tom_id = abschnitt["id"]
    kategorie = abschnitt["kategorie"]

    # Collect evidence citations for this section via DSGVO requirement IDs
    all_citations: list[dict[str, Any]] = []
    for req_id in abschnitt["dsgvo_req_ids"]:
        for mapping in approved_mappings.get(req_id, []):
            all_citations.append({
                "claim": mapping.get("claim", ""),
                "citations": mapping.get("citations", []),
                "rationale": mapping.get("rationale", ""),
                "confidence": mapping.get("confidence", 0.0),
            })

    # Also check TOM-ID directly in approved_mappings
    for mapping in approved_mappings.get(tom_id, []):
        all_citations.append({
            "claim": mapping.get("claim", ""),
            "citations": mapping.get("citations", []),
            "rationale": mapping.get("rationale", ""),
            "confidence": mapping.get("confidence", 0.0),
        })

    # Collect ratings from DSGVO bewertungen
    related_bewertungen = [
        bewertungen[req_id]
        for req_id in abschnitt["dsgvo_req_ids"]
        if req_id in bewertungen
    ]
    avg_bewertung = None
    if related_bewertungen:
        vals = [b.get("bewertung", 0) for b in related_bewertungen]
        avg_bewertung = round(sum(vals) / len(vals), 1)

    # Build massnahmen list
    massnahmen: list[dict[str, Any]] = []
    citation_claims = {m["claim"] for m in all_citations}

    # #1954: Zugeordnet wird über den **deutschen** Hinweis, gedruckt wird der
    # Hinweis in der Sprache des Dokuments. Zwei Gründe:
    #   * Auf Deutsch sind beide Listen identisch — die Zuordnung ist damit
    #     nachweislich unverändert (Regel 1 des Vorgangs).
    #   * Die Nachweis-Aussagen (`claim`) stammen aus den Dokumenten des
    #     Mandanten und können in jeder Sprache vorliegen. Deshalb wird
    #     zusätzlich gegen den übersetzten Hinweis geprüft: Ein englischer
    #     Nachweis soll nicht daran scheitern, dass unser Katalog deutsch ist.
    hinweise_de = abschnitt["massnahmen_hinweise"]
    hinweise_anzeige = abschnitt_text(abschnitt, "massnahmen_hinweise", sprache) \
        or hinweise_de
    if len(hinweise_anzeige) != len(hinweise_de):
        # Eine Übersetzung anderer Länge würde die Entsprechung verschieben —
        # dann gilt die deutsche Liste, und die Lücke fällt im Dokument auf.
        hinweise_anzeige = hinweise_de
    for hint, hint_anzeige in zip(hinweise_de, hinweise_anzeige):
        # Check if any approved mapping covers this hint
        matching = [c for c in all_citations
                    if _text_overlap(hint, c["claim"])
                    or (hint_anzeige != hint
                        and _text_overlap(hint_anzeige, c["claim"]))]
        if matching:
            massnahmen.append({
                "text": hint_anzeige,
                "status": "cited",
                "citations": matching[0]["citations"],
                "rationale": matching[0]["rationale"],
            })
        else:
            # Use assessment rating to decide if "assumed" or "open"
            if avg_bewertung is not None and avg_bewertung >= 4:
                massnahmen.append({"text": hint_anzeige, "status": "assumed",
                                   "citations": []})
            else:
                massnahmen.append({"text": hint_anzeige, "status": "open",
                                   "citations": []})

    # Add any extra cited claims not yet in hints
    for citation in all_citations:
        if citation["claim"] not in [m["text"] for m in massnahmen]:
            massnahmen.append({
                "text": citation["claim"],
                "status": "cited",
                "citations": citation["citations"],
                "rationale": citation.get("rationale", ""),
            })

    open_items = [m["text"] for m in massnahmen if m["status"] == "open"]

    return {
        "abschnitt": abschnitt,
        "massnahmen": massnahmen,
        "avg_bewertung": avg_bewertung,
        "has_evidence": bool(all_citations),
        "open_items": open_items,
    }


def _text_overlap(a: str, b: str) -> bool:
    """Rough overlap check: shared significant words."""
    stopwords = {"und", "oder", "der", "die", "das", "von", "für", "bei", "mit",
                 "in", "an", "zu", "des", "den", "dem", "ein", "eine", "einen"}
    a_words = {w.lower() for w in re.split(r"\W+", a) if len(w) > 3 and w.lower() not in stopwords}
    b_words = {w.lower() for w in re.split(r"\W+", b) if len(w) > 3 and w.lower() not in stopwords}
    if not a_words or not b_words:
        return False
    return len(a_words & b_words) >= 2


# ── DOCX export ───────────────────────────────────────────────────────────────

def export_tom_docx(
    *,
    out_dir: Path,
    projekt_name: str,
    unternehmen: str = "",
    berater: str = "",
    bewertungen: dict[str, dict[str, Any]] | None = None,
    approved_mappings: dict[str, list[dict[str, Any]]] | None = None,
    doc_index: dict[str, str] | None = None,
    sprache: str | None = None,
) -> Path:
    """Generate TOM DOCX draft.

    Args:
        out_dir: Output directory.
        projekt_name: DSGVO project name.
        unternehmen: Company name.
        berater: Consultant name.
        bewertungen: Dict of requirement_id → bewertung row.
        approved_mappings: Dict of requirement_id/tom_id → list of approved mapping dicts.
        doc_index: Dict of doc_id → filename for citation display.
        sprache: Übersteuert die Sprache des Dokuments für diesen Lauf; ohne
            Angabe entscheidet der Mandant (#1954).

    Returns:
        Path to the generated DOCX file.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bewertungen = bewertungen or {}
    approved_mappings = approved_mappings or {}
    doc_index = doc_index or {}

    spr = _rt.aufloesen("dsgvo", projekt_name, sprache)
    platzhalter = _t(spr, "platzhalter")

    doc = Document()
    if spr != "de":
        # Dokumentsprache (`w:lang`) nur bei abweichender Sprache setzen: Für
        # Deutsch war sie vor #1954 nicht gesetzt, und „auf Deutsch
        # byte-identisch" ist der Regressionsschutz dieses Vorgangs. Ohne die
        # Angabe unterstreicht Word in einem englischen Dokument jedes Wort rot.
        from shared.reports.docx_pdf import set_doc_lang
        set_doc_lang(doc, spr)

    # ── Page margins ─────────────────────────────────────────────────────────
    for section in doc.sections:
        section.top_margin    = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin   = Inches(1.0)
        section.right_margin  = Inches(1.0)

    # ── DRAFT banner ─────────────────────────────────────────────────────────
    _banner(
        doc,
        _t(spr, "entwurf_banner"),
        _DRAFT_BG,
        fg=_DRAFT_FG,
        size=11,
    )
    doc.add_paragraph()

    # ── Title ─────────────────────────────────────────────────────────────────
    title_p = doc.add_paragraph()
    tr = title_p.add_run(_t(spr, "titel"))
    tr.bold = True
    tr.font.size = Pt(18)
    r, g, b = _hex_rgb(_EU_BLUE)
    tr.font.color.rgb = RGBColor(r, g, b)
    title_p.paragraph_format.space_after = Pt(4)

    subtitle_p = doc.add_paragraph(_t(spr, "untertitel"))
    subtitle_p.runs[0].font.size = Pt(11)
    subtitle_p.runs[0].italic = True
    subtitle_p.paragraph_format.space_after = Pt(6)

    # ── Metadata table ────────────────────────────────────────────────────────
    meta_tbl = doc.add_table(rows=0, cols=2)
    meta_tbl.autofit = False
    meta_tbl.columns[0].width = Inches(1.8)
    meta_tbl.columns[1].width = Inches(4.7)
    _label_value_row(meta_tbl, _t(spr, "m_organisation"), unternehmen or projekt_name)
    _label_value_row(meta_tbl, _t(spr, "m_projekt"), projekt_name)
    _label_value_row(meta_tbl, _t(spr, "m_erstellt_am"), str(date.today()))
    _label_value_row(meta_tbl, _t(spr, "m_erstellt_von"), berater or platzhalter)
    _label_value_row(meta_tbl, _t(spr, "m_status"), _t(spr, "m_status_wert"),
                     bg="FFF9C4")
    _label_value_row(meta_tbl, _t(spr, "m_rechtsgrundlage"),
                     _t(spr, "m_rechtsgrundlage_wert"))
    doc.add_paragraph()

    # ── Introduction ─────────────────────────────────────────────────────────
    _heading(doc, _t(spr, "h1"), level=2)
    _body(
        doc,
        _t(spr, "einleitung", organisation=unternehmen or projekt_name),
    )
    _body(
        doc,
        _t(spr, "legende"),
        italic=True,
    )
    doc.add_paragraph()

    # ── TOM Sections ─────────────────────────────────────────────────────────
    _heading(doc, _t(spr, "h2"), level=2)
    doc.add_paragraph()

    evidence_total = 0
    assumed_total = 0
    open_total = 0
    all_open_items: list[tuple[str, str]] = []

    for i, abschnitt in enumerate(TOM_ABSCHNITTE, start=1):
        content = build_tom_abschnitt(
            abschnitt=abschnitt,
            bewertungen=bewertungen,
            approved_mappings=approved_mappings,
            doc_index=doc_index,
            sprache=spr,
        )

        kategorie = abschnitt["kategorie"]
        fg_color, bg_color = _KATEGORIE_FARBEN.get(kategorie, ("#2C3E50", "#F5F5F5"))

        # Section header
        _banner(
            doc,
            _t(spr, "abschnitt_banner", nr=i, id=abschnitt["id"],
               titel=abschnitt_text(abschnitt, "titel", spr)),
            fg_color,
            fg="#FFFFFF",
            size=11,
        )

        # Art. reference + description
        ref_p = doc.add_paragraph()
        ref_r = ref_p.add_run(
            _t(spr, "abschnitt_referenz",
               art=abschnitt_text(abschnitt, "art", spr),
               untertitel=abschnitt_text(abschnitt, "untertitel", spr)))
        ref_r.italic = True
        ref_r.font.size = Pt(9)
        r, g, b = _hex_rgb(fg_color)
        ref_r.font.color.rgb = RGBColor(r, g, b)
        ref_p.paragraph_format.space_after = Pt(2)

        _body(doc, abschnitt_text(abschnitt, "beschreibung", spr), size=10)

        # Bewertung
        if content["avg_bewertung"] is not None:
            bval = content["avg_bewertung"]
            blabel = _bewertung_label(round(bval), spr)
            bp = doc.add_paragraph()
            br = bp.add_run(_t(spr, "reifegrad", wert=f"{bval:.1f}", label=blabel))
            br.bold = True
            br.font.size = Pt(9)
            bp.paragraph_format.space_after = Pt(4)

        # Measures table
        tbl = doc.add_table(rows=0, cols=3)
        tbl.autofit = False
        tbl.columns[0].width = Inches(0.7)
        tbl.columns[1].width = Inches(3.9)
        tbl.columns[2].width = Inches(1.9)

        # Header row
        hrow = tbl.add_row()
        for ci, htxt in enumerate([_t(spr, "t_status"), _t(spr, "t_massnahme"),
                                   _t(spr, "t_nachweis")]):
            hc = hrow.cells[ci]
            _set_shading(hc, fg_color)
            _set_border(hc, fg_color)
            hp = hc.paragraphs[0]
            hr_ = hp.add_run(htxt)
            hr_.bold = True
            hr_.font.size = Pt(9)
            hr_.font.color.rgb = RGBColor(255, 255, 255)

        for m in content["massnahmen"]:
            # `status` ist ein **Datenwert** (cited/assumed/open) und bleibt
            # unverändert; übersetzt wird nur die gedruckte Marke (Regel 7).
            status = m["status"]
            if status == "cited":
                status_label = _t(spr, "marke_nachweis")
                row_bg = _CITE_BG
                evidence_total += 1
            elif status == "assumed":
                status_label = _t(spr, "marke_annahme")
                row_bg = _ASSUM_BG
                assumed_total += 1
            else:
                status_label = _t(spr, "marke_offen")
                row_bg = _OPEN_BG
                open_total += 1

            mrow = tbl.add_row()
            sc, mc, nc = mrow.cells[0], mrow.cells[1], mrow.cells[2]
            for cell in (sc, mc, nc):
                _set_shading(cell, row_bg.lstrip("#"))
                _set_border(cell)

            # `sp_` wie `np_` daneben, nicht `sp`: Die Sprachvariable dieser
            # Funktion heißt `spr`, und ein `sp` direkt daneben hat beim Bau von
            # #1954 genau einmal zugeschlagen — die Zuweisung hier überschrieb
            # sie, worauf `abschnitt_text` ab dem zweiten Abschnitt die
            # englischen Texte zog, während `_t` über seinen Rückfall weiter
            # deutsch antwortete. Ein halb übersetztes Dokument, ohne Fehler.
            sp_ = sc.paragraphs[0]
            sr_ = sp_.add_run(status_label)
            sr_.bold = True
            sr_.font.size = Pt(8)

            mp = mc.paragraphs[0]
            mr_ = mp.add_run(m["text"])
            mr_.font.size = Pt(9)

            np_ = nc.paragraphs[0]
            if m.get("citations"):
                cit_strs = []
                for c in m["citations"]:
                    doc_id = c.get("doc_id", c.get("document_id", ""))
                    chunk = c.get("chunk", c.get("chunk_idx", ""))
                    # #2011: `doc_name` hat Vorrang, wenn die Zuordnung ihn
                    # mitbringt. Der KI-Entwurf trägt keine Datei im
                    # `doc_index`; ohne diesen Zweig stand im Dokument die rohe
                    # Kennung („ai“) statt „KI-Entwurf“ — eine Quellenangabe,
                    # die den Leser nicht weiterbringt.
                    fname = (c.get("doc_name")
                             or doc_index.get(doc_id)
                             or (doc_id[:12] + "…" if len(doc_id) > 12 else doc_id))
                    cit_strs.append(_t(spr, "zitat", datei=fname, abschnitt=chunk))
                nr_ = np_.add_run("; ".join(cit_strs))
                nr_.font.size = Pt(8)
                nr_.italic = True
            elif status == "assumed":
                nr_ = np_.add_run(_t(spr, "annahme_hinweis"))
                nr_.font.size = Pt(8)
                nr_.italic = True

        doc.add_paragraph()

        if content["open_items"]:
            all_open_items.extend(
                (abschnitt_text(abschnitt, "titel", spr), item)
                for item in content["open_items"]
            )

    # ── Open items summary ────────────────────────────────────────────────────
    _heading(doc, _t(spr, "h3"), level=2)
    if all_open_items:
        _body(
            doc,
            _t(spr, "offen_intro"),
        )
        oi_tbl = doc.add_table(rows=0, cols=2)
        oi_tbl.autofit = False
        oi_tbl.columns[0].width = Inches(1.8)
        oi_tbl.columns[1].width = Inches(4.7)
        hrow = oi_tbl.add_row()
        for ci, htxt in enumerate([_t(spr, "o_kategorie"), _t(spr, "o_massnahme")]):
            hc = hrow.cells[ci]
            _set_shading(hc, _EU_BLUE)
            hp = hc.paragraphs[0]
            hr_ = hp.add_run(htxt)
            hr_.bold = True
            hr_.font.size = Pt(9)
            hr_.font.color.rgb = RGBColor(255, 255, 255)
        for kategorie_titel, item in all_open_items:
            row = oi_tbl.add_row()
            kc, ic = row.cells[0], row.cells[1]
            _set_shading(kc, "FFF3E0")
            _set_shading(ic, "FFFDE7")
            _set_border(kc)
            _set_border(ic)
            kp = kc.paragraphs[0]
            kr_ = kp.add_run(kategorie_titel)
            kr_.font.size = Pt(9)
            ip = ic.paragraphs[0]
            ir_ = ip.add_run(item)
            ir_.font.size = Pt(9)
    else:
        _body(doc, _t(spr, "alles_belegt"), italic=True)

    doc.add_paragraph()

    # ── Coverage summary ──────────────────────────────────────────────────────
    _heading(doc, _t(spr, "h4"), level=2)
    total = evidence_total + assumed_total + open_total
    cov_tbl = doc.add_table(rows=0, cols=2)
    cov_tbl.autofit = False
    cov_tbl.columns[0].width = Inches(2.5)
    cov_tbl.columns[1].width = Inches(4.0)
    for label, val in [
        (_t(spr, "c_gesamt"), str(total)),
        (_t(spr, "c_nachweis"),
         _t(spr, "c_anteil", anzahl=evidence_total,
            pct=evidence_total * 100 // total if total else 0)),
        (_t(spr, "c_annahme"),
         _t(spr, "c_anteil", anzahl=assumed_total,
            pct=assumed_total * 100 // total if total else 0)),
        (_t(spr, "c_offen"),
         _t(spr, "c_anteil", anzahl=open_total,
            pct=open_total * 100 // total if total else 0)),
    ]:
        _label_value_row(cov_tbl, label, val)

    doc.add_paragraph()

    # ── Legal disclaimer ──────────────────────────────────────────────────────
    _banner(
        doc,
        _t(spr, "disclaimer"),
        _DRAFT_BG,
        fg=_DRAFT_FG,
        size=9,
    )

    # ── Save ──────────────────────────────────────────────────────────────────
    ts = date.today().strftime("%Y%m%d")
    filename = f"TOM_Entwurf_{_safe_filename(projekt_name)}_{ts}.docx"
    out_path = out_dir / filename
    doc.save(str(out_path))
    return out_path


# ── Der TOM-Entwurf als Berichtstyp (#2005) ──────────────────────────────────
#
# Bis v8.6.x gab es den Entwurf nur am Knopf im TOM-Generator, und sein
# Datenweg (KI-Entwurf → ``approved_mappings``) stand **im Endpunkt**. Damit
# ließ sich für ihn keine Word-Vorlage hinterlegen, und das Berichts-Center
# hätte ihn nur über einen zweiten Erzeugungsweg anbieten können — zwei Wege
# zum selben Dokument sind zwei Wahrheiten (#1727). Die Funktionen hier sind
# die **eine** Stelle; Endpunkt und Berichts-Center rufen beide sie.

#: Schlüssel des Entwurfs im Berichts-Center und als ``bericht_typ`` einer
#: Vorlage. Er steht hier und nirgends sonst — eine zweite Schreibweise an
#: einer zweiten Stelle wäre die Spiegel-Liste aus #1731/#1735.
ENTWURF_TYP = "tom_entwurf"


def entwurf_mappings(payload: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    """KI-Entwurf (``{'abschnitte': {…}}``) → ``approved_mappings`` je TOM-ID.

    Wortgleich zu dem, was bis v8.6.x im Endpunkt stand — der Entwurf darf sich
    durch diesen Umzug nicht ändern (das ist der Regressionsschutz von #2005).
    Ein Abschnitt ohne jeden Eintrag kommt bewusst **nicht** in das Ergebnis:
    Ein leerer Eintrag wäre im Dokument eine Aussage ohne Inhalt.

    **#2011 — behoben.** Die Einträge trugen den Schlüssel ``text``,
    :func:`build_tom_abschnitt` liest aber ``claim``. Der Entwurfstext erreichte
    das programmatische Dokument deshalb **nicht**; statt der Einträge entstand
    je Abschnitt genau eine Zeile ``[NACHWEIS]`` mit leerem Text — eine Zeile,
    die einen Nachweis behauptet und nichts sagt. #2005 hat den Befund
    ausdrücklich nicht mitgenommen, weil dort zugesagt war, dass sich der
    Entwurf **ohne** ``template_id`` nicht ändert.

    Jetzt folgen die Einträge dem Vertrag von ``approved_mappings``:
    ``claim`` (die Nachweis-Aussage, gegen die ``_text_overlap`` die
    Katalog-Hinweise abgleicht) und ``citations`` (die Belegliste in der Form,
    die ``:1039`` liest — ``doc_id``/``doc_name``). ``text`` bleibt zusätzlich
    stehen: Der Vorlagen-Weg liest den Entwurf über :func:`entwurf_kontext`
    direkt, und diese Zusage von #2005 soll gelten.
    """
    roh = (payload or {}) if isinstance(payload, dict) else {}
    abschnitte = roh.get("abschnitte") or {}
    out: dict[str, list[dict[str, Any]]] = {}
    for tom_id, content in abschnitte.items():
        if not isinstance(content, dict):
            continue
        items: list[dict[str, Any]] = []
        def _eintrag(aussage: str) -> dict[str, Any]:
            """Ein Entwurfs-Eintrag in der Form, die ``build_tom_abschnitt`` liest."""
            return {
                "claim": aussage,
                "citations": [{"doc_id": "ai", "doc_name": "KI-Entwurf"}],
                "rationale": "",
                "confidence": 0.0,
                # ``text`` bleibt für ``entwurf_kontext`` (Vorlagen-Weg, #2005).
                "text": aussage,
                "doc_id": "ai",
                "doc_name": "KI-Entwurf",
            }

        for m in (content.get("vorhandene_massnahmen") or []):
            items.append(_eintrag(str(m)))
        for g in (content.get("luecken") or []):
            items.append(_eintrag(f"⚠ Lücke: {g}"))
        for r in (content.get("empfehlungen") or []):
            items.append(_eintrag(f"→ Empfehlung: {r}"))
        if items:
            out[str(tom_id)] = items
    return out


def export_entwurf_docx(db_path: Path | str, projekt_name: str, *,
                        out_dir: Path, sprache: str | None = None) -> Path:
    """Den TOM-Entwurf dieses Projekts erzeugen — der **eine** Renderer.

    Ein nicht vorhandenes Projekt ist hier kein Fehler: Der Entwurf folgt dem
    Abschnitts-Katalog und ist auch ohne gespeicherte Daten ein vollständiges
    Arbeitspapier. Einen unbekannten Projektnamen weist der Endpunkt vorher mit
    404 ab.
    """
    from dsgvo.db import load_ai_draft, load_bewertungen, load_projekt

    db_path = Path(db_path)
    projekt = load_projekt(db_path, projekt_name) or {}
    ai = load_ai_draft(db_path, projekt_name, "tom")
    return export_tom_docx(
        out_dir=Path(out_dir),
        projekt_name=projekt_name,
        unternehmen=projekt.get("unternehmen", "") or "",
        berater=projekt.get("berater", "") or "",
        bewertungen=load_bewertungen(db_path, projekt_name),
        approved_mappings=entwurf_mappings((ai or {}).get("payload")),
        sprache=sprache,
    )


def entwurf_kontext(db_path: Path | str, projekt_name: str,
                    sprache: str | None = None) -> dict[str, Any]:
    """Die Entwurfsdaten für eine Word-Vorlage (``tom_entwurf.*``, #2005).

    **Eigene Wurzel, nicht in ``toms``.** ``toms`` ist das gepflegte
    Art.-32-Register aus ``dsgvo_tom`` — gespeicherte Zeilen mit
    Umsetzungsstatus. Der Entwurf ist etwas anderes: der Abschnitts-Katalog
    (TOM-A…TOM-J) mit Maßnahmen, Lücken und Empfehlungen aus dem KI-Entwurf.
    Beide in **eine** Liste zu legen hieße, dass jede bestehende Vorlage, die
    über ``toms`` iteriert, plötzlich Entwurfstext druckt — stillschweigend und
    ohne Fehlermeldung (die Klasse aus #1540/#1771/#1805).

    Gelesen wird der **rohe** Entwurf und nicht der Umweg über
    :func:`entwurf_mappings`: Dort verschmelzen Maßnahmen, Lücken und
    Empfehlungen zu einer Liste mit Textmarken, und eine Vorlage könnte sie
    nicht mehr getrennt setzen.
    """
    from dsgvo.db import load_ai_draft

    db_path = Path(db_path)
    spr = _rt.aufloesen("dsgvo", projekt_name, sprache)
    ai = load_ai_draft(db_path, projekt_name, "tom") or {}
    payload = ai.get("payload") if isinstance(ai.get("payload"), dict) else {}
    roh = (payload or {}).get("abschnitte") or {}

    def _liste(wert: Any) -> list[str]:
        if not isinstance(wert, (list, tuple)):
            return []
        return [str(x) for x in wert]

    abschnitte: list[dict[str, Any]] = []
    luecken_gesamt = 0
    for a in TOM_ABSCHNITTE:
        inhalt = roh.get(a["id"]) if isinstance(roh.get(a["id"]), dict) else {}
        massnahmen = _liste((inhalt or {}).get("vorhandene_massnahmen"))
        luecken = _liste((inhalt or {}).get("luecken"))
        empfehlungen = _liste((inhalt or {}).get("empfehlungen"))
        luecken_gesamt += len(luecken)
        abschnitte.append({
            "id": a["id"],
            "kategorie": a["kategorie"],
            "titel": abschnitt_text(a, "titel", spr) or a["titel"],
            "untertitel": abschnitt_text(a, "untertitel", spr) or a["untertitel"],
            "art": abschnitt_text(a, "art", spr) or a["art"],
            "vorhandene_massnahmen": massnahmen,
            "luecken": luecken,
            "empfehlungen": empfehlungen,
            "hat_entwurf": bool(massnahmen or luecken or empfehlungen),
        })

    return {
        "vorhanden": bool(roh),
        "stand": str(ai.get("updated_at") or ""),
        "fazit": str((payload or {}).get("fazit") or ""),
        "abschnitte": abschnitte,
        "anzahl_abschnitte": len(abschnitte),
        "anzahl_luecken": luecken_gesamt,
    }
