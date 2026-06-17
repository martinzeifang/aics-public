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


# ═════════════════════════════════════════════════════════════════════════
# Phase D — Incident-/Meldungs-Wizards (#513-#516)
# ═════════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────────────────
# N14 — 24h-Erstmeldung-Wizard (BSI-Portal-Format) — #513
# ─────────────────────────────────────────────────────────────────────────

def build_incident_24h_prompt(projekt: dict[str, Any], incident: dict[str, Any]) -> str:
    return f"""Erstelle eine **24-Stunden-Erstmeldung** (Early Warning) nach NIS2 Art. 23 Abs. 4 lit. a
für signifikante Sicherheitsvorfälle. Format-konform für das **BSI-Meldeportal** (deutsch).

# Einrichtung
- Organisation: {projekt.get('unternehmen', projekt.get('name', ''))}
- Sektor: {projekt.get('sektor', '(unbekannt)')}
- Einrichtungsart: {projekt.get('einrichtungsart', '(unbekannt)')}

# Incident-Daten
- Incident-ID: {incident.get('incident_id', '(generieren als YYYY-MM-DD-XXX)')}
- Eintritt: {incident.get('detected_at', '(unbekannt)')}
- Kurzbeschreibung: {incident.get('summary', '')}
- Vermutete Ursache: {incident.get('suspected_cause', '(unklar)')}
- Verdacht: rechtswidriger/böswilliger Akt? {incident.get('malicious_suspected', 'unklar')}
- Auswirkung grenzüberschreitend? {incident.get('cross_border', 'unklar')}

Pflicht-Inhalte der 24h-Meldung (Art. 23 Abs. 4 lit. a):
1. Vorläufige Einschätzung: Vorfall **signifikant**? (ja/nein/unklar — wenn unklar → trotzdem melden)
2. Verdacht eines rechtswidrigen/böswilligen Akts? (ja/nein/unklar)
3. Auswirkungen grenzüberschreitend? (ja/nein/unklar)
4. KEINE Detail-Analyse — bloß Mitteilung, dass etwas vorgefallen ist
5. Eskalationskontakt + Antwort-Channel

Antworte **ausschließlich** als JSON:
```json
{{
  "betreff": "24h-Erstmeldung — <Incident-ID> — <Datum>",
  "incident_id": "...",
  "signifikant": "ja|nein|unklar",
  "boeswillig_verdacht": "ja|nein|unklar",
  "grenzueberschreitend": "ja|nein|unklar",
  "kurztext": "Sehr knapper Meldungstext (max. 3 Sätze), keine Details",
  "kontakt": {{
    "name": "(Sicherheitsbeauftragter / CISO)",
    "email": "...",
    "telefon": "..."
  }},
  "naechster_meilenstein": "72h-Aktualisierung mit Ersteinschätzung",
  "empfaenger": ["BSI / CERT-Bund", "Sektor-Aufsichtsbehörde (falls separat)"]
}}
```
"""


def parse_incident_24h_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'betreff': data.get('betreff', '24h-Erstmeldung'),
        'incident_id': data.get('incident_id', ''),
        'signifikant': data.get('signifikant', 'unklar'),
        'boeswillig_verdacht': data.get('boeswillig_verdacht', 'unklar'),
        'grenzueberschreitend': data.get('grenzueberschreitend', 'unklar'),
        'kurztext': data.get('kurztext', ''),
        'kontakt': data.get('kontakt', {}) or {},
        'naechster_meilenstein': data.get('naechster_meilenstein', '72h-Aktualisierung'),
        'empfaenger': data.get('empfaenger', []) or [],
    }


# ─────────────────────────────────────────────────────────────────────────
# N15a — 72h-Aktualisierung — #514
# ─────────────────────────────────────────────────────────────────────────

