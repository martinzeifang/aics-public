"""SOC — Threat-Intelligence: IOC-Feeds + Alarm-Anreicherung (#1322).

IOC-Feeds (IP/Domain/Hash/URL) pflegen/importieren (CSV/STIX-light) und Alarme
bei Match markieren + priorisieren. IOC-Treffer sind im Alarm-/Incident-Detail
sichtbar und heben die Severity an (Priorisierungs-Hinweis).

Normbezug: ISO/IEC 27001 A.5.7 (Threat Intelligence) · SOC-CMM Services ·
NIST CSF Identify.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from soc.db import _connect, ensure_db

IOC_TYPES = ["ip", "domain", "hash", "url"]
_SEV_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def list_iocs(db_path: Path, *, only_active: bool = False) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute("SELECT * FROM soc_iocs ORDER BY typ, wert").fetchall()
    finally:
        con.close()
    out = [dict(r) for r in rows]
    if only_active:
        today = date.today().isoformat()
        out = [i for i in out if i["enabled"] and (not i["gueltig_bis"] or i["gueltig_bis"] >= today)]
    return out


def save_ioc(db_path: Path, *, id: int | None = None, typ: str, wert: str, quelle: str = "",
             confidence: int = 50, beschreibung: str = "", gueltig_bis: str = "",
             enabled: bool = True, actor: str = "") -> int:
    ensure_db(db_path)
    wert = (wert or "").strip().lower()
    con = _connect(db_path)
    try:
        if id:
            con.execute("""UPDATE soc_iocs SET typ=?, wert=?, quelle=?, confidence=?,
                           beschreibung=?, gueltig_bis=?, enabled=? WHERE id=?""",
                        (typ, wert, quelle, int(confidence), beschreibung, gueltig_bis,
                         1 if enabled else 0, id))
            iid = id
        else:
            cur = con.execute("""INSERT INTO soc_iocs(typ, wert, quelle, confidence, beschreibung,
                                 gueltig_bis, enabled, created_by) VALUES(?,?,?,?,?,?,?,?)
                                 ON CONFLICT(typ, wert) DO UPDATE SET quelle=excluded.quelle,
                                 confidence=excluded.confidence, beschreibung=excluded.beschreibung,
                                 gueltig_bis=excluded.gueltig_bis, enabled=excluded.enabled""",
                              (typ, wert, quelle, int(confidence), beschreibung, gueltig_bis,
                               1 if enabled else 0, actor))
            iid = int(cur.lastrowid) or _id_of(con, typ, wert)
        con.commit()
        return iid
    finally:
        con.close()


def _id_of(con, typ: str, wert: str) -> int:
    r = con.execute("SELECT id FROM soc_iocs WHERE typ=? AND wert=?", (typ, wert)).fetchone()
    return int(r["id"]) if r else 0


def delete_ioc(db_path: Path, ioc_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_iocs WHERE id=?", (ioc_id,))
        con.commit()
    finally:
        con.close()


_TYPE_GUESS = [
    ("hash", re.compile(r"^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{40}$|^[a-fA-F0-9]{64}$")),
    ("ip", re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")),
    ("url", re.compile(r"^https?://", re.I)),
]


def _guess_type(value: str) -> str:
    for t, rx in _TYPE_GUESS:
        if rx.search(value):
            return t
    return "domain"


def import_iocs(db_path: Path, text: str, *, quelle: str = "import", actor: str = "") -> int:
    """CSV/STIX-light-Import: je Zeile ``wert[;typ[;confidence[;beschreibung]]]``.

    Typ wird bei Bedarf erraten. Reine Wertlisten (eine pro Zeile) funktionieren.
    """
    n = 0
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in re.split(r"[;,\t]", line)]
        wert = parts[0]
        if not wert:
            continue
        typ = parts[1].lower() if len(parts) > 1 and parts[1].lower() in IOC_TYPES else _guess_type(wert)
        conf = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 50
        desc = parts[3] if len(parts) > 3 else ""
        save_ioc(db_path, typ=typ, wert=wert, quelle=quelle, confidence=conf,
                 beschreibung=desc, actor=actor)
        n += 1
    return n


def match_alert(alert: dict[str, Any], iocs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Findet IOC-Treffer für einen (normalisierten) Alarm."""
    srcip = (alert.get("srcip") or "").lower()
    haystack = " ".join(str(alert.get(k, "")) for k in ("description", "full_log", "srcip")).lower()
    try:
        haystack += " " + json.dumps(alert.get("raw_json", {}), default=str).lower()
    except (TypeError, ValueError):
        pass
    hits = []
    for ioc in iocs:
        val = ioc["wert"]
        if not val:
            continue
        matched = (val == srcip) if ioc["typ"] == "ip" else (val in haystack)
        if matched:
            hits.append({"typ": ioc["typ"], "wert": val, "quelle": ioc.get("quelle", ""),
                         "confidence": ioc.get("confidence", 50)})
    return hits


def enrich_alert(alert: dict[str, Any], iocs: list[dict[str, Any]]) -> dict[str, Any]:
    """Setzt ``ioc_hits`` und hebt bei Treffer die Severity auf mind. ``high`` an."""
    hits = match_alert(alert, iocs)
    alert["ioc_hits"] = hits
    if hits and _SEV_ORDER.get(alert.get("severity", "low"), 0) < _SEV_ORDER["high"]:
        alert["severity"] = "high"  # Priorisierungs-Hinweis durch Threat-Intel
    return alert


def rescan_alerts(db_path: Path, *, limit: int = 2000) -> int:
    """Berechnet ``ioc_hits`` für bestehende Alarme neu (nach IOC-Pflege)."""
    iocs = list_iocs(db_path, only_active=True)
    con = _connect(db_path)
    updated = 0
    try:
        rows = con.execute(
            "SELECT id, description, full_log, srcip, raw_json FROM soc_alerts ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
        for r in rows:
            try:
                raw = json.loads(r["raw_json"] or "{}")
            except (ValueError, TypeError):
                raw = {}
            hits = match_alert({"description": r["description"], "full_log": r["full_log"],
                                "srcip": r["srcip"], "raw_json": raw}, iocs)
            con.execute("UPDATE soc_alerts SET ioc_hits=? WHERE id=?",
                        (json.dumps(hits), r["id"]))
            if hits:
                updated += 1
        con.commit()
    finally:
        con.close()
    return updated


def alerts_with_iocs(db_path: Path, *, limit: int = 200) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM soc_alerts WHERE ioc_hits != '[]' ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["ioc_hits"] = json.loads(d.get("ioc_hits") or "[]")
        except (ValueError, TypeError):
            d["ioc_hits"] = []
        out.append(d)
    return out
