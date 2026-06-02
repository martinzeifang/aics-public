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
- Betroffene Personen/Kunden: {incident.get('affected_subjects', '')}
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
