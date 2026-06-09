"""DS12 (#1112) — DSB-Verwaltung (Datenschutzbeauftragter, Art. 37-39 DSGVO).

Selbst-enthaltene neue Area: eigene Tabelle ``dsgvo_dsb`` in der geteilten
``data/db/dsgvo.sqlite`` — die zentrale ``dsgvo/db.py``-SCHEMA wird NICHT
angefasst. ``ensure_table()`` ist idempotent und wird zu Beginn jeder Lese-/
Schreiboperation aufgerufen (Muster wie ``shared/templates/db.py``).

Pro Projekt existiert i. d. R. genau ein DSB-Datensatz (Upsert auf
``projekt_name``). Erfasst werden Stammdaten (intern/extern, Name, Bestelldatum,
Kontakt), die Meldung an die Aufsichtsbehörde (Art. 37 Abs. 7), der Nachweis der
Aufgaben (Art. 39) sowie ein Tätigkeitsbericht.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

# Geteilte DSGVO-DB; Verbindung über die zentrale dsgvo-Connection
# (con.row_factory = Row ist dort bereits gesetzt).
from dsgvo.db import _connect

DB_PATH = Path('data/db/dsgvo.sqlite')

# Erlaubte DSB-Typen.
TYPEN = (
    'intern',
    'extern',
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsgvo_dsb (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name           TEXT NOT NULL UNIQUE,
    typ                    TEXT NOT NULL DEFAULT 'intern',
    name                   TEXT NOT NULL DEFAULT '',
    bestelldatum           TEXT NOT NULL DEFAULT '',
    kontakt_email          TEXT NOT NULL DEFAULT '',
    kontakt_veroeffentlicht INTEGER NOT NULL DEFAULT 0,
    gemeldet_aufsicht      INTEGER NOT NULL DEFAULT 0,
    aufgaben_nachweis      TEXT NOT NULL DEFAULT '',
    taetigkeitsbericht     TEXT NOT NULL DEFAULT '',
    notizen                TEXT NOT NULL DEFAULT '',
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_dsgvo_dsb_projekt
    ON dsgvo_dsb(projekt_name);
"""


def ensure_table(db_path: Path = DB_PATH) -> None:
    """Legt Tabelle + Index an (idempotent)."""
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


# ============================================================
# Serialisierung
# ============================================================

def _row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    d['kontakt_veroeffentlicht'] = int(d.get('kontakt_veroeffentlicht') or 0)
    d['gemeldet_aufsicht'] = int(d.get('gemeldet_aufsicht') or 0)
    return d


# ============================================================
# CRUD / Upsert
# ============================================================

def get_dsb(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    """Liefert den DSB-Datensatz eines Projekts oder ``None``."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        r = con.execute(
            "SELECT * FROM dsgvo_dsb WHERE projekt_name = ?",
            (projekt_name,),
        ).fetchone()
        return _row_to_dict(r) if r is not None else None
    finally:
        con.close()


# Felder, die per Upsert/Update gesetzt werden dürfen.
_ALLOWED = (
    'typ',
    'name',
    'bestelldatum',
    'kontakt_email',
    'kontakt_veroeffentlicht',
    'gemeldet_aufsicht',
    'aufgaben_nachweis',
    'taetigkeitsbericht',
    'notizen',
)


def upsert_dsb(db_path: Path, projekt_name: str,
               **fields: Any) -> dict[str, Any]:
    """Legt den DSB-Datensatz eines Projekts an oder aktualisiert ihn.

    Nur Felder aus ``_ALLOWED`` mit Wert ``!= None`` werden übernommen. Ein
    ungültiger ``typ`` löst ``ValueError`` aus.
    """
    ensure_table(db_path)
    if not projekt_name:
        raise ValueError('projekt_name ist Pflicht')

    values = {k: v for k, v in fields.items() if k in _ALLOWED and v is not None}

    if 'typ' in values and values['typ'] not in TYPEN:
        raise ValueError(f"Ungültiger Typ: {values['typ']}")

    if 'kontakt_veroeffentlicht' in values:
        values['kontakt_veroeffentlicht'] = int(bool(values['kontakt_veroeffentlicht']))
    if 'gemeldet_aufsicht' in values:
        values['gemeldet_aufsicht'] = int(bool(values['gemeldet_aufsicht']))

    existing = get_dsb(db_path, projekt_name)
    con = _connect(Path(db_path))
    try:
        if existing is None:
            cols = ['projekt_name'] + list(values.keys())
            placeholders = ','.join('?' for _ in cols)
            params = [projekt_name] + list(values.values())
            con.execute(
                f"INSERT INTO dsgvo_dsb ({','.join(cols)}) VALUES ({placeholders})",
                params,
            )
        elif values:
            set_clause = ', '.join(f'{k} = ?' for k in values)
            params = list(values.values()) + [projekt_name]
            con.execute(
                f"UPDATE dsgvo_dsb SET {set_clause}, "
                f"updated_at = datetime('now') WHERE projekt_name = ?",
                params,
            )
        con.commit()
    finally:
        con.close()
    return get_dsb(db_path, projekt_name)  # type: ignore[return-value]


def delete_dsb(db_path: Path, projekt_name: str) -> bool:
    """Löscht den DSB-Datensatz eines Projekts. ``True`` bei Treffer."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            "DELETE FROM dsgvo_dsb WHERE projekt_name = ?", (projekt_name,),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()
