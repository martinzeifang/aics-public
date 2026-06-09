"""DSGVO DS9 (#1109) – Drittlandtransfer + TIA (Art. 44–49).

Eigenständiger, additiver Datenzugriff (kein Eingriff in das zentrale
``dsgvo/db.py``-SCHEMA). Nutzt die DSGVO-SQLite-Verbindung über
``dsgvo.db._connect`` (Row-Factory bereits gesetzt) und legt die Tabelle
``dsgvo_transfer`` idempotent per ``ensure_table`` an — gerufen zu Beginn jeder
Lese-/Schreiboperation (analog ``shared/templates/db.py``).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from dsgvo.db import _connect

DB_PATH = Path("data/db/dsgvo.sqlite")

# Erlaubte Übermittlungs-Grundlagen (Art. 45/46/47/49).
GRUNDLAGEN = ("angemessenheit45", "scc46", "bcr", "ausnahme49")
# TIA-Status (EDSA 01/2020 Schritt-Workflow).
TIA_STATUS = ("offen", "in_arbeit", "abgeschlossen")

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsgvo_transfer (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name    TEXT NOT NULL,
    transfer_id     TEXT NOT NULL,
    empfaenger      TEXT NOT NULL DEFAULT '',
    drittland       TEXT NOT NULL DEFAULT '',
    grundlage       TEXT NOT NULL DEFAULT '',
    garantie_detail TEXT NOT NULL DEFAULT '',
    tia_status      TEXT NOT NULL DEFAULT 'offen',
    tia_json        TEXT NOT NULL DEFAULT '{}',
    vvt_ref         TEXT NOT NULL DEFAULT '',
    avv_ref         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(projekt_name, transfer_id)
);
CREATE INDEX IF NOT EXISTS idx_dsgvo_transfer_projekt
    ON dsgvo_transfer(projekt_name);
"""


def ensure_table(db_path: Path = DB_PATH) -> None:
    """Tabelle + Indizes anlegen (idempotent)."""
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


# ── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    try:
        d["tia_json"] = json.loads(d.get("tia_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["tia_json"] = {}
    return d


def _normalize_tia(tia: Any) -> str:
    """TIA-Felder (EDSA 01/2020) als kompaktes JSON serialisieren."""
    if isinstance(tia, str):
        try:
            tia = json.loads(tia) if tia.strip() else {}
        except json.JSONDecodeError:
            tia = {}
    if not isinstance(tia, dict):
        tia = {}
    return json.dumps(
        {
            "rechtslage": tia.get("rechtslage", ""),
            "zusatzgarantien": tia.get("zusatzgarantien", ""),
            "risikoabwaegung": tia.get("risikoabwaegung", ""),
            "ergebnis": tia.get("ergebnis", ""),
        },
        ensure_ascii=False,
    )


# ── CRUD ────────────────────────────────────────────────────────────────────

def list_transfers(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM dsgvo_transfer WHERE projekt_name=? "
            "ORDER BY transfer_id",
            (projekt_name,),
        ).fetchall()
        return [d for d in (_row_to_dict(r) for r in rows) if d is not None]
    finally:
        con.close()


def get_transfer(
    db_path: Path, projekt_name: str, transfer_id: str
) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        row = con.execute(
            "SELECT * FROM dsgvo_transfer WHERE projekt_name=? AND transfer_id=?",
            (projekt_name, transfer_id),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        con.close()


def upsert_transfer(
    db_path: Path,
    projekt_name: str,
    transfer_id: str,
    *,
    empfaenger: str = "",
    drittland: str = "",
    grundlage: str = "",
    garantie_detail: str = "",
    tia_status: str = "offen",
    tia: Any = None,
    vvt_ref: str = "",
    avv_ref: str = "",
) -> dict[str, Any]:
    """Transfer anlegen oder aktualisieren (idempotent über UNIQUE-Key)."""
    ensure_table(db_path)
    tia_serialized = _normalize_tia(tia)
    con = _connect(Path(db_path))
    try:
        con.execute(
            """
            INSERT INTO dsgvo_transfer
                (projekt_name, transfer_id, empfaenger, drittland, grundlage,
                 garantie_detail, tia_status, tia_json, vvt_ref, avv_ref)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(projekt_name, transfer_id) DO UPDATE SET
                empfaenger=excluded.empfaenger,
                drittland=excluded.drittland,
                grundlage=excluded.grundlage,
                garantie_detail=excluded.garantie_detail,
                tia_status=excluded.tia_status,
                tia_json=excluded.tia_json,
                vvt_ref=excluded.vvt_ref,
                avv_ref=excluded.avv_ref,
                updated_at=datetime('now')
            """,
            (
                projekt_name, transfer_id, empfaenger, drittland, grundlage,
                garantie_detail, tia_status, tia_serialized, vvt_ref, avv_ref,
            ),
        )
        con.commit()
    finally:
        con.close()
    result = get_transfer(db_path, projekt_name, transfer_id)
    assert result is not None
    return result


def save_tia(
    db_path: Path,
    projekt_name: str,
    transfer_id: str,
    *,
    tia: Any,
    tia_status: str | None = None,
) -> dict[str, Any] | None:
    """Geführte TIA (EDSA 01/2020) für einen bestehenden Transfer speichern."""
    ensure_table(db_path)
    existing = get_transfer(db_path, projekt_name, transfer_id)
    if existing is None:
        return None
    tia_serialized = _normalize_tia(tia)
    status = tia_status if tia_status is not None else existing.get("tia_status", "offen")
    con = _connect(Path(db_path))
    try:
        con.execute(
            "UPDATE dsgvo_transfer SET tia_json=?, tia_status=?, "
            "updated_at=datetime('now') "
            "WHERE projekt_name=? AND transfer_id=?",
            (tia_serialized, status, projekt_name, transfer_id),
        )
        con.commit()
    finally:
        con.close()
    return get_transfer(db_path, projekt_name, transfer_id)


def delete_transfer(db_path: Path, projekt_name: str, transfer_id: str) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            "DELETE FROM dsgvo_transfer WHERE projekt_name=? AND transfer_id=?",
            (projekt_name, transfer_id),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()
