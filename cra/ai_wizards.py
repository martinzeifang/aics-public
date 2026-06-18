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
# C10 — EU-Konformitätserklärung (Annex V, Art. 28) — #1237
# ─────────────────────────────────────────────────────────────────────────

# Produktklassen, die eine Beteiligung einer notifizierten Stelle (Notified
# Body) verlangen können (Annex III Klasse I/II, Annex IV kritisch).
_NB_PFLICHT_KLASSEN = {"important_i", "important_ii", "critical"}


def _klasse_label(klasse: str) -> str:
    return {
        "default": "Standard (nicht in Annex III/IV gelistet)",
        "important_i": "Annex III Klasse I (Wichtig Klasse 1)",
        "important_ii": "Annex III Klasse II (Wichtig Klasse 2)",
        "critical": "Annex IV (Kritisch)",
    }.get(klasse, klasse)


def build_konformitaetserklaerung_prompt(projekt: dict[str, Any],
                                         konformitaet: dict[str, Any] | None = None,
                                         normen: list[str] | None = None) -> str:
    """Annex-V-DoC-Prompt (Copy/Paste). Vorbefüllung aus Projekt-/Konformitäts-
    Stammdaten (#1201) + angewandten Normen. Kein API-Call."""
    konformitaet = konformitaet or {}
    klasse = projekt.get('produktklasse', 'default') or 'default'
    nb_pflicht = klasse in _NB_PFLICHT_KLASSEN
    norm_liste = ", ".join(normen or []) or "(noch nicht erfasst)"
    weg = konformitaet.get('bewertungsweg', '(noch nicht gewählt)')
    nb_nr = konformitaet.get('nb_kennnummer', '') or "(noch nicht erfasst)"
    return f"""Erstelle eine EU-Konformitätserklärung (EU Declaration of Conformity) nach
CRA (VO 2024/2847) **Annex V** i.V.m. Art. 28 (deutsch).

**Produkt:** {projekt.get('name', '')}
**Hersteller:** {projekt.get('unternehmen', '')}
**Produktbeschreibung:** {projekt.get('beschreibung', '')}
**CRA-Produktklasse:** {_klasse_label(klasse)}
**Konformitätsbewertungsweg (Annex VIII):** {weg}
**Notified-Body-Kennnummer:** {nb_nr}
**Angewandte harmonisierte Normen/Spezifikationen:** {norm_liste}

Annex V verlangt folgende **Pflicht-Felder** (alle ausfüllen, fehlende als
„[zu ergänzen]" markieren):
1. Name und Anschrift des Herstellers (ggf. EU-Bevollmächtigter)
2. Eindeutige Produktidentifikation (Name/Typ/Charge/Version)
3. Erklärung: „Diese EU-Konformitätserklärung wird unter alleiniger Verantwortung
   des Herstellers ausgestellt."
4. Gegenstand der Erklärung (Produktbeschreibung zur Rückverfolgbarkeit)
5. Erklärung, dass der Gegenstand die einschlägigen Harmonisierungsrechtsvorschriften
   der Union erfüllt — insb. die **Verordnung (EU) 2024/2847 (CRA)**; ggf. weitere
   Rechtsakte auflisten (eine einzige Erklärung bei mehreren Rechtsakten)
6. Verweis auf die angewandten **harmonisierten Normen** oder Spezifikationen
7. Falls erforderlich (Annex III/IV): Name/Kennnummer der **notifizierten Stelle**
   und durchgeführtes Konformitätsbewertungsverfahren{"" if nb_pflicht else " — bei dieser Klasse i.d.R. nicht erforderlich (Selbstbewertung)"}
8. Ort und Datum der Ausstellung, Name/Funktion + Unterschriftszeile

Antworte **ausschließlich** als JSON in genau diesem Schema:
```json
{{
  "titel": "EU-Konformitätserklärung — <Produkt>",
  "doc_text": "Vollständiger Markdown-Text der DoC nach Annex V (alle 8 Punkte)",
  "produkt_identifikation": "Name/Typ/Version",
  "angewandte_normen": ["..."],
  "konformitaetsbewertung_modul": "Modul A|Modul B+C|Modul H|EUCC",
  "notified_body_pflicht": {str(nb_pflicht).lower()},
  "notified_body_kennnummer": "Kennnummer oder leer",
  "fehlende_pflichtfelder": ["Liste der noch zu ergänzenden Annex-V-Felder"]
}}
```
"""


