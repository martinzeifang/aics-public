"""SOC — Übungen / Tests: Tabletop-Szenarien + Detection-Tests (#1319).

Geplante und dokumentierte SOC-Übungen: Tabletop (Szenario durchspielen) und
Detection-Tests (löst ein Testalarm die erwartete Erkennung aus?), inkl.
Auswertung und abgeleiteten Maßnahmen.

Normbezug: BSI DER.4 (Notfallmanagement/Übungen) · ISO 27035 'Plan & Prepare' ·
SOC-CMM Process.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from soc.db import _connect, ensure_db

_FIELDS = ("typ", "titel", "szenario", "datum", "teilnehmer", "status",
           "erwartete_erkennung", "tatsaechliche_erkennung", "test_alert_uid",
           "ergebnis", "auswertung", "massnahmen",
           # ISO-22398 (#1351): Lebenszyklus, Rollen, EXPLAN, AAR-Felder
           "lifecycle", "uebungsleitung", "moderator", "evaluator", "explan",
           "aar_staerken", "aar_verbesserung", "aar_lessons", "aar_empfehlungen",
           "aar_signoff_by")

_ZIEL_FIELDS = ("ziel", "typ", "kriterien", "soll", "ist", "bewertung", "sortierung")
_INJECT_FIELDS = ("zeit", "beschreibung", "erwartete_reaktion",
                  "tatsaechliche_reaktion", "status", "sortierung")


def list_uebungen(db_path: Path) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM soc_uebungen ORDER BY datum DESC, id DESC").fetchall()]
    finally:
        con.close()


def get_uebung(db_path: Path, uebung_id: int, *, with_details: bool = False) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM soc_uebungen WHERE id=?", (uebung_id,)).fetchone()
        item = dict(r) if r else None
    finally:
        con.close()
    if item is None:
        return None
    # Nach dem Schließen der eigenen Verbindung nachladen, damit keine geschachtelte
    # Pool-Belegung über die list_*-Aufrufe entsteht.
    if with_details:
        item["ziele"] = list_ziele(db_path, uebung_id)
        item["injects"] = list_injects(db_path, uebung_id)
        item["massnahmen_plan"] = list_massnahmen(db_path, uebung_id)
    return item


def save_uebung(db_path: Path, *, id: int | None = None, actor: str = "", **fields: Any) -> int:
    """Anlegen/Aktualisieren — nur übergebene Felder werden geschrieben (partiell)."""
    ensure_db(db_path)
    data = {k: fields[k] for k in _FIELDS if k in fields}
    con = _connect(db_path)
    try:
        if id:
            if data:
                sets = ", ".join(f"{k}=?" for k in data)
                extra = ""
                # Sign-off-Zeitstempel automatisch beim Setzen der Freigabe (#1351).
                if data.get("aar_signoff_by"):
                    extra = ", aar_signoff_at=CASE WHEN aar_signoff_at IS NULL THEN aics_now() ELSE aar_signoff_at END"
                con.execute(
                    f"UPDATE soc_uebungen SET {sets}{extra}, updated_at=aics_now() WHERE id=?",
                    (*data.values(), id))
            uid = id
        else:
            data.setdefault("typ", "tabletop")
            data["created_by"] = actor
            cols = ", ".join(data)
            ph = ",".join("?" * len(data))
            cur = con.execute(f"INSERT INTO soc_uebungen({cols}) VALUES({ph})", tuple(data.values()))
            uid = int(cur.lastrowid)
        con.commit()
        return uid
    finally:
        con.close()


def delete_uebung(db_path: Path, uebung_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_uebung_ziele WHERE uebung_id=?", (uebung_id,))
        con.execute("DELETE FROM soc_uebung_injects WHERE uebung_id=?", (uebung_id,))
        con.execute("DELETE FROM soc_uebung_massnahmen WHERE uebung_id=?", (uebung_id,))
        con.execute("DELETE FROM soc_uebungen WHERE id=?", (uebung_id,))
        con.commit()
    finally:
        con.close()


# ── Übungsziele (Performance-Objectives, ISO 22398) — CRUD (#1351) ──────────

def list_ziele(db_path: Path, uebung_id: int) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM soc_uebung_ziele WHERE uebung_id=? ORDER BY sortierung, id",
            (uebung_id,)).fetchall()]
    finally:
        con.close()


def save_ziel(db_path: Path, *, id: int | None = None, uebung_id: int | None = None, **fields: Any) -> int:
    ensure_db(db_path)
    data = {k: fields[k] for k in _ZIEL_FIELDS if k in fields}
    con = _connect(db_path)
    try:
        if id:
            if data:
                sets = ", ".join(f"{k}=?" for k in data)
                con.execute(f"UPDATE soc_uebung_ziele SET {sets}, updated_at=aics_now() WHERE id=?",
                            (*data.values(), id))
            zid = id
        else:
            data["uebung_id"] = uebung_id
            cols = ", ".join(data)
            ph = ",".join("?" * len(data))
            cur = con.execute(f"INSERT INTO soc_uebung_ziele({cols}) VALUES({ph}) RETURNING id",
                              tuple(data.values()))
            zid = int(cur.lastrowid)
        con.commit()
        return zid
    finally:
        con.close()


def delete_ziel(db_path: Path, ziel_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_uebung_ziele WHERE id=?", (ziel_id,))
        con.commit()
    finally:
        con.close()


# ── MSEL-Injects — CRUD (#1351) ─────────────────────────────────────────────

def list_injects(db_path: Path, uebung_id: int) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM soc_uebung_injects WHERE uebung_id=? ORDER BY sortierung, id",
            (uebung_id,)).fetchall()]
    finally:
        con.close()


def save_inject(db_path: Path, *, id: int | None = None, uebung_id: int | None = None, **fields: Any) -> int:
    ensure_db(db_path)
    data = {k: fields[k] for k in _INJECT_FIELDS if k in fields}
    con = _connect(db_path)
    try:
        if id:
            if data:
                sets = ", ".join(f"{k}=?" for k in data)
                con.execute(f"UPDATE soc_uebung_injects SET {sets}, updated_at=aics_now() WHERE id=?",
                            (*data.values(), id))
            iid = id
        else:
            data["uebung_id"] = uebung_id
            cols = ", ".join(data)
            ph = ",".join("?" * len(data))
            cur = con.execute(f"INSERT INTO soc_uebung_injects({cols}) VALUES({ph}) RETURNING id",
                              tuple(data.values()))
            iid = int(cur.lastrowid)
        con.commit()
        return iid
    finally:
        con.close()


def delete_inject(db_path: Path, inject_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_uebung_injects WHERE id=?", (inject_id,))
        con.commit()
    finally:
        con.close()


# ── Improvement Plan / Korrekturmaßnahmen — CRUD (#1351) ────────────────────
# Eigenständige Maßnahmen-Tabelle (soc_uebung_massnahmen), aber identische
# Owner/Frist/Status-Maschinerie wie das PIR-Maßnahmen-Tracking (#1316).

def list_massnahmen(db_path: Path, uebung_id: int | None = None, *,
                    only_open: bool = False) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        q = ("SELECT m.*, u.titel AS uebung_titel FROM soc_uebung_massnahmen m "
             "LEFT JOIN soc_uebungen u ON u.id = m.uebung_id")
        clauses, params = [], []
        if uebung_id is not None:
            clauses.append("m.uebung_id=?"); params.append(uebung_id)
        if only_open:
            clauses.append("m.status != 'erledigt'")
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY (m.status='erledigt'), m.frist, m.id"
        return [dict(r) for r in con.execute(q, params).fetchall()]
    finally:
        con.close()


def save_massnahme(db_path: Path, *, id: int | None = None, uebung_id: int,
                   beschreibung: str = "", owner: str = "", frist: str = "",
                   status: str = "offen", actor: str = "") -> int:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if id:
            con.execute(
                """UPDATE soc_uebung_massnahmen SET beschreibung=?, owner=?, frist=?, status=?,
                   done_at=CASE WHEN ?='erledigt' AND status!='erledigt' THEN aics_now()
                                WHEN ?!='erledigt' THEN NULL ELSE done_at END,
                   done_by=CASE WHEN ?='erledigt' THEN ? ELSE done_by END WHERE id=?""",
                (beschreibung, owner, frist, status, status, status, status, actor, id))
            mid = id
        else:
            cur = con.execute(
                """INSERT INTO soc_uebung_massnahmen(uebung_id, beschreibung, owner, frist, status,
                   created_by) VALUES(?,?,?,?,?,?) RETURNING id""",
                (uebung_id, beschreibung, owner, frist, status, actor))
            mid = int(cur.lastrowid)
        con.commit()
        return mid
    finally:
        con.close()


def set_massnahme_status(db_path: Path, massnahme_id: int, status: str, *, actor: str = "") -> dict[str, Any]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT id FROM soc_uebung_massnahmen WHERE id=?", (massnahme_id,)).fetchone()
        if not r:
            return {"ok": False, "error": "Maßnahme nicht gefunden"}
        con.execute(
            """UPDATE soc_uebung_massnahmen SET status=?,
               done_at=CASE WHEN ?='erledigt' THEN aics_now() ELSE NULL END,
               done_by=CASE WHEN ?='erledigt' THEN ? ELSE '' END WHERE id=?""",
            (status, status, status, actor, massnahme_id))
        con.commit()
        return {"ok": True}
    finally:
        con.close()


def delete_massnahme(db_path: Path, massnahme_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_uebung_massnahmen WHERE id=?", (massnahme_id,))
        con.commit()
    finally:
        con.close()
