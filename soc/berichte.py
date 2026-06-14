"""SOC-Berichts-Center (#1350) — vier Berichtstypen über frei wählbaren Zeitraum.

Generischer Report-Renderer je Typ + Zeitraum (von/bis). HTML → DOCX über die
geteilte ``shared/documents/export._html_to_docx``-Hilfe; PDF über den zentralen
Gotenberg-Konverter (``shared/templates/pdf_converter``).

Berichtstypen (``BERICHT_TYPEN``):
- ``incident_gesamt``  — abgeschlossene Incidents im Zeitraum mit ALLEN Infos
  (Stammdaten, Timeline, Alarme, Playbook-Status, PIR + Maßnahmen, Asservaten/
  Chain-of-Custody-Zusammenfassung, Meldetracks, Eskalation).
- ``use_cases``        — Detection-Use-Cases + ATT&CK-Coverage-Stand.
- ``alle_incidents``   — Liste aller Incidents im Zeitraum mit Bearbeitungszeiten
  (Dauer offen, MTTA/MTTR, Klassifikation/Bewertung, Status, SLA).
- ``alle_alarme``      — Liste aller Alarme im Zeitraum mit Bearbeitungszeiten
  (Zeit bis Triage, Triage-Status/Bewertung, Severity, IOC-Treffer).

Bearbeitungszeiten werden aus den TEXT-Timestamps (``'YYYY-MM-DD HH:MM:SS'``)
berechnet (:func:`_minutes_between` / :func:`_fmt_dauer`).

Normbezug: ISO 27035 Reporting · NIST CSF Govern · SOC-CMM Business.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

from soc import db as sdb
from soc.constants import REGIMES
from soc.db import _connect, ensure_db

DB_PATH = Path("data/db/soc.sqlite")

# Berichtstyp-Keys → Metadaten (Single Source of Truth für Katalog + Dispatch).
BERICHT_TYPEN: dict[str, dict[str, str]] = {
    "incident_gesamt": {
        "titel": "Incident-Gesamtbericht",
        "norm": "ISO 27035",
        "beschreibung": "Abgeschlossene Incidents im Zeitraum mit allen Details "
                        "(Timeline, Alarme, Playbooks, PIR, Asservaten, Meldetracks, Eskalation).",
    },
    "use_cases": {
        "titel": "Use-Cases-Bericht",
        "norm": "BSI DER.1 / NIST CSF Detect",
        "beschreibung": "Detection-Use-Cases + MITRE-ATT&CK-Coverage-Stand.",
    },
    "alle_incidents": {
        "titel": "Alle-Incidents-Bericht",
        "norm": "SOC-CMM Business",
        "beschreibung": "Liste aller Incidents im Zeitraum inkl. Bearbeitungszeiten "
                        "(Dauer, MTTA/MTTR), Klassifikation, Status und SLA.",
    },
    "alle_alarme": {
        "titel": "Alle-Alarme-Bericht",
        "norm": "SOC-CMM Services",
        "beschreibung": "Liste aller Alarme im Zeitraum inkl. Bearbeitungszeiten "
                        "(Zeit bis Triage), Triage-Status, Severity und IOC-Treffern.",
    },
}

_SEV = {"critical": "Kritisch", "high": "Hoch", "medium": "Mittel", "low": "Niedrig"}
_IST = {"new": "Neu", "in_review": "In Prüfung", "false_positive": "False Positive",
        "confirmed": "Bestätigt", "contained": "Eingedämmt", "eradicated": "Beseitigt",
        "resolved": "Behoben", "closed": "Geschlossen", "reopened": "Wieder geöffnet"}
_AST = {"new": "Neu", "in_review": "In Prüfung", "false_positive": "False Positive",
        "confirmed": "Bestätigt", "suppressed": "Unterdrückt"}
_FMT = "%Y-%m-%d %H:%M:%S"


def available_reports() -> list[dict[str, str]]:
    """Katalog der Berichtstypen (Key, Titel, Norm, Beschreibung)."""
    return [{"key": k, **v} for k, v in BERICHT_TYPEN.items()]


# ── Zeitraum / Bearbeitungszeit-Helfer ──────────────────────────────────────

def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:19], _FMT)
    except (ValueError, TypeError):
        return None


def _minutes_between(a: str | None, b: str | None) -> float | None:
    """Minuten zwischen zwei TEXT-Timestamps ('YYYY-MM-DD HH:MM:SS')."""
    da, db = _parse_ts(a), _parse_ts(b)
    if da is None or db is None:
        return None
    return (db - da).total_seconds() / 60.0


def _fmt_dauer(minutes: float | None) -> str:
    """Minuten als lesbare Dauer (z. B. '3 h 12 min', '2 d 4 h')."""
    if minutes is None:
        return "—"
    mins = int(round(minutes))
    if mins < 0:
        return "—"
    if mins < 60:
        return f"{mins} min"
    if mins < 60 * 24:
        h, m = divmod(mins, 60)
        return f"{h} h {m} min" if m else f"{h} h"
    d, rest = divmod(mins, 60 * 24)
    h = rest // 60
    return f"{d} d {h} h" if h else f"{d} d"


def normalize_zeitraum(von: str | None, bis: str | None) -> tuple[str, str]:
    """Normalisiert ``von``/``bis`` zu ('YYYY-MM-DD 00:00:00', 'YYYY-MM-DD 23:59:59').

    Fehlt ``bis``, wird der heutige Tag genutzt; fehlt ``von``, die letzten 90 Tage.
    Akzeptiert reines Datum ('YYYY-MM-DD') oder vollen Timestamp.
    """
    from datetime import date, timedelta

    def _day(v: str | None) -> date | None:
        if not v:
            return None
        try:
            return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    bis_d = _day(bis) or date.today()
    von_d = _day(von) or (bis_d - timedelta(days=90))
    if von_d > bis_d:
        von_d, bis_d = bis_d, von_d
    return (f"{von_d.isoformat()} 00:00:00", f"{bis_d.isoformat()} 23:59:59")


# ── Datensammlung je Typ ────────────────────────────────────────────────────

def _incident_full(db_path: Path, incident_id: int) -> dict[str, Any]:
    """Alle Detail-Daten eines Incidents für den Gesamtbericht einsammeln."""
    from soc import betrieb, evidence
    inc = sdb.get_incident(db_path, incident_id) or {}
    item: dict[str, Any] = {
        "incident": inc,
        "timeline": sdb.list_timeline(db_path, incident_id),
        "alerts": sdb.get_incident_alerts(db_path, incident_id),
        "meldetracks": sdb.list_meldetracks(db_path, incident_id),
        "pir": sdb.get_pir(db_path, incident_id),
        "pir_actions": sdb.list_pir_actions(db_path, incident_id=incident_id),
        "sla": sdb.incident_sla(db_path, inc) if inc else {},
    }
    try:
        item["evidence"] = evidence.list_evidence(db_path, incident_id)
    except Exception:  # noqa: BLE001
        item["evidence"] = []
    try:
        item["escalation"] = betrieb.list_escalation(db_path, severity=inc.get("severity"))
    except Exception:  # noqa: BLE001
        item["escalation"] = []
    # Playbook-Status (#1294): zugeordnete Playbooks + Schritt-Fortschritt.
    try:
        item["playbooks"] = sdb.list_incident_playbooks(db_path, incident_id)
    except Exception:  # noqa: BLE001
        item["playbooks"] = []
    return item


def build_data(db_path: Path, typ: str, *, von: str | None = None,
               bis: str | None = None) -> dict[str, Any]:
    """Liest die Rohdaten für einen Berichtstyp + Zeitraum aus der DB."""
    ensure_db(db_path)
    seed_sla_safe(db_path)
    von_ts, bis_ts = normalize_zeitraum(von, bis)
    base: dict[str, Any] = {
        "typ": typ, "titel": BERICHT_TYPEN.get(typ, {}).get("titel", typ),
        "norm": BERICHT_TYPEN.get(typ, {}).get("norm", ""),
        "von": von_ts[:10], "bis": bis_ts[:10],
        "erstellt": datetime.utcnow().strftime(_FMT),
    }

    if typ == "incident_gesamt":
        con = _connect(db_path)
        try:
            ids = [r["id"] for r in con.execute(
                "SELECT id FROM soc_incidents WHERE status='closed' "
                "AND COALESCE(closed_at, created_at) >= ? AND COALESCE(closed_at, created_at) <= ? "
                "ORDER BY closed_at, id", (von_ts, bis_ts)).fetchall()]
        finally:
            con.close()
        base["incidents"] = [_incident_full(db_path, int(i)) for i in ids]
        return base

    if typ == "use_cases":
        from soc import detection
        base["usecases"] = detection.list_usecases(db_path)
        base["coverage"] = detection.attack_coverage(db_path)
        base["gaps"] = detection.coverage_gaps(db_path)
        return base

    if typ == "alle_incidents":
        con = _connect(db_path)
        try:
            rows = [sdb._incident_to_dict(r) for r in con.execute(
                "SELECT * FROM soc_incidents WHERE created_at >= ? AND created_at <= ? "
                "ORDER BY created_at DESC, id DESC", (von_ts, bis_ts)).fetchall()]
        finally:
            con.close()
        sla_cfg = sdb.list_sla(db_path)
        out = []
        for inc in rows:
            mtta = _minutes_between(inc.get("created_at"), inc.get("acknowledged_at"))
            mttr = _minutes_between(inc.get("created_at"), inc.get("resolved_at"))
            end = inc.get("closed_at") or inc.get("resolved_at")
            offen = _minutes_between(inc.get("created_at"), end) if end else \
                _minutes_between(inc.get("created_at"), datetime.utcnow().strftime(_FMT))
            target = (sla_cfg.get(inc.get("severity") or "medium") or {}).get("resolve_minutes")
            sla_ok = None
            if mttr is not None and target:
                sla_ok = mttr <= target
            out.append({**inc, "_mtta": mtta, "_mttr": mttr, "_dauer": offen, "_sla_ok": sla_ok})
        base["rows"] = out
        base["kpi"] = _incidents_kpi(out)
        return base

    if typ == "alle_alarme":
        con = _connect(db_path)
        try:
            rows = [sdb._alert_to_dict(r) for r in con.execute(
                "SELECT * FROM soc_alerts WHERE ingested_at >= ? AND ingested_at <= ? "
                "ORDER BY ingested_at DESC, id DESC", (von_ts, bis_ts)).fetchall()]
        finally:
            con.close()
        out = []
        for a in rows:
            # Zeit bis Triage: ingested_at → erster Timeline-/Status-Wechsel.
            triaged = a.get("status") not in ("new", "")
            ttt = _alert_time_to_triage(db_path, a) if triaged else None
            out.append({**a, "_ttt": ttt, "_ioc_count": len(a.get("ioc_hits") or [])})
        base["rows"] = out
        base["kpi"] = _alerts_kpi(out)
        return base

    raise ValueError(f"Unbekannter Berichtstyp: {typ}")


def seed_sla_safe(db_path: Path) -> None:
    try:
        sdb.seed_sla(db_path)
    except Exception:  # noqa: BLE001
        pass


def _alert_time_to_triage(db_path: Path, alert: dict[str, Any]) -> float | None:
    """Zeit (Minuten) von Ingestion bis zur ersten Triage-Aktion eines Alarms.

    Quelle ist der ``triaged_at``-Timestamp (#1350), den :func:`db.set_alert_status`
    beim ersten Wechsel weg von ``new`` setzt. Für Alt-Bestand ohne Timestamp None.
    """
    return _minutes_between(alert.get("ingested_at"), alert.get("triaged_at"))


def _incidents_kpi(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mttas = [r["_mtta"] for r in rows if r.get("_mtta") is not None]
    mttrs = [r["_mttr"] for r in rows if r.get("_mttr") is not None]
    breached = sum(1 for r in rows if r.get("_sla_ok") is False)
    within = sum(1 for r in rows if r.get("_sla_ok") is True)

    def _avg_h(xs):
        return round(sum(xs) / len(xs) / 60.0, 1) if xs else None
    return {
        "total": len(rows),
        "closed": sum(1 for r in rows if r.get("status") == "closed"),
        "mtta_hours": _avg_h(mttas),
        "mttr_hours": _avg_h(mttrs),
        "sla_breached": breached,
        "sla_within": within,
    }


def _alerts_kpi(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ttts = [r["_ttt"] for r in rows if r.get("_ttt") is not None]
    return {
        "total": len(rows),
        "triaged": sum(1 for r in rows if r.get("status") not in ("new", "")),
        "ioc_hits": sum(1 for r in rows if r.get("_ioc_count")),
        "avg_triage_hours": round(sum(ttts) / len(ttts) / 60.0, 1) if ttts else None,
    }


# ── HTML-Render je Typ ──────────────────────────────────────────────────────

def _meta_header(d: dict[str, Any]) -> str:
    return (f"<h1>SOC-Bericht: {escape(d['titel'])}</h1>"
            f"<p>Zeitraum: {escape(d['von'])} bis {escape(d['bis'])} · "
            f"Erstellt (UTC): {escape(d['erstellt'])} · Normbezug: {escape(d.get('norm', ''))}</p>")


def _incident_section(item: dict[str, Any]) -> str:
    inc = item.get("incident") or {}
    p: list[str] = []
    p.append(f"<h2>Incident #{inc.get('id')}: {escape(str(inc.get('titel', '')))}</h2>")
    sla = item.get("sla") or {}
    mttr = _minutes_between(inc.get("created_at"), inc.get("closed_at") or inc.get("resolved_at"))
    p.append("<table>"
             f"<tr><td>Status</td><td>{_IST.get(inc.get('status'), inc.get('status', ''))}</td></tr>"
             f"<tr><td>Schwere</td><td>{_SEV.get(inc.get('severity'), inc.get('severity', ''))}</td></tr>"
             f"<tr><td>Klassifikation</td><td>{escape(str(inc.get('klassifikation') or '—'))}</td></tr>"
             f"<tr><td>Owner</td><td>{escape(str(inc.get('owner') or '—'))}</td></tr>"
             f"<tr><td>Asset</td><td>{escape(str(inc.get('agent_name') or '—'))}</td></tr>"
             f"<tr><td>Erstellt</td><td>{escape(str(inc.get('created_at') or '—'))}</td></tr>"
             f"<tr><td>Geschlossen</td><td>{escape(str(inc.get('closed_at') or '—'))}</td></tr>"
             f"<tr><td>Bearbeitungsdauer</td><td>{_fmt_dauer(mttr)}</td></tr>"
             f"<tr><td>MTTA / MTTR</td><td>{_fmt_dauer(_minutes_between(inc.get('created_at'), inc.get('acknowledged_at')))}"
             f" / {_fmt_dauer(_minutes_between(inc.get('created_at'), inc.get('resolved_at')))}</td></tr>"
             "</table>")
    if inc.get("beschreibung"):
        p.append(f"<h3>Beschreibung</h3><p>{escape(str(inc['beschreibung']))}</p>")
    if inc.get("closed_reason"):
        p.append(f"<h3>Abschluss-Begründung</h3><p>{escape(str(inc['closed_reason']))} "
                 f"({escape(str(inc.get('closed_by') or ''))})</p>")
    # Alarme
    alerts = item.get("alerts") or []
    p.append(f"<h3>Verknüpfte Wazuh-Alarme ({len(alerts)})</h3>")
    if alerts:
        p.append("<ul>")
        for a in alerts:
            p.append(f"<li>[{_SEV.get(a.get('severity'), a.get('severity', ''))}/L{a.get('rule_level', 0)}] "
                     f"{escape(str(a.get('description', '')))} — {escape(str(a.get('agent_name', '')))}, "
                     f"{escape(str(a.get('event_ts', '')))}</li>")
        p.append("</ul>")
    else:
        p.append("<p>—</p>")
    # Playbooks
    pbs = item.get("playbooks") or []
    if pbs:
        p.append("<h3>Playbook-Status</h3><ul>")
        for pb in pbs:
            prog_d = pb.get("progress") or {}
            done, total = prog_d.get("done"), prog_d.get("total")
            prog = f" ({done}/{total} Schritte)" if total else ""
            p.append(f"<li>{escape(str(pb.get('name', '')))} — Status {escape(str(pb.get('status', '—')))}{prog}</li>")
        p.append("</ul>")
    # PIR
    pir = item.get("pir") or {}
    if pir.get("root_cause") or pir.get("lessons"):
        p.append("<h3>Post-Incident-Review</h3>")
        if pir.get("root_cause"):
            p.append(f"<p><b>Ursache:</b> {escape(str(pir['root_cause']))}</p>")
        if pir.get("what_went_well"):
            p.append(f"<p><b>Gut gelaufen:</b> {escape(str(pir['what_went_well']))}</p>")
        if pir.get("what_went_wrong"):
            p.append(f"<p><b>Verbesserung:</b> {escape(str(pir['what_went_wrong']))}</p>")
        if pir.get("lessons"):
            p.append(f"<p><b>Lessons Learned:</b> {escape(str(pir['lessons']))}</p>")
    actions = item.get("pir_actions") or []
    if actions:
        p.append("<h3>Maßnahmen</h3><table><tr><th>Maßnahme</th><th>Owner</th><th>Frist</th><th>Status</th></tr>")
        for a in actions:
            p.append(f"<tr><td>{escape(str(a.get('beschreibung', '')))}</td>"
                     f"<td>{escape(str(a.get('owner') or '—'))}</td>"
                     f"<td>{escape(str(a.get('frist') or '—'))}</td>"
                     f"<td>{escape(str(a.get('status', '')))}</td></tr>")
        p.append("</table>")
    # Asservaten / Chain of Custody
    evi = item.get("evidence") or []
    p.append(f"<h3>Asservaten / Chain of Custody ({len(evi)})</h3>")
    if evi:
        p.append("<table><tr><th>Datei</th><th>Art</th><th>SHA-256</th><th>Gesichert</th></tr>")
        for e in evi:
            if e.get("deleted_at"):
                continue
            sha = str(e.get("sha256") or "")
            p.append(f"<tr><td>{escape(str(e.get('filename', '')))}</td>"
                     f"<td>{escape(str(e.get('kind', '')))}</td>"
                     f"<td>{escape(sha[:16] + '…' if len(sha) > 16 else sha)}</td>"
                     f"<td>{escape(str(e.get('created_at') or ''))}</td></tr>")
        p.append("</table>")
    else:
        p.append("<p>— Keine Asservaten erfasst —</p>")
    # Meldetracks
    tracks = item.get("meldetracks") or []
    if tracks:
        p.append("<h3>Meldepflichten</h3><ul>")
        for t in tracks:
            legal = REGIMES.get(t.get("regime"), {}).get("legal", t.get("legal", ""))
            dls = "; ".join(f"{dd.get('label')}: {dd.get('due_at') or 'n/a'}" for dd in t.get("deadlines", []))
            p.append(f"<li>{str(t.get('regime', '')).upper()} ({escape(str(legal))}) — "
                     f"Status {escape(str(t.get('status', '')))}; {escape(dls)}</li>")
        p.append("</ul>")
    # Eskalation
    esc = item.get("escalation") or []
    if esc:
        p.append("<h3>Eskalationspfad (Severity)</h3><table><tr><th>Stufe</th><th>Rolle</th><th>Person</th><th>Frist</th></tr>")
        for e in esc:
            p.append(f"<tr><td>{e.get('stufe', '')}</td><td>{escape(str(e.get('rolle') or '—'))}</td>"
                     f"<td>{escape(str(e.get('person') or '—'))}</td>"
                     f"<td>{e.get('frist_minuten', '')} min</td></tr>")
        p.append("</table>")
    # Timeline
    tl = item.get("timeline") or []
    if tl:
        p.append("<h3>Verlauf</h3><ul>")
        for e in tl:
            p.append(f"<li>{escape(str(e.get('ts', '')))} — {escape(str(e.get('event', '')))}: "
                     f"{escape(str(e.get('detail', '')))} ({escape(str(e.get('actor', '')))})</li>")
        p.append("</ul>")
    return "".join(p)


def render_html(d: dict[str, Any]) -> str:
    typ = d.get("typ")
    parts = [_meta_header(d)]
    if typ == "incident_gesamt":
        incs = d.get("incidents") or []
        parts.append(f"<p>Abgeschlossene Incidents im Zeitraum: <b>{len(incs)}</b></p>")
        if not incs:
            parts.append("<p>— Keine abgeschlossenen Incidents im Zeitraum —</p>")
        for item in incs:
            parts.append(_incident_section(item))
    elif typ == "use_cases":
        parts.append(_use_cases_html(d))
    elif typ == "alle_incidents":
        parts.append(_alle_incidents_html(d))
    elif typ == "alle_alarme":
        parts.append(_alle_alarme_html(d))
    return "".join(parts)


def _use_cases_html(d: dict[str, Any]) -> str:
    cov = d.get("coverage") or {}
    counts = cov.get("counts") or {}
    ucs = d.get("usecases") or []
    gaps = d.get("gaps") or []
    p: list[str] = []
    p.append("<h2>ATT&CK-Coverage-Stand</h2><table>"
             f"<tr><td>Abgedeckt</td><td>{counts.get('covered', 0)}</td></tr>"
             f"<tr><td>Teilweise</td><td>{counts.get('partial', 0)}</td></tr>"
             f"<tr><td>Lücke</td><td>{counts.get('gap', 0)}</td></tr>"
             f"<tr><td>Coverage</td><td>{round((cov.get('coverage_pct') or 0) * 100)} %</td></tr>"
             "</table>")
    p.append(f"<h2>Detection-Use-Cases ({len(ucs)})</h2>")
    if ucs:
        p.append("<table><tr><th>Use-Case</th><th>Bedrohung</th><th>Techniken</th><th>Status</th><th>Datenquelle</th></tr>")
        for uc in ucs:
            techs = ", ".join(uc.get("attack_techniques") or [])
            p.append(f"<tr><td>{escape(str(uc.get('name', '')))}</td>"
                     f"<td>{escape(str(uc.get('bedrohung') or '—'))}</td>"
                     f"<td>{escape(techs or '—')}</td>"
                     f"<td>{escape(str(uc.get('status', '')))}</td>"
                     f"<td>{escape(str(uc.get('datenquelle') or '—'))}</td></tr>")
        p.append("</table>")
    else:
        p.append("<p>— Keine Use-Cases gepflegt —</p>")
    if gaps:
        p.append(f"<h2>Detektionslücken ({len(gaps)})</h2><ul>")
        for g in gaps[:60]:
            p.append(f"<li>{escape(str(g.get('id', '')))} {escape(str(g.get('name', '')))} "
                     f"({escape(str(g.get('tactic', '')))})</li>")
        p.append("</ul>")
    return "".join(p)


def _alle_incidents_html(d: dict[str, Any]) -> str:
    rows = d.get("rows") or []
    kpi = d.get("kpi") or {}
    p: list[str] = []
    p.append("<h2>Kennzahlen</h2><table>"
             f"<tr><td>Incidents gesamt</td><td>{kpi.get('total', 0)}</td></tr>"
             f"<tr><td>davon geschlossen</td><td>{kpi.get('closed', 0)}</td></tr>"
             f"<tr><td>MTTA (Ø)</td><td>{kpi.get('mtta_hours') if kpi.get('mtta_hours') is not None else '–'} h</td></tr>"
             f"<tr><td>MTTR (Ø)</td><td>{kpi.get('mttr_hours') if kpi.get('mttr_hours') is not None else '–'} h</td></tr>"
             f"<tr><td>SLA eingehalten / verletzt</td><td>{kpi.get('sla_within', 0)} / {kpi.get('sla_breached', 0)}</td></tr>"
             "</table>")
    p.append(f"<h2>Incidents im Zeitraum ({len(rows)})</h2>")
    if not rows:
        return "".join(p) + "<p>— Keine Incidents im Zeitraum —</p>"
    p.append("<table><tr><th>ID</th><th>Titel</th><th>Schwere</th><th>Klassifikation</th>"
             "<th>Status</th><th>MTTA</th><th>MTTR</th><th>Dauer</th><th>SLA</th></tr>")
    for r in rows:
        sla = "—" if r.get("_sla_ok") is None else ("✓" if r["_sla_ok"] else "verletzt")
        p.append(f"<tr><td>{r.get('id')}</td><td>{escape(str(r.get('titel', '')))}</td>"
                 f"<td>{_SEV.get(r.get('severity'), r.get('severity', ''))}</td>"
                 f"<td>{escape(str(r.get('klassifikation') or '—'))}</td>"
                 f"<td>{_IST.get(r.get('status'), r.get('status', ''))}</td>"
                 f"<td>{_fmt_dauer(r.get('_mtta'))}</td>"
                 f"<td>{_fmt_dauer(r.get('_mttr'))}</td>"
                 f"<td>{_fmt_dauer(r.get('_dauer'))}</td>"
                 f"<td>{sla}</td></tr>")
    p.append("</table>")
    return "".join(p)


def _alle_alarme_html(d: dict[str, Any]) -> str:
    rows = d.get("rows") or []
    kpi = d.get("kpi") or {}
    p: list[str] = []
    p.append("<h2>Kennzahlen</h2><table>"
             f"<tr><td>Alarme gesamt</td><td>{kpi.get('total', 0)}</td></tr>"
             f"<tr><td>davon triagiert</td><td>{kpi.get('triaged', 0)}</td></tr>"
             f"<tr><td>mit IOC-Treffer</td><td>{kpi.get('ioc_hits', 0)}</td></tr>"
             f"<tr><td>Ø Zeit bis Triage</td><td>{kpi.get('avg_triage_hours') if kpi.get('avg_triage_hours') is not None else '–'} h</td></tr>"
             "</table>")
    p.append(f"<h2>Alarme im Zeitraum ({len(rows)})</h2>")
    if not rows:
        return "".join(p) + "<p>— Keine Alarme im Zeitraum —</p>"
    p.append("<table><tr><th>Schwere</th><th>Regel</th><th>Beschreibung</th><th>Asset</th>"
             "<th>Triage-Status</th><th>Zeit bis Triage</th><th>IOC</th><th>Zeitpunkt</th></tr>")
    for r in rows:
        ioc = r.get("_ioc_count") or 0
        p.append(f"<tr><td>{_SEV.get(r.get('severity'), r.get('severity', ''))}</td>"
                 f"<td>{escape(str(r.get('rule_id') or '—'))}/L{r.get('rule_level', 0)}</td>"
                 f"<td>{escape(str(r.get('description', '')))}</td>"
                 f"<td>{escape(str(r.get('agent_name') or '—'))}</td>"
                 f"<td>{_AST.get(r.get('status'), r.get('status', ''))}</td>"
                 f"<td>{_fmt_dauer(r.get('_ttt'))}</td>"
                 f"<td>{('⚠ ' + str(ioc)) if ioc else '—'}</td>"
                 f"<td>{escape(str(r.get('event_ts') or r.get('ingested_at') or ''))}</td></tr>")
    p.append("</table>")
    return "".join(p)


# ── Renderer (DOCX/PDF) ──────────────────────────────────────────────────────

def render_docx(db_path: Path, typ: str, *, von: str | None = None,
                bis: str | None = None) -> bytes:
    from docx import Document

    from shared.documents.export import _html_to_docx
    data = build_data(db_path, typ, von=von, bis=bis)
    doc = Document()
    _html_to_docx(doc, render_html(data))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


def render_pdf(db_path: Path, typ: str, *, von: str | None = None,
               bis: str | None = None) -> bytes:
    from shared.templates.pdf_converter import convert_docx_to_pdf
    return convert_docx_to_pdf(render_docx(db_path, typ, von=von, bis=bis))


# ── Automatisch erzeugte Berichte: Ablage + Lauf-Historie (#1350) ───────────

BERICHTE_DIR = Path("data/soc/berichte")

_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS soc_bericht_runs (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    typ         TEXT NOT NULL,
    periode     TEXT NOT NULL DEFAULT '',          -- z.B. 'quartal' | 'jahr'
    von         TEXT NOT NULL DEFAULT '',
    bis         TEXT NOT NULL DEFAULT '',
    format      TEXT NOT NULL DEFAULT 'docx',
    dateiname   TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'finished',  -- finished | failed
    fehler      TEXT NOT NULL DEFAULT '',
    erzeugt_von TEXT NOT NULL DEFAULT 'scheduler',
    created_at  TEXT DEFAULT (aics_now())
);
"""


def ensure_history(db_path: Path) -> None:
    con = _connect(db_path)
    try:
        con.executescript(_HISTORY_SCHEMA)
        con.commit()
    finally:
        con.close()


def record_run(db_path: Path, *, typ: str, periode: str, von: str, bis: str,
               fmt: str, dateiname: str, status: str = "finished",
               fehler: str = "", erzeugt_von: str = "scheduler") -> int:
    ensure_history(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO soc_bericht_runs(typ, periode, von, bis, format, dateiname,
               status, fehler, erzeugt_von) VALUES(?,?,?,?,?,?,?,?,?) RETURNING id""",
            (typ, periode, von, bis, fmt, dateiname, status, fehler, erzeugt_von))
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def list_runs(db_path: Path, *, limit: int = 100) -> list[dict[str, Any]]:
    ensure_history(db_path)
    con = _connect(db_path)
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM soc_bericht_runs ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()]
    finally:
        con.close()


def _safe_name(typ: str, von: str, bis: str, fmt: str) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"soc_{typ}_{von}_{bis}_{stamp}.{fmt}"


def generate_and_store(db_path: Path, typ: str, *, von: str | None = None,
                       bis: str | None = None, fmt: str = "docx", periode: str = "",
                       erzeugt_von: str = "scheduler") -> dict[str, Any]:
    """Erzeugt einen Bericht, legt ihn unter ``data/soc/berichte/`` ab und protokolliert.

    PDF wird versucht; ist der Konverter (Gotenberg/soffice) nicht erreichbar,
    fällt die Erzeugung auf DOCX zurück (kein harter Fehler im Scheduler).
    """
    von_ts, bis_ts = normalize_zeitraum(von, bis)
    von_d, bis_d = von_ts[:10], bis_ts[:10]
    BERICHTE_DIR.mkdir(parents=True, exist_ok=True)
    use_fmt = (fmt or "docx").lower()
    try:
        if use_fmt == "pdf":
            try:
                data = render_pdf(db_path, typ, von=von_d, bis=bis_d)
            except Exception:  # noqa: BLE001 — Konverter weg → DOCX-Fallback
                use_fmt = "docx"
                data = render_docx(db_path, typ, von=von_d, bis=bis_d)
        else:
            data = render_docx(db_path, typ, von=von_d, bis=bis_d)
        name = _safe_name(typ, von_d, bis_d, use_fmt)
        (BERICHTE_DIR / name).write_bytes(data)
        rid = record_run(db_path, typ=typ, periode=periode, von=von_d, bis=bis_d,
                         fmt=use_fmt, dateiname=name, erzeugt_von=erzeugt_von)
        return {"ok": True, "id": rid, "dateiname": name, "format": use_fmt}
    except Exception as e:  # noqa: BLE001
        record_run(db_path, typ=typ, periode=periode, von=von_d, bis=bis_d,
                   fmt=use_fmt, dateiname="", status="failed", fehler=str(e),
                   erzeugt_von=erzeugt_von)
        return {"ok": False, "error": str(e)}


def read_stored(name: str) -> bytes | None:
    """Liest einen abgelegten Auto-Bericht (Pfad-traversal-sicher)."""
    if "/" in name or "\\" in name or ".." in name:
        return None
    fp = (BERICHTE_DIR / name).resolve()
    try:
        if fp.parent != BERICHTE_DIR.resolve() or not fp.is_file():
            return None
        return fp.read_bytes()
    except OSError:
        return None


# ── After-Action-Report (ISO 22398, #1351) ─────────────────────────────────
# Eigenständiger Renderer im Stil der Berichts-Center-Reports, aber je Übung
# (nicht zeitraum-basiert). Layout: Stammdaten, Ziele+Soll/Ist-Bewertung,
# MSEL-Verlauf, Stärken/Verbesserung, Lessons Learned, Empfehlungen,
# Improvement Plan (Owner/Frist/Status).

_UEB_LIFECYCLE_LABEL = {"design": "Design", "develop": "Develop", "conduct": "Conduct",
                        "evaluate": "Evaluate", "improve": "Improve"}
_ZIEL_TYP_LABEL = {"orientation": "Orientierung", "learning": "Lernen",
                   "cooperation": "Kooperation", "experimenting": "Experimentieren",
                   "testing": "Test"}
_ZIEL_BEW_LABEL = {"offen": "offen", "erfuellt": "erfüllt", "teilweise": "teilweise",
                   "nicht_erfuellt": "nicht erfüllt"}
_INJECT_STATUS_LABEL = {"geplant": "geplant", "injiziert": "injiziert",
                        "bewaeltigt": "bewältigt", "verpasst": "verpasst"}


def build_aar_data(db_path: Path, uebung_id: int) -> dict[str, Any] | None:
    """Sammelt alle AAR-Daten einer Übung (Stammdaten + Ziele + Injects + Plan)."""
    from soc import uebungen
    ensure_db(db_path)
    return uebungen.get_uebung(db_path, uebung_id, with_details=True)


def render_aar_html(u: dict[str, Any]) -> str:
    """ISO-22398-konformes After-Action-Report-Layout als HTML."""
    p: list[str] = []
    titel = escape(str(u.get("titel") or ""))
    p.append(f"<h1>After-Action-Report: {titel}</h1>")
    p.append("<p>Normbezug: ISO 22398 (Übungs-Lebenszyklus) · ISO/IEC 27035 "
             "(Lessons Learnt) · BSI DER.4 · "
             f"Erstellt (UTC): {escape(datetime.utcnow().strftime(_FMT))}</p>")
    # Stammdaten
    typ_lbl = "Detection-Test" if u.get("typ") == "detection_test" else "Tabletop"
    p.append("<h2>1. Übungs-Stammdaten</h2><table>"
             f"<tr><td>Übungstyp</td><td>{escape(typ_lbl)}</td></tr>"
             f"<tr><td>Datum</td><td>{escape(str(u.get('datum') or '—'))}</td></tr>"
             f"<tr><td>Lebenszyklus-Phase</td><td>{escape(_UEB_LIFECYCLE_LABEL.get(u.get('lifecycle'), str(u.get('lifecycle') or '—')))}</td></tr>"
             f"<tr><td>Status</td><td>{escape(str(u.get('status') or '—'))}</td></tr>"
             f"<tr><td>Gesamtergebnis</td><td>{escape(str(u.get('ergebnis') or '—'))}</td></tr>"
             f"<tr><td>Übungsleitung</td><td>{escape(str(u.get('uebungsleitung') or '—'))}</td></tr>"
             f"<tr><td>Moderator</td><td>{escape(str(u.get('moderator') or '—'))}</td></tr>"
             f"<tr><td>Evaluator</td><td>{escape(str(u.get('evaluator') or '—'))}</td></tr>"
             f"<tr><td>Teilnehmer</td><td>{escape(str(u.get('teilnehmer') or '—'))}</td></tr>"
             "</table>")
    if u.get("szenario"):
        p.append(f"<h3>Szenario</h3><p>{escape(str(u['szenario']))}</p>")
    if u.get("explan"):
        p.append(f"<h3>Übungsplan (EXPLAN)</h3><p>{escape(str(u['explan']))}</p>")
    # Ziele + Bewertung Soll/Ist
    ziele = u.get("ziele") or []
    p.append(f"<h2>2. Übungsziele &amp; Bewertung ({len(ziele)})</h2>")
    if ziele:
        p.append("<table><tr><th>Ziel</th><th>Typ</th><th>Bewertungskriterien</th>"
                 "<th>Soll</th><th>Ist</th><th>Bewertung</th></tr>")
        for z in ziele:
            p.append(f"<tr><td>{escape(str(z.get('ziel') or ''))}</td>"
                     f"<td>{escape(_ZIEL_TYP_LABEL.get(z.get('typ'), str(z.get('typ') or '')))}</td>"
                     f"<td>{escape(str(z.get('kriterien') or '—'))}</td>"
                     f"<td>{escape(str(z.get('soll') or '—'))}</td>"
                     f"<td>{escape(str(z.get('ist') or '—'))}</td>"
                     f"<td>{escape(_ZIEL_BEW_LABEL.get(z.get('bewertung'), str(z.get('bewertung') or '')))}</td></tr>")
        p.append("</table>")
    else:
        p.append("<p>— Keine Ziele definiert —</p>")
    # MSEL-Verlauf
    injects = u.get("injects") or []
    p.append(f"<h2>3. Szenario-Verlauf (MSEL · {len(injects)} Injects)</h2>")
    if injects:
        p.append("<table><tr><th>Zeit</th><th>Inject</th><th>Erwartete Reaktion</th>"
                 "<th>Tatsächliche Reaktion</th><th>Status</th></tr>")
        for inj in injects:
            p.append(f"<tr><td>{escape(str(inj.get('zeit') or '—'))}</td>"
                     f"<td>{escape(str(inj.get('beschreibung') or ''))}</td>"
                     f"<td>{escape(str(inj.get('erwartete_reaktion') or '—'))}</td>"
                     f"<td>{escape(str(inj.get('tatsaechliche_reaktion') or '—'))}</td>"
                     f"<td>{escape(_INJECT_STATUS_LABEL.get(inj.get('status'), str(inj.get('status') or '')))}</td></tr>")
        p.append("</table>")
    else:
        p.append("<p>— Keine Injects erfasst —</p>")
    # Detection-Test Soll/Ist (falls befüllt)
    if u.get("erwartete_erkennung") or u.get("tatsaechliche_erkennung"):
        p.append("<h2>Detektions-Test (Soll/Ist)</h2><table>"
                 f"<tr><td>Erwartete Erkennung</td><td>{escape(str(u.get('erwartete_erkennung') or '—'))}</td></tr>"
                 f"<tr><td>Tatsächliche Erkennung</td><td>{escape(str(u.get('tatsaechliche_erkennung') or '—'))}</td></tr>"
                 "</table>")
    # AAR-Bewertung
    p.append("<h2>4. Auswertung (After-Action-Review)</h2>")
    if u.get("auswertung"):
        p.append(f"<h3>Gesamtauswertung</h3><p>{escape(str(u['auswertung']))}</p>")
    p.append(f"<h3>Stärken</h3><p>{escape(str(u.get('aar_staerken') or '—'))}</p>")
    p.append(f"<h3>Verbesserungsbereiche</h3><p>{escape(str(u.get('aar_verbesserung') or '—'))}</p>")
    p.append(f"<h3>Lessons Learned (ISO/IEC 27035)</h3><p>{escape(str(u.get('aar_lessons') or '—'))}</p>")
    p.append(f"<h3>Empfehlungen</h3><p>{escape(str(u.get('aar_empfehlungen') or '—'))}</p>")
    # Improvement Plan
    plan = u.get("massnahmen_plan") or []
    p.append(f"<h2>5. Improvement Plan / Korrekturmaßnahmen ({len(plan)})</h2>")
    if plan:
        p.append("<table><tr><th>Maßnahme</th><th>Owner</th><th>Frist</th><th>Status</th><th>Erledigt am</th></tr>")
        for m in plan:
            p.append(f"<tr><td>{escape(str(m.get('beschreibung') or ''))}</td>"
                     f"<td>{escape(str(m.get('owner') or '—'))}</td>"
                     f"<td>{escape(str(m.get('frist') or '—'))}</td>"
                     f"<td>{escape(str(m.get('status') or ''))}</td>"
                     f"<td>{escape(str(m.get('done_at') or '—'))}</td></tr>")
        p.append("</table>")
    else:
        p.append("<p>— Keine Korrekturmaßnahmen erfasst —</p>")
    # Sign-off
    if u.get("aar_signoff_by"):
        p.append("<h2>6. Freigabe</h2>"
                 f"<p>Freigegeben durch: {escape(str(u.get('aar_signoff_by')))} "
                 f"am {escape(str(u.get('aar_signoff_at') or '—'))}</p>")
    return "".join(p)


def render_aar_docx(db_path: Path, uebung_id: int) -> bytes:
    from docx import Document

    from shared.documents.export import _html_to_docx
    u = build_aar_data(db_path, uebung_id)
    if not u:
        raise ValueError("Übung nicht gefunden")
    doc = Document()
    _html_to_docx(doc, render_aar_html(u))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


def render_aar_pdf(db_path: Path, uebung_id: int) -> bytes:
    from shared.templates.pdf_converter import convert_docx_to_pdf
    return convert_docx_to_pdf(render_aar_docx(db_path, uebung_id))


def quarter_range(*, today=None) -> tuple[str, str, str]:
    """(von, bis, periode-Label) des zuletzt abgeschlossenen Quartals."""
    from datetime import date
    t = today or date.today()
    q = (t.month - 1) // 3  # 0..3 des aktuellen Quartals
    year = t.year
    if q == 0:
        year, sq = t.year - 1, 3
    else:
        sq = q - 1
    start_month = sq * 3 + 1
    von = date(year, start_month, 1)
    end_month = start_month + 2
    from calendar import monthrange
    bis = date(year, end_month, monthrange(year, end_month)[1])
    return von.isoformat(), bis.isoformat(), f"Q{sq + 1}/{year}"


def year_range(*, today=None) -> tuple[str, str, str]:
    """(von, bis, periode-Label) des zuletzt abgeschlossenen Kalenderjahres."""
    from datetime import date
    t = today or date.today()
    y = t.year - 1
    return date(y, 1, 1).isoformat(), date(y, 12, 31).isoformat(), str(y)
