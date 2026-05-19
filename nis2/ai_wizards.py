"""NIS2 Phase B — KI-Wizards (Issue #580).

Pattern wie CRA Phase B: Backend baut Prompt mit JSON-Schema, User kopiert
nach ChatGPT, Antwort wird per parse_*_response zurück-geparsed.
"""
from __future__ import annotations

import json
from typing import Any


# ─────────────────────────────────────────────────────────────────────────
# N6 — Entity-Klassifikator (essential / important / out-of-scope)
# ─────────────────────────────────────────────────────────────────────────

ENTITY_KLASSEN = ['essential', 'important', 'out-of-scope']

_KLASSE_SYNONYMS = {
    'essential': 'essential', 'wesentlich': 'essential', 'we': 'essential',
    'important': 'important', 'wichtig': 'important', 'wi': 'important',
    'out-of-scope': 'out-of-scope', 'nicht-im-scope': 'out-of-scope', 'oos': 'out-of-scope',
    'nicht betroffen': 'out-of-scope',
}


def _normalize_klasse(value: str) -> str:
    return _KLASSE_SYNONYMS.get((value or '').strip().lower(), 'out-of-scope')


def build_klassifikator_prompt(projekt: dict[str, Any]) -> str:
    return f"""Du bist ein NIS2-Experte (EU-Richtlinie 2022/2555).

Klassifiziere die folgende Organisation nach NIS2-Anhang I/II:

**Organisation:** {projekt.get('unternehmen', projekt.get('name', ''))}
**Beschreibung:** {projekt.get('beschreibung', '')}
**Aktuelle Klasse:** {projekt.get('einrichtungsklasse', 'wesentlich')}

NIS2 unterscheidet zwei Klassen + nicht-betroffene Einrichtungen:

- **essential** (wesentlich, Anhang I): Energie, Verkehr, Banken, Finanzmarkt-Infrastrukturen,
  Gesundheit, Trinkwasser, Abwasser, digitale Infrastruktur (DNS/TLD/Datacenter/CDN/Cloud/MSP),
  Verwaltung von IKT-Diensten, öffentliche Verwaltung, Raumfahrt.
  Größenschwelle: ≥250 MA ODER ≥50 Mio€ Umsatz ODER ≥43 Mio€ Bilanzsumme.

- **important** (wichtig, Anhang II): Post-/Kurierdienste, Abfallwirtschaft, Chemikalien,
  Lebensmittel, Industrieprodukte, Anbieter digitaler Dienste (Online-Marktplätze, Suchmaschinen,
  Social Networks), Forschungseinrichtungen.
  Größenschwelle: 50-249 MA ODER 10-50 Mio€ Umsatz.

- **out-of-scope**: KMU < 50 MA UND < 10 Mio€, kein Sektor aus Anhang I/II.

Antworte **ausschließlich** als JSON:
```json
{{
  "klasse": "essential|important|out-of-scope",
  "sektor": "z.B. Energie, Gesundheit, Digitale Infrastruktur, ...",
  "begruendung": "2-3 Sätze unter Bezug auf Anhang I/II + Größenschwelle",
  "konfidenz": "hoch|mittel|niedrig",
  "registrierungspflicht": true|false,
  "csirt_meldepflicht": "24h-Early-Warning / 72h-Notification / 1M-Final"
}}
```
"""


def parse_klassifikator_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'klasse': _normalize_klasse(data.get('klasse', 'out-of-scope')),
        'sektor': data.get('sektor', ''),
        'begruendung': data.get('begruendung', ''),
        'konfidenz': data.get('konfidenz', 'mittel'),
        'registrierungspflicht': bool(data.get('registrierungspflicht', False)),
        'csirt_meldepflicht': data.get('csirt_meldepflicht', '24h-Early-Warning / 72h-Notification / 1M-Final'),
    }


# ─────────────────────────────────────────────────────────────────────────
# N7 — Sektor-Templates
# ─────────────────────────────────────────────────────────────────────────

SEKTOR_TEMPLATES = {
    'energie': {
        'name': 'Energie (Strom/Gas/Wärme)',
        'klasse': 'essential',
        'csirt_kontakt': 'BSI/CERT-Bund + BNetzA',
        'csirt_email': 'meldung@bsi.bund.de',
        'rpo_minuten': 15,
        'rto_minuten': 60,
        'zusatz_normen': ['ISO 27019', 'IT-Sicherheitskatalog § 11 EnWG', 'B3S Energie'],
        'hinweise': 'Hochkritisch — Black-Out-Szenarien. Mindestens halbjährliche BCP-Übungen.',
    },
    'gesundheit': {
        'name': 'Gesundheit (Krankenhaus/Pflege/Labor)',
        'klasse': 'essential',
        'csirt_kontakt': 'BSI/CERT-Bund + BfArM',
        'csirt_email': 'meldung@bsi.bund.de',
        'rpo_minuten': 30,
        'rto_minuten': 120,
        'zusatz_normen': ['ISO 27799', 'B3S Krankenhaus', 'MDR (für Medizingeräte)'],
        'hinweise': 'Patientensicherheit ist Top-Priorität. KRITIS-Pflichten ab Schwellwerten beachten.',
    },
    'banken-finanzen': {
        'name': 'Banken & Finanzmarkt',
        'klasse': 'essential',
        'csirt_kontakt': 'BSI/CERT-Bund + BaFin',
        'csirt_email': 'meldung@bsi.bund.de',
        'rpo_minuten': 5,
        'rto_minuten': 30,
        'zusatz_normen': ['BAIT', 'KAIT', 'VAIT', 'DORA', 'ISO 27001'],
        'hinweise': 'DORA-Doppelregulierung — Lex specialis. Resilience-Tests mind. quartalsweise.',
    },
    'digitale-infrastruktur': {
        'name': 'Digitale Infrastruktur (DNS/TLD/Cloud/MSP)',
        'klasse': 'essential',
        'csirt_kontakt': 'BSI/CERT-Bund',
        'csirt_email': 'meldung@bsi.bund.de',
        'rpo_minuten': 30,
        'rto_minuten': 60,
        'zusatz_normen': ['ISO 27001', 'ISO 27017', 'C5'],
        'hinweise': 'MSP/Cloud-Provider: zusätzliche Anforderungen aus § 8a BSIG.',
    },
    'oeffentliche-verwaltung': {
        'name': 'Öffentliche Verwaltung (Bund/Länder)',
        'klasse': 'essential',
        'csirt_kontakt': 'BSI/CERT-Bund',
        'csirt_email': 'meldung@bsi.bund.de',
        'rpo_minuten': 60,
        'rto_minuten': 240,
        'zusatz_normen': ['BSI IT-Grundschutz', 'ISO 27001'],
        'hinweise': 'IT-Grundschutz-Kompendium ist Pflicht. Stärkere Transparenzpflichten.',
    },
}


