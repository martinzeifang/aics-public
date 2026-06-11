"""CRA Art. 13(19)-(22) — Korrekturmaßnahmen-/Rückruf-Workflow (#1202).

Bei Nicht-Konformität eines bereits in Verkehr gebrachten Produkts: unverzüglich
Korrekturmaßnahmen ergreifen, ggf. vom Markt nehmen (withdraw) oder zurückrufen
(recall) und bei Risiko die Marktüberwachungsbehörden informieren.

Tabelle ``cra_korrektur`` (projekt-scoped). Maßnahmentyp korrektur|ruecknahme|
rueckruf, betroffene Versionen/Mitgliedstaaten, Behörden-Informations-Record
(ja/nein + Datum), Abschluss-Workflow + Audit-Trail (JSON-Event-Log).
Optionale Verknüpfung zu cra_vuln.id / cra_meldung.id.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path("data/db/cra.sqlite")

# Maßnahmentypen (Single Source of Truth fürs Frontend).
TYPEN = ("korrektur", "ruecknahme", "rueckruf")

# Status / Abschluss-Workflow (nur vorwärts).
STATUS = ("offen", "in_durchfuehrung", "behoerde_informiert", "abgeschlossen")
_STATUS_ORDER = {s: i for i, s in enumerate(STATUS)}


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def ensure_table(db_path: Path = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS cra_korrektur (
                id              INTEGER PRIMARY KEY,
                projekt_name    TEXT NOT NULL,
                massnahmentyp   TEXT NOT NULL DEFAULT 'korrektur',
                titel           TEXT NOT NULL DEFAULT '',
                ausloeser       TEXT NOT NULL DEFAULT '',   -- Nicht-Konformitäts-Befund
                betroffene_versionen TEXT NOT NULL DEFAULT '',
                betroffene_ms   TEXT NOT NULL DEFAULT '',   -- betroffene Mitgliedstaaten
                behoerde_informiert INTEGER NOT NULL DEFAULT 0,
                behoerde_info_datum TEXT,
                behoerde_name   TEXT NOT NULL DEFAULT '',
                vuln_id         INTEGER,                    -- optionaler FK auf cra_vuln.id
                meldung_id      INTEGER,                    -- optionaler FK auf cra_meldung.id
                status          TEXT NOT NULL DEFAULT 'offen',
                beschreibung    TEXT NOT NULL DEFAULT '',
                abgeschlossen_am TEXT,
                audit_json      TEXT NOT NULL DEFAULT '[]', -- Audit-Trail (Event-Liste)
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_cra_korrektur_projekt
                ON cra_korrektur(projekt_name);
            """
        )
        con.commit()
    finally:
        con.close()


def _row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    try:
        d["audit_trail"] = json.loads(d.get("audit_json") or "[]")
    except Exception:
        d["audit_trail"] = []
    d["behoerde_informiert"] = bool(d.get("behoerde_informiert"))
    return d


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_audit(con: sqlite3.Connection, korrektur_id: int, projekt_name: str,
                  event: str, **extra) -> None:
    r = con.execute(
        "SELECT audit_json FROM cra_korrektur WHERE id=? AND projekt_name=?",
        (korrektur_id, projekt_name),
    ).fetchone()
    if not r:
        return
    try:
        trail = json.loads(r["audit_json"] or "[]")
    except Exception:
        trail = []
    trail.append({"event": event, "ts": _now_iso(), **extra})
    con.execute(
        "UPDATE cra_korrektur SET audit_json=? WHERE id=? AND projekt_name=?",
        (json.dumps(trail, ensure_ascii=False), korrektur_id, projekt_name),
    )


def list_korrektur(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_korrektur WHERE projekt_name=? ORDER BY created_at DESC, id DESC",
            (projekt_name,),
        ).fetchall()
        return [_row(r) for r in rows]
    finally:
        con.close()


def get_korrektur(db_path: Path, korrektur_id: int,
                  projekt_name: Optional[str] = None) -> Optional[dict[str, Any]]:
    """IDOR-sicher: optional auf projekt_name scopen."""
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        if projekt_name is not None:
            r = con.execute(
                "SELECT * FROM cra_korrektur WHERE id=? AND projekt_name=?",
                (korrektur_id, projekt_name),
            ).fetchone()
        else:
            r = con.execute(
                "SELECT * FROM cra_korrektur WHERE id=?", (korrektur_id,)
            ).fetchone()
        return _row(r) if r else None
    finally:
        con.close()


