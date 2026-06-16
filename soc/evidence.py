"""SOC — Beweissicherung / Asservaten + Chain of Custody (#1317).

Beweismittel je Incident: Datei-Upload + Rohlog-Snapshot, SHA-256-gesichert,
Magic-Bytes-validiert, mit lückenloser Chain of Custody (wer/wann/Aktion) und
konfigurierbarer Aufbewahrungsfrist. Muster: Gutachten-Final-Archiv.

Normbezug: ISO/IEC 27037 (Chain of Custody) · BSI DER.2.2 (IT-Forensik-Vorsorge).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from security_utils import safe_generated_file, workspace_root_from
from soc.db import _append_timeline, _connect, ensure_db, get_incident, get_incident_alerts

_BASE = Path("data/soc/evidence")
MAX_EVIDENCE_BYTES = 100 * 1024 * 1024  # 100 MB pro Asservat

# Forensik-freundliche Endungen. Für die „starken" Typen (PDF/Office/Text) prüfen
# wir Magic-Bytes; für Roh-/Binärformate (Logs, PCAP, Bilder) genügt Größen-/
# Leer-Prüfung, da Asservate beliebige Binärinhalte sein dürfen.
_STRICT_SUFFIXES = {".pdf", ".docx", ".xlsx", ".pptx", ".zip", ".txt", ".log", ".csv", ".md", ".json"}
_ALLOWED_SUFFIXES = _STRICT_SUFFIXES | {
    ".pcap", ".pcapng", ".evtx", ".bin", ".dmp", ".mem", ".png", ".jpg", ".jpeg",
    ".gif", ".eml", ".msg", ".xml", ".yara", ".ioc", ".har", ".pem", ".cer",
}


def _safe(p: Path) -> Path:
    return safe_generated_file(p, workspace_root_from(Path(__file__)))


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate(filename: str, data: bytes) -> str:
    if not data:
        raise ValueError("Leere Datei wird abgelehnt")
    if len(data) > MAX_EVIDENCE_BYTES:
        raise ValueError(f"Datei zu groß (max. {MAX_EVIDENCE_BYTES // (1024 * 1024)} MB)")
    sfx = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""
    if sfx not in _ALLOWED_SUFFIXES:
        raise ValueError(f"Dateityp {sfx or '(ohne Endung)'} nicht erlaubt")
    # Magic-Bytes nur für die „starken" Office/PDF-Typen erzwingen
    if sfx in {".pdf", ".docx", ".xlsx", ".pptx", ".zip"}:
        from shared.upload_validation import validate_magic_bytes
        validate_magic_bytes(data[:8], suffix=sfx)
    return sfx


def _record(con, evidence_id: int, action: str, actor: str, note: str = "") -> None:
    con.execute("INSERT INTO soc_custody(evidence_id, action, actor, note) VALUES(?,?,?,?)",
                (evidence_id, action, actor, note))


def add_evidence(db_path: Path, incident_id: int, *, filename: str, data: bytes,
                 content_type: str = "", retention_days: int = 365, beschreibung: str = "",
                 actor: str = "") -> dict[str, Any]:
    """Speichert ein Asservat (Datei) integritätsgesichert + Chain-of-Custody-Eintrag."""
    ensure_db(db_path)
    if not get_incident(db_path, incident_id):
        return {"ok": False, "error": "Incident nicht gefunden"}
    _validate(filename, data)
    sha = compute_sha256(data)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:120] or "asservat"
    retention_until = (datetime.now(timezone.utc) + timedelta(days=max(1, int(retention_days)))).strftime("%Y-%m-%d")
    con = _connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO soc_evidence(incident_id, kind, filename, content_type, size, sha256,
               retention_until, beschreibung, created_by) VALUES(?,?,?,?,?,?,?,?,?)""",
            (incident_id, "file", filename, content_type, len(data), sha, retention_until,
             beschreibung, actor))
        eid = int(cur.lastrowid)
        stored = f"{eid}_{sha[:12]}_{safe_name}"
        target = _safe(_BASE / str(incident_id) / stored)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        con.execute("UPDATE soc_evidence SET stored_name=? WHERE id=?", (stored, eid))
        _record(con, eid, "added", actor, f"{filename} ({len(data)} B, sha256:{sha[:12]}…)")
        con.commit()
    finally:
        con.close()
    _append_timeline(db_path, incident_id, actor=actor, event="evidence.added",
                     detail=f"Asservat '{filename}' gesichert (sha256:{sha[:12]}…)")
    return {"ok": True, "id": eid, "sha256": sha}