def parse_konformitaetserklaerung_response(raw: str,
                                           projekt: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parsed Annex-V-DoC-Antwort + ergänzt serverseitige Plausibilitätshinweise."""
    data = _extract_json(raw)
    klasse = (projekt or {}).get('produktklasse', 'default') or 'default'
    nb_pflicht = klasse in _NB_PFLICHT_KLASSEN
    normen = data.get('angewandte_normen', []) or []
    fehlend = list(data.get('fehlende_pflichtfelder', []) or [])

    # Serverseitige Plausibilitätsprüfung (additiv zu ChatGPT-Selbstauskunft).
    hinweise: list[str] = []
    if not (projekt or {}).get('unternehmen'):
        hinweise.append("Herstellername fehlt (Annex V Pkt. 1).")
    if not data.get('produkt_identifikation'):
        hinweise.append("Eindeutige Produktidentifikation fehlt (Annex V Pkt. 2).")
    if not normen:
        hinweise.append("Keine angewandten Normen angegeben (Annex V Pkt. 6).")
    if nb_pflicht and not data.get('notified_body_kennnummer'):
        hinweise.append(
            f"Produktklasse {_klasse_label(klasse)} — Kennnummer der notifizierten "
            "Stelle erforderlich (Annex V Pkt. 7).")

    return {
        'titel': data.get('titel', 'EU-Konformitätserklärung (Annex V)'),
        'doc_text': data.get('doc_text', ''),
        'produkt_identifikation': data.get('produkt_identifikation', ''),
        'angewandte_normen': normen,
        'konformitaetsbewertung_modul': data.get('konformitaetsbewertung_modul', 'Modul A'),
        'notified_body_pflicht': bool(data.get('notified_body_pflicht', nb_pflicht)),
        'notified_body_kennnummer': data.get('notified_body_kennnummer', ''),
        'fehlende_pflichtfelder': fehlend,
        'plausibilitaet_hinweise': hinweise,
    }


# ─────────────────────────────────────────────────────────────────────────
# C11 — SBOM-Begleitdokument (Annex I Teil II) — #1239
# ─────────────────────────────────────────────────────────────────────────

def build_sbom_begleitdoc_prompt(projekt: dict[str, Any],
                                 sboms: list[dict[str, Any]] | None = None) -> str:
    """SBOM-Begleitdokument-Prompt (Copy/Paste). Vorbefüllung aus C1-SBOM-
    Verzeichnis (`cra_sbom`); funktioniert auch ohne SBOM-Daten."""
    sboms = sboms or []
    if sboms:
        zeilen = []
        lizenzen_gesamt: set[str] = set()
        for s in sboms:
            lz = s.get('lizenzen') or []
            if isinstance(lz, list):
                lizenzen_gesamt.update(str(x) for x in lz)
            zeilen.append(
                f"- Release {s.get('release_version', '?')}: Format "
                f"{str(s.get('sbom_format', 'spdx')).upper()}, "
                f"{s.get('komponenten_count', 0)} Komponenten, "
                f"Quelle: {s.get('quelle', '(manuell)')}")
        sbom_block = "\n".join(zeilen)
        lizenz_block = ", ".join(sorted(lizenzen_gesamt)) or "(nicht erfasst)"
    else:
        sbom_block = ("(Noch kein SBOM im C1-Verzeichnis erfasst — bitte Geltungsbereich, "
                      "Format und Komponenten manuell beschreiben.)")
        lizenz_block = "(nicht erfasst)"
    return f"""Erstelle ein CRA-konformes **SBOM-Begleitdokument** (deutsch) nach
CRA (VO 2024/2847) **Annex I Teil II** (Schwachstellenbehandlung) i.V.m. Annex VII.

**Produkt:** {projekt.get('name', '')}
**Hersteller:** {projekt.get('unternehmen', '')}
**Vorhandene SBOM-Stände (C1-Verzeichnis):**
{sbom_block}
**Erfasste Lizenzen:** {lizenz_block}

Das Begleitdokument ordnet die SBOM ein und beschreibt:
1. Zweck und Geltungsbereich der SBOM (welche Releases/Komponenten abgedeckt sind)
2. SBOM-Format und -Standard (SPDX / CycloneDX) + Versionsstand
3. Tiefe (Top-Level- vs. transitive Abhängigkeiten)
4. Aktualisierungszyklus/-politik (wann wird die SBOM neu erzeugt)
5. Komponenten- und Lizenzübersicht (inkl. Umgang mit kritischen Lizenzen)
6. Bezug zur Schwachstellenbehandlung (Annex I Teil II): Monitoring, CVE-Mapping,
   Sicherheitsupdates für Drittkomponenten
7. Bezugsquelle/Verteilung der SBOM für Nutzer und Marktaufsicht

Antworte **ausschließlich** als JSON:
```json
{{
  "titel": "SBOM-Begleitdokument — <Produkt>",
  "doc_text": "Vollständiger Markdown-Text des Begleitdokuments (Punkte 1-7)",
  "sbom_format": "SPDX|CycloneDX|gemischt",
  "geltungsbereich": "Kurzbeschreibung des abgedeckten Umfangs",
  "aktualisierungszyklus": "z.B. je Release / monatlich / bei jedem Build",
  "bezug_schwachstellenbehandlung": "Wie die SBOM in das PSIRT/CVE-Monitoring einfließt"
}}
```
"""


def parse_sbom_begleitdoc_response(raw: str) -> dict[str, Any]:
    data = _extract_json(raw)
    return {
        'titel': data.get('titel', 'SBOM-Begleitdokument'),
        'doc_text': data.get('doc_text', ''),
        'sbom_format': data.get('sbom_format', 'SPDX'),
        'geltungsbereich': data.get('geltungsbereich', ''),
        'aktualisierungszyklus': data.get('aktualisierungszyklus', 'je Release'),
        'bezug_schwachstellenbehandlung': data.get('bezug_schwachstellenbehandlung', ''),
    }


# ─────────────────────────────────────────────────────────────────────────
# Versions-Änderungen zusammenfassen (#1249)
# Aufbau auf dem Repo-Import (#1248): rohe Commits/PRs/Changelog → kompakte
# „Wesentliche Änderungen je Version"-Liste für DoC (Annex V) + Tech-Doku (Annex VII).
# ─────────────────────────────────────────────────────────────────────────

# Stichworte, die typischerweise auf eine CRA-/security-relevante (ggf.
# „wesentliche") Änderung hindeuten — als Hinweis im Prompt + Heuristik-Markierung.
_CRA_RELEVANT_HINTS = (
    'auth', 'login', 'passwort', 'password', 'token', 'oauth', 'session',
    'crypto', 'krypto', 'tls', 'ssl', 'cipher', 'encrypt', 'hash', 'signatur',
    'cve', 'vuln', 'security', 'sicherheit', 'xss', 'sqli', 'injection',
    'permission', 'berechtigung', 'rbac', 'privilege', 'sandbox',
    'network', 'netzwerk', 'port', 'endpoint', 'api', 'interface', 'schnittstelle',
    'dependency', 'dependencies', 'abhängigkeit', 'upgrade', 'bump', 'sbom',
    'update', 'patch', 'firmware', 'boot', 'secret',
)


def _changes_block(changes: dict[str, Any] | None) -> str:
    """Rohe Änderungsliste (#1248-Format) als kompakten Prompt-Text rendern.
    Funktioniert auch mit manuell eingefügtem Freitext (Fallback ohne Repo)."""
    changes = changes or {}
    commits = changes.get('commits') or []
    files = changes.get('changed_files') or []
    changelog = str(changes.get('changelog') or '').strip()
    zeilen: list[str] = []
    for c in commits[:200]:
        if isinstance(c, dict):
            msg = str(c.get('message') or '').strip().splitlines()[0:1]
            zeilen.append(f"- {msg[0] if msg else ''} ({c.get('sha', '')})")
        else:
            zeilen.append(f"- {str(c).strip()}")
    commit_block = "\n".join(zeilen) or "(keine Commits übermittelt)"
    file_block = ", ".join(str(f) for f in files[:80]) or "(keine Dateiliste)"
    out = f"**Commits / PR-Titel:**\n{commit_block}\n\n**Geänderte Dateien:** {file_block}"
    if changelog:
        out += f"\n\n**CHANGELOG-Auszug:**\n{changelog[:4000]}"
    return out


def build_version_changes_prompt(changes: dict[str, Any] | None,
                                 base: str = '', head: str = '',
                                 projekt: dict[str, Any] | None = None) -> str:
    """Prompt (Copy/Paste) für die Verdichtung der Versions-Änderungen (#1249).

    Erzeugt eine kompakte „Wesentliche Änderungen"-Liste, markiert CRA-/security-
    relevante Punkte und gibt einen Hinweis „mögliche wesentliche Änderung →
    Konformität prüfen". Input = strukturierte Liste aus dem Import (#1248) oder
    manuell eingefügter Freitext (Fallback)."""
    projekt = projekt or {}
    spanne = f"{base or '?'} → {head or '?'}"
    return f"""Du bist ein CRA-Experte (EU Cyber Resilience Act, VO 2024/2847).

Fasse die folgenden Repository-Änderungen einer Produktversion zu einer prägnanten
**„Wesentliche Änderungen"**-Liste zusammen. Hebe **CRA-/security-relevante**
Änderungen hervor (z. B. neue Netzwerk-Schnittstellen, Krypto-/Auth-Änderungen,
neue Abhängigkeiten, Schwachstellen-Fixes). Eine **wesentliche Änderung**
(„substantial modification") kann eine erneute Konformitätsbewertung auslösen —
markiere solche Kandidaten ausdrücklich.

**Produkt:** {projekt.get('name', '')}
**Hersteller:** {projekt.get('unternehmen', '')}
**Versions-Spanne:** {spanne}

{_changes_block(changes)}

Antworte **ausschließlich** als JSON in genau diesem Schema:
```json
{{
  "version": "{head or ''}",
  "zusammenfassung": "1-3 Sätze Gesamteinordnung der Version",
  "aenderungen": [
    {{
      "titel": "Kurztitel der Änderung",
      "beschreibung": "1-2 Sätze",
      "cra_relevant": true,
      "moegliche_wesentliche_aenderung": false,
      "kategorie": "security|feature|fix|dependency|sonstiges"
    }}
  ],
  "konformitaet_pruefen": false,
  "hinweis": "Begründung, falls eine Konformitätsprüfung empfohlen wird"
}}
```
"""


def parse_version_changes_response(raw: str) -> dict[str, Any]:
    """Parsed die Versions-Zusammenfassung + härtet die Markierungen serverseitig
    (Heuristik markiert security-Stichworte zusätzlich, falls ChatGPT sie übersieht)."""
    data = _extract_json(raw)
    aenderungen_in = data.get('aenderungen') or []
    aenderungen: list[dict[str, Any]] = []
    konformitaet_pruefen = bool(data.get('konformitaet_pruefen', False))
    for a in aenderungen_in:
        if not isinstance(a, dict):
            a = {'titel': str(a), 'beschreibung': ''}
        text = f"{a.get('titel', '')} {a.get('beschreibung', '')}".lower()
        heur = any(h in text for h in _CRA_RELEVANT_HINTS)
        cra_relevant = bool(a.get('cra_relevant', False)) or heur
        wesentlich = bool(a.get('moegliche_wesentliche_aenderung', False))
        if wesentlich:
            konformitaet_pruefen = True
        aenderungen.append({
            'titel': str(a.get('titel', '')),
            'beschreibung': str(a.get('beschreibung', '')),
            'cra_relevant': cra_relevant,
            'moegliche_wesentliche_aenderung': wesentlich,
            'kategorie': str(a.get('kategorie', 'sonstiges')),
        })
    return {
        'version': str(data.get('version', '')),
        'zusammenfassung': str(data.get('zusammenfassung', '')),
        'aenderungen': aenderungen,
        'konformitaet_pruefen': konformitaet_pruefen,
        'hinweis': str(data.get('hinweis', '')),
    }


def version_changes_to_markdown(parsed: dict[str, Any]) -> str:
    """Geparstes Ergebnis als Markdown-Abschnitt „Wesentliche Änderungen" rendern —
    zum Übernehmen in Konformitätserklärung (#1237) / technische Doku (#1236)."""
    version = parsed.get('version') or ''
    lines = [f"## Wesentliche Änderungen{f' — Version {version}' if version else ''}", ""]
    if parsed.get('zusammenfassung'):
        lines += [parsed['zusammenfassung'], ""]
    for a in parsed.get('aenderungen') or []:
        marker = ''
        if a.get('moegliche_wesentliche_aenderung'):
            marker = ' ⚠️ **mögliche wesentliche Änderung — Konformität prüfen**'
        elif a.get('cra_relevant'):
            marker = ' 🔒 *CRA-/security-relevant*'
        titel = a.get('titel') or '(ohne Titel)'
        beschreibung = a.get('beschreibung') or ''
        lines.append(f"- **{titel}**{marker}" + (f": {beschreibung}" if beschreibung else ''))
    if parsed.get('konformitaet_pruefen'):
        # Hinweis außerhalb des f-Strings bauen (mehrzeilige f-String-Ausdrücke
        # sind erst ab Python 3.12 / PEP 701 erlaubt; Prod läuft auf 3.11).
        _hinweis = parsed.get('hinweis') or (
            'Diese Version enthält mögliche wesentliche Änderungen — '
            'Konformitätsbewertung prüfen.')
        lines += ["", f"> ⚠️ {_hinweis}"]
    return "\n".join(lines)


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
