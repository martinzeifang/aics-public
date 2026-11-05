"""WiBA — Copy/Paste-KI-Prompts (Default-KI-Workflow).

Erzeugt einen Prompt, den der Anwender in ChatGPT o. ä. einfügt, und parst die
JSON-Antwort zurück. Kontext: Prüffrage + Hilfsmittel + Thema/Baustein + optional
bei der Firma hinterlegte Nachweis-Texte (#1123).
"""
from __future__ import annotations

import json
import re
from typing import Any

PROMPT_INTRO = (
    "Du bist Informationssicherheits-Berater:in und hilfst einer kleinen "
    "Organisation (KMU/Kommune) bei der BSI-Basis-Absicherung (WiBA). "
    "Beantworte die folgende Prüffrage auf Basis der bereitgestellten Nachweise. "
    "Antworte AUSSCHLIESSLICH mit einem JSON-Objekt im angegebenen Format."
)

JSON_FORMAT = (
    '{\n'
    '  "status": "ja | nein | nicht_relevant",\n'
    '  "notiz": "kurze, prüffähige Begründung/Nachweis (welche Doku, welche Maßnahme)",\n'
    '  "empfehlung": "falls Status nein: konkrete nächste Maßnahme"\n'
    '}'
)


def build_prompt(control: dict[str, Any], theme: dict[str, Any] | None = None,
                 evidence_texts: list[dict[str, Any]] | None = None,
                 max_evidence_chars: int = 6000, issue_context: str = "") -> str:
    """Baut den Prompt für eine einzelne Prüffrage.

    #1524: ``issue_context`` (Inhalt verknüpfter Issues) wird — falls vorhanden — als
    Review-Feedback-Block ergänzt (Neubewertung mit Issue-Feedback)."""
    theme = theme or {}
    parts: list[str] = [PROMPT_INTRO, ""]
    parts.append(f"# Thema / Baustein: {theme.get('titel', '')}")
    if theme.get('bausteine'):
        parts.append(f"Zugrundeliegende BSI-Bausteine: {theme['bausteine']}")
    if theme.get('ziel'):
        parts.append(f"Ziel des Bausteins: {theme['ziel']}")
    parts.append("")
    parts.append(f"# Prüffrage ({control.get('control_id', '')}):")
    parts.append(control.get('frage', ''))
    if control.get('hilfsmittel'):
        parts.append("")
        parts.append(f"Hilfestellung des BSI: {control['hilfsmittel']}")

    if evidence_texts:
        parts.append("")
        parts.append("# Vorliegende Nachweise der Organisation:")
        budget = max_evidence_chars
        for ev in evidence_texts:
            if budget <= 0:
                break
            snippet = (ev.get('text') or '')[:budget]
            budget -= len(snippet)
            parts.append(f"\n--- {ev.get('filename', 'Dokument')} ---\n{snippet}")
    else:
        parts.append("")
        parts.append("# Hinweis: Es liegen keine hochgeladenen Nachweise vor — "
                     "beantworte konservativ und fordere fehlende Nachweise an.")

    if issue_context and issue_context.strip():
        parts.append("")
        parts.append("# Feedback aus verknüpftem Issue (GitHub/GitLab) — bei der "
                     "Neubewertung berücksichtigen:")
        parts.append(str(issue_context)[:5000])

    parts.append("")
    parts.append("# Antworte ausschließlich mit diesem JSON-Format:")
    parts.append(JSON_FORMAT)
    return "\n".join(parts)


def build_theme_prompt(theme: dict[str, Any], controls: list[dict[str, Any]],
                       evidence_texts: list[dict[str, Any]] | None = None) -> str:
    """Sammelprompt für ein ganzes Thema (mehrere Prüffragen auf einmal)."""
    parts: list[str] = [PROMPT_INTRO, ""]
    parts.append(f"# Thema: {theme.get('titel', '')}  (BSI: {theme.get('bausteine', '')})")
    if theme.get('ziel'):
        parts.append(f"Ziel: {theme['ziel']}")
    parts.append("\n# Prüffragen:")
    for c in controls:
        line = f"- [{c.get('control_id')}] {c.get('frage')}"
        if c.get('hilfsmittel'):
            line += f"  (Hilfe: {c['hilfsmittel']})"
        parts.append(line)
    if evidence_texts:
        parts.append("\n# Vorliegende Nachweise:")
        budget = 8000
        for ev in evidence_texts:
            if budget <= 0:
                break
            snip = (ev.get('text') or '')[:budget]
            budget -= len(snip)
            parts.append(f"\n--- {ev.get('filename', 'Dokument')} ---\n{snip}")
    parts.append(
        "\n# Antworte mit einem JSON-Array, ein Objekt je Prüffrage:\n"
        '[{"control_id": "...", "status": "ja|nein|nicht_relevant", '
        '"notiz": "...", "empfehlung": "..."}]')
    return "\n".join(parts)


def build_mass_control_prompt(controls: list[dict[str, Any]],
                              evidence_texts: list[dict[str, Any]] | None = None) -> str:
    """#1528 (WiBA): EIN Sammel-Prompt über MEHRERE (auch themenübergreifend) ausgewählte
    Prüffragen. Jede Prüffrage nennt ihren Baustein/Thema inline. Antwort: JSON-Array
    ``[{control_id, status, notiz}]`` (status = ja|nein|nicht_relevant)."""
    parts: list[str] = [PROMPT_INTRO, ""]
    parts.append(f"# Zu bewertende Prüffragen ({len(controls)}):")
    for c in controls:
        thema = c.get('theme_titel') or c.get('thema') or ''
        baustein = c.get('bausteine') or c.get('baustein') or ''
        ctx = ' · '.join(x for x in (thema, baustein) if x)
        line = f"- [{c.get('control_id')}] {c.get('frage')}"
        if ctx:
            line += f"  (Kontext: {ctx})"
        if c.get('hilfsmittel'):
            line += f"  (Hilfe: {c['hilfsmittel']})"
        parts.append(line)
    if evidence_texts:
        parts.append("\n# Vorliegende Nachweise der Organisation:")
        budget = 8000
        for ev in evidence_texts:
            if budget <= 0:
                break
            snip = (ev.get('text') or '')[:budget]
            budget -= len(snip)
            parts.append(f"\n--- {ev.get('filename', 'Dokument')} ---\n{snip}")
    parts.append(
        "\n# Antworte AUSSCHLIESSLICH mit einem gültigen JSON-Array — kein Text davor/danach,"
        " KEINE Markdown-Codeblöcke. Genau ein Objekt je Prüffrage, die 'control_id' exakt wie oben:\n"
        '[{"control_id": "...", "status": "ja|nein|nicht_relevant", "notiz": "kurze Begründung"}]')
    return "\n".join(parts)


def parse_json_antwort(raw: str) -> Any:
    """Extrahiert das JSON aus einer (ggf. in Markdown gehüllten) LLM-Antwort."""
    if not raw or not raw.strip():
        raise ValueError("Leere Antwort")
    text = raw.strip()
    # ```json ... ``` Block entfernen
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    # erstes { … } oder [ … ] greifen
    if not text.lstrip().startswith(("{", "[")):
        m2 = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m2:
            text = m2.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Antwort ist kein gültiges JSON: {e}") from e
