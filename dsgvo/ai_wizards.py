"""DSGVO Phase B — KI-Wizards (Issue #584).

D6 Verarbeitung-Klassifikator (Rechtsgrundlage Art. 6)
D7 Branchen-Templates
D8 Datenpannen-Meldung Art. 33 (72h)
D9 Betroffenenrechte-Workflow (Art. 15/17/20)
"""
from __future__ import annotations

import json
from typing import Any


# ─────────────────────────────────────────────────────────────────────────
# D6 — Rechtsgrundlagen-Klassifikator (Art. 6)
# ─────────────────────────────────────────────────────────────────────────

RECHTSGRUNDLAGEN = ['einwilligung', 'vertrag', 'rechtliche-verpflichtung',
                    'lebenswichtige-interessen', 'oeffentliches-interesse',
                    'berechtigte-interessen']

_RG_SYNONYMS = {
    'einwilligung': 'einwilligung', 'art. 6(1)(a)': 'einwilligung', 'consent': 'einwilligung',
    'vertrag': 'vertrag', 'art. 6(1)(b)': 'vertrag', 'contract': 'vertrag',
    'rechtliche-verpflichtung': 'rechtliche-verpflichtung', 'art. 6(1)(c)': 'rechtliche-verpflichtung',
    'lebenswichtige-interessen': 'lebenswichtige-interessen', 'art. 6(1)(d)': 'lebenswichtige-interessen',
    'oeffentliches-interesse': 'oeffentliches-interesse', 'art. 6(1)(e)': 'oeffentliches-interesse',
    'berechtigte-interessen': 'berechtigte-interessen', 'art. 6(1)(f)': 'berechtigte-interessen',
    'legitimate-interest': 'berechtigte-interessen', 'interessenabwägung': 'berechtigte-interessen',
}


def _normalize_rg(value: str) -> str:
    return _RG_SYNONYMS.get((value or '').strip().lower(), 'berechtigte-interessen')


def build_rechtsgrundlage_prompt(projekt: dict[str, Any], verarbeitung: dict[str, Any]) -> str:
    return f"""Du bist ein DSGVO-Experte (Verordnung EU 2016/679).

Bestimme die passende Rechtsgrundlage nach Art. 6 für diese Verarbeitung:

**Organisation:** {projekt.get('unternehmen', projekt.get('name', ''))}
**Verarbeitungs-Name:** {verarbeitung.get('name', '')}
**Zweck:** {verarbeitung.get('zweck', '')}
**Betroffene Kategorien:** {verarbeitung.get('betroffene_kategorien', '')}
**Datenkategorien:** {verarbeitung.get('datenkategorien', '')}

DSGVO Art. 6 bietet 6 Rechtsgrundlagen:
- **einwilligung** (Art. 6(1)(a)): freiwillige, informierte Einwilligung. Hohe Hürde, jederzeit widerrufbar.
- **vertrag** (Art. 6(1)(b)): Erfüllung eines Vertrags MIT dem Betroffenen, oder vorvertragliche Maßnahmen.
- **rechtliche-verpflichtung** (Art. 6(1)(c)): gesetzliche Pflicht (Steuer, Sozialversicherung, etc.)
- **lebenswichtige-interessen** (Art. 6(1)(d)): Lebensschutz — meist medizinische Notfälle.
- **oeffentliches-interesse** (Art. 6(1)(e)): hoheitliche Aufgabenwahrnehmung.
- **berechtigte-interessen** (Art. 6(1)(f)): Interessenabwägung mit Rechten Betroffener. Häufigster Fall in B2B/Marketing.

Beachte besondere Datenkategorien (Art. 9): Gesundheit/Religion/Gewerkschaft etc. brauchen zusätzlich Art. 9(2).

Antworte **ausschließlich** als JSON:
```json
{{
  "rechtsgrundlage": "einwilligung|vertrag|rechtliche-verpflichtung|lebenswichtige-interessen|oeffentliches-interesse|berechtigte-interessen",
  "art_referenz": "z.B. Art. 6(1)(f) + Art. 9(2)(a) falls besondere Kategorien",
  "begruendung": "2-3 Sätze warum diese Rechtsgrundlage passt",
  "interessenabwaegung_noetig": true|false,
  "einwilligung_ueberpruefen": "Empfehlung falls problematisch",
  "dpia_pflicht": true|false
}}
```
"""


def parse_rechtsgrundlage_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'rechtsgrundlage': _normalize_rg(data.get('rechtsgrundlage', 'berechtigte-interessen')),
        'art_referenz': data.get('art_referenz', ''),
        'begruendung': data.get('begruendung', ''),
        'interessenabwaegung_noetig': bool(data.get('interessenabwaegung_noetig', False)),
        'einwilligung_ueberpruefen': data.get('einwilligung_ueberpruefen', ''),
        'dpia_pflicht': bool(data.get('dpia_pflicht', False)),
    }


