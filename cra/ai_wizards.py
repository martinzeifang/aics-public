"""CRA Phase B — KI-Wizards (Issues #477-#480).

Pattern: Backend baut Prompt mit JSON-Schema, User kopiert nach ChatGPT,
Antwort wird per parse_*_response zurück-geparsed und ins Modell übernommen.
"""
from __future__ import annotations

import json
from typing import Any


# ─────────────────────────────────────────────────────────────────────────
# C6 — Klassifikator-Wizard (#477)
# Bestimmt CRA-Produktklasse aus Beschreibung
# ─────────────────────────────────────────────────────────────────────────

# Canonical Keys gemäß cra.requirements.PRODUKTKLASSEN
PRODUKTKLASSEN_CRA = ["default", "important_i", "important_ii", "critical"]

# Synonyme → canonical (akzeptiert deutsche/englische Schreibweisen aus ChatGPT)
_KLASSE_SYNONYMS = {
    'default': 'default',
    'standard': 'default',
    'nicht-kritisch': 'default',
    'non-critical': 'default',
    'important_i': 'important_i',
    'important-i': 'important_i',
    'important i': 'important_i',
    'wichtig-klasse-1': 'important_i',
    'wichtig klasse 1': 'important_i',
    'klasse 1': 'important_i',
    'class i': 'important_i',
    'annex iii klasse i': 'important_i',
    'important_ii': 'important_ii',
    'important-ii': 'important_ii',
    'important ii': 'important_ii',
    'wichtig-klasse-2': 'important_ii',
    'wichtig klasse 2': 'important_ii',
    'klasse 2': 'important_ii',
    'class ii': 'important_ii',
    'annex iii klasse ii': 'important_ii',
    'critical': 'critical',
    'kritisch': 'critical',
    'annex iv': 'critical',
}


def _normalize_klasse(value: str) -> str:
    key = (value or '').strip().lower()
    return _KLASSE_SYNONYMS.get(key, 'default')


def build_klassifikator_prompt(projekt: dict[str, Any]) -> str:
    return f"""Du bist ein CRA-Experte (EU Cyber Resilience Act).

Klassifiziere das folgende Produkt nach den CRA-Risikoklassen:

**Produkt:** {projekt.get('name', '')}
**Hersteller:** {projekt.get('unternehmen', '')}
**Beschreibung:** {projekt.get('beschreibung', '')}
**Aktuelle Klasse:** {projekt.get('produktklasse', 'default')}

CRA-Klassen (gib genau einen dieser **technischen Keys** zurück):
- "default"       — Nicht-kritische Produkte (Standard-Anforderungen CRA Annex I)
- "important_i"   — CRA Annex III Klasse I („Wichtig Klasse 1"): Browser, Password-Manager,
                    VPN-Clients, IAM-Software, Public-Key-Infrastruktur
- "important_ii"  — CRA Annex III Klasse II („Wichtig Klasse 2"): Hypervisoren, Firewalls,
                    IDS/IPS, Smart-Cards, Boot-Manager
- "critical"      — CRA Annex IV („Kritisch"): Hardware-Security-Module, Smart-Meter-Gateways

Antworte **ausschließlich** als JSON in genau diesem Schema. Verwende die technischen Keys oben:
```json
{{
  "klasse": "default|important_i|important_ii|critical",
  "begruendung": "Erklärung in 2-3 Sätzen unter Bezug auf konkrete CRA-Anhänge",
  "konfidenz": "hoch|mittel|niedrig",
  "indikatoren": ["Stichwort 1", "Stichwort 2"],
  "konformitaetsbewertung": "Selbstbewertung|Modul B+C|Modul H|nicht erforderlich"
}}
```
"""


def parse_klassifikator_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    klasse = _normalize_klasse(data.get('klasse', 'default'))
    return {
        'klasse': klasse,
        'begruendung': data.get('begruendung', ''),
        'konfidenz': data.get('konfidenz', 'mittel'),
        'indikatoren': data.get('indikatoren', []) or [],
        'konformitaetsbewertung': data.get('konformitaetsbewertung', 'Selbstbewertung'),
    }


