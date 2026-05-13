"""DSGVO-Modul – SQLite-Datenzugriff."""
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

CREATE TABLE IF NOT EXISTS dsgvo_projekte (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    unternehmen     TEXT NOT NULL DEFAULT '',
    organisationstyp TEXT NOT NULL DEFAULT 'verantwortlicher',
    beschreibung    TEXT NOT NULL DEFAULT '',
    berater         TEXT NOT NULL DEFAULT '',
    meta_json       TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dsgvo_bewertungen (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    anforderung_id  TEXT NOT NULL,
    bewertung       INTEGER NOT NULL DEFAULT 0,
    kommentar       TEXT NOT NULL DEFAULT '',
    massnahme       TEXT NOT NULL DEFAULT '',
    verantwortlich  TEXT NOT NULL DEFAULT '',
    zieldatum       TEXT NOT NULL DEFAULT '',
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, anforderung_id)
);

CREATE INDEX IF NOT EXISTS idx_db_projekt ON dsgvo_bewertungen(projekt_name);

CREATE TABLE IF NOT EXISTS dsgvo_anforderungen_custom (
    id              TEXT PRIMARY KEY,
    kapitel         TEXT NOT NULL DEFAULT 'GDS6',
    ref             TEXT NOT NULL DEFAULT '',
    titel           TEXT NOT NULL DEFAULT '',
    beschreibung    TEXT NOT NULL DEFAULT '',
    hinweise        TEXT NOT NULL DEFAULT '',
    gewichtung      INTEGER NOT NULL DEFAULT 1,
    ist_override    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dsgvo_dokumente (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    doc_name        TEXT NOT NULL,
    doc_path        TEXT NOT NULL,
    doc_type        TEXT NOT NULL DEFAULT 'resource',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_dd_projekt ON dsgvo_dokumente(projekt_name);

CREATE TABLE IF NOT EXISTS dsgvo_privacy_intake (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL UNIQUE,
    intake_json     TEXT NOT NULL DEFAULT '{}',
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- KI-Generierte Inhalte (TOM, Privacy, Schulung)
CREATE TABLE IF NOT EXISTS dsgvo_ai_drafts (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    kind            TEXT NOT NULL,         -- 'tom' | 'privacy'
    payload_json    TEXT NOT NULL DEFAULT '{}',
    source_documents TEXT NOT NULL DEFAULT '[]',  -- JSON-Liste der genutzten doc-IDs
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, kind)
);
"""


def save_ai_draft(db_path: Path, projekt_name: str, kind: str,
                  payload: dict, source_documents: list[str] | None = None) -> None:
    """Speichert/aktualisiert einen KI-Generierten Draft (tom/privacy)."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO dsgvo_ai_drafts (projekt_name, kind, payload_json, source_documents, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(projekt_name, kind) DO UPDATE SET
                payload_json    = excluded.payload_json,
                source_documents = excluded.source_documents,
                updated_at      = datetime('now')
            """,
            (projekt_name, kind, json.dumps(payload, ensure_ascii=False),
             json.dumps(source_documents or [])),
        )
        con.commit()
    finally:
        con.close()


def load_ai_draft(db_path: Path, projekt_name: str, kind: str) -> dict | None:
    """Lädt den gespeicherten KI-Draft, oder None."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT payload_json, source_documents, updated_at FROM dsgvo_ai_drafts WHERE projekt_name=? AND kind=?",
            (projekt_name, kind),
        ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row['payload_json'] or '{}')
        except Exception:
            payload = {}
        try:
            sources = json.loads(row['source_documents'] or '[]')
        except Exception:
            sources = []
        return {
            'payload': payload,
            'source_documents': sources,
            'updated_at': row['updated_at'],
        }
    finally:
        con.close()


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


# ── Projekte ──────────────────────────────────────────────────────────────────

def save_projekt(
    db_path: Path,
    name: str,
    unternehmen: str = "",
    organisationstyp: str = "verantwortlicher",
    beschreibung: str = "",
    berater: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO dsgvo_projekte
                (name, unternehmen, organisationstyp, beschreibung, berater, meta_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(name) DO UPDATE SET
                unternehmen      = excluded.unternehmen,
                organisationstyp = excluded.organisationstyp,
                beschreibung     = excluded.beschreibung,
                berater          = excluded.berater,
                meta_json        = excluded.meta_json,
                updated_at       = datetime('now')
            """,
            (name, unternehmen, organisationstyp, beschreibung, berater,
             json.dumps(meta or {}, ensure_ascii=False)),
        )
        con.commit()
    finally:
        con.close()


def load_projekt(db_path: Path, name: str) -> dict[str, Any] | None:
    con = _connect(db_path)
    try:
        cur = con.execute("SELECT * FROM dsgvo_projekte WHERE name=?", (name,))
        row = cur.fetchone()
        if row is None:
            return None
        d = dict(row)
        try:
            d["meta"] = json.loads(d.get("meta_json", "{}"))
        except Exception:
            d["meta"] = {}
        return d
    finally:
        con.close()


def list_projekte(db_path: Path) -> list[str]:
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT name FROM dsgvo_projekte ORDER BY updated_at DESC, name"
        )
        return [r["name"] for r in cur.fetchall()]
    finally:
        con.close()


def delete_projekt(db_path: Path, name: str) -> None:
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM dsgvo_bewertungen WHERE projekt_name=?", (name,))
        con.execute("DELETE FROM dsgvo_dokumente   WHERE projekt_name=?", (name,))
        con.execute("DELETE FROM dsgvo_projekte    WHERE name=?", (name,))
        con.commit()
    finally:
        con.close()


# ── Bewertungen ───────────────────────────────────────────────────────────────

def save_bewertung(
    db_path: Path,
    projekt_name: str,
    anforderung_id: str,
    bewertung: int,
    kommentar: str = "",
    massnahme: str = "",
    verantwortlich: str = "",
    zieldatum: str = "",
) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO dsgvo_bewertungen
                (projekt_name, anforderung_id, bewertung, kommentar,
                 massnahme, verantwortlich, zieldatum, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET
                bewertung      = excluded.bewertung,
                kommentar      = excluded.kommentar,
                massnahme      = excluded.massnahme,
                verantwortlich = excluded.verantwortlich,
                zieldatum      = excluded.zieldatum,
                updated_at     = datetime('now')
            """,
            (projekt_name, anforderung_id, bewertung, kommentar,
             massnahme, verantwortlich, zieldatum),
        )
        con.commit()
    finally:
        con.close()


def bulk_save_bewertungen(
    db_path: Path,
    projekt_name: str,
    rows: list[dict[str, Any]],
) -> int:
    con = _connect(db_path)
    try:
        count = 0
        for r in rows:
            aid = str(r.get("anforderung_id", "")).strip()
            if not aid:
                continue
            bew = int(r.get("bewertung", 0))
            if bew < 0 or bew > 5:
                bew = 0
            con.execute(
                """
                INSERT INTO dsgvo_bewertungen
                    (projekt_name, anforderung_id, bewertung, kommentar,
                     massnahme, verantwortlich, zieldatum, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET
                    bewertung      = excluded.bewertung,
                    kommentar      = excluded.kommentar,
                    massnahme      = excluded.massnahme,
                    verantwortlich = excluded.verantwortlich,
                    zieldatum      = excluded.zieldatum,
                    updated_at     = datetime('now')
                """,
                (projekt_name, aid, bew,
                 str(r.get("kommentar", "")),
                 str(r.get("massnahme", "")),
                 str(r.get("verantwortlich", "")),
                 str(r.get("zieldatum", ""))),
            )
            count += 1
        con.commit()
        return count
    finally:
        con.close()


def load_bewertungen(db_path: Path, projekt_name: str) -> dict[str, dict[str, Any]]:
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM dsgvo_bewertungen WHERE projekt_name=?", (projekt_name,)
        )
        return {row["anforderung_id"]: dict(row) for row in cur.fetchall()}
    finally:
        con.close()


# ── Benutzerdefinierte Anforderungen ──────────────────────────────────────────

def save_custom_anforderung(db_path: Path, req: dict[str, Any]) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO dsgvo_anforderungen_custom
                (id, kapitel, ref, titel, beschreibung, hinweise, gewichtung, ist_override, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                kapitel      = excluded.kapitel,
                ref          = excluded.ref,
                titel        = excluded.titel,
                beschreibung = excluded.beschreibung,
                hinweise     = excluded.hinweise,
                gewichtung   = excluded.gewichtung,
                ist_override = excluded.ist_override,
                updated_at   = datetime('now')
            """,
            (
                req["id"], req.get("kapitel", "GDS6"), req.get("ref", ""),
                req.get("titel", ""), req.get("beschreibung", ""),
                req.get("hinweise", ""), int(req.get("gewichtung", 1)),
                1 if req.get("ist_override") else 0,
            ),
        )
        con.commit()
    finally:
        con.close()


def delete_custom_anforderung(db_path: Path, req_id: str) -> None:
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM dsgvo_anforderungen_custom WHERE id=?", (req_id,))
        con.commit()
    finally:
        con.close()


def load_custom_anforderungen(db_path: Path) -> list[dict[str, Any]]:
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM dsgvo_anforderungen_custom ORDER BY kapitel, id"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


# ── Privacy-Intake ─────────────────────────────────────────────────────────────

def save_privacy_intake(db_path: Path, projekt_name: str, intake: dict[str, Any]) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO dsgvo_privacy_intake (projekt_name, intake_json, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(projekt_name) DO UPDATE SET
                intake_json = excluded.intake_json,
                updated_at  = datetime('now')
            """,
            (projekt_name, json.dumps(intake, ensure_ascii=False)),
        )
        con.commit()
    finally:
        con.close()


def load_privacy_intake(db_path: Path, projekt_name: str) -> dict[str, Any]:
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT intake_json FROM dsgvo_privacy_intake WHERE projekt_name=?",
            (projekt_name,),
        )
        row = cur.fetchone()
        if row is None:
            return {}
        try:
            return json.loads(row["intake_json"]) or {}
        except Exception:
            return {}
    finally:
        con.close()
