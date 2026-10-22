"""SOC — Log-Source-/Coverage-Management + Health (#1324).

Übersicht der angebundenen Log-Quellen/Agenten: was ist onboarded, sendet es noch
(Health), welche kritischen Assets/Quellen fehlen (Coverage-Lücke). Weitgehend aus
Assets (#1309: agent_status/last_keepalive) + tatsächlichen Alarmen abgeleitet, plus
ein optionales Register für Nicht-Agent-Quellen (Syslog/Firewall/Cloud).

Normbezug: BSI DER.1 · OPS.1.1.5 (Protokollierung) · NIST CSF Detect.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc.db import _connect, ensure_db


def list_sources(db_path: Path) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM soc_log_sources ORDER BY name").fetchall()]
    finally:
        con.close()


def save_source(db_path: Path, *, id: int | None = None, name: str, typ: str = "",
                erwartet: bool = True, notizen: str = "") -> int:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if id:
            con.execute("UPDATE soc_log_sources SET name=?, typ=?, erwartet=?, notizen=? WHERE id=?",
                        (name, typ, 1 if erwartet else 0, notizen, id))
            sid = id
        else:
            cur = con.execute("""INSERT INTO soc_log_sources(name, typ, erwartet, notizen)
                                 VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET typ=excluded.typ,
                                 erwartet=excluded.erwartet, notizen=excluded.notizen""",
                              (name, typ, 1 if erwartet else 0, notizen))
            sid = int(cur.lastrowid)
        con.commit()
        return sid
    finally:
        con.close()


def delete_source(db_path: Path, source_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_log_sources WHERE id=?", (source_id,))
        con.commit()
    finally:
        con.close()


def _age_days(ts: str) -> float | None:
    if not ts:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            dt = datetime.strptime(ts[:26], fmt).replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
        except ValueError:
            continue
    return None


def health(db_path: Path, *, silent_days: int = 7) -> dict[str, Any]:
    """Health je Log-Quelle: aktiv | still | offline | unbekannt + Coverage-Lücken."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        assets = [dict(r) for r in con.execute(
            """SELECT agent_name, agent_status, last_keepalive, kritikalitaet, lifecycle, os
               FROM soc_assets WHERE agent_name != ''""").fetchall()]
        last_alert = {r["agent_name"]: r for r in con.execute(
            """SELECT agent_name, MAX(event_ts) AS last_ts, COUNT(*) AS cnt
               FROM soc_alerts WHERE agent_name != '' GROUP BY agent_name""").fetchall()}
        manual = [dict(r) for r in con.execute("SELECT * FROM soc_log_sources").fetchall()]
    finally:
        con.close()

    rows: list[dict[str, Any]] = []
    seen = set()
    for a in assets:
        name = a["agent_name"]
        seen.add(name)
        la = last_alert.get(name)
        last_ts = la["last_ts"] if la else ""
        age = _age_days(last_ts) if last_ts else _age_days(a.get("last_keepalive") or "")
        st = (a.get("agent_status") or "").lower()
        if st in ("disconnected", "never_connected"):
            status = "offline"
        elif age is None:
            status = "unbekannt"
        elif age > silent_days:
            status = "still"
        else:
            status = "aktiv"
        is_gap = (int(a.get("kritikalitaet") or 3) >= 4) and status in ("offline", "still", "unbekannt")
        rows.append({"name": name, "typ": "agent", "erwartet": 1, "kritikalitaet": a.get("kritikalitaet"),
                     "agent_status": a.get("agent_status"), "last_eingang": last_ts,
                     "alert_count": (la["cnt"] if la else 0), "age_days": round(age, 1) if age is not None else None,
                     "status": status, "is_gap": is_gap, "os": a.get("os")})

    # Manuelle Nicht-Agent-Quellen (sofern nicht schon als Agent erfasst)
    for m in manual:
        if m["name"] in seen:
            continue
        la = last_alert.get(m["name"])
        last_ts = la["last_ts"] if la else ""
        age = _age_days(last_ts) if last_ts else None
        if age is None:
            status = "unbekannt"
        elif age > silent_days:
            status = "still"
        else:
            status = "aktiv"
        rows.append({"name": m["name"], "typ": m["typ"] or "quelle", "erwartet": m["erwartet"],
                     "kritikalitaet": None, "agent_status": None, "last_eingang": last_ts,
                     "alert_count": (la["cnt"] if la else 0), "age_days": round(age, 1) if age is not None else None,
                     "status": status, "is_gap": (m["erwartet"] and status != "aktiv"), "notizen": m["notizen"]})

    counts = {"aktiv": 0, "still": 0, "offline": 0, "unbekannt": 0}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    gaps = [r for r in rows if r["is_gap"]]
    return {"sources": sorted(rows, key=lambda r: (not r["is_gap"], r["name"])),
            "counts": counts, "gap_count": len(gaps), "silent_days": silent_days}
