"""AI Act Phase B — KI-Wizards (Issue #583).

A6 Risk-Tier-Klassifikator (Annex III)
A7 Use-Case-Templates (Kreditscoring/HR/Biometrie/Bildung)
A8 EU-Konformitätserklärung-Generator (Annex V)
A9 Transparenz-Hinweis-Generator (Art. 50)
"""
from __future__ import annotations

import json
from typing import Any


# ─────────────────────────────────────────────────────────────────────────
# A6 — Risk-Tier-Klassifikator
# ─────────────────────────────────────────────────────────────────────────

AIACT_TIERS = ['prohibited', 'high-risk', 'limited-risk', 'minimal-risk']

_TIER_SYNONYMS = {
    'prohibited': 'prohibited', 'verboten': 'prohibited',
    'high-risk': 'high-risk', 'hoch-risiko': 'high-risk', 'high': 'high-risk',
    'annex iii': 'high-risk',
    'limited-risk': 'limited-risk', 'begrenztes-risiko': 'limited-risk', 'limited': 'limited-risk',
    'minimal-risk': 'minimal-risk', 'minimales-risiko': 'minimal-risk', 'minimal': 'minimal-risk',
    'none': 'minimal-risk',
}


def _normalize_tier(value: str) -> str:
    return _TIER_SYNONYMS.get((value or '').strip().lower(), 'minimal-risk')


def build_risk_tier_prompt(projekt: dict[str, Any]) -> str:
    return f"""Du bist ein AI-Act-Experte (EU-Verordnung 2024/1689).

Klassifiziere das folgende KI-System nach AI Act Risikoklassen:

**System:** {projekt.get('name', '')}
**Anbieter:** {projekt.get('organisation', '')}
**Produkt:** {projekt.get('produkt', '')}
**Beschreibung:** {projekt.get('beschreibung', '')}

AI Act unterscheidet 4 Klassen:

- **prohibited** (verboten, Art. 5): Social Scoring durch Behörden, manipulative Techniken
  bei Schwachen, biometrische Echtzeit-Fernidentifikation in öffentlich zugänglichen
  Räumen (Ausnahmen für Strafverfolgung), Emotion-Recognition am Arbeitsplatz/Schulen,
  ungezielte Scraping von Gesichtsbildern → **NICHT ERLAUBT**

- **high-risk** (Hoch-Risiko, Annex III): Kreditscoring, HR-Recruiting/Personalentscheidungen,
  Bildung (Prüfungsbewertung/Zulassung), biometrische Kategorisierung, kritische
  Infrastruktur, Strafverfolgung, Migration/Asyl, Justizverwaltung, demokratische
  Prozesse → strenge Pflichten (Art. 9-15)

- **limited-risk** (Begrenztes Risiko, Art. 50): Chatbots, Deepfakes, generative KI
  → Transparenzpflicht (Nutzer muss wissen, dass er mit KI interagiert)

- **minimal-risk** (Minimales Risiko): Alles andere (Empfehlungssysteme, Spam-Filter,
  Spiele) → freiwillige Codes of Conduct

Antworte **ausschließlich** als JSON:
```json
{{
  "tier": "prohibited|high-risk|limited-risk|minimal-risk",
  "annex_iii_kategorie": "z.B. 'Bildung & berufliche Bildung' oder 'n/a'",
  "begruendung": "2-3 Sätze unter Bezug auf konkrete Artikel/Annex",
  "konfidenz": "hoch|mittel|niedrig",
  "transparenzpflicht": true|false,
  "konformitaetsbewertung": "Self-Assessment|Notified-Body|nicht-erforderlich"
}}
```
"""


def parse_risk_tier_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'tier': _normalize_tier(data.get('tier', 'minimal-risk')),
        'annex_iii_kategorie': data.get('annex_iii_kategorie', ''),
        'begruendung': data.get('begruendung', ''),
        'konfidenz': data.get('konfidenz', 'mittel'),
        'transparenzpflicht': bool(data.get('transparenzpflicht', False)),
        'konformitaetsbewertung': data.get('konformitaetsbewertung', 'Self-Assessment'),
    }


# ─────────────────────────────────────────────────────────────────────────
# A7 — Use-Case-Templates
# ─────────────────────────────────────────────────────────────────────────