# ─────────────────────────────────────────────────────────────────────────
# C7 — Branchen-Templates (#478)
# Branchen-spezifische CRA-Vorlagen
# ─────────────────────────────────────────────────────────────────────────

BRANCHEN_TEMPLATES = {
    'medical': {
        'name': 'Medizingerät / MDR',
        'pflicht_doku_defaults': {
            'support_jahre': 10,
            'threat_framework': 'STRIDE',
            'triage_sla': '24h',
            'fix_sla_critical': '7 Tage',
        },
        'zusatz_normen': ['IEC 62443', 'ISO 14971', 'EN ISO 13485', 'MDR 2017/745'],
        'hinweise': 'Verzahnung CRA ↔ MDR — Berichtspflichten an BfArM + ENISA parallel.',
    },
    'iot-consumer': {
        'name': 'IoT-Consumer (Smart-Home)',
        'pflicht_doku_defaults': {
            'support_jahre': 5,
            'threat_framework': 'STRIDE',
            'triage_sla': '48h',
            'fix_sla_critical': '14 Tage',
        },
        'zusatz_normen': ['ETSI EN 303 645', 'NIST 8425'],
        'hinweise': 'CRA Annex III meist Klasse I; Default-Passwörter verboten, Auto-Updates Pflicht.',
    },
    'iot-industrial': {
        'name': 'Industrial IoT / OT',
        'pflicht_doku_defaults': {
            'support_jahre': 10,
            'threat_framework': 'STRIDE',
            'triage_sla': '24h',
            'fix_sla_critical': '7 Tage',
        },
        'zusatz_normen': ['IEC 62443', 'NIS2'],
        'hinweise': 'Häufig Annex III Klasse II — Konformität via Modul B+C oder H.',
    },
    'b2b-saas': {
        'name': 'B2B-SaaS / Web-App',
        'pflicht_doku_defaults': {
            'support_jahre': 5,
            'threat_framework': 'STRIDE',
            'triage_sla': '48h',
            'fix_sla_critical': '7 Tage',
        },
        'zusatz_normen': ['OWASP ASVS', 'ISO 27001'],
        'hinweise': 'Selbstbewertung meist ausreichend, wenn nicht in Annex III gelistet.',
    },
    'firewall': {
        'name': 'Firewall / Network-Security',
        'pflicht_doku_defaults': {
            'support_jahre': 7,
            'threat_framework': 'STRIDE',
            'triage_sla': '12h',
            'fix_sla_critical': '3 Tage',
        },
        'zusatz_normen': ['Common Criteria EAL4+', 'IEC 62443-3-3'],
        'hinweise': 'Annex III Klasse II — Modul B+C oder H zwingend.',
    },
}


def list_branchen_templates() -> list[dict[str, Any]]:
    return [{'id': k, **v} for k, v in BRANCHEN_TEMPLATES.items()]


def get_branchen_template(branche_id: str) -> dict[str, Any] | None:
    t = BRANCHEN_TEMPLATES.get(branche_id)
    return ({'id': branche_id, **t}) if t else None


# ─────────────────────────────────────────────────────────────────────────
# C8 — Vuln-Handling-Policy-Generator (#479)
# ─────────────────────────────────────────────────────────────────────────