def freeze_log_snapshot(db_path: Path, incident_id: int, *, actor: str = "",
                        retention_days: int = 365) -> dict[str, Any]:
    """Friert die verknüpften Alarme als unveränderliches JSON-Asservat ein."""
    ensure_db(db_path)
    inc = get_incident(db_path, incident_id)
    if not inc:
        return {"ok": False, "error": "Incident nicht gefunden"}
    alerts = get_incident_alerts(db_path, incident_id)
    snapshot = {
        "incident_id": incident_id, "titel": inc.get("titel"),
        "frozen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "frozen_by": actor, "alert_count": len(alerts), "alerts": alerts,
    }
    data = json.dumps(snapshot, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    fname = f"rohlog-snapshot_incident-{incident_id}.json"
    res = add_evidence(db_path, incident_id, filename=fname, data=data,
                       content_type="application/json", retention_days=retention_days,
                       beschreibung=f"Eingefrorener Rohlog-Snapshot ({len(alerts)} Alarme)",
                       actor=actor)
    if res.get("ok"):
        con = _connect(db_path)
        try:
            con.execute("UPDATE soc_evidence SET kind='log_snapshot' WHERE id=?", (res["id"],))
            _record(con, res["id"], "frozen", actor, f"{len(alerts)} Alarme eingefroren")
            con.commit()
        finally:
            con.close()
    return res


def list_evidence(db_path: Path, incident_id: int) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM soc_evidence WHERE incident_id=? ORDER BY id DESC", (incident_id,)).fetchall()]
    finally:
        con.close()


def get_evidence(db_path: Path, evidence_id: int) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM soc_evidence WHERE id=?", (evidence_id,)).fetchone()
        return dict(r) if r else None
    finally:
        con.close()


def list_custody(db_path: Path, evidence_id: int) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM soc_custody WHERE evidence_id=? ORDER BY id", (evidence_id,)).fetchall()]
    finally:
        con.close()


def read_evidence_file(db_path: Path, evidence_id: int, *, action: str = "viewed",
                       actor: str = "") -> tuple[bytes, dict[str, Any]] | None:
    """Liest den Asservat-Inhalt + protokolliert den Zugriff in der Chain of Custody."""
    ev = get_evidence(db_path, evidence_id)
    if not ev or ev.get("deleted_at") or not ev.get("stored_name"):
        return None
    target = _safe(_BASE / str(ev["incident_id"]) / ev["stored_name"])
    if not target.exists():
        return None
    data = target.read_bytes()
    con = _connect(db_path)
    try:
        _record(con, evidence_id, action, actor)
        con.commit()
    finally:
        con.close()
    return data, ev


def delete_evidence(db_path: Path, evidence_id: int, *, reason: str, actor: str = "") -> dict[str, Any]:
    """Soft-Delete: Datei wird entfernt, Metadaten + Chain of Custody bleiben erhalten."""
    if not reason or len(reason.strip()) < 10:
        return {"ok": False, "error": "Begründung erforderlich (mind. 10 Zeichen)"}
    ev = get_evidence(db_path, evidence_id)
    if not ev:
        return {"ok": False, "error": "Asservat nicht gefunden"}
    if ev.get("deleted_at"):
        return {"ok": False, "error": "Asservat bereits gelöscht"}
    if ev.get("stored_name"):
        target = _safe(_BASE / str(ev["incident_id"]) / ev["stored_name"])
        if target.exists():
            target.unlink()
    con = _connect(db_path)
    try:
        con.execute("""UPDATE soc_evidence SET deleted_at=aics_now(), deleted_by=?,
                       delete_reason=? WHERE id=?""", (actor, reason.strip(), evidence_id))
        _record(con, evidence_id, "deleted", actor, reason.strip())
        con.commit()
    finally:
        con.close()
    _append_timeline(db_path, ev["incident_id"], actor=actor, event="evidence.deleted",
                     detail=f"Asservat #{evidence_id} gelöscht: {reason.strip()}")
    return {"ok": True}
