"""G0-3 — Geteiltes Werkzeug-Register (SV-weit, NICHT projekt-spezifisch).

Wird von beiden Generatoren (Audit-Bericht + Gerichtsgutachten) genutzt.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from shared import db as _sdb

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gutachten_werkzeuge_register (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tool_name     TEXT NOT NULL,
    version       TEXT NOT NULL,
    hersteller    TEXT NOT NULL DEFAULT '',
    zweck         TEXT NOT NULL DEFAULT '',
    nachweis_url  TEXT NOT NULL DEFAULT '',
    bemerkungen   TEXT NOT NULL DEFAULT '',
    erstellt_am   TEXT NOT NULL DEFAULT (aics_now()),
    erstellt_von  TEXT NOT NULL DEFAULT '',
    UNIQUE(tool_name, version)
);

CREATE INDEX IF NOT EXISTS idx_werkzeuge_name ON gutachten_werkzeuge_register(tool_name);

CREATE TABLE IF NOT EXISTS gerichtsgutachten_werkzeug_verwendung (
    projekt_name  TEXT NOT NULL,
    werkzeug_id   INTEGER NOT NULL,
    PRIMARY KEY (projekt_name, werkzeug_id),
    FOREIGN KEY (werkzeug_id) REFERENCES gutachten_werkzeuge_register(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_werkzeug_verwendung (
    projekt_name  TEXT NOT NULL,
    werkzeug_id   INTEGER NOT NULL,
    PRIMARY KEY (projekt_name, werkzeug_id),
    FOREIGN KEY (werkzeug_id) REFERENCES gutachten_werkzeuge_register(id) ON DELETE CASCADE
);
"""


def _ensure(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = _sdb.connect(db_path)
    try:
        con.executescript(_SCHEMA)
        con.commit()
    finally:
        con.close()


def list_werkzeuge(db_path: Path) -> list[dict[str, Any]]:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM gutachten_werkzeuge_register ORDER BY tool_name, version"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_werkzeug(
    db_path: Path,
    tool_name: str,
    version: str,
    hersteller: str = "",
    zweck: str = "",
    nachweis_url: str = "",
    bemerkungen: str = "",
    erstellt_von: str = "",
) -> int:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO gutachten_werkzeuge_register
                 (tool_name, version, hersteller, zweck, nachweis_url, bemerkungen, erstellt_von)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(tool_name, version) DO UPDATE SET
                 hersteller   = excluded.hersteller,
                 zweck        = excluded.zweck,
                 nachweis_url = excluded.nachweis_url,
                 bemerkungen  = excluded.bemerkungen
               RETURNING id""",
            (tool_name, version, hersteller, zweck, nachweis_url, bemerkungen, erstellt_von),
        )
        row = cur.fetchone()
        con.commit()
        return int(row[0])
    finally:
        con.close()


def delete_werkzeug(db_path: Path, werkzeug_id: int) -> None:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gutachten_werkzeuge_register WHERE id=?", (werkzeug_id,))
        con.commit()
    finally:
        con.close()


def link_werkzeug(db_path: Path, projekt_typ: str, projekt_name: str, werkzeug_id: int) -> None:
    """Verknüpft ein Werkzeug mit einem Projekt (audit|gerichts)."""
    table = "audit_werkzeug_verwendung" if projekt_typ == "audit" else "gerichtsgutachten_werkzeug_verwendung"
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute(
            f"INSERT INTO {table} (projekt_name, werkzeug_id) VALUES (?, ?) ON CONFLICT DO NOTHING",
            (projekt_name, werkzeug_id),
        )
        con.commit()
    finally:
        con.close()


def list_werkzeuge_for_projekt(db_path: Path, projekt_typ: str, projekt_name: str) -> list[dict[str, Any]]:
    table = "audit_werkzeug_verwendung" if projekt_typ == "audit" else "gerichtsgutachten_werkzeug_verwendung"
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            f"""SELECT w.* FROM gutachten_werkzeuge_register w
                JOIN {table} v ON v.werkzeug_id = w.id
                WHERE v.projekt_name = ?
                ORDER BY w.tool_name, w.version""",
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
