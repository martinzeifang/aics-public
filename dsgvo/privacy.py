"""DSGVO Privacy Policy Draft Generator.

Generates a website/app privacy policy DOCX draft from a structured intake form and
optional evidence. Unknowns are explicit placeholders — nothing is hallucinated.

DIE SPRACHE GEHÖRT DEM MANDANTEN (#1954)
Dieses Dokument ist der Fall, für den die Firmensprache gebaut ist: Der Mandant
**veröffentlicht** es und haftet dafür. Über seine Sprache entscheidet deshalb
``firmen.sprache`` und nicht der Bearbeiter, der es zufällig erzeugt — aufgelöst
serverseitig über ``shared.reports.texte.aufloesen``, fail-open auf Deutsch.

Die englische Fassung benutzt die **amtliche englische Fassung** der Verordnung
(EU) 2016/679: ``personal data``, ``controller``, ``processor``, ``data
subject``, ``legitimate interests``, ``supervisory authority``, ``right to lodge
a complaint``, ``recipients``. Fundstellen behalten ihre Ziffern und wechseln
nur die Schreibweise (``Art. 6 Abs. 1 lit. f DSGVO`` → ``Art. 6(1)(f) GDPR``) —
die Lehre aus #1763/#1792, wo geratene Fundstellen in Dokumente gedruckt wurden,
die ein Prüfer liest. Deutsche Paragraphen bleiben deutsch zitiert
(``§ 38 BDSG``, ``§ 147 AO``).

ZWEI KANÄLE AN EINER STELLE
``INTAKE_FELDER`` speist zweierlei: das **Formular** (Bedienoberfläche, folgt der
Anzeigesprache des Bearbeiters — ``label``) und die **Fehlliste im Dokument**
(folgt dem Mandanten — ``label_en`` über :func:`intake_missing_fields`). Die
englische Beschriftung steht deshalb neben der deutschen und nicht in einem
eigenen Katalog (Muster ``ReportSpec.titel_en``): Wer eine Beschriftung ändert,
sieht die andere im selben Atemzug.
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


# ── Colours ───────────────────────────────────────────────────────────────────

_EU_BLUE   = "#003399"
_DARK      = "#1a237e"
_DRAFT_BG  = "#FFF9C4"
_DRAFT_FG  = "#5D4037"
_MISS_BG   = "#FCE4EC"
_SECTION_BG= "#E8EAF6"


# ── Intake schema (field definitions) ────────────────────────────────────────

INTAKE_FELDER: list[dict[str, Any]] = [
    # ── Verantwortlicher ──────────────────────────────────────────────────────
    {"key": "app_name",        "label": "Name der Website / App",            "label_en": "Name of the website / app",            "group": "Verantwortlicher", "required": True,  "tip": "z. B. 'Mein Webshop' oder 'MeineFirma.de'"},
    {"key": "betreiber_name",  "label": "Name des Betreibers",               "label_en": "Name of the operator",                 "group": "Verantwortlicher", "required": True,  "tip": "Vollständiger Firmen- oder Privatname"},
    {"key": "betreiber_strasse","label": "Straße und Hausnummer",            "label_en": "Street and house number",              "group": "Verantwortlicher", "required": True,  "tip": ""},
    {"key": "betreiber_plzort","label": "PLZ und Ort",                       "label_en": "Postcode and town",                    "group": "Verantwortlicher", "required": True,  "tip": ""},
    {"key": "betreiber_land",  "label": "Land",                              "label_en": "Country",                              "group": "Verantwortlicher", "required": False, "tip": "Standard: Deutschland"},
    {"key": "kontakt_email",   "label": "Kontakt-E-Mail-Adresse",            "label_en": "Contact email address",                "group": "Verantwortlicher", "required": True,  "tip": "Für Datenschutzanfragen"},
    {"key": "kontakt_telefon", "label": "Kontakt-Telefon (optional)",        "label_en": "Contact telephone (optional)",         "group": "Verantwortlicher", "required": False, "tip": ""},

    # ── Datenschutzbeauftragter ───────────────────────────────────────────────
    {"key": "dsb_name",        "label": "Name des Datenschutzbeauftragten",  "label_en": "Name of the data protection officer",  "group": "Datenschutzbeauftragter", "required": False, "tip": "Nur wenn DSB vorhanden oder gesetzlich vorgeschrieben"},
    {"key": "dsb_email",       "label": "E-Mail Datenschutzbeauftragter",    "label_en": "Email of the data protection officer", "group": "Datenschutzbeauftragter", "required": False, "tip": ""},

    # ── Verarbeitungszwecke ───────────────────────────────────────────────────
    {"key": "zwecke",          "label": "Verarbeitungszwecke",               "label_en": "Purposes of processing",               "group": "Verarbeitungszwecke", "required": True,
     "type": "checklist",
     "optionen": [
         ("kontaktformular",   "Kontaktformular / Anfragen"),
         ("newsletter",        "Newsletter / E-Mail-Marketing"),
         ("webanalyse",        "Website-Analyse / Statistik"),
         ("ecommerce",         "Online-Bestellungen / E-Commerce"),
         ("firmenkonto",       "Kundenkonto / Registrierung"),
         ("cookies_tracking",  "Cookies und Tracking (Werbung)"),
         ("bewerbungen",       "Bewerbungen / Personalgewinnung"),
         ("login_auth",        "Login / Authentifizierung"),
         ("support",           "Kundensupport / Helpdesk"),
         ("sonstiges",         "Sonstige (bitte beschreiben)"),
     ]},
    {"key": "zwecke_sonstiges","label": "Sonstige Zwecke (Freitext)",        "label_en": "Other purposes (free text)",           "group": "Verarbeitungszwecke", "required": False, "tip": ""},

    # ── Rechtsgrundlagen ─────────────────────────────────────────────────────
    {"key": "rechtsgrundlage_einwilligung", "label": "Einwilligung (Art. 6 Abs. 1 lit. a)",  "label_en": "Consent (Art. 6(1)(a))",                      "group": "Rechtsgrundlagen", "required": False, "type": "bool", "tip": "z. B. Newsletter, Tracking-Cookies"},
    {"key": "rechtsgrundlage_vertrag",      "label": "Vertragserfüllung (Art. 6 Abs. 1 lit. b)", "label_en": "Performance of a contract (Art. 6(1)(b))", "group": "Rechtsgrundlagen", "required": False, "type": "bool", "tip": "z. B. Bestellabwicklung"},
    {"key": "rechtsgrundlage_berechtigtes", "label": "Berechtigtes Interesse (Art. 6 Abs. 1 lit. f)", "label_en": "Legitimate interests (Art. 6(1)(f))",  "group": "Rechtsgrundlagen", "required": False, "type": "bool", "tip": "z. B. Websitestatistik ohne Einwilligung"},
    {"key": "rechtsgrundlage_beschreibung", "label": "Erläuterung Rechtsgrundlagen",       "label_en": "Explanation of the legal bases",              "group": "Rechtsgrundlagen", "required": False, "tip": "Kurze Erläuterung welche Grundlage für welchen Zweck gilt"},

    # ── Empfänger / Dritte ────────────────────────────────────────────────────
    {"key": "hosting_anbieter","label": "Hosting-Anbieter",                  "label_en": "Hosting provider",                     "group": "Empfänger & Hosting", "required": False, "tip": "z. B. IONOS, Hetzner, AWS Frankfurt"},
    {"key": "hosting_ort",     "label": "Hosting-Standort",                  "label_en": "Hosting location",                     "group": "Empfänger & Hosting", "required": False, "tip": "z. B. 'EU / Deutschland' oder 'USA'"},
    {"key": "dritte",          "label": "Sonstige Drittanbieter / Tools",    "label_en": "Other third-party providers / tools",  "group": "Empfänger & Hosting", "required": False, "tip": "z. B. Google Analytics, Stripe, Mailchimp – kommagetrennt"},
    {"key": "drittland",       "label": "Datenübertragung in Drittländer?",  "label_en": "Transfer of data to third countries?", "group": "Empfänger & Hosting", "required": False, "type": "bool", "tip": "Ja, falls Anbieter Daten in Länder außerhalb EU/EWR übertragen"},
    {"key": "drittland_beschreibung", "label": "Drittland-Details",          "label_en": "Third-country details",                "group": "Empfänger & Hosting", "required": False, "tip": "Welche Anbieter, welche Länder, welche Garantien (SCCs, Angemessenheitsbeschluss)"},

    # ── Speicherdauer ────────────────────────────────────────────────────────
    {"key": "speicherdauer_kontakt",   "label": "Speicherdauer Kontaktdaten", "label_en": "Storage period for contact data",     "group": "Speicherdauer", "required": False, "tip": "z. B. '3 Jahre nach letztem Kontakt'"},
    {"key": "speicherdauer_bestellungen","label": "Speicherdauer Bestelldaten","label_en": "Storage period for order data",       "group": "Speicherdauer", "required": False, "tip": "z. B. '10 Jahre (Handelsrechtliche Aufbewahrungspflicht)'"},
    {"key": "speicherdauer_logs",      "label": "Speicherdauer Server-Logs", "label_en": "Storage period for server logs",       "group": "Speicherdauer", "required": False, "tip": "z. B. '7 Tage'"},
    {"key": "speicherdauer_sonstiges", "label": "Weitere Speicherfristen",   "label_en": "Further storage periods",              "group": "Speicherdauer", "required": False, "tip": ""},

    # ── Cookies ──────────────────────────────────────────────────────────────
    {"key": "cookies_notwendig",   "label": "Notwendige Cookies",       "label_en": "Necessary cookies",                         "group": "Cookies", "required": False, "type": "bool", "tip": "Session-Cookies, Warenkorbcookies"},
    {"key": "cookies_analyse",     "label": "Analyse-Cookies",          "label_en": "Analytics cookies",                         "group": "Cookies", "required": False, "type": "bool", "tip": "z. B. Google Analytics, Matomo"},
    {"key": "cookies_marketing",   "label": "Marketing-/Tracking-Cookies","label_en": "Marketing / tracking cookies",            "group": "Cookies","required": False, "type": "bool", "tip": "z. B. Facebook Pixel, Google Ads"},
    {"key": "cookies_tools",       "label": "Verwendete Cookie-Tools",  "label_en": "Cookie tools used",                         "group": "Cookies", "required": False, "tip": "z. B. 'Cookiebot', 'Usercentrics', 'eigene Lösung'"},

    # ── Betroffenenrechte ─────────────────────────────────────────────────────
    {"key": "betroffenenrechte_email","label": "E-Mail für Betroffenenanfragen","label_en": "Email for data subject requests",   "group": "Betroffenenrechte","required": False,"tip": "Falls abweichend von Kontakt-E-Mail"},
]

INTAKE_GRUPPEN = [
    "Verantwortlicher",
    "Datenschutzbeauftragter",
    "Verarbeitungszwecke",
    "Rechtsgrundlagen",
    "Empfänger & Hosting",
    "Speicherdauer",
    "Cookies",
    "Betroffenenrechte",
]

_PFLICHTFELDER = {f["key"] for f in INTAKE_FELDER if f.get("required")}


def _feld_label(feld: dict[str, Any], sprache: str = "de") -> str:
    """Beschriftung eines Intake-Feldes in der gewünschten Sprache.

    Fehlt die Übersetzung, gilt die deutsche Beschriftung — dieselbe Zusage wie
    ``shared.reports.texte.macher``: Ein neues Feld erscheint sofort in jedem
    Dokument, auf Deutsch, bis es jemand übersetzt. Eine leere Zeile in einer
    Fehlliste sähe dagegen aus wie „nichts fehlt".
    """
    if sprache != "de":
        return str(feld.get("label_en") or feld.get("label") or "")
    return str(feld.get("label") or "")


def intake_missing_fields(intake: dict[str, Any], *,
                          sprache: str | None = None) -> list[str]:
    """Return list of labels for required fields not yet filled.

    ``sprache`` entscheidet über die Beschriftungen (#1954). Ohne Angabe gilt
    Deutsch — die Aufrufer in ``server/api/dsgvo.py`` liefern damit unverändert
    die deutsche Liste an das Formular, während das **Dokument** die Sprache des
    Mandanten bekommt.
    """
    spr = sprache or "de"
    missing = []
    for f in INTAKE_FELDER:
        if not f.get("required"):
            continue
        val = intake.get(f["key"])
        if f.get("type") == "checklist":
            if not (isinstance(val, list) and val):
                missing.append(_feld_label(f, spr))
        elif not str(val or "").strip():
            missing.append(_feld_label(f, spr))
    return missing


# ── Prosa des Dokuments je Sprache (#1954) ───────────────────────────────────
#
# Die Texte stehen bei ihrem Renderer und nicht in einem zentralen Katalog
# (Begründung im Kopf von ``shared/reports/texte.py``): Wer einen Abschnitt
# ändert, sieht seinen Text im selben Atemzug.
#
# Der deutsche Katalog ist eine **zeichengenaue** Kopie der Zeichenketten, die
# vorher im Quelltext standen — einschließlich der doppelten Leerzeichen in den
# Überschriften, der Gedankenstriche und der Leerzeichen am Anfang der
# Anfügungen. Das ist die Zusage dieses Umbaus: Auf Deutsch bleibt das Dokument
# byte-identisch, und damit bleibt jeder Bestandstest ein Regressionsschutz.
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        # ── Banner, Titel, Kopf ─────────────────────────────────────────────
        "entwurf_banner": "⚠  ENTWURF – Nicht rechtsverbindlich. Vor Veröffentlichung rechtlich prüfen lassen.",
        "fehlen_banner": "ℹ  {n} Pflichtfeld(er) fehlen: {felder}",
        "fehlen_weitere": " … und {n} weitere",
        "titel": "Datenschutzerklärung",
        "untertitel": "für {app}",
        "stand": "Stand: {datum}",

        # ── Platzhalter-Gerüst ──────────────────────────────────────────────
        "platzhalter": "[PLATZHALTER: {feld}]",
        "platzhalter_hinweis": "  – {hinweis}",

        # ── 1. Verantwortlicher ─────────────────────────────────────────────
        "h_1": "1.  Verantwortlicher",
        "verantwortlicher_intro": (
            "Verantwortlicher im Sinne der Datenschutz-Grundverordnung (DSGVO) und sonstiger "
            "nationaler Datenschutzgesetze der Mitgliedstaaten sowie anderer datenschutzrechtlicher "
            "Bestimmungen ist:"),
        "land_standard": "Deutschland",
        "email_zeile": "E-Mail: {wert}",
        "telefon_zeile": "Telefon: {wert}",
        "kontakt_zeile": "Kontakt: {wert}",
        "ph_betreiber": "Name des Betreibers",
        "ph_betreiber_hinweis": "Vollständiger Firmen- oder Privatname",
        "ph_strasse": "Straße und Hausnummer",
        "ph_plzort": "PLZ, Ort, Land",
        "ph_email": "Kontakt-E-Mail-Adresse",

        # ── 1.1 Vertreter in der Union ──────────────────────────────────────
        "h_1_1": "1.1  Vertreter in der Union (Art. 27 DSGVO)",
        "euv_intro": (
            "Da der Verantwortliche nicht in der Union niedergelassen ist, jedoch "
            "Verarbeitungen nach Art. 3 Abs. 2 DSGVO vornimmt, wurde gemäß Art. 27 "
            "DSGVO folgender Vertreter in der Union benannt:"),
        "ph_euv_name": "Name des EU-Vertreters",
        "ph_euv_anschrift": "Anschrift des EU-Vertreters (Mitgliedstaat)",
        "ph_euv_kontakt": "Kontaktdaten des EU-Vertreters",

        # ── 2. Datenschutzbeauftragter ──────────────────────────────────────
        "h_2": "2.  Datenschutzbeauftragter",
        "dsb_ist": "Unser Datenschutzbeauftragter ist:",
        "dsb_pflicht": (
            "Ein Datenschutzbeauftragter ist gesetzlich vorgeschrieben, wenn z. B. eine "
            "Behörde oder öffentliche Stelle verarbeitet, wenn im Kernbereich regelmäßig "
            "mindestens 20 Personen personenbezogene Daten verarbeiten (§ 38 BDSG), "
            "oder wenn besondere Kategorien von Daten oder Daten über strafrechtliche "
            "Verurteilungen systematisch verarbeitet werden."),
        "ph_dsb": "Datenschutzbeauftragter",
        "ph_dsb_hinweis": "Name und Kontaktdaten des DSB oder Feststellung, dass keine Pflicht besteht",

        # ── 3. Allgemeine Hinweise ──────────────────────────────────────────
        "h_3": "3.  Allgemeine Hinweise zur Datenverarbeitung",
        "allgemein_intro": (
            "Wir verarbeiten personenbezogene Daten unserer Nutzer grundsätzlich nur, soweit dies "
            "zur Bereitstellung einer funktionsfähigen Website sowie unserer Inhalte und Leistungen "
            "erforderlich ist. Die Verarbeitung personenbezogener Daten erfolgt regelmäßig nur nach "
            "Einwilligung des Nutzers. Eine Ausnahme gilt in solchen Fällen, in denen eine vorherige "
            "Einholung einer Einwilligung aus tatsächlichen Gründen nicht möglich ist und die "
            "Verarbeitung der Daten durch gesetzliche Vorschriften gestattet ist."),

        # ── 3.1 Hosting und Logfiles ────────────────────────────────────────
        "h_3_1": "3.1  Bereitstellung der Website und Server-Logfiles",
        "hosting_satz": "Diese Website wird bei {anbieter} gehostet",
        "hosting_rz": " (Rechenzentrum: {ort})",
        "hosting_logs": (
            ". Bei jedem Aufruf unserer Internetseite erfasst unser System automatisiert "
            "Daten und Informationen vom Computersystem des aufrufenden Rechners. "
            "Erfasst werden dabei: IP-Adresse, Datum und Uhrzeit des Zugriffs, "
            "aufgerufene Seite, Referrer-URL, Browsertyp, Betriebssystem."),
        "ph_hosting": "Hosting-Anbieter und Rechenzentrumsstandort",
        "logs_rechtsgrundlage": (
            "Rechtsgrundlage für die vorübergehende Speicherung der Daten ist "
            "Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse an der Sicherheit und "
            "dem stabilen Betrieb der Website)."),
        "loeschung_satz": (
            "Die Daten werden gelöscht, sobald sie für die Erreichung des Zweckes ihrer "
            "Erhebung nicht mehr erforderlich sind."),
        "logs_dauer": " Server-Logs werden nach {dauer} gelöscht.",
        "ph_logs": "Speicherdauer Server-Logs",
        "ph_logs_hinweis": "z. B. '7 Tage'",

        # ── 4. Zwecke ───────────────────────────────────────────────────────
        "h_4": "4.  Zwecke der Datenverarbeitung",
        "ph_zwecke": "Verarbeitungszwecke",
        "ph_zwecke_hinweis": "Bitte Zwecke im Intake-Formular auswählen",
        "abschnitt_4": "4.{nr}  {titel}",
        "rechtsgrundlage_zeile": "Rechtsgrundlage: {rg}",
        "aufbewahrung": " Aufbewahrungsdauer: {dauer}.",

        # Bezeichnungen der Zwecke (Reihenfolge: `_ZWECK_KEYS`)
        "zweck_kontaktformular": "Kontaktformular und Anfragen",
        "zweck_newsletter": "Newsletter und E-Mail-Marketing",
        "zweck_webanalyse": "Website-Analyse und Statistik",
        "zweck_ecommerce": "Online-Bestellungen und E-Commerce",
        "zweck_firmenkonto": "Kundenkonto und Registrierung",
        "zweck_cookies_tracking": "Cookies und Tracking",
        "zweck_bewerbungen": "Bewerbungen und Personalgewinnung",
        "zweck_login_auth": "Login und Authentifizierung",
        "zweck_support": "Kundensupport",
        "zweck_sonstiges": "Weitere Zwecke",

        # Rechtsgrundlagen je Zweck
        "rg_kontaktformular": "Art. 6 Abs. 1 lit. b DSGVO (Vertragsanbahnung) oder Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse)",
        "rg_newsletter": "Art. 6 Abs. 1 lit. a DSGVO (Einwilligung)",
        "rg_webanalyse": "Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse) oder Art. 6 Abs. 1 lit. a DSGVO (Einwilligung bei Tracking-Cookies)",
        "rg_ecommerce": "Art. 6 Abs. 1 lit. b DSGVO (Vertragserfüllung), Art. 6 Abs. 1 lit. c DSGVO (gesetzliche Verpflichtung für Buchhaltung)",
        "rg_firmenkonto": "Art. 6 Abs. 1 lit. b DSGVO (Vertragserfüllung)",
        "rg_cookies_tracking": "Art. 6 Abs. 1 lit. a DSGVO (Einwilligung)",
        "rg_bewerbungen": "Art. 6 Abs. 1 lit. b DSGVO (vorvertragliche Maßnahmen), § 26 BDSG",
        "rg_login_auth": "Art. 6 Abs. 1 lit. b DSGVO (Vertragserfüllung)",
        "rg_support": "Art. 6 Abs. 1 lit. b DSGVO (Vertragserfüllung) oder Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse)",

        "zweck_kontakt_text": (
            "Wenn Sie uns über das Kontaktformular oder per E-Mail kontaktieren, "
            "speichern wir die von Ihnen angegebenen Daten (Name, E-Mail-Adresse, "
            "Nachricht) zur Bearbeitung Ihrer Anfrage."),
        "ph_speicher_kontakt": "Speicherdauer Kontaktdaten",
        "ph_speicher_kontakt_hinweis": "z. B. '3 Jahre'",

        "zweck_newsletter_text": (
            "Wenn Sie unseren Newsletter abonnieren möchten, benötigen wir von Ihnen "
            "eine E-Mail-Adresse sowie Informationen, die uns die Überprüfung gestatten, "
            "dass Sie der Inhaber der angegebenen E-Mail-Adresse sind (Double-Opt-in)."),
        "newsletter_widerruf": (
            "Die Einwilligung zur Speicherung der Daten, der E-Mail-Adresse sowie "
            "deren Nutzung zum Versand des Newsletters können Sie jederzeit widerrufen."),

        "zweck_webanalyse_text": (
            "Diese Website nutzt Tools zur Webanalyse, um die Nutzung unserer "
            "Website auszuwerten und unsere Website und Werbung zu verbessern."),
        "tools_zeile": "Verwendete Tools: {tools}",
        "ph_analyse_tools": "Verwendete Analyse-Tools",
        "ph_analyse_tools_hinweis": "z. B. Google Analytics, Matomo",

        "zweck_ecommerce_text": (
            "Wenn Sie bei uns bestellen, erheben und verwenden wir Ihre personenbezogenen "
            "Daten, soweit dies für die Abwicklung der Bestellung, die Abwicklung der "
            "Zahlung und die Lieferung der Waren notwendig ist."),
        "bestelldaten_aufbewahrung": "Bestelldaten unterliegen den gesetzlichen Aufbewahrungspflichten.",
        "ph_speicher_bestellungen": "Speicherdauer Bestelldaten",
        "ph_speicher_bestellungen_hinweis": "z. B. '10 Jahre (§ 147 AO)'",

        "ph_detail": "Detailbeschreibung: {titel}",
        "ph_detail_hinweis": "Bitte Zweck, verarbeitete Daten, Rechtsgrundlage und Speicherdauer ergänzen",

        # ── 5. Cookies ──────────────────────────────────────────────────────
        "h_5": "5.  Cookies",
        "cookies_intro": (
            "Unsere Website verwendet Cookies. Cookies sind Textdateien, die im Internetbrowser "
            "bzw. vom Internetbrowser auf dem Computersystem des Nutzers gespeichert werden. "
            "Ruft ein Nutzer eine Website auf, so kann ein Cookie auf dem Betriebssystem des "
            "Nutzers gespeichert werden."),
        "cookies_notwendig": (
            "Notwendige Cookies: Diese Cookies sind für den Betrieb der Website technisch "
            "erforderlich (z. B. Session-Cookies). Rechtsgrundlage: Art. 6 Abs. 1 lit. f DSGVO."),
        "cookies_analyse": (
            "Analyse-Cookies: Diese Cookies ermöglichen uns, die Nutzung unserer Website "
            "zu analysieren. Rechtsgrundlage: Art. 6 Abs. 1 lit. a DSGVO (Einwilligung)."),
        "cookies_marketing": (
            "Marketing-Cookies: Diese Cookies werden eingesetzt, um Nutzern auf sie "
            "zugeschnittene Werbung anzuzeigen. Rechtsgrundlage: Art. 6 Abs. 1 lit. a DSGVO (Einwilligung)."),
        "ph_analyse_name": "Analyse-Tool-Name",
        "ph_analyse_name_hinweis": "z. B. Google Analytics 4, Matomo",
        "ph_cookie_typen": "Cookie-Typen und Details",
        "ph_cookie_typen_hinweis": "Bitte angeben welche Cookie-Typen verwendet werden",

        # ── 6. Weitergabe ───────────────────────────────────────────────────
        "h_6": "6.  Weitergabe personenbezogener Daten",
        "weitergabe_intro": (
            "Eine Übermittlung Ihrer persönlichen Daten an Dritte zu anderen als den im Folgenden "
            "aufgeführten Zwecken findet nicht statt. Wir geben Ihre persönlichen Daten nur an Dritte "
            "weiter, wenn Sie Ihre ausdrückliche Einwilligung dazu erteilt haben, wenn die Weitergabe "
            "zur Abwicklung eines Vertrags mit Ihnen erforderlich ist, wenn wir zur Weitergabe "
            "gesetzlich verpflichtet sind, oder wenn die Weitergabe zur Geltendmachung, Ausübung oder "
            "Verteidigung von Rechtsansprüchen erforderlich ist und kein Grund zur Annahme besteht, "
            "dass Sie ein überwiegendes schutzwürdiges Interesse an der Nichtweitergabe Ihrer Daten haben."),
        "dienstleister_zeile": "Folgende Dienstleister erhalten Zugang zu personenbezogenen Daten: {dritte}",
        "h_6_1": "6.1  Datenübertragung in Drittländer",
        "ph_drittland": "Drittland-Details",
        "ph_drittland_hinweis": "Welche Anbieter, welche Länder, welche Garantien (z. B. EU-SCCs, Angemessenheitsbeschluss)?",
        "ph_drittland_klaeren": "Drittlandtransfer – Klärung erforderlich",
        "ph_drittland_klaeren_hinweis": "Bitte prüfen ob Hosting oder Drittanbieter Daten außerhalb EU/EWR übertragen",

        # ── 7. Betroffenenrechte ────────────────────────────────────────────
        "h_7": "7.  Ihre Rechte als betroffene Person",
        "rechte_intro": (
            "Im Rahmen der geltenden gesetzlichen Bestimmungen haben Sie jederzeit das Recht auf "
            "unentgeltliche Auskunft über Ihre gespeicherten personenbezogenen Daten, deren Herkunft "
            "und Empfänger und den Zweck der Datenverarbeitung und ggf. ein Recht auf Berichtigung, "
            "Sperrung oder Löschung dieser Daten."),
        "recht_auskunft": "Auskunftsrecht",
        "recht_auskunft_norm": "Art. 15 DSGVO",
        "recht_auskunft_text": "Recht auf Auskunft über die zu Ihrer Person gespeicherten Daten.",
        "recht_berichtigung": "Berichtigungsrecht",
        "recht_berichtigung_norm": "Art. 16 DSGVO",
        "recht_berichtigung_text": "Recht auf Berichtigung unrichtiger oder unvollständiger personenbezogener Daten.",
        "recht_loeschung": "Recht auf Löschung",
        "recht_loeschung_norm": "Art. 17 DSGVO",
        "recht_loeschung_text": "Recht auf Löschung Ihrer personenbezogenen Daten, sofern kein Aufbewahrungsgrund entgegensteht.",
        "recht_einschraenkung": "Recht auf Einschränkung",
        "recht_einschraenkung_norm": "Art. 18 DSGVO",
        "recht_einschraenkung_text": "Recht auf Einschränkung der Verarbeitung Ihrer Daten.",
        "recht_widerspruch": "Widerspruchsrecht",
        "recht_widerspruch_norm": "Art. 21 DSGVO",
        "recht_widerspruch_text": "Recht auf Widerspruch gegen die Verarbeitung Ihrer Daten.",
        "recht_portabilitaet": "Datenübertragbarkeit",
        "recht_portabilitaet_norm": "Art. 20 DSGVO",
        "recht_portabilitaet_text": "Recht auf Erhalt Ihrer Daten in einem maschinenlesbaren Format.",
        "recht_widerruf": "Widerruf der Einwilligung",
        "recht_widerruf_norm": "Art. 7 Abs. 3 DSGVO",
        "recht_widerruf_text": "Recht auf Widerruf einer erteilten Einwilligung mit Wirkung für die Zukunft.",
        "recht_beschwerde": "Beschwerderecht",
        "recht_beschwerde_norm": "Art. 77 DSGVO",
        "recht_beschwerde_text": "Recht auf Beschwerde bei der zuständigen Datenschutz-Aufsichtsbehörde.",
        "rechte_kontakt": "Zur Ausübung Ihrer Rechte wenden Sie sich bitte an: {email}",
        "ph_rechte_kontakt": "Kontaktadresse für Betroffenenanfragen",

        # ── 8. Checkliste ───────────────────────────────────────────────────
        "h_8": "8.  Checkliste fehlender Informationen",
        "checkliste_banner": "Folgende {n} Felder müssen vor der Veröffentlichung ausgefüllt werden:",
        "checkliste_zeile": "  ☐  {feld}",
        "alles_gefuellt": (
            "Alle Pflichtfelder sind ausgefüllt. Bitte trotzdem durch eine "
            "Fachperson prüfen lassen."),

        # ── Disclaimer ──────────────────────────────────────────────────────
        "disclaimer": (
            "Rechtlicher Hinweis: Dieses Dokument wurde automatisiert erstellt und stellt einen "
            "unverbindlichen Entwurf dar. Es ersetzt keine rechtliche Prüfung. "
            "Bitte lassen Sie dieses Dokument vor der Veröffentlichung durch einen "
            "qualifizierten Datenschutzbeauftragten oder Rechtsanwalt prüfen."),
    },
    "en": {
        # ── Banner, Titel, Kopf ─────────────────────────────────────────────
        "entwurf_banner": "⚠  DRAFT – Not legally binding. Have it reviewed legally before publication.",
        "fehlen_banner": "ℹ  {n} mandatory field(s) missing: {felder}",
        "fehlen_weitere": " … and {n} more",
        "titel": "Privacy Policy",
        "untertitel": "for {app}",
        "stand": "As of: {datum}",

        # ── Platzhalter-Gerüst ──────────────────────────────────────────────
        "platzhalter": "[PLACEHOLDER: {feld}]",
        "platzhalter_hinweis": "  – {hinweis}",

        # ── 1. Controller ───────────────────────────────────────────────────
        "h_1": "1.  Controller",
        "verantwortlicher_intro": (
            "The controller within the meaning of the General Data Protection Regulation "
            "(GDPR), of other national data protection laws of the Member States and of "
            "other data protection provisions is:"),
        "land_standard": "Germany",
        "email_zeile": "Email: {wert}",
        "telefon_zeile": "Telephone: {wert}",
        "kontakt_zeile": "Contact: {wert}",
        "ph_betreiber": "Name of the operator",
        "ph_betreiber_hinweis": "Full company or private name",
        "ph_strasse": "Street and house number",
        "ph_plzort": "Postcode, town, country",
        "ph_email": "Contact email address",

        # ── 1.1 Representative in the Union ─────────────────────────────────
        "h_1_1": "1.1  Representative in the Union (Art. 27 GDPR)",
        "euv_intro": (
            "As the controller is not established in the Union but carries out processing "
            "within the meaning of Art. 3(2) GDPR, the following representative in the "
            "Union has been designated in accordance with Art. 27 GDPR:"),
        "ph_euv_name": "Name of the EU representative",
        "ph_euv_anschrift": "Address of the EU representative (Member State)",
        "ph_euv_kontakt": "Contact details of the EU representative",

        # ── 2. Data Protection Officer ──────────────────────────────────────
        "h_2": "2.  Data Protection Officer",
        "dsb_ist": "Our data protection officer is:",
        "dsb_pflicht": (
            "A data protection officer is required by law, for example where a public "
            "authority or body carries out the processing, where at least 20 persons are "
            "regularly engaged in the core activity of processing personal data "
            "(§ 38 BDSG), or where special categories of data or data relating to "
            "criminal convictions are processed systematically."),
        "ph_dsb": "Data protection officer",
        "ph_dsb_hinweis": "Name and contact details of the DPO, or a statement that no obligation exists",

        # ── 3. General information ──────────────────────────────────────────
        "h_3": "3.  General information on the data processing",
        "allgemein_intro": (
            "As a rule, we process personal data of our users only to the extent "
            "necessary to provide a functioning website and our content and services. "
            "Personal data are regularly processed only with the consent of the user. "
            "An exception applies in cases where obtaining prior consent is not possible "
            "for factual reasons and the processing of the data is permitted by statutory "
            "provisions."),

        # ── 3.1 Hosting and log files ───────────────────────────────────────
        "h_3_1": "3.1  Provision of the website and server log files",
        "hosting_satz": "This website is hosted by {anbieter}",
        "hosting_rz": " (data centre: {ort})",
        "hosting_logs": (
            ". Each time our website is accessed, our system automatically collects data "
            "and information from the computer system of the accessing device. The "
            "following are collected: IP address, date and time of access, page accessed, "
            "referrer URL, browser type, operating system."),
        "ph_hosting": "Hosting provider and data centre location",
        "logs_rechtsgrundlage": (
            "The legal basis for the temporary storage of the data is Art. 6(1)(f) GDPR "
            "(legitimate interests in the security and stable operation of the website)."),
        "loeschung_satz": (
            "The data are erased as soon as they are no longer necessary for achieving "
            "the purpose for which they were collected."),
        "logs_dauer": " Server logs are erased after {dauer}.",
        "ph_logs": "Storage period for server logs",
        "ph_logs_hinweis": "e.g. '7 days'",

        # ── 4. Purposes ─────────────────────────────────────────────────────
        "h_4": "4.  Purposes of the data processing",
        "ph_zwecke": "Purposes of processing",
        "ph_zwecke_hinweis": "Please select the purposes in the intake form",
        "abschnitt_4": "4.{nr}  {titel}",
        "rechtsgrundlage_zeile": "Legal basis: {rg}",
        "aufbewahrung": " Retention period: {dauer}.",

        # Bezeichnungen der Zwecke (Reihenfolge: `_ZWECK_KEYS`)
        # `firmenkonto`/`support` folgen bewusst dem deutschen Wortlaut
        # („Firmenkonto"/„Firmensupport") — siehe Befund im Bericht zu #1003.
        "zweck_kontaktformular": "Contact form and enquiries",
        "zweck_newsletter": "Newsletter and email marketing",
        "zweck_webanalyse": "Website analysis and statistics",
        "zweck_ecommerce": "Online orders and e-commerce",
        "zweck_firmenkonto": "Customer account and registration",
        "zweck_cookies_tracking": "Cookies and tracking",
        "zweck_bewerbungen": "Job applications and recruitment",
        "zweck_login_auth": "Login and authentication",
        "zweck_support": "Customer support",
        "zweck_sonstiges": "Further purposes",

        # Rechtsgrundlagen je Zweck — Ziffern unverändert, nur die Schreibweise
        # wechselt (`Abs. 1 lit. f` → `(1)(f)`), und `DSGVO` → `GDPR`.
        "rg_kontaktformular": "Art. 6(1)(b) GDPR (steps prior to entering into a contract) or Art. 6(1)(f) GDPR (legitimate interests)",
        "rg_newsletter": "Art. 6(1)(a) GDPR (consent)",
        "rg_webanalyse": "Art. 6(1)(f) GDPR (legitimate interests) or Art. 6(1)(a) GDPR (consent in the case of tracking cookies)",
        "rg_ecommerce": "Art. 6(1)(b) GDPR (performance of a contract), Art. 6(1)(c) GDPR (legal obligation for accounting purposes)",
        "rg_firmenkonto": "Art. 6(1)(b) GDPR (performance of a contract)",
        "rg_cookies_tracking": "Art. 6(1)(a) GDPR (consent)",
        "rg_bewerbungen": "Art. 6(1)(b) GDPR (pre-contractual measures), § 26 BDSG",
        "rg_login_auth": "Art. 6(1)(b) GDPR (performance of a contract)",
        "rg_support": "Art. 6(1)(b) GDPR (performance of a contract) or Art. 6(1)(f) GDPR (legitimate interests)",

        "zweck_kontakt_text": (
            "If you contact us via the contact form or by email, we store the data you "
            "provide (name, email address, message) in order to process your enquiry."),
        "ph_speicher_kontakt": "Storage period for contact data",
        "ph_speicher_kontakt_hinweis": "e.g. '3 years'",

        "zweck_newsletter_text": (
            "If you wish to subscribe to our newsletter, we require an email address from "
            "you as well as information that allows us to verify that you are the owner "
            "of the email address provided (double opt-in)."),
        "newsletter_widerruf": (
            "You may withdraw your consent to the storage of the data and of the email "
            "address, and to their use for sending the newsletter, at any time."),

        "zweck_webanalyse_text": (
            "This website uses web analytics tools in order to evaluate the use of our "
            "website and to improve our website and our advertising."),
        "tools_zeile": "Tools used: {tools}",
        "ph_analyse_tools": "Analytics tools used",
        "ph_analyse_tools_hinweis": "e.g. Google Analytics, Matomo",

        "zweck_ecommerce_text": (
            "When you place an order with us, we collect and use your personal data to "
            "the extent necessary for processing the order, handling the payment and "
            "delivering the goods."),
        "bestelldaten_aufbewahrung": "Order data are subject to the statutory retention obligations.",
        "ph_speicher_bestellungen": "Storage period for order data",
        "ph_speicher_bestellungen_hinweis": "e.g. '10 years (§ 147 AO)'",

        "ph_detail": "Detailed description: {titel}",
        "ph_detail_hinweis": "Please add the purpose, the data processed, the legal basis and the storage period",

        # ── 5. Cookies ──────────────────────────────────────────────────────
        "h_5": "5.  Cookies",
        "cookies_intro": (
            "Our website uses cookies. Cookies are text files that are stored in or by "
            "the internet browser on the user's computer system. When a user accesses a "
            "website, a cookie may be stored on the user's operating system."),
        "cookies_notwendig": (
            "Necessary cookies: these cookies are technically required for the operation "
            "of the website (e.g. session cookies). Legal basis: Art. 6(1)(f) GDPR."),
        "cookies_analyse": (
            "Analytics cookies: these cookies enable us to analyse the use of our "
            "website. Legal basis: Art. 6(1)(a) GDPR (consent)."),
        "cookies_marketing": (
            "Marketing cookies: these cookies are used to display advertising tailored "
            "to users. Legal basis: Art. 6(1)(a) GDPR (consent)."),
        "ph_analyse_name": "Name of the analytics tool",
        "ph_analyse_name_hinweis": "e.g. Google Analytics 4, Matomo",
        "ph_cookie_typen": "Cookie types and details",
        "ph_cookie_typen_hinweis": "Please state which cookie types are used",

        # ── 6. Disclosure ──────────────────────────────────────────────────
        "h_6": "6.  Disclosure of personal data",
        "weitergabe_intro": (
            "Your personal data are not transferred to third parties for purposes other "
            "than those listed below. We disclose your personal data to third parties "
            "only where you have given your explicit consent, where the disclosure is "
            "necessary for the performance of a contract with you, where we are legally "
            "obliged to disclose them, or where the disclosure is necessary for the "
            "establishment, exercise or defence of legal claims and there is no reason to "
            "assume that you have an overriding legitimate interest in your data not "
            "being disclosed."),
        "dienstleister_zeile": "The following service providers are given access to personal data: {dritte}",
        "h_6_1": "6.1  Transfers of data to third countries",
        "ph_drittland": "Third-country details",
        "ph_drittland_hinweis": "Which providers, which countries, which safeguards (e.g. EU standard contractual clauses, adequacy decision)?",
        "ph_drittland_klaeren": "Third-country transfer – clarification required",
        "ph_drittland_klaeren_hinweis": "Please check whether hosting or third-party providers transfer data outside the EU/EEA",

        # ── 7. Data subject rights ─────────────────────────────────────────
        "h_7": "7.  Your rights as a data subject",
        "rechte_intro": (
            "Within the framework of the applicable statutory provisions, you have the "
            "right at any time to obtain information free of charge about your stored "
            "personal data, their origin and recipients and the purpose of the data "
            "processing and, where applicable, a right to rectification, blocking or "
            "erasure of those data."),
        "recht_auskunft": "Right of access",
        "recht_auskunft_norm": "Art. 15 GDPR",
        "recht_auskunft_text": "Right of access to the data stored about you.",
        "recht_berichtigung": "Right to rectification",
        "recht_berichtigung_norm": "Art. 16 GDPR",
        "recht_berichtigung_text": "Right to rectification of inaccurate or incomplete personal data.",
        "recht_loeschung": "Right to erasure",
        "recht_loeschung_norm": "Art. 17 GDPR",
        # „Aufbewahrungsgrund" ist weiter als eine Pflicht — „ground for
        # retention" hält das offen, „retention obligation" hätte es auf eine
        # gesetzliche Pflicht verengt.
        "recht_loeschung_text": "Right to erasure of your personal data, provided that no ground for retention stands in the way.",
        "recht_einschraenkung": "Right to restriction",
        "recht_einschraenkung_norm": "Art. 18 GDPR",
        "recht_einschraenkung_text": "Right to restriction of the processing of your data.",
        "recht_widerspruch": "Right to object",
        "recht_widerspruch_norm": "Art. 21 GDPR",
        "recht_widerspruch_text": "Right to object to the processing of your data.",
        "recht_portabilitaet": "Data portability",
        "recht_portabilitaet_norm": "Art. 20 GDPR",
        "recht_portabilitaet_text": "Right to receive your data in a machine-readable format.",
        "recht_widerruf": "Withdrawal of consent",
        "recht_widerruf_norm": "Art. 7(3) GDPR",
        "recht_widerruf_text": "Right to withdraw a consent given, with effect for the future.",
        "recht_beschwerde": "Right to lodge a complaint",
        "recht_beschwerde_norm": "Art. 77 GDPR",
        "recht_beschwerde_text": "Right to lodge a complaint with the competent data protection supervisory authority.",
        "rechte_kontakt": "To exercise your rights, please contact: {email}",
        "ph_rechte_kontakt": "Contact address for data subject requests",

        # ── 8. Checklist ───────────────────────────────────────────────────
        "h_8": "8.  Checklist of missing information",
        "checkliste_banner": "The following {n} fields must be completed before publication:",
        "checkliste_zeile": "  ☐  {feld}",
        "alles_gefuellt": (
            "All mandatory fields have been completed. Please still have the document "
            "reviewed by a qualified expert."),

        # ── Disclaimer ─────────────────────────────────────────────────────
        "disclaimer": (
            "Legal notice: this document was generated automatically and constitutes a "
            "non-binding draft. It does not replace a legal review. Please have this "
            "document reviewed by a qualified data protection officer or a lawyer before "
            "publication."),
    },
}

_t = _rt.macher(TEXTE)


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


def _banner(doc, text: str, bg: str, fg: str = "#FFFFFF", size: int = 11) -> None:
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
    run.font.size = Pt(13 if level == 1 else 11)
    r, g, b = _hex_rgb(color)
    run.font.color.rgb = RGBColor(r, g, b)
    p.paragraph_format.space_before = Pt(10 if level == 1 else 6)
    p.paragraph_format.space_after = Pt(3)


def _body(doc, text: str, size: int = 10, italic: bool = False, bold: bool = False) -> None:
    p = doc.add_paragraph(text)
    if p.runs:
        run = p.runs[0]
        run.font.size = Pt(size)
        run.italic = italic
        run.bold = bold
    p.paragraph_format.space_after = Pt(3)


def _placeholder(doc, spr: str, field_name: str, hint: str = "") -> None:
    """Add a visually distinct placeholder paragraph.

    ``spr`` wird nur für das Gerüst gebraucht (``[PLATZHALTER: …]`` /
    ``[PLACEHOLDER: …]``); Feldname und Hinweis löst der Aufrufer auf.
    """
    p = doc.add_paragraph()
    tbl = doc.add_table(rows=1, cols=1)
    cell = tbl.cell(0, 0)
    _set_shading(cell, _MISS_BG)
    _set_border(cell, "F48FB1")
    cp = cell.paragraphs[0]
    cp.paragraph_format.space_before = Pt(2)
    cp.paragraph_format.space_after = Pt(2)
    cr = cp.add_run(_t(spr, "platzhalter", feld=field_name))
    cr.bold = True
    cr.font.size = Pt(9)
    cr.font.color.rgb = RGBColor(0xC6, 0x28, 0x28)
    if hint:
        hr = cp.add_run(_t(spr, "platzhalter_hinweis", hinweis=hint))
        hr.font.size = Pt(9)
        hr.italic = True
        hr.font.color.rgb = RGBColor(0x5D, 0x40, 0x37)
    doc.add_paragraph()


def _val(intake: dict[str, Any], key: str, fallback: str = "") -> str:
    v = intake.get(key)
    return str(v).strip() if v and str(v).strip() else fallback


def _bool_val(intake: dict[str, Any], key: str) -> bool | None:
    v = intake.get(key)
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("1", "true", "ja", "yes")
    return bool(v)


def _safe_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "-", s or "")
    s = re.sub(r"\s+", "_", s).strip("_")
    return s[:80] or "Datenschutzerklaerung_Entwurf"


#: Die Zwecke in der Reihenfolge, in der sie im Dokument erscheinen.
#:
#: Bis #1954 war das ein Dict mit den deutschen Bezeichnungen (``_ZWECK_LABELS``);
#: die Bezeichnungen stehen jetzt im Katalog (``zweck_<key>``), damit es sie nur
#: **einmal** gibt. Die Reihenfolge bleibt hier, weil sie der Dokumentaufbau ist
#: und keine Übersetzung — Abschnitt 4.1 ist in beiden Sprachen derselbe Zweck.
_ZWECK_KEYS: tuple[str, ...] = (
    "kontaktformular",
    "newsletter",
    "webanalyse",
    "ecommerce",
    "firmenkonto",
    "cookies_tracking",
    "bewerbungen",
    "login_auth",
    "support",
    "sonstiges",
)

#: Die Reihenfolge der Betroffenenrechte in der Tabelle in Abschnitt 7.
#:
#: Sie folgt dem Bestand und **nicht** der Artikelnummer (Art. 21 steht vor
#: Art. 20). Geändert wird sie hier nicht — eine Übersetzung ist kein Anlass,
#: die Reihenfolge eines Dokuments umzustellen, das ein Mandant veröffentlicht.
_RECHTE_KEYS: tuple[str, ...] = (
    "recht_auskunft",
    "recht_berichtigung",
    "recht_loeschung",
    "recht_einschraenkung",
    "recht_widerspruch",
    "recht_portabilitaet",
    "recht_widerruf",
    "recht_beschwerde",
)


# ── DOCX export ───────────────────────────────────────────────────────────────

def export_privacy_docx(
    *,
    out_dir: Path,
    projekt_name: str,
    intake: dict[str, Any],
    sprache: str | None = None,
) -> Path:
    """Generate a privacy policy DOCX draft from intake data.

    Unknowns are rendered as [PLATZHALTER] blocks, never hallucinated.
    Returns the path to the generated file.

    ``sprache`` übersteuert für diesen einen Lauf; ohne Angabe entscheidet
    ``firmen.sprache`` des Mandanten (#1954), fail-open auf Deutsch. Der
    Dateiname bleibt in jeder Sprache derselbe — er ist ein Bezeichner, kein
    Dokumenttext.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spr = _rt.aufloesen("dsgvo", projekt_name, sprache)

    doc = Document()
    for section in doc.sections:
        section.top_margin    = Inches(0.9)
        section.bottom_margin = Inches(0.9)
        section.left_margin   = Inches(1.1)
        section.right_margin  = Inches(1.1)

    # Dokumentsprache (``w:lang``) nur außerhalb von Deutsch setzen: Auf Deutsch
    # bleibt das Dokument damit byte-identisch zum Bestand, und eine englische
    # Fassung wird in Word nicht Wort für Wort rot unterstrichen.
    if spr != "de":
        from shared.reports.docx_pdf import set_doc_lang
        set_doc_lang(doc, spr)

    app_name    = _val(intake, "app_name", projekt_name)
    betreiber   = _val(intake, "betreiber_name")
    strasse     = _val(intake, "betreiber_strasse")
    plzort      = _val(intake, "betreiber_plzort")
    land        = _val(intake, "betreiber_land", _t(spr, "land_standard"))
    email       = _val(intake, "kontakt_email")
    telefon     = _val(intake, "kontakt_telefon")
    missing     = intake_missing_fields(intake, sprache=spr)

    # ── DRAFT banner ──────────────────────────────────────────────────────────
    _banner(
        doc,
        _t(spr, "entwurf_banner"),
        _DRAFT_BG, fg=_DRAFT_FG, size=10,
    )
    doc.add_paragraph()

    if missing:
        _banner(
            doc,
            _t(spr, "fehlen_banner", n=len(missing), felder=", ".join(missing[:4]))
            + (_t(spr, "fehlen_weitere", n=len(missing) - 4) if len(missing) > 4 else ""),
            _MISS_BG, fg="#C62828", size=9,
        )
        doc.add_paragraph()

    # ── Title ─────────────────────────────────────────────────────────────────
    title_p = doc.add_paragraph()
    tr = title_p.add_run(_t(spr, "titel"))
    tr.bold = True
    tr.font.size = Pt(20)
    r, g, b = _hex_rgb(_EU_BLUE)
    tr.font.color.rgb = RGBColor(r, g, b)
    title_p.paragraph_format.space_after = Pt(2)

    if app_name:
        sub_p = doc.add_paragraph(_t(spr, "untertitel", app=app_name))
        sub_p.runs[0].font.size = Pt(12)
        sub_p.runs[0].italic = True
        sub_p.paragraph_format.space_after = Pt(6)

    # Das Datumsformat bleibt in jeder Sprache ``TT.MM.JJJJ`` — es ist kein Text,
    # sondern eine Formatierung, und sie zu ändern wäre ein Eingriff in den
    # Dateninhalt des Dokuments (siehe Befund im Bericht zu #1954).
    date_p = doc.add_paragraph(
        _t(spr, "stand", datum=date.today().strftime('%d.%m.%Y')))
    date_p.runs[0].font.size = Pt(9)
    date_p.runs[0].italic = True
    doc.add_paragraph()

    # ── 1. Verantwortlicher ───────────────────────────────────────────────────
    _heading(doc, _t(spr, "h_1"), level=1)
    _body(doc, _t(spr, "verantwortlicher_intro"))
    doc.add_paragraph()
    if betreiber:
        _body(doc, betreiber, bold=True)
    else:
        _placeholder(doc, spr, _t(spr, "ph_betreiber"), _t(spr, "ph_betreiber_hinweis"))
    if strasse:
        _body(doc, strasse)
    else:
        _placeholder(doc, spr, _t(spr, "ph_strasse"))
    if plzort:
        _body(doc, f"{plzort}, {land}")
    else:
        _placeholder(doc, spr, _t(spr, "ph_plzort"))
    doc.add_paragraph()
    if email:
        _body(doc, _t(spr, "email_zeile", wert=email))
    else:
        _placeholder(doc, spr, _t(spr, "ph_email"))
    if telefon:
        _body(doc, _t(spr, "telefon_zeile", wert=telefon))

    # ── 1.1 Vertreter in der Union (Art. 27) ──────────────────────────────────
    # #1219: EU-Vertreter nur, wenn der Verantwortliche nicht in der EU
    # niedergelassen ist (Art. 3(2)). Steuerung über Intake-Variablen.
    eu_vertreter_anwendbar = _bool_val(intake, "eu_vertreter_anwendbar")
    euv_name    = _val(intake, "eu_vertreter_name")
    euv_anschrift = _val(intake, "eu_vertreter_anschrift")
    euv_kontakt = _val(intake, "eu_vertreter_kontakt")
    if eu_vertreter_anwendbar or euv_name:
        _heading(doc, _t(spr, "h_1_1"), level=2, color="#1a237e")
        _body(doc, _t(spr, "euv_intro"))
        if euv_name:
            _body(doc, euv_name, bold=True)
        else:
            _placeholder(doc, spr, _t(spr, "ph_euv_name"))
        if euv_anschrift:
            _body(doc, euv_anschrift)
        else:
            _placeholder(doc, spr, _t(spr, "ph_euv_anschrift"))
        if euv_kontakt:
            _body(doc, _t(spr, "kontakt_zeile", wert=euv_kontakt))
        else:
            _placeholder(doc, spr, _t(spr, "ph_euv_kontakt"))

    # ── 2. Datenschutzbeauftragter ────────────────────────────────────────────
    dsb_name  = _val(intake, "dsb_name")
    dsb_email = _val(intake, "dsb_email")
    _heading(doc, _t(spr, "h_2"), level=1)
    if dsb_name or dsb_email:
        _body(doc, _t(spr, "dsb_ist"))
        if dsb_name:
            _body(doc, dsb_name, bold=True)
        if dsb_email:
            _body(doc, _t(spr, "email_zeile", wert=dsb_email))
    else:
        _body(
            doc,
            _t(spr, "dsb_pflicht"),
            italic=True,
        )
        _placeholder(
            doc,
            spr,
            _t(spr, "ph_dsb"),
            _t(spr, "ph_dsb_hinweis"),
        )

    # ── 3. Allgemeine Hinweise zur Datenverarbeitung ──────────────────────────
    _heading(doc, _t(spr, "h_3"), level=1)
    _body(doc, _t(spr, "allgemein_intro"))

    # Hosting
    _heading(doc, _t(spr, "h_3_1"), level=2, color="#1a237e")
    hosting  = _val(intake, "hosting_anbieter")
    host_ort = _val(intake, "hosting_ort")
    if hosting:
        _body(doc,
              _t(spr, "hosting_satz", anbieter=hosting)
              + (_t(spr, "hosting_rz", ort=host_ort) if host_ort else "")
              + _t(spr, "hosting_logs"))
    else:
        _placeholder(doc, spr, _t(spr, "ph_hosting"))
    spec_host = _val(intake, "speicherdauer_logs")
    _body(doc, _t(spr, "logs_rechtsgrundlage"))
    _body(doc,
          _t(spr, "loeschung_satz")
          + (_t(spr, "logs_dauer", dauer=spec_host) if spec_host else ""))
    if not spec_host:
        _placeholder(doc, spr, _t(spr, "ph_logs"), _t(spr, "ph_logs_hinweis"))

    # ── 4. Verarbeitungszwecke ────────────────────────────────────────────────
    _heading(doc, _t(spr, "h_4"), level=1)
    zwecke: list[str] = intake.get("zwecke", []) if isinstance(intake.get("zwecke"), list) else []

    if not zwecke:
        _placeholder(doc, spr, _t(spr, "ph_zwecke"), _t(spr, "ph_zwecke_hinweis"))
    else:
        section_num = 1
        for zweck_key, zweck_label in [
            (k, _t(spr, f"zweck_{k}")) for k in _ZWECK_KEYS if k in zwecke
        ] + ([("sonstiges", _val(intake, "zwecke_sonstiges", _t(spr, "zweck_sonstiges")))]
              if "sonstiges" in zwecke and _val(intake, "zwecke_sonstiges") else []):
            _heading(doc, _t(spr, "abschnitt_4", nr=section_num, titel=zweck_label),
                     level=2, color="#1a237e")
            section_num += 1
            rg = _rechtsgrundlage(spr, zweck_key)
            if zweck_key == "kontaktformular":
                _body(doc, _t(spr, "zweck_kontakt_text"))
                spec = _val(intake, "speicherdauer_kontakt")
                _body(doc, _t(spr, "rechtsgrundlage_zeile", rg=rg))
                _body(doc,
                      _t(spr, "loeschung_satz")
                      + (_t(spr, "aufbewahrung", dauer=spec) if spec else ""))
                if not spec:
                    _placeholder(doc, spr, _t(spr, "ph_speicher_kontakt"),
                                 _t(spr, "ph_speicher_kontakt_hinweis"))

            elif zweck_key == "newsletter":
                _body(doc, _t(spr, "zweck_newsletter_text"))
                _body(doc, _t(spr, "rechtsgrundlage_zeile", rg=rg))
                _body(doc, _t(spr, "newsletter_widerruf"))

            elif zweck_key == "webanalyse":
                _body(doc, _t(spr, "zweck_webanalyse_text"))
                dritte = _val(intake, "dritte")
                if dritte:
                    _body(doc, _t(spr, "tools_zeile", tools=dritte))
                else:
                    _placeholder(doc, spr, _t(spr, "ph_analyse_tools"),
                                 _t(spr, "ph_analyse_tools_hinweis"))
                _body(doc, _t(spr, "rechtsgrundlage_zeile", rg=rg))

            elif zweck_key == "ecommerce":
                _body(doc, _t(spr, "zweck_ecommerce_text"))
                spec = _val(intake, "speicherdauer_bestellungen")
                _body(doc, _t(spr, "rechtsgrundlage_zeile", rg=rg))
                _body(doc,
                      _t(spr, "bestelldaten_aufbewahrung")
                      + (_t(spr, "aufbewahrung", dauer=spec) if spec else ""))
                if not spec:
                    _placeholder(doc, spr, _t(spr, "ph_speicher_bestellungen"),
                                 _t(spr, "ph_speicher_bestellungen_hinweis"))

            else:
                _body(doc, _t(spr, "rechtsgrundlage_zeile", rg=rg) if rg else "")
                _placeholder(doc, spr, _t(spr, "ph_detail", titel=zweck_label),
                             _t(spr, "ph_detail_hinweis"))

    # ── 5. Cookies ────────────────────────────────────────────────────────────
    _heading(doc, _t(spr, "h_5"), level=1)
    cookies_notwendig = _bool_val(intake, "cookies_notwendig")
    cookies_analyse   = _bool_val(intake, "cookies_analyse")
    cookies_marketing = _bool_val(intake, "cookies_marketing")
    cookies_tools     = _val(intake, "cookies_tools")

    _body(doc, _t(spr, "cookies_intro"))

    if cookies_notwendig is True:
        _body(doc, _t(spr, "cookies_notwendig"))
    if cookies_analyse is True:
        _body(doc, _t(spr, "cookies_analyse"))
        if cookies_tools:
            _body(doc, _t(spr, "tools_zeile", tools=cookies_tools))
        else:
            _placeholder(doc, spr, _t(spr, "ph_analyse_name"),
                         _t(spr, "ph_analyse_name_hinweis"))
    if cookies_marketing is True:
        _body(doc, _t(spr, "cookies_marketing"))
    if cookies_notwendig is None and cookies_analyse is None and cookies_marketing is None:
        _placeholder(doc, spr, _t(spr, "ph_cookie_typen"),
                     _t(spr, "ph_cookie_typen_hinweis"))

    # ── 6. Weitergabe an Dritte ───────────────────────────────────────────────
    _heading(doc, _t(spr, "h_6"), level=1)
    dritte = _val(intake, "dritte")
    drittland = _bool_val(intake, "drittland")
    drittland_desc = _val(intake, "drittland_beschreibung")

    _body(doc, _t(spr, "weitergabe_intro"))

    if dritte:
        _body(doc, _t(spr, "dienstleister_zeile", dritte=dritte))

    if drittland is True:
        _heading(doc, _t(spr, "h_6_1"), level=2, color="#1a237e")
        if drittland_desc:
            _body(doc, drittland_desc)
        else:
            _placeholder(doc, spr, _t(spr, "ph_drittland"),
                         _t(spr, "ph_drittland_hinweis"))
    elif drittland is None:
        _placeholder(doc, spr, _t(spr, "ph_drittland_klaeren"),
                     _t(spr, "ph_drittland_klaeren_hinweis"))

    # ── 7. Betroffenenrechte ──────────────────────────────────────────────────
    _heading(doc, _t(spr, "h_7"), level=1)
    rights_email = _val(intake, "betroffenenrechte_email") or email
    _body(doc, _t(spr, "rechte_intro"))

    rights_list = [(_t(spr, k), _t(spr, f"{k}_norm"), _t(spr, f"{k}_text"))
                   for k in _RECHTE_KEYS]
    r_tbl = doc.add_table(rows=0, cols=2)
    r_tbl.autofit = False
    r_tbl.columns[0].width = Inches(2.0)
    r_tbl.columns[1].width = Inches(4.5)
    for title, art, text in rights_list:
        row = r_tbl.add_row()
        lc, vc = row.cells[0], row.cells[1]
        _set_shading(lc, "E8EAF6")
        _set_shading(vc, "FFFFFF")
        _set_border(lc)
        _set_border(vc)
        lp = lc.paragraphs[0]
        lr = lp.add_run(f"{title}\n{art}")
        lr.bold = True
        lr.font.size = Pt(9)
        r, g, b = _hex_rgb(_EU_BLUE)
        lr.font.color.rgb = RGBColor(r, g, b)
        vp = vc.paragraphs[0]
        vr = vp.add_run(text)
        vr.font.size = Pt(9)

    doc.add_paragraph()
    if rights_email:
        _body(doc, _t(spr, "rechte_kontakt", email=rights_email))
    else:
        _placeholder(doc, spr, _t(spr, "ph_rechte_kontakt"))

    # ── 8. Fehlende-Informationen-Checkliste ──────────────────────────────────
    _heading(doc, _t(spr, "h_8"), level=1)
    if missing:
        _banner(
            doc,
            _t(spr, "checkliste_banner", n=len(missing)),
            _MISS_BG, fg="#C62828", size=9,
        )
        for m in missing:
            p = doc.add_paragraph(_t(spr, "checkliste_zeile", feld=m), style="List Bullet")
            if p.runs:
                p.runs[0].font.size = Pt(9)
    else:
        _body(doc, _t(spr, "alles_gefuellt"), italic=True)

    doc.add_paragraph()

    # ── Disclaimer ────────────────────────────────────────────────────────────
    _banner(
        doc,
        _t(spr, "disclaimer"),
        _DRAFT_BG, fg=_DRAFT_FG, size=9,
    )

    # ── Save ──────────────────────────────────────────────────────────────────
    ts = date.today().strftime("%Y%m%d")
    filename = f"Datenschutzerklaerung_Entwurf_{_safe_filename(app_name or projekt_name)}_{ts}.docx"
    out_path = out_dir / filename
    doc.save(str(out_path))
    return out_path


def _rechtsgrundlage(spr: str, zweck_key: str) -> str:
    """Die Rechtsgrundlage eines Zwecks — leer, wenn keine hinterlegt ist.

    ``_t`` liefert für einen unbekannten Schlüssel den Schlüssel selbst zurück
    (damit eine fehlende Überschrift auffällt). Hier wäre das falsch: Der Zweck
    ``sonstiges`` hat bewusst **keine** Rechtsgrundlage, und ein gedrucktes
    ``Rechtsgrundlage: rg_sonstiges`` wäre in einem veröffentlichten Dokument
    schlimmer als eine leere Angabe. Deshalb wird hier gegen den Katalog geprüft.
    """
    schluessel = f"rg_{zweck_key}"
    if schluessel in TEXTE["de"]:
        return _t(spr, schluessel)
    return ""
