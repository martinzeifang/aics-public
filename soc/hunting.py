"""SOC — Threat-Hunting: Hypothesen, Ad-hoc-Queries, Findings (#1323).

Proaktive, hypothesengetriebene Hunts dokumentieren: Hypothese (oft ATT&CK-basiert),
ausgeführte (read-only) Indexer-Query, Findings, Ergebnis (bestätigt/verworfen) →
ggf. neuer Incident oder Detection-Use-Case-Vorschlag.

Normbezug: SOC-CMM Services (proaktive Detektion) · NIST CSF Detect/Identify.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from soc import db as sdb
from soc.db import _connect, ensure_db

_FIELDS = ("hypothese", "attack_bezug", "datum", "jaeger", "query", "findings",
           "ergebnis", "status")


def list_hunts(db_path: Path) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM soc_hunts ORDER BY datum DESC, id DESC").fetchall()]
    finally:
        con.close()


def get_hunt(db_path: Path, hunt_id: int) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM soc_hunts WHERE id=?", (hunt_id,)).fetchone()
        return dict(r) if r else None
    finally:
        con.close()


def save_hunt(db_path: Path, *, id: int | None = None, actor: str = "", **fields: Any) -> int:
    ensure_db(db_path)
    data = {k: fields[k] for k in _FIELDS if k in fields}
    con = _connect(db_path)
    try:
        if id:
            if data:
                sets = ", ".join(f"{k}=?" for k in data)
                con.execute(f"UPDATE soc_hunts SET {sets}, updated_at=aics_now() WHERE id=?",
                            (*data.values(), id))
            hid = id
        else:
            data["created_by"] = actor
            cols = ", ".join(data)
            ph = ",".join("?" * len(data))
            cur = con.execute(f"INSERT INTO soc_hunts({cols}) VALUES({ph})", tuple(data.values()))
            hid = int(cur.lastrowid)
        con.commit()
        return hid
    finally:
        con.close()


def delete_hunt(db_path: Path, hunt_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_hunts WHERE id=?", (hunt_id,))
        con.commit()
    finally:
        con.close()


def run_query(db_path: Path, query: str, *, connection_name: str = "default",
              limit: int = 50) -> dict[str, Any]:
    """Führt eine read-only Ad-hoc-Indexer-Query aus (über die gespeicherte Verbindung)."""
    from soc import wazuh_client as wz
    conn = sdb.load_connection(db_path, connection_name, with_secret=True)
    if not conn:
        return {"ok": False, "error": "Keine Wazuh-Verbindung konfiguriert"}
    if conn.get("modus") != "pull":
        return {"ok": False, "error": "Verbindung ist nicht im PULL-Modus (Indexer nötig)"}
    try:
        res = wz.run_query(conn, query, limit=limit)
    except wz.WazuhError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, **res}


def escalate_to_incident(db_path: Path, hunt_id: int, *, titel: str = "", severity: str = "medium",
                         actor: str = "") -> dict[str, Any]:
    """Erzeugt aus einem Hunt-Finding einen Incident und verknüpft ihn (Timeline)."""
    hunt = get_hunt(db_path, hunt_id)
    if not hunt:
        return {"ok": False, "error": "Hunt nicht gefunden"}
    title = (titel or f"Threat-Hunt: {hunt['hypothese'][:80]}").strip()
    beschreibung = (f"Aus Threat-Hunt #{hunt_id} eskaliert.\n\nHypothese: {hunt['hypothese']}\n"
                    f"Query: {hunt['query']}\nFindings: {hunt['findings']}")
    iid = sdb.create_incident(db_path, titel=title, severity=severity,
                              klassifikation="threat_hunt", beschreibung=beschreibung, actor=actor)
    save_hunt(db_path, id=hunt_id, status="abgeschlossen", ergebnis="bestaetigt")
    return {"ok": True, "incident_id": iid}