def build_incident_72h_prompt(projekt: dict[str, Any], incident: dict[str, Any]) -> str:
    return f"""Erstelle eine **72-Stunden-Aktualisierung** nach NIS2 Art. 23 Abs. 4 lit. b. Aufbauend
auf der 24h-Erstmeldung gibt sie eine **Ersteinschätzung** zum Vorfall.

# Einrichtung
- Organisation: {projekt.get('unternehmen', projekt.get('name', ''))}
- Sektor: {projekt.get('sektor', '(unbekannt)')}

# Incident-Daten
- Incident-ID: {incident.get('incident_id', '')}
- 24h-Meldung am: {incident.get('first_notified_at', '(unbekannt)')}
- Aktueller Stand: {incident.get('current_status', 'in Analyse')}
- Auswirkung (vorläufig): {incident.get('impact_preliminary', '')}
- Schweregrad: {incident.get('severity', 'mittel')}
- Betroffene Services: {incident.get('affected_services', '')}
- Betroffene Personen/Firmen: {incident.get('affected_subjects', '')}
- Sofortmaßnahmen: {incident.get('immediate_actions', '')}
- Kompromittierungsindikatoren (IoCs): {incident.get('iocs', '(noch keine)')}

Pflicht-Inhalte der 72h-Aktualisierung (Art. 23 Abs. 4 lit. b):
1. Aktualisierung der 24h-Meldung
2. **Ersteinschätzung**: Schweregrad + Auswirkung
3. **Kompromittierungsindikatoren** (sofern bekannt) — IoC-Liste für CSIRT-Netz
4. Sofortmaßnahmen, die ergriffen wurden
5. Erwarteter Zeitrahmen weitere Maßnahmen

Antworte **ausschließlich** als JSON:
```json
{{
  "betreff": "72h-Aktualisierung — <Incident-ID>",
  "incident_id": "...",
  "schweregrad": "niedrig|mittel|hoch|kritisch",
  "ersteinschaetzung": "ausformulierter Text",
  "iocs": [
    {{"typ": "ip|domain|hash|cve", "wert": "...", "kommentar": "..."}}
  ],
  "sofortmassnahmen": ["Maßnahme 1", "Maßnahme 2"],
  "auswirkung": "Wer/Was ist wie betroffen?",
  "naechste_schritte": ["was bis zur 1M-Abschlussmeldung passiert"],
  "zeitrahmen": "z.B. Eindämmung bis +7 Tage, Forensik bis +14 Tage"
}}
```
"""


def parse_incident_72h_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'betreff': data.get('betreff', '72h-Aktualisierung'),
        'incident_id': data.get('incident_id', ''),
        'schweregrad': data.get('schweregrad', 'mittel'),
        'ersteinschaetzung': data.get('ersteinschaetzung', ''),
        'iocs': data.get('iocs', []) or [],
        'sofortmassnahmen': data.get('sofortmassnahmen', []) or [],
        'auswirkung': data.get('auswirkung', ''),
        'naechste_schritte': data.get('naechste_schritte', []) or [],
        'zeitrahmen': data.get('zeitrahmen', ''),
    }


# ─────────────────────────────────────────────────────────────────────────
# N15b — 1-Monats-Abschlussmeldung — #514
# ─────────────────────────────────────────────────────────────────────────

def build_incident_final_prompt(projekt: dict[str, Any], incident: dict[str, Any]) -> str:
    return f"""Erstelle eine **1-Monats-Abschlussmeldung** (Final Report) nach NIS2 Art. 23 Abs. 4 lit. c
für einen signifikanten Vorfall.

# Einrichtung
- Organisation: {projekt.get('unternehmen', projekt.get('name', ''))}
- Sektor: {projekt.get('sektor', '(unbekannt)')}

# Incident-Daten
- Incident-ID: {incident.get('incident_id', '')}
- Eintritt: {incident.get('detected_at', '(unbekannt)')}
- Behebung am: {incident.get('resolved_at', '(unbekannt)')}
- Endgültiger Schweregrad: {incident.get('severity', 'mittel')}
- Root-Cause: {incident.get('root_cause', '')}
- Lessons Learned: {incident.get('lessons_learned', '')}
- Umgesetzte Maßnahmen: {incident.get('mitigations', '')}

Pflicht-Inhalte der Abschlussmeldung (Art. 23 Abs. 4 lit. c):
1. **Detaillierte Beschreibung** des Vorfalls + Auswirkungen
2. **Bedrohungsart oder Ursache** (Root-Cause) — am Wahrscheinlichsten / Verifiziert
3. **Umgesetzte und laufende Abhilfemaßnahmen**
4. ggf. **grenzüberschreitende** Auswirkungen — wer wurde informiert
5. Lessons Learned + Vorbeugemaßnahmen für Zukunft

Antworte **ausschließlich** als JSON:
```json
{{
  "betreff": "1-Monats-Abschlussmeldung — <Incident-ID>",
  "incident_id": "...",
  "vorfall_beschreibung": "vollständige Beschreibung",
  "root_cause": "Bedrohungsart oder Ursache",
  "umgesetzte_massnahmen": ["Maßnahme 1", "Maßnahme 2"],
  "laufende_massnahmen": ["noch offene Maßnahme 1"],
  "grenzueberschreitend": {{
    "betroffen": true|false,
    "informiert": ["Liste der informierten Behörden/Mitgliedstaaten"]
  }},
  "lessons_learned": "ausformulierter Text",
  "vorbeugemassnahmen": ["was wird zukünftig verhindern"],
  "report_text": "vollständiger Markdown-Body für PDF/Mail-Export"
}}
```
"""


