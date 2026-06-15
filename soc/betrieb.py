"""SOC — Schicht-/On-Call-Betrieb: Handover, Eskalationsmatrix, RACI (#1318).

Schichtübergabe (Handover-Notizen), Eskalationsmatrix (Severity → Stufe → Rolle/
Person/Frist) und RACI je Vorfallstyp. Im Incident: Eskalationspfad sichtbar +
„eskalieren an Stufe N"-Aktion (dokumentierter Benachrichtigungs-Hinweis).

Normbezug: SOC-CMM People/Process · ISO 27035 Eskalation · NIST CSF Govern.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from soc.db import _append_timeline, _connect, ensure_db, get_incident

# ── Schichtübergabe ─────────────────────────────────────────────────────────

def list_handovers(db_path: Path, *, limit: int = 100) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM soc_handover ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
    finally:
        con.close()


def save_handover(db_path: Path, *, schicht: str, datum: str, von_user: str = "",
                  an_user: str = "", offene_punkte: str = "", notizen: str = "",
                  actor: str = "") -> int:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO soc_handover(schicht, datum, von_user, an_user, offene_punkte,
               notizen, created_by) VALUES(?,?,?,?,?,?,?)""",
            (schicht, datum, von_user, an_user, offene_punkte, notizen, actor))
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def delete_handover(db_path: Path, handover_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_handover WHERE id=?", (handover_id,))
        con.commit()
    finally:
        con.close()


# ── Eskalationsmatrix ───────────────────────────────────────────────────────

_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def list_escalation(db_path: Path, *, severity: str | None = None) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if severity:
            rows = con.execute("SELECT * FROM soc_escalation WHERE severity=? ORDER BY stufe",
                               (severity,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM soc_escalation ORDER BY severity, stufe").fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_escalation(db_path: Path, *, id: int | None = None, severity: str, stufe: int,
                    rolle: str = "", person: str = "", kontakt: str = "",
                    frist_minuten: int = 30) -> int:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if id:
            con.execute("""UPDATE soc_escalation SET severity=?, stufe=?, rolle=?, person=?,
                           kontakt=?, frist_minuten=? WHERE id=?""",
                        (severity, int(stufe), rolle, person, kontakt, int(frist_minuten), id))
            eid = id
        else:
            cur = con.execute("""INSERT INTO soc_escalation(severity, stufe, rolle, person,
                                 kontakt, frist_minuten) VALUES(?,?,?,?,?,?)""",
                              (severity, int(stufe), rolle, person, kontakt, int(frist_minuten)))
            eid = int(cur.lastrowid)
        con.commit()
        return eid
    finally:
        con.close()


def delete_escalation(db_path: Path, escalation_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_escalation WHERE id=?", (escalation_id,))
        con.commit()
    finally:
        con.close()


def escalate_incident(db_path: Path, incident_id: int, stufe: int, *, actor: str = "") -> dict[str, Any]:
    """Dokumentiert eine Eskalation auf Stufe N (Benachrichtigungs-Hinweis, kein Versand)."""
    inc = get_incident(db_path, incident_id)
    if not inc:
        return {"ok": False, "error": "Incident nicht gefunden"}
    targets = [e for e in list_escalation(db_path, severity=inc.get("severity") or "high")
               if e["stufe"] == int(stufe)]
    who = ", ".join(filter(None, [f"{t['rolle']} {t['person']}".strip() for t in targets])) or f"Stufe {stufe}"
    _append_timeline(db_path, incident_id, actor=actor, event="incident.escalated",
                     detail=f"Eskaliert (Stufe {stufe}) an: {who}")
    return {"ok": True, "stufe": int(stufe), "targets": targets, "notified": who}


# ── RACI je Vorfallstyp ─────────────────────────────────────────────────────

def list_raci(db_path: Path, *, vorfallstyp: str | None = None) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if vorfallstyp:
            rows = con.execute("SELECT * FROM soc_raci WHERE vorfallstyp=? ORDER BY id",
                               (vorfallstyp,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM soc_raci ORDER BY vorfallstyp, id").fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_raci(db_path: Path, *, id: int | None = None, vorfallstyp: str, rolle: str,
              raci: str = "R") -> int:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if id:
            con.execute("UPDATE soc_raci SET vorfallstyp=?, rolle=?, raci=? WHERE id=?",
                        (vorfallstyp, rolle, raci, id))
            rid = id
        else:
            cur = con.execute("INSERT INTO soc_raci(vorfallstyp, rolle, raci) VALUES(?,?,?)",
                              (vorfallstyp, rolle, raci))
            rid = int(cur.lastrowid)
        con.commit()
        return rid
    finally:
        con.close()


def delete_raci(db_path: Path, raci_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_raci WHERE id=?", (raci_id,))
        con.commit()
    finally:
        con.close()


def seed_defaults(db_path: Path) -> None:
    """Legt eine sinnvolle Standard-Eskalationsmatrix an, falls leer (idempotent)."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if con.execute("SELECT COUNT(*) c FROM soc_escalation").fetchone()["c"]:
            return
        rows = [
            ("critical", 1, "SOC-Analyst:in", 15), ("critical", 2, "SOC-Lead / IT-Leitung", 30),
            ("critical", 3, "Geschäftsführung / CISO", 60),
            ("high", 1, "SOC-Analyst:in", 30), ("high", 2, "SOC-Lead", 120),
            ("medium", 1, "SOC-Analyst:in", 120),
            ("low", 1, "SOC-Analyst:in", 480),
        ]
        for sev, stufe, rolle, frist in rows:
            con.execute("""INSERT INTO soc_escalation(severity, stufe, rolle, frist_minuten)
                           VALUES(?,?,?,?)""", (sev, stufe, rolle, frist))
        con.commit()
    finally:
        con.close()