USE_CASE_TEMPLATES = {
    'kreditscoring': {
        'name': 'Kreditscoring / Bonitätsbewertung',
        'tier': 'high-risk',
        'annex_iii_kategorie': 'Zugang zu wesentlichen privaten Diensten',
        'pflicht_defaults': {
            'oversight_mode': 'human-in-the-loop',
            'serious_incident_reporting_sla': '15 Tage',
            'bias_focus': 'Demografische Fairness (Alter, Geschlecht, Herkunft)',
        },
        'hinweise': 'Erklärbarkeit zwingend für Ablehnungen. Recht auf manuelle Prüfung.',
    },
    'hr-recruiting': {
        'name': 'HR / Recruiting / Personalentscheidungen',
        'tier': 'high-risk',
        'annex_iii_kategorie': 'Beschäftigung, Personalverwaltung',
        'pflicht_defaults': {
            'oversight_mode': 'human-in-the-loop',
            'bias_focus': 'Geschlecht, Alter, Herkunft, Behinderung',
        },
        'hinweise': 'Kein Auto-Reject. CV-Screening nur als Vorfilter, finale Entscheidung Mensch.',
    },
    'biometrie': {
        'name': 'Biometrische Identifikation / Kategorisierung',
        'tier': 'high-risk',
        'annex_iii_kategorie': 'Biometrie',
        'pflicht_defaults': {
            'oversight_mode': 'human-in-command',
            'bias_focus': 'Demografische Gruppen (False-Positive/Negative)',
        },
        'hinweise': 'Echtzeit-Fernidentifikation in öffentlichen Räumen meist verboten (Art. 5).',
    },
    'bildung': {
        'name': 'Bildung / Prüfungsbewertung / Zulassung',
        'tier': 'high-risk',
        'annex_iii_kategorie': 'Bildung & berufliche Bildung',
        'pflicht_defaults': {
            'oversight_mode': 'human-in-the-loop',
            'bias_focus': 'Soziale Herkunft, Sprache, Behinderung',
        },
        'hinweise': 'Lehrer/Prüfer behält Letztentscheidung. Schüler/Studenten müssen informiert sein.',
    },
    'chatbot-llm': {
        'name': 'Chatbot / LLM / generative KI',
        'tier': 'limited-risk',
        'annex_iii_kategorie': 'n/a',
        'pflicht_defaults': {
            'oversight_mode': 'on-the-loop',
            'serious_incident_reporting_sla': '15 Tage',
        },
        'hinweise': 'Transparenzpflicht (Art. 50): Nutzer muss wissen, dass er mit KI spricht. '
                   'Deepfake-Output muss als KI-generiert markiert werden.',
    },
}


def list_use_case_templates() -> list[dict[str, Any]]:
    return [{'id': k, **v} for k, v in USE_CASE_TEMPLATES.items()]


def get_use_case_template(uc_id: str) -> dict[str, Any] | None:
    t = USE_CASE_TEMPLATES.get(uc_id)
    return {'id': uc_id, **t} if t else None


# ─────────────────────────────────────────────────────────────────────────
# A8 — EU-Konformitätserklärung (Annex V)
# ─────────────────────────────────────────────────────────────────────────