def parse_incident_final_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    gb = data.get('grenzueberschreitend') or {}
    return {
        'betreff': data.get('betreff', '1-Monats-Abschlussmeldung'),
        'incident_id': data.get('incident_id', ''),
        'vorfall_beschreibung': data.get('vorfall_beschreibung', ''),
        'root_cause': data.get('root_cause', ''),
        'umgesetzte_massnahmen': data.get('umgesetzte_massnahmen', []) or [],
        'laufende_massnahmen': data.get('laufende_massnahmen', []) or [],
        'grenzueberschreitend': {
            'betroffen': bool(gb.get('betroffen', False)),
            'informiert': gb.get('informiert', []) or [],
        },
        'lessons_learned': data.get('lessons_learned', ''),
        'vorbeugemassnahmen': data.get('vorbeugemassnahmen', []) or [],
        'report_text': data.get('report_text', ''),
    }


# ─────────────────────────────────────────────────────────────────────────
# N16 — Cyberhygiene-Quiz für Mitarbeiter — #515
# ─────────────────────────────────────────────────────────────────────────

QUIZ_TOPICS = [
    'Phishing-Erkennung', 'Passwort-Hygiene', 'Social Engineering',
    'USB-Stick / Wechselmedien', 'Verschlüsselung', 'Patch-Management',
    'Cloud-Sicherheit', 'Mobile Devices', 'Datenschutz im Alltag',
    'Reporting verdächtiger Vorfälle',
]


def build_cyberhygiene_quiz_prompt(projekt: dict[str, Any],
                                   themen: list[str] | None = None,
                                   niveau: str = 'mittel') -> str:
    themen = themen or QUIZ_TOPICS
    themen_str = ', '.join(themen)
    return f"""Erstelle ein **10-Fragen-Cyberhygiene-Quiz** für Mitarbeiter-Awareness (deutsch).
Mix aus Multiple-Choice (4 Optionen, genau 1 richtig) und True/False.

# Kontext
- Einrichtung: {projekt.get('unternehmen', projekt.get('name', ''))}
- Sektor: {projekt.get('sektor', '(unbekannt)')}
- Schwierigkeitsgrad: {niveau} (leicht | mittel | hoch)

# Themen (10 Fragen — je 1 pro Thema, sofern möglich)
{themen_str}

Pro Frage:
- Klare, alltagsrelevante Frage
- 4 Antwortoptionen (oder 2 für True/False), genau 1 richtig
- Erklärung in 2-3 Sätzen warum die Antwort richtig ist (auch bei falscher Antwort lehrreich)
- Schwierigkeit + Quelle (z.B. BSI IT-Grundschutz, NIS2 Art. 21 lit. g)

Antworte **ausschließlich** als JSON:
```json
{{
  "titel": "Cyberhygiene-Quiz — <Datum>",
  "fragen": [
    {{
      "id": "Q1",
      "thema": "Phishing-Erkennung",
      "frage": "...",
      "typ": "mc|tf",
      "optionen": ["...", "...", "...", "..."],
      "korrekt_index": 0,
      "erklaerung": "...",
      "schwierigkeit": "leicht|mittel|hoch",
      "quelle": "BSI o.ä."
    }}
  ],
  "auswertung": {{
    "bestanden_ab_punkten": 7,
    "max_punkte": 10,
    "feedback_low": "Bitte Schulung wiederholen.",
    "feedback_mid": "OK, aber Awareness vertiefen.",
    "feedback_high": "Stark! Bitte trotzdem Refresher in 6 Monaten."
  }}
}}
```
"""


def parse_cyberhygiene_quiz_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'titel': data.get('titel', 'Cyberhygiene-Quiz'),
        'fragen': data.get('fragen', []) or [],
        'auswertung': data.get('auswertung', {}) or {},
    }


# ─────────────────────────────────────────────────────────────────────────
# N17 — Lieferanten-Tiering-Wizard — #516
# ─────────────────────────────────────────────────────────────────────────

VENDOR_TIERS = ['kritisch', 'wichtig', 'normal']


