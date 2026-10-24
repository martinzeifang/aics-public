"""SOC — Periodisches Management-Reporting (KPIs/Trends) (#1325).

Automatisierbarer SOC-Lagebericht für das Management (wöchentlich/monatlich/
quartalsweise): KPIs (MTTD/MTTR/SLA), Incident-Zahlen nach Severity/Kategorie,
Trend und Top-Assets — als DOCX/PDF.

Normbezug: SOC-CMM Business · NIST CSF Govern · ISO 27035 Reporting.
"""
from __future__ import annotations

from html import escape
from typing import Any

from soc import db as sdb
from soc.db import _connect, ensure_db

PERIODS = {"woche": 7, "monat": 30, "quartal": 90}


def build_report_data(db_path, *, period: str = "monat") -> dict[str, Any]:
    ensure_db(db_path)
    days = PERIODS.get(period, 30)
    con = _connect(db_path)
    try:
        since = con.execute(
            "SELECT to_char((now() AT TIME ZONE 'UTC') - (? || ' days')::interval, "
            "'YYYY-MM-DD HH24:MI:SS') AS s", (days,)).fetchone()["s"]
        inc_total = con.execute(
            "SELECT COUNT(*) c FROM soc_incidents WHERE created_at >= ?", (since,)).fetchone()["c"]
        by_sev = {r["severity"]: r["c"] for r in con.execute(
            """SELECT severity, COUNT(*) c FROM soc_incidents WHERE created_at >= ?
               GROUP BY severity""", (since,)).fetchall()}
        by_kat = {(r["klassifikation"] or "—"): r["c"] for r in con.execute(
            """SELECT klassifikation, COUNT(*) c FROM soc_incidents WHERE created_at >= ?
               GROUP BY klassifikation""", (since,)).fetchall()}
        closed = con.execute(
            "SELECT COUNT(*) c FROM soc_incidents WHERE status='closed' AND created_at >= ?",
            (since,)).fetchone()["c"]
        alerts_new = con.execute(
            "SELECT COUNT(*) c FROM soc_alerts WHERE ingested_at >= ?", (since,)).fetchone()["c"]
        top_assets = [dict(r) for r in con.execute(
            """SELECT agent_name, COUNT(*) c FROM soc_alerts WHERE agent_name != '' AND ingested_at >= ?
               GROUP BY agent_name ORDER BY c DESC LIMIT 10""", (since,)).fetchall()]
        # Wochen-Trend (Incidents je Kalenderwoche im Zeitraum)
        trend = [dict(r) for r in con.execute(
            """SELECT to_char(created_at::timestamp, 'IYYY-"W"IW') AS woche, COUNT(*) c
               FROM soc_incidents WHERE created_at >= ? GROUP BY woche ORDER BY woche""",
            (since,)).fetchall()]
    finally:
        con.close()
    sla = sdb.sla_kpis(db_path)
    return {
        "period": period, "days": days, "since": since[:10],
        "incidents_total": inc_total, "incidents_closed": closed,
        "by_severity": by_sev, "by_category": by_kat,
        "alerts_new": alerts_new, "top_assets": top_assets, "trend": trend,
        "mtta_hours": sla.get("mtta_hours"), "mttr_hours": sla.get("mttr_hours"),
        "sla_compliance": sla.get("sla_compliance"), "sla_breached": sla.get("sla_breached"),
    }


def _pct(v) -> str:
    return "–" if v is None else f"{round(v * 100)} %"


def render_html(d: dict[str, Any]) -> str:
    def _rows(dct):
        return "".join(f"<tr><td>{escape(str(k))}</td><td>{v}</td></tr>" for k, v in dct.items()) \
            or "<tr><td colspan='2'>—</td></tr>"
    top = "".join(f"<tr><td>{escape(a['agent_name'])}</td><td>{a['c']}</td></tr>"
                  for a in d["top_assets"]) or "<tr><td colspan='2'>—</td></tr>"
    trend = "".join(f"<tr><td>{escape(t['woche'])}</td><td>{t['c']}</td></tr>"
                    for t in d["trend"]) or "<tr><td colspan='2'>—</td></tr>"
    return f"""
    <h1>SOC-Management-Report</h1>
    <p>Zeitraum: {d['period']} (seit {d['since']}, {d['days']} Tage)</p>
    <h2>Kennzahlen</h2>
    <table>
      <tr><td>Neue Alarme</td><td>{d['alerts_new']}</td></tr>
      <tr><td>Incidents (gesamt)</td><td>{d['incidents_total']}</td></tr>
      <tr><td>Incidents (geschlossen)</td><td>{d['incidents_closed']}</td></tr>
      <tr><td>MTTA (Reaktion)</td><td>{d['mtta_hours'] if d['mtta_hours'] is not None else '–'} h</td></tr>
      <tr><td>MTTR (Behebung)</td><td>{d['mttr_hours'] if d['mttr_hours'] is not None else '–'} h</td></tr>
      <tr><td>SLA-Einhaltung</td><td>{_pct(d['sla_compliance'])}</td></tr>
      <tr><td>SLA-Verletzungen</td><td>{d['sla_breached'] if d['sla_breached'] is not None else '–'}</td></tr>
    </table>
    <h2>Incidents nach Schweregrad</h2>
    <table>{_rows(d['by_severity'])}</table>
    <h2>Incidents nach Kategorie</h2>
    <table>{_rows(d['by_category'])}</table>
    <h2>Trend (Incidents je Kalenderwoche)</h2>
    <table><tr><th>KW</th><th>Anzahl</th></tr>{trend}</table>
    <h2>Top-Assets (meiste Alarme)</h2>
    <table><tr><th>Agent</th><th>Alarme</th></tr>{top}</table>
    """


def render_docx(d: dict[str, Any]) -> bytes:
    from io import BytesIO

    from docx import Document

    from shared.documents.export import _html_to_docx
    doc = Document()
    _html_to_docx(doc, render_html(d))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


def render_pdf(d: dict[str, Any]) -> bytes:
    from shared.templates.pdf_converter import convert_docx_to_pdf
    return convert_docx_to_pdf(render_docx(d))