# ─────────────────────────────────────────────────────────────────────────
# D7 — Branchen-Templates (für VVT + TOM)
# ─────────────────────────────────────────────────────────────────────────

BRANCHEN_TEMPLATES_DSGVO = {
    'e-commerce': {
        'name': 'E-Commerce / Online-Shop',
        'typische_vvt': ['Bestellabwicklung', 'Newsletter', 'Customer-Support', 'Marketing-Analytics'],
        'tom_defaults': {
            'zutrittskontrolle': 'Serverraum mit Schließsystem + Logging',
            'zugangskontrolle': '2FA für Admin-Accounts',
            'zugriffskontrolle': 'Role-Based-Access-Control',
            'pseudonymisierung': 'E-Mail-Hash für Analytics',
            'verschluesselung': 'TLS 1.3 + at-rest-Encryption',
            'verfuegbarkeit': 'Backup-Strategie 3-2-1',
        },
        'kritische_avv': ['Payment-Provider', 'CDN', 'E-Mail-Service'],
        'hinweise': 'Cookie-Banner mit Consent-Layer, Newsletter via Double-Opt-In.',
    },
    'b2b-saas': {
        'name': 'B2B-SaaS',
        'typische_vvt': ['Account-Management', 'Support-Tickets', 'Usage-Analytics', 'Billing'],
        'tom_defaults': {
            'zugriffskontrolle': 'SSO + SCIM + Audit-Log',
            'verschluesselung': 'TLS + KMS-Backed at-rest',
            'integritaet': 'Audit-Trail aller Datenänderungen',
        },
        'kritische_avv': ['Cloud-Provider (AWS/Azure/GCP)', 'CRM (HubSpot/Salesforce)', 'Support-Tool'],
        'hinweise': 'DPA mit Firmen + Sub-Processor-Liste publik halten.',
    },
    'healthcare': {
        'name': 'Healthcare / Praxis / Klinik',
        'typische_vvt': ['Patientenakte', 'Abrechnung mit Kassen', 'Rezept-Versand', 'Forschung'],
        'tom_defaults': {
            'zutrittskontrolle': 'Karten-System + Videoaufzeichnung',
            'zugriffskontrolle': 'Need-to-Know-Prinzip + Audit',
            'verschluesselung': 'Patientendaten verschlüsselt at-rest+in-transit',
            'datentrennung': 'Mandanten/Patienten-Separation',
        },
        'kritische_avv': ['Praxis-Software-Anbieter', 'Hosting', 'KIS/HIS'],
        'hinweise': 'Art. 9 besondere Kategorien — DSFA fast immer Pflicht. Schweigepflicht beachten.',
    },
    'hr-personalwesen': {
        'name': 'HR / Personalwesen',
        'typische_vvt': ['Bewerber-Daten', 'Mitarbeiter-Stammdaten', 'Lohnabrechnung', 'Zeiterfassung'],
        'tom_defaults': {
            'zugriffskontrolle': 'Strikt HR-only mit 4-Augen-Prinzip',
            'datentrennung': 'Bewerber von Mitarbeiter trennen',
            'loeschkonzept': 'Bewerberdaten 6 Monate nach Absage',
        },
        'kritische_avv': ['Bewerbermanagement-Tool', 'Lohn-/Gehalts-Software', 'BAV-Anbieter'],
        'hinweise': 'BetrVG-Mitbestimmung beachten. Hinweisgeberschutz (HinSchG).',
    },
}


def list_branchen_templates_dsgvo() -> list[dict[str, Any]]:
    return [{'id': k, **v} for k, v in BRANCHEN_TEMPLATES_DSGVO.items()]


def get_branchen_template_dsgvo(branche_id: str) -> dict[str, Any] | None:
    t = BRANCHEN_TEMPLATES_DSGVO.get(branche_id)
    return {'id': branche_id, **t} if t else None


# ─────────────────────────────────────────────────────────────────────────
# D8 — Datenpannen-Meldung Art. 33 (72h)
# ─────────────────────────────────────────────────────────────────────────