def build_vendor_tiering_prompt(projekt: dict[str, Any], vendor: dict[str, Any]) -> str:
    return f"""Klassifiziere einen Lieferanten nach **NIS2-Tiering-Logik** (kritisch / wichtig / normal)
und liefere tier-spezifische **Kontroll-Empfehlungen**.

# Eigene Einrichtung
- Organisation: {projekt.get('unternehmen', projekt.get('name', ''))}
- Sektor: {projekt.get('sektor', '(unbekannt)')}

# Vendor
- Name: {vendor.get('vendor_name', '')}
- Leistung: {vendor.get('leistung', '')}
- Zugriff auf eigene Daten: {vendor.get('data_access', 'kein')}
- Vertragsvolumen p.a.: {vendor.get('contract_volume_eur', '(unbekannt)')}
- Ersetzbarkeit: {vendor.get('substitutability', 'mittel')}  # niedrig=Lock-in, hoch=austauschbar
- Geografische Lage: {vendor.get('jurisdiction', '(unbekannt)')}
- Sub-Processor-Kette: {vendor.get('sub_processors', '(keine Angabe)')}
- Vorhandene Zertifikate: {', '.join(vendor.get('zertifikate', []) or [])}

Tier-Schwellen:
- **kritisch** = Lieferant fällt aus → eigener Geschäftsbetrieb stoppt; oder Zugang zu sensitiven Daten
  (PII, Auth-Material, Kronjuwelen-Code); niedrige Ersetzbarkeit
- **wichtig** = Ausfall führt zu spürbarer Service-Degradation; teilweiser Datenzugriff
- **normal** = austauschbar; keine sensitiven Daten

Antworte **ausschließlich** als JSON:
```json
{{
  "tier": "kritisch|wichtig|normal",
  "tier_begruendung": "warum dieses Tier — 2-3 Sätze mit konkreten Faktoren",
  "konfidenz": "hoch|mittel|niedrig",
  "kontrollen_empfehlung": [
    {{"id": "K1", "name": "Audit-Recht", "beschreibung": "...", "pflicht_ab_tier": "kritisch"}},
    {{"id": "K2", "name": "Pen-Test-Bericht jährlich", "beschreibung": "...", "pflicht_ab_tier": "wichtig"}}
  ],
  "fragebogen_versenden": true|false,
  "naechste_review": "z.B. quartalsweise|jährlich",
  "soforthandlungen": ["was JETZT geprüft werden sollte"]
}}
```
"""


def parse_vendor_tiering_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    tier = (data.get('tier') or '').strip().lower()
    if tier not in VENDOR_TIERS:
        tier = 'normal'
    return {
        'tier': tier,
        'tier_begruendung': data.get('tier_begruendung', ''),
        'konfidenz': data.get('konfidenz', 'mittel'),
        'kontrollen_empfehlung': data.get('kontrollen_empfehlung', []) or [],
        'fragebogen_versenden': bool(data.get('fragebogen_versenden', False)),
        'naechste_review': data.get('naechste_review', 'jährlich'),
        'soforthandlungen': data.get('soforthandlungen', []) or [],
    }


# ═════════════════════════════════════════════════════════════════════════
# Sprint #21 — N1/N2 Auto-Fill-/Wizard-Ergänzungen (#1072/#1073)
# ═════════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────────────────
# N1 (#1072) — Asset-Inventar-Wizard (manueller Copy-Paste-Pfad)
# Ergänzt den Repo-Scan (nis2/repo_autofill.suggest_assets) um einen
# Prompt/Parse-Wizard für Anwender ohne (zugängliches) Repo.
# ─────────────────────────────────────────────────────────────────────────

ASSET_TYPEN = ['it', 'ot', 'daten', 'cloud-service', 'netzwerk', 'personen']
ASSET_KRITIKALITAET = ['niedrig', 'mittel', 'hoch', 'kritisch']


def build_asset_inventory_prompt(projekt: dict[str, Any]) -> str:
    return f"""Du bist NIS2-Experte (Richtlinie (EU) 2022/2555, Art. 21 Abs. 2 lit. a)
und erstellst ein **Asset-Inventar** für das folgende Unternehmen.

# Kontext
- Unternehmen: {projekt.get('unternehmen', '') or projekt.get('name', '')}
- Sektor: {projekt.get('sektor', '(unbekannt)')}
- Beschreibung: {projekt.get('beschreibung', '(keine)')}

Liste die wichtigsten IT-/OT-/Daten-/Cloud-/Netzwerk-Assets im NIS2-Scope.
Verwende für `asset_typ` eines von: {', '.join(ASSET_TYPEN)}.
Verwende für `kritikalitaet` eines von: {', '.join(ASSET_KRITIKALITAET)}.
Schätze den Schutzbedarf je Asset für Vertraulichkeit/Integrität/Verfügbarkeit (1-3).

Antworte **ausschließlich** als JSON-Objekt:
```json
{{
  "assets": [
    {{
      "asset_name": "z.B. ERP-System",
      "asset_typ": "it",
      "kritikalitaet": "hoch",
      "verantwortlich": "z.B. IT-Leitung",
      "standort": "z.B. RZ Frankfurt",
      "beschreibung": "Kurzbeschreibung + Funktion",
      "schutzbedarf_v": 2,
      "schutzbedarf_i": 3,
      "schutzbedarf_a": 3
    }}
  ]
}}
```
"""


