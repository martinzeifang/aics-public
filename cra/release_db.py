"""CRA Art. 13(4) — Wesentliche Änderung + Release-Versionierung (#1208).

Bei einer wesentlichen Änderung gilt das Produkt als neu in Verkehr gebracht:
erneute Risiko- + Konformitätsbewertung, Aktualisierung techn. Doku + DoC.

Modell: eine ``cra_release``-Achse pro Projekt (aktive Produkt-Version) +
``cra_release_snapshot`` für eingefrorene Vorgänger-Versionen. Die Aktion
``substantial_modification`` friert die aktuelle Version als Snapshot ein und
setzt die Re-Assessment-Checkliste der neuen Version auf offen.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from shared import db as _sdb

DB_PATH = Path("data/db/cra.sqlite")

# Re-Assessment-Bausteine (Art. 13(4)).
REASSESS_ITEMS = ("risikobewertung", "konformitaetsbewertung", "technische_doku", "doc")


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer (#1332)."""
    return _sdb.connect(db_path)


def ensure_table(db_path: Path = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS cra_release (
                id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                projekt_name    TEXT NOT NULL UNIQUE,
                aktuelle_version TEXT NOT NULL DEFAULT 'v1.0',
                reassess_json   TEXT NOT NULL DEFAULT '{}',   -- {baustein: 'offen'|'erledigt'}
                letzte_aenderung_am TEXT,
                letzte_aenderung_grund TEXT NOT NULL DEFAULT '',
                created_at      TEXT DEFAULT (aics_now()),
                updated_at      TEXT DEFAULT (aics_now())
            );
            CREATE TABLE IF NOT EXISTS cra_release_snapshot (
                id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                projekt_name    TEXT NOT NULL,
                version         TEXT NOT NULL,
                grund           TEXT NOT NULL DEFAULT '',
                snapshot_json   TEXT NOT NULL DEFAULT '{}',
                eingefroren_am  TEXT DEFAULT (aics_now())
            );
            CREATE INDEX IF NOT EXISTS idx_cra_release_snap_projekt
                ON cra_release_snapshot(projekt_name);
            """
        )
        con.commit()
    finally:
        con.close()


def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    try:
        d["reassess"] = json.loads(d.get("reassess_json") or "{}")
    except Exception:
        d["reassess"] = {}
    return d


def get_release(db_path: Path, projekt_name: str) -> Optional[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        r = con.execute(
            "SELECT * FROM cra_release WHERE projekt_name=?", (projekt_name,)
        ).fetchone()
        return _row(r) if r else None
    finally:
        con.close()


def save_release(db_path: Path, projekt_name: str, data: dict) -> dict[str, Any]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO cra_release (projekt_name, aktuelle_version, reassess_json, updated_at)
               VALUES (?,?,?,aics_now())
               ON CONFLICT(projekt_name) DO UPDATE SET
                   aktuelle_version=excluded.aktuelle_version,
                   reassess_json=excluded.reassess_json,
                   updated_at=aics_now()""",
            (projekt_name, data.get("aktuelle_version", "v1.0"),
             json.dumps(data.get("reassess") or {}, ensure_ascii=False)),
        )
        con.commit()
    finally:
        con.close()
    return get_release(db_path, projekt_name)


def list_snapshots(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_release_snapshot WHERE projekt_name=? "
            "ORDER BY eingefroren_am DESC, id DESC",
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def _collect_snapshot(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Aktuellen Nachweis-Stand für den Snapshot einsammeln (best effort)."""
    snap: dict[str, Any] = {}
    try:
        from cra.db import load_bewertungen
        snap["bewertungen"] = load_bewertungen(db_path, projekt_name)
    except Exception:
        snap["bewertungen"] = {}
    try:
        from cra import konformitaet_db as kdb
        snap["konformitaet"] = kdb.list_konformitaet(db_path, projekt_name)
    except Exception:
        snap["konformitaet"] = []
    return snap


def substantial_modification(db_path: Path, projekt_name: str, *,
                             neue_version: str, grund: str) -> dict[str, Any]:
    """Wesentliche Änderung erfassen: alte Version einfrieren, Re-Assessment öffnen."""
    ensure_table(db_path)
    rec = get_release(db_path, projekt_name) or save_release(
        db_path, projekt_name, {"aktuelle_version": "v1.0"})
    alte_version = rec.get("aktuelle_version", "v1.0")
    snapshot = _collect_snapshot(db_path, projekt_name)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO cra_release_snapshot
                   (projekt_name, version, grund, snapshot_json)
               VALUES (?,?,?,?)""",
            (projekt_name, alte_version, grund,
             json.dumps(snapshot, ensure_ascii=False)),
        )
        reassess = {item: "offen" for item in REASSESS_ITEMS}
        con.execute(
            """UPDATE cra_release SET aktuelle_version=?, reassess_json=?,
                      letzte_aenderung_am=aics_now(), letzte_aenderung_grund=?,
                      updated_at=aics_now()
               WHERE projekt_name=?""",
            (neue_version, json.dumps(reassess, ensure_ascii=False), grund, projekt_name),
        )
        con.commit()
    finally:
        con.close()
    return {
        "release": get_release(db_path, projekt_name),
        "eingefrorene_version": alte_version,
        "snapshots": list_snapshots(db_path, projekt_name),
    }
