"""SOC-AI-Alarmanalyse — zweigleisig: konfigurierter KI-Provider + Copy/Paste-Prompt.

Der KI-Aufruf respektiert ``ai.provider`` (#1342): on_prem (lokales Ollama, Default —
sensible Alarmdaten bleiben im Haus) ODER cloud (CloudProvider, nur bei expliziter
``allow_data_egress``-Freigabe, mit Redaction + Audit). Der Copy/Paste-Pfad erzeugt
denselben Prompt zum Einfügen in ChatGPT o.ä. und parst die JSON-Antwort.
"""
from __future__ import annotations

import json
from typing import Any

PROMPT_INTRO = (
    "Du bist erfahrene:r SOC-Analyst:in. Analysiere den folgenden Wazuh-Sicherheitsalarm. "
    "Beurteile, was er bedeutet, ob es sich um einen False Positive handelt und welche Reaktion "
    "angemessen ist. Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in genau diesem Schema:"
)

JSON_SCHEMA = (
    "{\n"
    '  "zusammenfassung": "1-2 Sätze, was hier passiert",\n'
    '  "severity": "low | medium | high | critical",\n'
    '  "prioritaet": 1,\n'
    '  "false_positive_wahrscheinlichkeit": "low | medium | high",\n'
    '  "empfohlene_aktion": "investigate | monitor | contain | false-positive",\n'
    '  "begruendung": "kurze Begründung",\n'
    '  "mitre": ["Txxxx"],\n'
    '  "personenbezug_moeglich": false,\n'
    '  "meldepflicht_pruefen": ["dsgvo", "nis2", "cra", "aiact"],\n'
    '  "naechste_schritte": ["..."]\n'
    "}"
)


def build_alert_prompt(alert: dict[str, Any]) -> str:
    """Markdown-Prompt aus einem SOC-Alarm-Dict (siehe soc.db.get_alert)."""
    mitre = alert.get("mitre", {}) or {}
    lines = [
        PROMPT_INTRO, "",
        "## Alarm", "",
        f"- Regel: {alert.get('description', '')} (ID {alert.get('rule_id', '')}, Level {alert.get('rule_level', 0)})",
        f"- Severity: {alert.get('severity', '')}",
        f"- Gruppen: {', '.join(alert.get('groups', []) or [])}",
        f"- MITRE ATT&CK: {', '.join(mitre.get('id', []) or [])} "
        f"({', '.join(mitre.get('tactic', []) or [])})",
        f"- Agent/Asset: {alert.get('agent_name', '')} ({alert.get('agent_id', '')})",
        f"- Quell-IP: {alert.get('srcip', '')}",
        f"- Ort: {alert.get('location', '')}",
        f"- Zeit: {alert.get('event_ts', '')}",
        "", "## Rohlog", "", "```", str(alert.get("full_log", ""))[:2000], "```", "",
        "## Antwortformat (NUR dieses JSON):", "", JSON_SCHEMA,
    ]
    return "\n".join(lines)


def parse_analysis(raw: str) -> dict[str, Any]:
    """Extrahiert das JSON-Objekt aus einer LLM-Antwort (robust gegen Markdown-Backticks)."""
    if not raw:
        return {}
    text = raw.strip()
    if "```" in text:
        # Inhalt zwischen den ersten ```-Fences
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_parse_error": True, "_raw": raw[:2000]}


def analyze_with_ollama(alert: dict[str, Any]) -> dict[str, Any]:
    """Lokale Analyse via Ollama. Raises OllamaError bei Problemen."""
    return _run_ollama(build_alert_prompt(alert))


# ── Incident-Analyse (Gesamtbild aus verknüpften Alarmen, #1290) ────────────

INCIDENT_INTRO = (
    "Du bist erfahrene:r SOC-Analyst:in. Bewerte den folgenden Incident im Gesamtbild "
    "der verknüpften Wazuh-Alarme. Antworte AUSSCHLIESSLICH mit JSON in genau diesem Schema:"
)

INCIDENT_SCHEMA = (
    "{\n"
    '  "zusammenfassung": "Gesamtbild in 2-3 Sätzen",\n'
    '  "ist_echter_vorfall": true,\n'
    '  "schwere": "low | medium | high | critical",\n'
    '  "angriffsmuster": "z.B. mehrstufiger Brute-Force → Lateral Movement",\n'
    '  "mitre": ["Txxxx"],\n'
    '  "empfohlene_eindaemmung": ["..."],\n'
    '  "personenbezug_moeglich": false,\n'
    '  "meldepflicht_pruefen": ["dsgvo", "nis2", "cra", "aiact"],\n'
    '  "naechste_schritte": ["..."]\n'
    "}"
)