def parse_asset_inventory_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    assets_in = data.get('assets') if isinstance(data, dict) else None
    if not isinstance(assets_in, list):
        assets_in = _extract_json_array(raw)
    out: list[dict[str, Any]] = []
    for a in assets_in or []:
        if not isinstance(a, dict):
            continue
        name = str(a.get('asset_name') or a.get('name') or '').strip()
        if not name:
            continue
        typ = str(a.get('asset_typ') or 'it').strip().lower()
        if typ not in ASSET_TYPEN:
            typ = 'it'
        krit = str(a.get('kritikalitaet') or 'mittel').strip().lower()
        if krit not in ASSET_KRITIKALITAET:
            krit = 'mittel'

        def _sb(key: str) -> int:
            try:
                v = int(a.get(key, 1))
            except (TypeError, ValueError):
                v = 1
            return min(3, max(1, v))

        out.append({
            'asset_name': name[:200],
            'asset_typ': typ,
            'kritikalitaet': krit,
            'verantwortlich': str(a.get('verantwortlich', '') or '')[:200],
            'standort': str(a.get('standort', '') or '')[:200],
            'beschreibung': str(a.get('beschreibung', '') or '')[:1000],
            'schutzbedarf_v': _sb('schutzbedarf_v'),
            'schutzbedarf_i': _sb('schutzbedarf_i'),
            'schutzbedarf_a': _sb('schutzbedarf_a'),
        })
    return {'assets': out}


# ─────────────────────────────────────────────────────────────────────────
# N2 (#1073) — Risiko-Register: Sektor-Template-Wizard bleibt erhalten.
#
# Der bestehende Sektor-Template-Wizard (list_sektor_templates /
# get_sektor_template / nis2_sektor_apply) deckt N2 weiter ab. Manuelle
# Risiko-Eingabe (POST /risiken) bleibt in dieser Wave aktiv.
#
# TODO(Wave 2 / S7 #107x): Read-only-Schaltung des manuellen Risiko-Registers,
# sobald Risiken ausschließlich aus dem Risikobewertungs-Modul importiert
# werden. Bis dahin nur Read-only-Display-Prep im Frontend (Banner-Hinweis),
# KEINE Entfernung der manuellen Eingabe.
# ─────────────────────────────────────────────────────────────────────────


# ═════════════════════════════════════════════════════════════════════════
# #1240 — Pflichtdokument-Generatoren (Copy/Paste, Art. 21(2) NIS2)
#
# Je NIS2-Pflichtdokument ein „Doc-only"-Wizard: Backend baut einen
# kontext-bewussten Prompt (Vorbefüllung aus N1/N4/N5, ohne Doppelerfassung),
# der Anwender kopiert ihn nach ChatGPT und speichert das Ergebnis über die
# generische „Als Dokument speichern"-Aktion (#1235) als editier-/freigabe-/
# exportierbares managed_doc. Die parse_*-Funktionen liefern nur Vorschau +
# Plausibilitätshinweise (keine direkte Persistenz, kein API-Call).
# ═════════════════════════════════════════════════════════════════════════

# Gemeinsames Antwort-Schema aller Doc-Generatoren.
_DOC_JSON_HINT = """Antworte **ausschließlich** als JSON in genau diesem Schema:
```json
{{
  "titel": "{titel}",
  "doc_text": "Vollständiger Markdown-Text des Dokuments (alle Pflichtpunkte)",
  "abgedeckte_punkte": ["Liste der adressierten Mindestinhalte"],
  "offene_punkte": ["Noch zu ergänzende/zu klärende Punkte"]
}}
```"""


def _parse_doc_response(raw: str, default_titel: str,
                        pflicht_punkte: list[str] | None = None) -> dict[str, Any]:
    """Gemeinsamer Parser der Doc-Generatoren (Vorschau + Plausibilität)."""
    data = _extract_json(raw)
    doc_text = str(data.get('doc_text', '') or '')
    abgedeckt = [str(x) for x in (data.get('abgedeckte_punkte') or []) if x]
    offen = [str(x) for x in (data.get('offene_punkte') or []) if x]
    hinweise: list[str] = []
    if not doc_text.strip():
        hinweise.append('Kein Dokumenttext erkannt — bitte JSON-Antwort prüfen.')
    low = doc_text.lower()
    for pp in (pflicht_punkte or []):
        if pp.lower() not in low:
            hinweise.append(f'Pflichtpunkt evtl. nicht adressiert: {pp}')
    return {
        'titel': str(data.get('titel') or default_titel),
        'doc_text': doc_text,
        'abgedeckte_punkte': abgedeckt,
        'offene_punkte': offen,
        'plausibilitaet_hinweise': hinweise,
    }