def build_datenpanne_meldung_prompt(projekt: dict[str, Any], panne: dict[str, Any]) -> str:
    return f"""Erstelle die Pflichtmeldungen für eine DSGVO-Datenpanne (deutsch):
- 72h-Meldung an Aufsichtsbehörde (Art. 33)
- ggf. Information der Betroffenen (Art. 34)

**Verantwortlicher:** {projekt.get('unternehmen', projekt.get('name', ''))}
**Panne-ID:** {panne.get('panne_id', '')}
**Beschreibung:** {panne.get('beschreibung', '')}
**Art:** {panne.get('art', '')} (Vertraulichkeit/Integrität/Verfügbarkeit)
**Festgestellt am:** {panne.get('festgestellt_am', '')}
**Betroffene Anzahl:** {panne.get('betroffene_anzahl', 'unbekannt')}
**Datenkategorien:** {panne.get('datenkategorien', '')}
**Risikoeinschätzung:** {panne.get('risikoeinschaetzung', 'mittel')}

Art. 33 verlangt die Meldung innerhalb 72h an die Aufsichtsbehörde, sofern voraussichtlich ein Risiko entsteht.
Art. 34 verlangt zusätzlich die Information der Betroffenen, wenn hohes Risiko.

Inhalte der Meldung:
- Art der Verletzung + Kategorien + ungefähre Anzahl
- Voraussichtliche Folgen
- Ergriffene/vorgeschlagene Maßnahmen
- Kontaktdaten Datenschutzbeauftragter

Antworte **ausschließlich** als JSON:
```json
{{
  "aufsicht_meldung_text": "Vollständiger Markdown-Text für Aufsichtsbehörde",
  "betroffene_info_text": "Vollständiger Text für Betroffene (oder null wenn nicht nötig)",
  "betroffene_info_erforderlich": true|false,
  "aufsichtsbehoerde_kontakt": "z.B. LfDI Baden-Württemberg, https://www.baden-wuerttemberg.datenschutz.de/",
  "art_referenz": "Art. 33 + ggf. Art. 34"
}}
```
"""


def parse_datenpanne_meldung_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'aufsicht_meldung_text': data.get('aufsicht_meldung_text', ''),
        'betroffene_info_text': data.get('betroffene_info_text'),
        'betroffene_info_erforderlich': bool(data.get('betroffene_info_erforderlich', False)),
        'aufsichtsbehoerde_kontakt': data.get('aufsichtsbehoerde_kontakt', ''),
        'art_referenz': data.get('art_referenz', 'Art. 33'),
    }


# ─────────────────────────────────────────────────────────────────────────
# D9 — Betroffenenrechte (Art. 15 Auskunft, Art. 17 Löschung, Art. 20 Portabilität)
# ─────────────────────────────────────────────────────────────────────────

def build_betroffenenrechte_prompt(projekt: dict[str, Any], anfrage: dict[str, Any]) -> str:
    return f"""Erstelle eine DSGVO-Antwortvorlage für eine Betroffenenrechts-Anfrage (deutsch).

**Verantwortlicher:** {projekt.get('unternehmen', projekt.get('name', ''))}
**Antragsart:** {anfrage.get('antragsart', 'auskunft')}
  (auskunft Art. 15 | berichtigung Art. 16 | loeschung Art. 17 | einschraenkung Art. 18 | portabilitaet Art. 20 | widerspruch Art. 21)
**Identität verifiziert:** {anfrage.get('identitaet_verifiziert', 'ja')}
**Anfrage-Datum:** {anfrage.get('anfrage_datum', '')}

DSGVO-Fristen: 1 Monat Antwort (verlängerbar auf 3 Monate bei Komplexität, Art. 12(3)).
Bei Ablehnung: Recht auf Beschwerde + gerichtlicher Rechtsbehelf in der Antwort erwähnen.

Generiere drei Texte:
1. Eingangsbestätigung (innerhalb von 1 Woche)
2. Vollständige Antwort (innerhalb 1 Monat) mit Inhalten je nach Antragsart
3. Falls Ablehnung: Begründung + Rechtsbehelf

Antworte als JSON:
```json
{{
  "eingangsbestaetigung": "Sehr geehrte/r ...",
  "antwort_template": "Vollständiger Markdown-Text der Antwort",
  "ablehnung_template": null,
  "art_referenz": "Art. 15 DSGVO",
  "frist_tage": 30,
  "checkliste_zu_beachten": ["Identitätsprüfung", "Logging der Anfrage", "..."]
}}
```
"""


def parse_betroffenenrechte_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'eingangsbestaetigung': data.get('eingangsbestaetigung', ''),
        'antwort_template': data.get('antwort_template', ''),
        'ablehnung_template': data.get('ablehnung_template'),
        'art_referenz': data.get('art_referenz', 'Art. 15'),
        'frist_tage': int(data.get('frist_tage', 30)),
        'checkliste_zu_beachten': data.get('checkliste_zu_beachten', []) or [],
    }


# ─────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict[str, Any]:
    if not raw: return {}
    text = raw.strip()
    for marker in ('```json', '```'):
        if marker in text:
            parts = text.split(marker)
            if len(parts) >= 2:
                text = parts[1].split('```')[0] if marker == '```json' else parts[1]
                break
    start, end = text.find('{'), text.rfind('}')
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
