"""DB-Layer der Template-Engine — Tabelle ``template_registry`` (#989)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from shared import db as _sdb

DEFAULT_DB_PATH = Path("data/db/templates.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS template_registry (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    modul           TEXT NOT NULL,
    name            TEXT NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    datei_pfad      TEXT NOT NULL,
    datei_sha256    TEXT NOT NULL,
    variablen_json  TEXT NOT NULL DEFAULT '[]',
    mapping_json    TEXT NOT NULL DEFAULT '{}',
    ist_default     INTEGER NOT NULL DEFAULT 0,
    aktiv           INTEGER NOT NULL DEFAULT 1,
    hochgeladen_am  TEXT NOT NULL DEFAULT (aics_now()),
    hochgeladen_von TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT '',
    deleted_at      TEXT,
    deleted_by      TEXT,
    deletion_reason TEXT,
    UNIQUE(modul, name, version)
);
CREATE INDEX IF NOT EXISTS idx_template_modul ON template_registry(modul, aktiv);
"""


def _connect(db_path: Path = DEFAULT_DB_PATH) -> Any:
    return _sdb.connect(db_path)


def ensure_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def row_to_dict(r: Any | None) -> dict[str, Any] | None:
    return dict(r) if r is not None else None


def next_version(con: Any, modul: str, name: str) -> int:
    row = con.execute(
        "SELECT MAX(version) AS v FROM template_registry WHERE modul=? AND name=?",
        (modul, name),
    ).fetchone()
    return int(row["v"] or 0) + 1


def insert_template(db_path: Path, **fields: Any) -> int:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO template_registry
                 (modul, name, version, datei_pfad, datei_sha256, variablen_json,
                  mapping_json, ist_default, aktiv, hochgeladen_von, notizen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                fields["modul"], fields["name"], int(fields["version"]),
                fields["datei_pfad"], fields["datei_sha256"],
                fields.get("variablen_json", "[]"), fields.get("mapping_json", "{}"),
                int(fields.get("ist_default", 0)), int(fields.get("aktiv", 1)),
                fields.get("hochgeladen_von", ""), fields.get("notizen", ""),
            ),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def get_template(db_path: Path, template_id: int) -> dict[str, Any] | None:
    ensure_db(db_path)  # #1066: Lese-Pfad auf frischer Container-DB darf nicht 500en
    con = _connect(db_path)
    try:
        return row_to_dict(con.execute(
            "SELECT * FROM template_registry WHERE id=?", (int(template_id),)).fetchone())
    finally:
        con.close()


def list_templates(db_path: Path, modul: str | None = None,
                   include_inactive: bool = False) -> list[dict[str, Any]]:
    ensure_db(db_path)  # #1066: Tabelle anlegen, falls noch kein Upload erfolgt ist
    con = _connect(db_path)
    try:
        q = "SELECT * FROM template_registry WHERE 1=1"
        params: list[Any] = []
        if modul:
            q += " AND modul=?"
            params.append(modul)
        if not include_inactive:
            q += " AND aktiv=1"
        q += " ORDER BY modul, name, version DESC"
        return [dict(r) for r in con.execute(q, params).fetchall()]
    finally:
        con.close()


def set_mapping(db_path: Path, template_id: int, mapping_json: str,
                variablen_json: str | None = None) -> None:
    con = _connect(db_path)
    try:
        if variablen_json is not None:
            con.execute(
                "UPDATE template_registry SET mapping_json=?, variablen_json=? WHERE id=?",
                (mapping_json, variablen_json, int(template_id)))
        else:
            con.execute("UPDATE template_registry SET mapping_json=? WHERE id=?",
                        (mapping_json, int(template_id)))
        con.commit()
    finally:
        con.close()


def set_default(db_path: Path, template_id: int) -> None:
    """Setzt ist_default atomar: alle anderen des Moduls verlieren das Flag."""
    con = _connect(db_path)
    try:
        row = con.execute("SELECT modul FROM template_registry WHERE id=?",
                          (int(template_id),)).fetchone()
        if not row:
            return
        con.execute("UPDATE template_registry SET ist_default=0 WHERE modul=?", (row["modul"],))
        con.execute("UPDATE template_registry SET ist_default=1 WHERE id=?", (int(template_id),))
        con.commit()
    finally:
        con.close()


def soft_delete(db_path: Path, template_id: int, *, by: str = "", reason: str = "") -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE template_registry
               SET aktiv=0, ist_default=0, deleted_at=aics_now(),
                   deleted_by=?, deletion_reason=?
               WHERE id=?""",
            (by, reason, int(template_id)))
        con.commit()
    finally:
        con.close()