def list_sektor_templates() -> list[dict[str, Any]]:
    return [{'id': k, **v} for k, v in SEKTOR_TEMPLATES.items()]


def get_sektor_template(sektor_id: str) -> dict[str, Any] | None:
    t = SEKTOR_TEMPLATES.get(sektor_id)
    return {'id': sektor_id, **t} if t else None


# ─────────────────────────────────────────────────────────────────────────
# N8 — Incident-Notification-Generator (24h/72h/1M)
# ─────────────────────────────────────────────────────────────────────────

def build_incident_notification_prompt(projekt: dict[str, Any], incident_meta: dict[str, Any]) -> str:
    return f"""Erstelle drei NIS2-konforme Incident-Meldungen für CSIRT (deutsch):
- 24h Early-Warning (kurz, keine Details, nur 'es ist was passiert')
- 72h Notification (mit Ersteinschätzung Auswirkung + Maßnahmen)
- 1-Monats-Final-Report (Root-Cause + Lessons Learned + Mitigationen)

**Einrichtung:** {projekt.get('unternehmen', projekt.get('name', ''))}
**Sektor:** {projekt.get('sektor', '(unbekannt)')}
**Incident-Beschreibung:** {incident_meta.get('description', '(bitte Beschreibung ergänzen)')}
**Schweregrad:** {incident_meta.get('severity', 'mittel')}
**Betroffene Services:** {incident_meta.get('affected_services', '(unbekannt)')}

Antworte **ausschließlich** als JSON:
```json
{{
  "early_warning": "Vollständiger 24h-Text...",
  "notification": "Vollständiger 72h-Text...",
  "final_report": "Vollständiger 1M-Text...",
  "verteiler": ["BSI/CERT-Bund", "Sektor-Aufsicht (z.B. BaFin/BNetzA)", "Datenschutzbehörde (falls Daten betroffen)"]
}}
```
"""


def parse_incident_notification_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'early_warning': data.get('early_warning', ''),
        'notification': data.get('notification', ''),
        'final_report': data.get('final_report', ''),
        'verteiler': data.get('verteiler', []) or [],
    }


# ─────────────────────────────────────────────────────────────────────────
# N9 — Supply-Chain-Assessment
# ─────────────────────────────────────────────────────────────────────────

def build_supply_chain_assessment_prompt(projekt: dict[str, Any], vendor: dict[str, Any]) -> str:
    return f"""Erstelle ein NIS2-konformes Supply-Chain-Security-Assessment (deutsch) für einen Vendor.

**Eigene Einrichtung:** {projekt.get('unternehmen', projekt.get('name', ''))}
**Vendor:** {vendor.get('vendor_name', '')}
**Leistung:** {vendor.get('leistung', '')}
**Kritikalität:** {vendor.get('kritikalitaet', 'mittel')}
**Vorhandene Zertifikate:** {', '.join(vendor.get('zertifikate', []) or [])}

Liefere ein Bewertungsraster mit 10 Kategorien (jeweils Score 0-10) + Empfehlungen.

Antworte als JSON:
```json
{{
  "kategorien": [
    {{"name": "Zertifizierungen", "score": 0-10, "kommentar": "..."}},
    {{"name": "Sub-Processor-Kette", "score": 0-10, "kommentar": "..."}},
    {{"name": "Datenresidenz", "score": 0-10, "kommentar": "..."}},
    {{"name": "SLA-Verfügbarkeit", "score": 0-10, "kommentar": "..."}},
    {{"name": "Incident-Response", "score": 0-10, "kommentar": "..."}},
    {{"name": "Audit-Rechte", "score": 0-10, "kommentar": "..."}},
    {{"name": "Kündbarkeit/Lock-in", "score": 0-10, "kommentar": "..."}},
    {{"name": "Pen-Test-Berichte", "score": 0-10, "kommentar": "..."}},
    {{"name": "Verschlüsselung at-rest/in-transit", "score": 0-10, "kommentar": "..."}},
    {{"name": "Mitarbeiter-Sicherheit (Background-Check)", "score": 0-10, "kommentar": "..."}}
  ],
  "gesamt_score": 0-100,
  "empfehlung": "akzeptieren|akzeptieren-mit-Auflagen|ablehnen",
  "naechste_schritte": "..."
}}
```
"""


def parse_supply_chain_assessment_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'kategorien': data.get('kategorien', []) or [],
        'gesamt_score': int(data.get('gesamt_score', 0)),
        'empfehlung': data.get('empfehlung', 'akzeptieren-mit-Auflagen'),
        'naechste_schritte': data.get('naechste_schritte', ''),
    }


# ─────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
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
