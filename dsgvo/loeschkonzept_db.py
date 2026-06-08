"""DS10 (#1110) — Löschkonzept (Art. 17 DSGVO + DIN 66398).

Self-contained, additiver DB-Layer für das DSGVO-Löschkonzept. Verwendet die
gemeinsame DSGVO-SQLite (``data/db/dsgvo.sqlite``) über ``dsgvo.db._connect``,
legt aber die eigene Tabelle ``dsgvo_loeschkonzept`` idempotent an (kein Eingriff
in das zentrale SCHEMA in ``dsgvo/db.py``).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from dsgvo.db import _connect

DB_PATH = Path("data/db/dsgvo.sqlite")

# Erlaubte Werte (Validierung erfolgt im Blueprint; hier nur Doku).
RECHTSGRUNDLAGE_FRIST = ("gesetzlich", "zweckbindung")

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsgvo_loeschkonzept (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name         TEXT NOT NULL,
    regel_id             TEXT NOT NULL,
    datenkategorie       TEXT NOT NULL DEFAULT '',
    aufbewahrungsfrist   TEXT NOT NULL DEFAULT '',
    rechtsgrundlage_frist TEXT NOT NULL DEFAULT 'gesetzlich',
    loeschklasse         TEXT NOT NULL DEFAULT '',
    loesch_trigger       TEXT NOT NULL DEFAULT '',
    verantwortlich       TEXT NOT NULL DEFAULT '',
    status               TEXT NOT NULL DEFAULT 'offen',
    vvt_ref              TEXT NOT NULL DEFAULT '',
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(projekt_name, regel_id)
);
CREATE INDEX IF NOT EXISTS idx_loeschkonzept_projekt
    ON dsgvo_loeschkonzept(projekt_name);
CREATE INDEX IF NOT EXISTS idx_loeschkonzept_kategorie
    ON dsgvo_loeschkonzept(projekt_name, datenkategorie);
"""


def ensure_table(db_path: Path = DB_PATH) -> None:
    """Legt Tabelle + Indizes idempotent an."""
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _row_to_dict(r: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(r) if r is not None else None


def list_regeln(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    """Alle Löschregeln eines Projekts, nach Datenkategorie + Regel-ID sortiert."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            """
            SELECT * FROM dsgvo_loeschkonzept
            WHERE projekt_name = ?
            ORDER BY datenkategorie COLLATE NOCASE, regel_id COLLATE NOCASE
            """,
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_regel(db_path: Path, regel_pk: int) -> dict[str, Any] | None:
    """Einzelne Löschregel über Primärschlüssel."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        row = con.execute(
            "SELECT * FROM dsgvo_loeschkonzept WHERE id = ?", (regel_pk,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        con.close()


def save_regel(
    db_path: Path,
    projekt_name: str,
    regel_id: str,
    *,
    datenkategorie: str = "",
    aufbewahrungsfrist: str = "",
    rechtsgrundlage_frist: str = "gesetzlich",
    loeschklasse: str = "",
    loesch_trigger: str = "",
    verantwortlich: str = "",
    status: str = "offen",
    vvt_ref: str = "",
) -> int:
    """Upsert anhand (projekt_name, regel_id). Gibt die Zeilen-id zurück."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        con.execute(
            """
            INSERT INTO dsgvo_loeschkonzept (
                projekt_name, regel_id, datenkategorie, aufbewahrungsfrist,
                rechtsgrundlage_frist, loeschklasse, loesch_trigger,
                verantwortlich, status, vvt_ref
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(projekt_name, regel_id) DO UPDATE SET
                datenkategorie=excluded.datenkategorie,
                aufbewahrungsfrist=excluded.aufbewahrungsfrist,
                rechtsgrundlage_frist=excluded.rechtsgrundlage_frist,
                loeschklasse=excluded.loeschklasse,
                loesch_trigger=excluded.loesch_trigger,
                verantwortlich=excluded.verantwortlich,
                status=excluded.status,
                vvt_ref=excluded.vvt_ref,
                updated_at=datetime('now')
            """,
            (
                projekt_name, regel_id, datenkategorie, aufbewahrungsfrist,
                rechtsgrundlage_frist, loeschklasse, loesch_trigger,
                verantwortlich, status, vvt_ref,
            ),
        )
        con.commit()
        row = con.execute(
            "SELECT id FROM dsgvo_loeschkonzept WHERE projekt_name=? AND regel_id=?",
            (projekt_name, regel_id),
        ).fetchone()
        return int(row["id"])
    finally:
        con.close()


def update_status(db_path: Path, regel_pk: int, status: str) -> bool:
    """Setzt nur den Status (z. B. 'erledigt')."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            "UPDATE dsgvo_loeschkonzept SET status=?, updated_at=datetime('now') WHERE id=?",
            (status, regel_pk),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def delete_regel(db_path: Path, regel_pk: int) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        cur = con.execute("DELETE FROM dsgvo_loeschkonzept WHERE id=?", (regel_pk,))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def list_faellig(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    """Fällige Löschungen: Regeln mit Status != 'erledigt'/'deaktiviert',
    deren Trigger gesetzt ist. Bewusst konservativ (status-basiert), da Fristen
    als Freitext erfasst werden (DIN-66398-Löschklassen)."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            """
            SELECT * FROM dsgvo_loeschkonzept
            WHERE projekt_name = ?
              AND status NOT IN ('erledigt', 'deaktiviert')
              AND TRIM(loesch_trigger) <> ''
            ORDER BY datenkategorie COLLATE NOCASE, regel_id COLLATE NOCASE
            """,
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