def build_vuln_policy_prompt(projekt: dict[str, Any], psirt: dict[str, Any]) -> str:
    return f"""Erstelle einen CRA-konformen Vulnerability-Handling-Policy-Text (deutsch).

**Produkt:** {projekt.get('name', '')}
**Hersteller:** {projekt.get('unternehmen', '')}
**Aktuelle PSIRT-Konfiguration:**
- Intake-Kanal: {psirt.get('intake_kanal', '(noch nicht gesetzt)')}
- Triage-SLA: {psirt.get('triage_sla', '(noch nicht gesetzt)')}
- Fix-SLA Critical/High/Medium: {psirt.get('fix_sla_critical', '?')} / {psirt.get('fix_sla_high', '?')} / {psirt.get('fix_sla_medium', '?')}

Generiere einen vollständigen Policy-Text mit folgenden Abschnitten:
1. Scope (welche Produkte/Versionen)
2. Reporting-Kanal + PGP-Key-Hinweis
3. Triage-Prozess + Akzeptanz-Kriterien
4. SLAs nach Schwere
5. Coordinated Disclosure (90/180-Tage-Frist)
6. CVE-Zuweisung + Hall of Fame
7. Verweis auf SECURITY.md / Advisories
8. Kontakt + Eskalation

Antworte als JSON:
```json
{{
  "titel": "Vulnerability-Disclosure-Policy für <Produkt>",
  "policy_text": "Vollständiger Policy-Text im Markdown",
  "publikationspfad_vorschlag": "/.well-known/security.txt oder SECURITY.md",
  "review_frequenz": "12 Monate"
}}
```
"""


def parse_vuln_policy_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'titel': data.get('titel', 'Vulnerability-Disclosure-Policy'),
        'policy_text': data.get('policy_text', ''),
        'publikationspfad_vorschlag': data.get('publikationspfad_vorschlag', 'SECURITY.md'),
        'review_frequenz': data.get('review_frequenz', '12 Monate'),
    }


# ─────────────────────────────────────────────────────────────────────────
# C9 — Update-Policy-Generator (#480)
# ─────────────────────────────────────────────────────────────────────────

def build_update_policy_prompt(projekt: dict[str, Any], support_period: dict[str, Any]) -> str:
    return f"""Erstelle eine CRA-konforme Security-Update-Policy (deutsch).

**Produkt:** {projekt.get('name', '')}
**Markteintritt:** {support_period.get('markteintritt_datum', '(noch nicht gesetzt)')}
**Support-Jahre:** {support_period.get('support_jahre', 5)}
**Geplantes EOL:** {support_period.get('eol_datum', '(berechnet sobald Markteintritt gesetzt)')}
**Update-Kanal:** {support_period.get('update_kanal', '(noch nicht gesetzt)')}

Erstelle eine Update-Policy mit folgenden Abschnitten:
1. Support-Zeitraum (mit konkretem EOL-Datum)
2. Update-Kanäle (Auto-Update, manueller Pull, Repo)
3. Update-Kadenz (Security-Patches: 30 Tage, Feature: vierteljährlich, etc.)
4. Notfall-Patches (Out-of-Band für Critical CVEs)
5. Signatur + Integrität (Code-Signing, Hash-Verification)
6. Backwards-Compat-Versprechen
7. Migration-Pfad für EOL (LTS-Branch oder Forced-Upgrade)
8. End-User-Kommunikation

Antworte als JSON:
```json
{{
  "titel": "Security-Update-Policy für <Produkt>",
  "policy_text": "Vollständiger Policy-Text im Markdown",
  "kadenz_security": "30 Tage / Out-of-Band für Critical",
  "kadenz_feature": "vierteljährlich",
  "eol_kommunikation": "12 Monate Vorlauf via Newsletter + In-App-Banner"
}}
```
"""


def parse_update_policy_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'titel': data.get('titel', 'Security-Update-Policy'),
        'policy_text': data.get('policy_text', ''),
        'kadenz_security': data.get('kadenz_security', '30 Tage'),
        'kadenz_feature': data.get('kadenz_feature', 'vierteljährlich'),
        'eol_kommunikation': data.get('eol_kommunikation', '12 Monate Vorlauf'),
    }


# ─────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict[str, Any]:
    """Robust JSON-Extraktion aus ChatGPT-Antwort (mit/ohne ```json-Fences)."""
    if not raw:
        return {}
    text = raw.strip()
    # Fenced code blocks entfernen
    for marker in ('```json', '```'):
        if marker in text:
            parts = text.split(marker)
            if len(parts) >= 2:
                text = parts[1].split('```')[0] if marker == '```json' else parts[1]
                break
    # Erstes { bis letztes }
    start, end = text.find('{'), text.rfind('}')
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