def build_incident_prompt(incident: dict[str, Any], alerts: list[dict[str, Any]]) -> str:
    lines = [
        INCIDENT_INTRO, "",
        f"# Incident #{incident.get('id')}: {incident.get('titel', '')}",
        f"Status: {incident.get('status', '')} · Schwere: {incident.get('severity', '')}",
        f"Klassifikation: {incident.get('klassifikation', '') or '—'}",
        f"Beschreibung: {incident.get('beschreibung', '') or '—'}",
        f"Bereits getroffene Maßnahmen: {incident.get('response_actions', '') or '—'}",
        "", f"## Verknüpfte Alarme ({len(alerts)})", "",
    ]
    for a in alerts[:25]:
        mitre = a.get("mitre", {}) or {}
        lines.append(
            f"- [{a.get('severity', '')}/L{a.get('rule_level', 0)}] {a.get('description', '')} "
            f"| Agent {a.get('agent_name', '')} | IP {a.get('srcip', '')} "
            f"| MITRE {', '.join(mitre.get('id', []) or [])} | {a.get('event_ts', '')}")
    lines += ["", "## Antwortformat (NUR dieses JSON):", "", INCIDENT_SCHEMA]
    return "\n".join(lines)


def analyze_incident_with_ollama(incident: dict[str, Any], alerts: list[dict[str, Any]]) -> dict[str, Any]:
    return _run_ollama(build_incident_prompt(incident, alerts))


_SOC_SYSTEM_PROMPT = (
    "Du bist erfahrene:r SOC-Analyst:in. Antworte präzise und folge dem geforderten Format."
)


def _run_ollama(prompt: str) -> dict[str, Any]:
    return parse_analysis(_run_ai_text(prompt))


def _run_ai_text(prompt: str) -> str:
    """KI-Aufruf über den konfigurierten Provider (#1342): on_prem (Ollama) ODER cloud.

    Respektiert ``ai.provider``: bei cloud erzwingt der ``CloudProvider``
    ``allow_data_egress`` + Redaction + Audit (``ai.cloud.request``) — KEIN stiller
    Ollama-Fallback. Sensible Alarmdaten verlassen das Haus nur bei expliziter
    Cloud-Freigabe.
    """
    try:
        from ai_compliance_suite.ai.dispatch import is_cloud_provider, generate_text
    except Exception:
        is_cloud_provider = None  # type: ignore[assignment]

    if is_cloud_provider is not None and is_cloud_provider():
        resp = generate_text(
            system=_SOC_SYSTEM_PROMPT,
            prompt=prompt,
            temperature=0.2,
            max_output_tokens=1200,
        )
        return resp.text or ""

    # on_prem: lokales Ollama (unverändertes Verhalten)
    from shared.ollama_config import get_ollama_config
    from compliance_db.local_llm import generate_ollama
    oc = get_ollama_config()
    chunks = list(generate_ollama(base_url=oc.base_url, model=oc.model, question=prompt,
                                  context=[], timeout_s=min(oc.timeout_s, 180)))
    return "".join(chunks)


# Rückwärtskompatibler Alias (frühere interne Bezeichnung).
_run_ollama_text = _run_ai_text


# ── Lagebericht-Assistent (Prosa, #1270) ────────────────────────────────────

def build_lagebericht_prompt(kpis: dict[str, Any], incidents: list[dict[str, Any]]) -> str:
    lines = [
        "Erstelle einen prägnanten SOC-Lagebericht (Fließtext, Deutsch) für das Management "
        "auf Basis der folgenden Kennzahlen und offenen Incidents. Struktur: Gesamtlage, "
        "kritische Punkte, Empfehlungen.", "",
        "## Kennzahlen",
        f"- Neue Alarme: {kpis.get('alerts_new', 0)} von {kpis.get('alerts_total', 0)}",
        f"- Schwachstellen-Alarme: {kpis.get('alerts_vulnerability', 0)}",
        f"- False-Positive-Rate: {round((kpis.get('fp_rate', 0) or 0) * 100)}%",
        f"- Offene Incidents: {kpis.get('incidents_open', 0)}", "",
        f"## Offene Incidents ({len(incidents)})",
    ]
    for i in incidents[:20]:
        lines.append(f"- #{i.get('id')} [{i.get('severity', '')}/{i.get('status', '')}] {i.get('titel', '')}")
    return "\n".join(lines)


def lagebericht_with_ollama(kpis: dict[str, Any], incidents: list[dict[str, Any]]) -> str:
    return _run_ollama_text(build_lagebericht_prompt(kpis, incidents))