def build_eu_doc_prompt(projekt: dict[str, Any], system_doku: dict[str, Any], tier: str = 'high-risk') -> str:
    return f"""Erstelle eine EU-Konformitätserklärung (EU Declaration of Conformity) nach AI Act Annex V (deutsch).

**System:** {projekt.get('name', '')}
**Anbieter:** {projekt.get('organisation', '')} ({projekt.get('produkt', '')})
**System-Doku:**
- System-Name: {system_doku.get('system_name', '(nicht gesetzt)')}
- Version: {system_doku.get('version', '(nicht gesetzt)')}
- Intended Purpose: {system_doku.get('intended_purpose', '(nicht gesetzt)')}
- Architektur: {system_doku.get('architecture', '(nicht gesetzt)')}
**Risk-Tier:** {tier}

Annex V verlangt folgende Pflicht-Felder:
1. Name/Anschrift des Anbieters + EU-Bevollmächtigter (falls außerhalb EU)
2. Eindeutige System-ID (Produktcode/Version)
3. Erklärung: "Diese DOC wird unter alleiniger Verantwortung des Anbieters ausgestellt"
4. System ist in Übereinstimmung mit:
   - Verordnung (EU) 2024/1689 (AI Act)
   - ggf. weitere Unionsrechtsakte (Aufzählen)
5. Angewandte harmonisierte Normen (z.B. ISO/IEC 23894, ISO/IEC 42001)
6. Name der Notified Body (falls High-Risk + Modul B+C-Konformitätsbewertung)
7. Datum + Ort der Ausstellung, Unterschriftszeile

Antworte **ausschließlich** als JSON:
```json
{{
  "titel": "EU-Konformitätserklärung — <System-Name>",
  "doc_text": "Vollständiger Markdown-Text der DOC nach Annex V",
  "angewandte_normen": ["ISO/IEC 23894", "ISO/IEC 42001"],
  "konformitaetsbewertung_modul": "Self-Assessment|Modul-A|Modul-B+C|Modul-H",
  "notified_body_pflicht": true|false
}}
```
"""


def parse_eu_doc_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'titel': data.get('titel', 'EU-Konformitätserklärung'),
        'doc_text': data.get('doc_text', ''),
        'angewandte_normen': data.get('angewandte_normen', []) or [],
        'konformitaetsbewertung_modul': data.get('konformitaetsbewertung_modul', 'Self-Assessment'),
        'notified_body_pflicht': bool(data.get('notified_body_pflicht', False)),
    }


# ─────────────────────────────────────────────────────────────────────────
# A9 — Transparenz-Hinweis-Generator (Art. 50)
# ─────────────────────────────────────────────────────────────────────────

def build_transparency_prompt(projekt: dict[str, Any], system_doku: dict[str, Any]) -> str:
    return f"""Erstelle Transparenz-Hinweis-Texte nach AI Act Art. 50 (deutsch).

**System:** {projekt.get('name', '')}
**Anbieter:** {projekt.get('organisation', '')}
**Intended Purpose:** {system_doku.get('intended_purpose', '(nicht gesetzt)')}
**Architektur:** {system_doku.get('architecture', '(nicht gesetzt)')}

Art. 50 verlangt folgende Hinweise an Endnutzer:
1. **Chatbot-Hinweis**: Nutzer muss wissen, dass er mit KI interagiert (außer wenn offensichtlich)
2. **AI-generierter-Inhalt-Marker**: Output muss als KI-generiert erkennbar sein
3. **Deepfake-Markierung**: Bild/Video/Audio von realen Personen muss gekennzeichnet sein
4. **Emotion-Recognition-Disclosure**: falls solche Funktion vorhanden
5. **Biometrische-Kategorisierung-Disclosure**

Generiere für jeden zutreffenden Punkt einen User-Facing-Text + technischen Vorschlag wo der Hinweis platziert wird (UI-Element).

Antworte **ausschließlich** als JSON:
```json
{{
  "chatbot_hinweis": {{
    "user_text": "Sie chatten gerade mit einer KI. Antworten können fehlerhaft sein.",
    "platzierung": "Banner über Chatfenster + persistent in Header"
  }},
  "ai_content_marker": {{
    "user_text": "Diese Antwort wurde von einer KI generiert.",
    "platzierung": "Sichtbar unter jeder generierten Nachricht"
  }},
  "deepfake_marker": {{
    "user_text": "...",
    "platzierung": "Watermark + Metadaten + UI-Hinweis"
  }},
  "emotion_recognition_disclosure": null,
  "biometric_categorization_disclosure": null,
  "uebersicht_url_vorschlag": "z.B. /transparenz oder Impressum-Anhang"
}}
```
Setze nicht zutreffende Felder auf null.
"""


def parse_transparency_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'chatbot_hinweis': data.get('chatbot_hinweis'),
        'ai_content_marker': data.get('ai_content_marker'),
        'deepfake_marker': data.get('deepfake_marker'),
        'emotion_recognition_disclosure': data.get('emotion_recognition_disclosure'),
        'biometric_categorization_disclosure': data.get('biometric_categorization_disclosure'),
        'uebersicht_url_vorschlag': data.get('uebersicht_url_vorschlag', '/transparenz'),
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