def _firma(projekt: dict[str, Any]) -> str:
    return projekt.get('unternehmen', '') or projekt.get('name', '') or '(Einrichtung)'


# ── is_leitlinie — IS-Leitlinie + Risikoanalyse-Policy (Art. 21(2)a) ──────────

_IS_LEITLINIE_PUNKTE = [
    'Geltungsbereich', 'Sicherheitsziele', 'Rollen', 'Risikoanalyse',
    'Leitungsverantwortung', 'Überprüfung',
]


def build_is_leitlinie_prompt(projekt: dict[str, Any],
                              assets: list[dict[str, Any]] | None = None) -> str:
    """IS-Leitlinie + Risikoanalyse-Policy (Art. 21(2)a). Kontext: N1-Assets."""
    assets = assets or []
    if assets:
        krit = [a for a in assets if str(a.get('kritikalitaet')) in ('hoch', 'kritisch')]
        asset_block = (
            f"{len(assets)} Assets im Inventar, davon {len(krit)} hoch/kritisch. "
            "Beispiele: "
            + ", ".join(str(a.get('asset_name')) for a in assets[:6]))
    else:
        asset_block = "(Noch kein Asset-Inventar erfasst — Geltungsbereich generisch fassen.)"
    return f"""Erstelle eine **Informationssicherheits-Leitlinie inkl. Risikoanalyse-Policy**
(deutsch) nach NIS2 (Richtlinie (EU) 2022/2555) **Art. 21 Abs. 2 lit. a** für:

**Einrichtung:** {_firma(projekt)}
**Beschreibung:** {projekt.get('beschreibung', '') or '(keine)'}
**Asset-Kontext (N1):** {asset_block}

Pflichtinhalte (alle adressieren, fehlende als „[zu ergänzen]" markieren):
1. Geltungsbereich + Schutzziele (Vertraulichkeit/Integrität/Verfügbarkeit)
2. Sicherheitsziele und Grundsätze der Informationssicherheit
3. Rollen und Verantwortlichkeiten (inkl. ISB/CISO)
4. Methodik der Risikoanalyse (Identifikation, Bewertung, Behandlung)
5. Verantwortung und Verpflichtung der Leitungsorgane (Art. 20 NIS2)
6. Regelmäßige Überprüfung und Aktualisierung der Leitlinie

""" + _DOC_JSON_HINT.format(titel=f"IS-Leitlinie — {_firma(projekt)}")


def parse_is_leitlinie_response(raw: str) -> dict[str, Any]:
    return _parse_doc_response(raw, 'IS-Leitlinie + Risikoanalyse-Policy',
                               _IS_LEITLINIE_PUNKTE)


# ── incident_handling_konzept — Art. 21(2)b ──────────────────────────────────

_INCIDENT_KONZEPT_PUNKTE = [
    'Erkennung', 'Klassifizierung', 'Reaktion', 'Meldepflicht', 'Wiederherstellung',
]


def build_incident_handling_konzept_prompt(projekt: dict[str, Any],
                                           ir: dict[str, Any] | None = None) -> str:
    """Incident-Handling-Konzept (Art. 21(2)b). Kontext: N3-Incident-Response."""
    ir = ir or {}
    csirt = ir.get('csirt_kontakt', '') or '(noch nicht erfasst)'
    sla = (f"Early-Warning {ir.get('early_warning_sla', '24h')}, "
           f"Notification {ir.get('notification_sla', '72h')}, "
           f"Final {ir.get('final_report_sla', '1 Monat')}")
    return f"""Erstelle ein **Konzept zur Behandlung von Sicherheitsvorfällen**
(Incident-Handling, deutsch) nach NIS2 **Art. 21 Abs. 2 lit. b** i.V.m. **Art. 23**
(Meldepflichten) für:

**Einrichtung:** {_firma(projekt)}
**CSIRT-Kontakt (N3):** {csirt}
**Melde-SLAs (N3):** {sla}

Pflichtinhalte:
1. Erkennung und Erfassung von Sicherheitsvorfällen (Detection/Logging)
2. Klassifizierung/Triage (Schweregrad, „erheblicher Sicherheitsvorfall")
3. Reaktion und Eindämmung (Rollen, Eskalationspfad, Playbooks)
4. Meldepflicht-Prozess (24h Frühwarnung / 72h Meldung / 1 Monat Abschluss, Art. 23)
5. Wiederherstellung und Lessons Learned (Post-Incident-Review)

""" + _DOC_JSON_HINT.format(titel=f"Incident-Handling-Konzept — {_firma(projekt)}")


