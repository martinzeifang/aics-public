"""SOC-Incident-Report (#1299): einzelne oder mehrere Incidents als DOCX/PDF.

Baut je Incident eine HTML-Sektion (Kernfakten, verknüpfte Alarme, Meldetracks,
Verlauf) und rendert sie über die geteilte ``_html_to_docx``-Hilfe zu DOCX; PDF
via ``convert_docx_to_pdf`` (Gotenberg/soffice).
"""
from __future__ import annotations

from html import escape
from io import BytesIO
from typing import Any

from soc.constants import REGIMES

_SEV = {"critical": "Kritisch", "high": "Hoch", "medium": "Mittel", "low": "Niedrig"}
_IST = {"new": "Neu", "in_review": "In Prüfung", "false_positive": "False Positive",
        "confirmed": "Bestätigt", "contained": "Eingedämmt", "eradicated": "Beseitigt",
        "resolved": "Behoben", "closed": "Geschlossen", "reopened": "Wieder geöffnet"}


def _incident_html(item: dict[str, Any]) -> str:
    inc = item.get("incident", {})
    alerts = item.get("alerts", [])
    tracks = item.get("meldetracks", [])
    timeline = item.get("timeline", [])
    p: list[str] = []
    p.append(f"<h1>Incident #{inc.get('id')}: {escape(str(inc.get('titel', '')))}</h1>")
    p.append("<h2>Kernfakten</h2>")
    p.append(f"<p>Status: {_IST.get(inc.get('status'), inc.get('status', ''))} · "
             f"Schwere: {_SEV.get(inc.get('severity'), inc.get('severity', ''))} · "
             f"Klassifikation: {escape(str(inc.get('klassifikation') or '—'))}</p>")
    p.append(f"<p>Owner: {escape(str(inc.get('owner') or '—'))} · "
             f"Asset: {escape(str(inc.get('agent_name') or '—'))} · "
             f"Awareness: {escape(str(inc.get('awareness_at') or inc.get('created_at') or '—'))}</p>")
    if inc.get("personal_data_involved"):
        p.append("<p>Personenbezug: ja</p>")
    if inc.get("beschreibung"):
        p.append(f"<h2>Beschreibung</h2><p>{escape(str(inc['beschreibung']))}</p>")
    if inc.get("response_actions"):
        p.append(f"<h2>Maßnahmen</h2><p>{escape(str(inc['response_actions']))}</p>")
    if inc.get("lessons_learned"):
        p.append(f"<h2>Lessons Learned</h2><p>{escape(str(inc['lessons_learned']))}</p>")
    if inc.get("status") == "closed" and inc.get("closed_reason"):
        p.append(f"<h2>Abschluss-Begründung</h2><p>{escape(str(inc['closed_reason']))} "
                 f"({escape(str(inc.get('closed_by') or ''))}, {escape(str(inc.get('closed_at') or ''))})</p>")
    # Alarme
    p.append(f"<h2>Verknüpfte Wazuh-Alarme ({len(alerts)})</h2>")
    if alerts:
        p.append("<ul>")
        for a in alerts:
            mitre = ", ".join((a.get("mitre", {}) or {}).get("id", []) or [])
            p.append(f"<li>[{_SEV.get(a.get('severity'), a.get('severity', ''))}/L{a.get('rule_level', 0)}] "
                     f"{escape(str(a.get('description', '')))} — Agent {escape(str(a.get('agent_name', '')))}, "
                     f"IP {escape(str(a.get('srcip') or '—'))}, {escape(str(a.get('event_ts', '')))}"
                     f"{(' · MITRE ' + escape(mitre)) if mitre else ''}</li>")
        p.append("</ul>")
    else:
        p.append("<p>—</p>")
    # Meldetracks
    if tracks:
        p.append("<h2>Meldepflichten</h2><ul>")
        for t in tracks:
            legal = REGIMES.get(t.get("regime"), {}).get("legal", t.get("legal", ""))
            dls = "; ".join(f"{d.get('label')}: {d.get('due_at') or 'n/a'}" for d in t.get("deadlines", []))
            p.append(f"<li>{str(t.get('regime', '')).upper()} ({escape(str(legal))}) — Status {escape(str(t.get('status', '')))}; {escape(dls)}</li>")
        p.append("</ul>")
    # Timeline
    if timeline:
        p.append("<h2>Verlauf</h2><ul>")
        for e in timeline:
            p.append(f"<li>{escape(str(e.get('ts', '')))} — {escape(str(e.get('event', '')))}: "
                     f"{escape(str(e.get('detail', '')))} ({escape(str(e.get('actor', '')))})</li>")
        p.append("</ul>")
    return "".join(p)


def render_incidents_docx(items: list[dict[str, Any]]) -> bytes:
    from docx import Document
    from shared.documents.export import _html_to_docx
    doc = Document()
    doc.add_heading("SOC-Incident-Report", 0)
    for idx, item in enumerate(items):
        _html_to_docx(doc, _incident_html(item))
        if idx < len(items) - 1:
            doc.add_page_break()
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


def render_incidents_pdf(items: list[dict[str, Any]]) -> bytes:
    from shared.templates.pdf_converter import convert_docx_to_pdf
    return convert_docx_to_pdf(render_incidents_docx(items))
