"""AI Act module – SQLite data access."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from shared.db_security import connect_sqlite


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-32000;

CREATE TABLE IF NOT EXISTS ai_act_projekte (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    organisation TEXT NOT NULL DEFAULT '',
    produkt     TEXT NOT NULL DEFAULT '',
    beschreibung TEXT NOT NULL DEFAULT '',
    meta_json   TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_act_bewertungen (
    id           INTEGER PRIMARY KEY,
    projekt_name TEXT NOT NULL,
    anforderung_id TEXT NOT NULL,
    bewertung    INTEGER NOT NULL DEFAULT 0,
    kommentar    TEXT NOT NULL DEFAULT '',
    massnahme    TEXT NOT NULL DEFAULT '',
    updated_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, anforderung_id)
);

CREATE INDEX IF NOT EXISTS idx_aia_bew_projekt ON ai_act_bewertungen(projekt_name);

CREATE TABLE IF NOT EXISTS ai_act_overlay_checks (
    id            INTEGER PRIMARY KEY,
    projekt_name  TEXT NOT NULL,
    overlay_id    TEXT NOT NULL,
    status        INTEGER NOT NULL DEFAULT 0,
    kommentar     TEXT NOT NULL DEFAULT '',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, overlay_id)
);

CREATE INDEX IF NOT EXISTS idx_aia_overlay_projekt ON ai_act_overlay_checks(projekt_name);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    con = connect_sqlite(db_path, anchor=Path(__file__))
    con.row_factory = sqlite3.Row
    con.executescript("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")
    return con


def ensure_db(db_path: Path) -> None:
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def save_projekt(
    db_path: Path,
    *,
    name: str,
    organisation: str = "",
    produkt: str = "",
    beschreibung: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO ai_act_projekte(name, organisation, produkt, beschreibung, meta_json, updated_at)
            VALUES(?,?,?,?,?,datetime('now'))
            ON CONFLICT(name) DO UPDATE SET
              organisation=excluded.organisation,
              produkt=excluded.produkt,
              beschreibung=excluded.beschreibung,
              meta_json=excluded.meta_json,
              updated_at=datetime('now')
            """,
            (
                name,
                organisation,
                produkt,
                beschreibung,
                json.dumps(meta or {}, ensure_ascii=False),
            ),
        )
        con.commit()
    finally:
        con.close()


def load_projekt(db_path: Path, name: str) -> dict[str, Any] | None:
    con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM ai_act_projekte WHERE name=?", (name,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["meta"] = json.loads(d.get("meta_json", "{}") or "{}")
        except Exception:
            d["meta"] = {}
        return d
    finally:
        con.close()


def list_projekte(db_path: Path) -> list[str]:
    con = _connect(db_path)
    try:
        rows = con.execute("SELECT name FROM ai_act_projekte ORDER BY updated_at DESC, name").fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


def delete_projekt(db_path: Path, name: str) -> None:
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM ai_act_bewertungen WHERE projekt_name=?", (name,))
        con.execute("DELETE FROM ai_act_projekte WHERE name=?", (name,))
        con.commit()
    finally:
        con.close()


def save_bewertung(
    db_path: Path,
    *,
    projekt_name: str,
    anforderung_id: str,
    bewertung: int,
    kommentar: str = "",
    massnahme: str = "",
) -> None:
    bew = int(bewertung)
    if bew < 0 or bew > 5:
        bew = 0
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO ai_act_bewertungen(projekt_name, anforderung_id, bewertung, kommentar, massnahme, updated_at)
            VALUES(?,?,?,?,?,datetime('now'))
            ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET
              bewertung=excluded.bewertung,
              kommentar=excluded.kommentar,
              massnahme=excluded.massnahme,
              updated_at=datetime('now')
            """,
            (projekt_name, anforderung_id, bew, kommentar or "", massnahme or ""),
        )
        con.commit()
    finally:
        con.close()


def load_bewertungen(db_path: Path, projekt_name: str) -> dict[str, dict[str, Any]]:
    con = _connect(db_path)
    try:
        rows = con.execute("SELECT * FROM ai_act_bewertungen WHERE projekt_name=?", (projekt_name,)).fetchall()
        return {str(r["anforderung_id"]): dict(r) for r in rows}
    finally:
        con.close()


def upsert_overlay_check(
    db_path: Path,
    *,
    projekt_name: str,
    overlay_id: str,
    status: int,
    kommentar: str = "",
    evidence: list[dict[str, Any]] | None = None,
) -> None:
    import json

    st = int(status)
    if st < 0 or st > 5:
        st = 0
    ev_json = json.dumps(evidence or [], ensure_ascii=False)
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO ai_act_overlay_checks(projekt_name, overlay_id, status, kommentar, evidence_json, updated_at)
            VALUES(?,?,?,?,?,datetime('now'))
            ON CONFLICT(projekt_name, overlay_id) DO UPDATE SET
              status=excluded.status,
              kommentar=excluded.kommentar,
              evidence_json=excluded.evidence_json,
              updated_at=datetime('now')
            """,
            (projekt_name, overlay_id, st, kommentar or "", ev_json),
        )
        con.commit()
    finally:
        con.close()


def load_overlay_checks(db_path: Path, projekt_name: str) -> dict[str, dict[str, Any]]:
    import json

    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM ai_act_overlay_checks WHERE projekt_name=?",
            (projekt_name,),
        ).fetchall()
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            d = dict(r)
            try:
                d["evidence"] = json.loads(d.get("evidence_json", "[]") or "[]")
            except Exception:
                d["evidence"] = []
            out[str(d.get("overlay_id"))] = d
        return out
    finally:
        con.close()