def parse_incident_handling_konzept_response(raw: str) -> dict[str, Any]:
    return _parse_doc_response(raw, 'Incident-Handling-Konzept',
                               _INCIDENT_KONZEPT_PUNKTE)


# ── bcm_dr_plan — BCM/DR/Krisenmanagement (Art. 21(2)c) ───────────────────────

_BCM_PUNKTE = ['Business Impact', 'RPO', 'RTO', 'Wiederanlauf', 'Krisenstab', 'Test']


def build_bcm_dr_plan_prompt(projekt: dict[str, Any],
                             bcp: dict[str, Any] | None = None) -> str:
    """BCM-/DR-/Krisenmanagement-Plan (Art. 21(2)c). Kontext: N5-BCP (RPO/RTO)."""
    bcp = bcp or {}
    rpo = bcp.get('rpo_minuten', 60)
    rto = bcp.get('rto_minuten', 240)
    backup = bcp.get('backup_strategie', '') or '(noch nicht erfasst)'
    dr_standort = bcp.get('dr_standort', '') or '(noch nicht erfasst)'
    return f"""Erstelle einen **Business-Continuity-, Disaster-Recovery- und
Krisenmanagement-Plan** (deutsch) nach NIS2 **Art. 21 Abs. 2 lit. c** für:

**Einrichtung:** {_firma(projekt)}
**RPO (N5):** {rpo} Minuten   **RTO (N5):** {rto} Minuten
**Backup-Strategie (N5):** {backup}
**DR-Standort (N5):** {dr_standort}

Pflichtinhalte:
1. Business-Impact-Analyse (kritische Prozesse + Abhängigkeiten)
2. Recovery-Ziele: RPO/RTO je kritischem Prozess (vorbefüllte Werte einarbeiten)
3. Backup- und Wiederherstellungsstrategie (3-2-1, Tests, Aufbewahrung)
4. Wiederanlauf-/Notbetriebsverfahren (Disaster Recovery)
5. Krisenmanagement und Krisenstab (Rollen, Alarmierung, Kommunikation)
6. Test- und Übungsplan (Frequenz, Auswertung, Verbesserung)

""" + _DOC_JSON_HINT.format(titel=f"BCM-/DR-Plan — {_firma(projekt)}")


def parse_bcm_dr_plan_response(raw: str) -> dict[str, Any]:
    return _parse_doc_response(raw, 'BCM-/DR-/Krisenmanagement-Plan', _BCM_PUNKTE)


# ── lieferketten_richtlinie — Art. 21(2)d ────────────────────────────────────

_LIEFERKETTE_PUNKTE = [
    'Lieferanten', 'Kritikalität', 'Anforderungen', 'Bewertung', 'Vertrag', 'Monitoring',
]


def build_lieferketten_richtlinie_prompt(projekt: dict[str, Any],
                                         vendors: list[dict[str, Any]] | None = None) -> str:
    """Lieferketten-Sicherheitsrichtlinie (Art. 21(2)d). Kontext: N4-Vendoren."""
    vendors = vendors or []
    if vendors:
        krit = [v for v in vendors if str(v.get('kritikalitaet')) in ('hoch', 'kritisch')]
        vendor_block = (
            f"{len(vendors)} erfasste Lieferanten, davon {len(krit)} hoch/kritisch. "
            "Beispiele: "
            + ", ".join(f"{v.get('vendor_name')} ({v.get('leistung', '')})"
                        for v in vendors[:6]))
    else:
        vendor_block = "(Noch keine Lieferanten in N4 erfasst — Richtlinie generisch fassen.)"
    return f"""Erstelle eine **Lieferketten-Sicherheitsrichtlinie** (deutsch) nach
NIS2 **Art. 21 Abs. 2 lit. d** (Sicherheit der Lieferkette) für:

**Einrichtung:** {_firma(projekt)}
**Lieferanten-Kontext (N4):** {vendor_block}

Pflichtinhalte:
1. Identifikation und Inventarisierung von Lieferanten/Dienstleistern
2. Kritikalitäts-Einstufung (Tiering) der Lieferanten
3. Sicherheitsanforderungen an Lieferanten (ISO 27001, SBOM, Patch-SLAs)
4. Bewertungs-/Auditprozess (Onboarding + periodische Re-Assessments)
5. Vertragliche Vorgaben (Meldepflichten, Audit-Rechte, DPA/SLA)
6. Laufendes Monitoring und Offboarding

""" + _DOC_JSON_HINT.format(titel=f"Lieferketten-Sicherheitsrichtlinie — {_firma(projekt)}")


def parse_lieferketten_richtlinie_response(raw: str) -> dict[str, Any]:
    return _parse_doc_response(raw, 'Lieferketten-Sicherheitsrichtlinie',
                               _LIEFERKETTE_PUNKTE)