def create_korrektur(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_table(db_path)
    typ = data.get("massnahmentyp") or "korrektur"
    if typ not in TYPEN:
        raise ValueError(f"Ungültiger Maßnahmentyp: {typ}")
    con = _connect(db_path)
    try:
        cur = con.execute(
            """
            INSERT INTO cra_korrektur
                (projekt_name, massnahmentyp, titel, ausloeser,
                 betroffene_versionen, betroffene_ms, vuln_id, meldung_id,
                 beschreibung, audit_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (projekt_name, typ, data.get("titel", ""), data.get("ausloeser", ""),
             data.get("betroffene_versionen", ""), data.get("betroffene_ms", ""),
             data.get("vuln_id"), data.get("meldung_id"),
             data.get("beschreibung", ""),
             json.dumps([{"event": "erstellt", "ts": _now_iso(), "typ": typ}],
                        ensure_ascii=False)),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def update_korrektur(db_path: Path, korrektur_id: int, projekt_name: str,
                     data: dict) -> Optional[dict[str, Any]]:
    ensure_table(db_path)
    if "massnahmentyp" in data and data["massnahmentyp"] not in TYPEN:
        raise ValueError(f"Ungültiger Maßnahmentyp: {data['massnahmentyp']}")
    sets, vals = [], []
    for f in ("massnahmentyp", "titel", "ausloeser", "betroffene_versionen",
              "betroffene_ms", "vuln_id", "meldung_id", "beschreibung"):
        if f in data:
            sets.append(f"{f}=?")
            vals.append(data[f])
    if not sets:
        return get_korrektur(db_path, korrektur_id, projekt_name)
    vals += [korrektur_id, projekt_name]
    con = _connect(db_path)
    try:
        cur = con.execute(
            f"UPDATE cra_korrektur SET {', '.join(sets)}, updated_at=datetime('now') "
            "WHERE id=? AND projekt_name=?",
            vals,
        )
        if cur.rowcount == 0:
            con.commit()
            return None
        _append_audit(con, korrektur_id, projekt_name, "aktualisiert")
        con.commit()
    finally:
        con.close()
    return get_korrektur(db_path, korrektur_id, projekt_name)


def inform_behoerde(db_path: Path, korrektur_id: int, projekt_name: str,
                    behoerde_name: str = "", datum: str = "") -> Optional[dict[str, Any]]:
    """Behörden-Informations-Record setzen (ja + Datum) + Audit-Trail."""
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            """UPDATE cra_korrektur
               SET behoerde_informiert=1,
                   behoerde_info_datum=COALESCE(NULLIF(?, ''), datetime('now')),
                   behoerde_name=?, updated_at=datetime('now')
               WHERE id=? AND projekt_name=?""",
            (datum, behoerde_name, korrektur_id, projekt_name),
        )
        if cur.rowcount == 0:
            con.commit()
            return None
        _append_audit(con, korrektur_id, projekt_name, "behoerde_informiert",
                      behoerde=behoerde_name)
        con.commit()
    finally:
        con.close()
    return get_korrektur(db_path, korrektur_id, projekt_name)


def set_status(db_path: Path, korrektur_id: int, projekt_name: str,
               neuer_status: str) -> dict[str, Any]:
    """Status-Transition (nur vorwärts) + Audit-Trail. Abschluss setzt Datum."""
    if neuer_status not in STATUS:
        raise ValueError(f"Ungültiger Status: {neuer_status}")
    k = get_korrektur(db_path, korrektur_id, projekt_name)
    if not k:
        raise ValueError("Korrekturmaßnahme nicht gefunden")
    if _STATUS_ORDER[neuer_status] <= _STATUS_ORDER[k["status"]]:
        raise ValueError("Status kann nur vorwärts gewechselt werden")
    con = _connect(db_path)
    try:
        if neuer_status == "abgeschlossen":
            con.execute(
                "UPDATE cra_korrektur SET status=?, abgeschlossen_am=datetime('now'), "
                "updated_at=datetime('now') WHERE id=? AND projekt_name=?",
                (neuer_status, korrektur_id, projekt_name),
            )
        else:
            con.execute(
                "UPDATE cra_korrektur SET status=?, updated_at=datetime('now') "
                "WHERE id=? AND projekt_name=?",
                (neuer_status, korrektur_id, projekt_name),
            )
        _append_audit(con, korrektur_id, projekt_name, "status_gewechselt",
                      status=neuer_status)
        con.commit()
    finally:
        con.close()
    return get_korrektur(db_path, korrektur_id, projekt_name)


def delete_korrektur(db_path: Path, korrektur_id: int, projekt_name: str) -> bool:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            "DELETE FROM cra_korrektur WHERE id=? AND projekt_name=?",
            (korrektur_id, projekt_name),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()