# ── krypto_richtlinie — Art. 21(2)h ──────────────────────────────────────────

_KRYPTO_PUNKTE = [
    'Geltungsbereich', 'Algorithmen', 'Schlüsselverwaltung', 'Transport',
    'Speicher', 'Verantwortlich',
]


def build_krypto_richtlinie_prompt(projekt: dict[str, Any]) -> str:
    """Krypto-/Verschlüsselungsrichtlinie (Art. 21(2)h)."""
    return f"""Erstelle eine **Krypto-/Verschlüsselungsrichtlinie** (deutsch) nach
NIS2 **Art. 21 Abs. 2 lit. h** (Kryptografie und ggf. Verschlüsselung) für:

**Einrichtung:** {_firma(projekt)}
**Beschreibung:** {projekt.get('beschreibung', '') or '(keine)'}

Pflichtinhalte (orientiert an BSI TR-02102 / Stand der Technik):
1. Geltungsbereich + Schutzklassen der Daten
2. Zugelassene Algorithmen und Mindest-Schlüssellängen (AES-256, RSA-3072/ECC, TLS 1.3)
3. Schlüsselverwaltung (Lebenszyklus, Rotation, Hinterlegung, HSM)
4. Transportverschlüsselung (TLS, VPN, sichere Protokolle)
5. Speicherverschlüsselung (At-Rest, Datenträger, Backups)
6. Rollen/Verantwortlichkeiten + Ausnahmen-/Überprüfungsprozess

""" + _DOC_JSON_HINT.format(titel=f"Krypto-/Verschlüsselungsrichtlinie — {_firma(projekt)}")


def parse_krypto_richtlinie_response(raw: str) -> dict[str, Any]:
    return _parse_doc_response(raw, 'Krypto-/Verschlüsselungsrichtlinie',
                               _KRYPTO_PUNKTE)


# ── zugriffskontroll_policy — Art. 21(2)i/j ──────────────────────────────────

_ZUGRIFF_PUNKTE = [
    'Asset-Management', 'Rollen', 'Least Privilege', 'MFA', 'Review', 'Protokollierung',
]


def build_zugriffskontroll_policy_prompt(projekt: dict[str, Any],
                                         assets: list[dict[str, Any]] | None = None) -> str:
    """Zugriffskontroll-/Asset-Management-Policy (Art. 21(2)i/j). Kontext: N1."""
    assets = assets or []
    if assets:
        asset_block = (
            f"{len(assets)} Assets im Inventar. Schützenswerte Beispiele: "
            + ", ".join(str(a.get('asset_name')) for a in assets[:6]))
    else:
        asset_block = "(Noch kein Asset-Inventar erfasst — Policy generisch fassen.)"
    return f"""Erstelle eine **Zugriffskontroll- und Asset-Management-Policy** (deutsch)
nach NIS2 **Art. 21 Abs. 2 lit. i und j** (Zugriffskontrolle, Asset-Management,
MFA/sichere Authentisierung) für:

**Einrichtung:** {_firma(projekt)}
**Asset-Kontext (N1):** {asset_block}

Pflichtinhalte:
1. Asset-Management (Inventarisierung, Klassifizierung, Eigentümer)
2. Rollen-/Rechtekonzept (RBAC, Need-to-know, Funktionstrennung)
3. Least-Privilege + Privileged-Access-Management (PAM)
4. Authentisierung: MFA, Passwort-/Secrets-Vorgaben, sichere Kommunikation
5. Periodische Rezertifizierung der Berechtigungen (Access Review)
6. Protokollierung und Überwachung der Zugriffe (Logging/Monitoring)

""" + _DOC_JSON_HINT.format(titel=f"Zugriffskontroll-/Asset-Management-Policy — {_firma(projekt)}")


def parse_zugriffskontroll_policy_response(raw: str) -> dict[str, Any]:
    return _parse_doc_response(raw, 'Zugriffskontroll-/Asset-Management-Policy',
                               _ZUGRIFF_PUNKTE)


# ─────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────

def _extract_json_array(raw: str) -> list[Any]:
    """Robustes Parsen eines JSON-Arrays (Fences/Prosa tolerieren)."""
    if not raw:
        return []
    text = raw.strip()
    for marker in ('```json', '```'):
        if marker in text:
            parts = text.split(marker)
            if len(parts) >= 2:
                text = parts[1].split('```')[0] if marker == '```json' else parts[1]
                break
    a_start, a_end = text.find('['), text.rfind(']')
    if a_start >= 0 and a_end > a_start:
        try:
            data = json.loads(text[a_start:a_end + 1])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    return []


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
