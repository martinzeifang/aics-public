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

-- ───────────────────────────────────────────────────────────────────
-- Sprint δ Phase A: DSGVO Pflicht-Doku-Manager (Issue #584)
-- ───────────────────────────────────────────────────────────────────

-- D1: Verzeichnis der Verarbeitungstätigkeiten (Art. 30)
CREATE TABLE IF NOT EXISTS dsgvo_vvt_pflicht (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    vvt_id          TEXT NOT NULL,                -- z.B. VVT-001
    name            TEXT NOT NULL,                -- Bezeichnung der Verarbeitung
    zweck           TEXT NOT NULL DEFAULT '',
    rechtsgrundlage TEXT NOT NULL DEFAULT '',     -- Art. 6 Buchstaben
    betroffene_kategorien TEXT NOT NULL DEFAULT '',
    datenkategorien TEXT NOT NULL DEFAULT '',
    empfaenger      TEXT NOT NULL DEFAULT '',
    drittland       TEXT NOT NULL DEFAULT '',     -- nein | EU+US-Privacy-Shield | …
    loeschfrist     TEXT NOT NULL DEFAULT '',
    tom_referenz    TEXT NOT NULL DEFAULT '',
    verantwortlich  TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, vvt_id)
);
CREATE INDEX IF NOT EXISTS idx_dsgvo_vvt_pflicht_projekt ON dsgvo_vvt_pflicht(projekt_name);

-- D2: Technische und Organisatorische Maßnahmen (Art. 32)
CREATE TABLE IF NOT EXISTS dsgvo_tom (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    kategorie       TEXT NOT NULL,                -- zutrittskontrolle | zugangskontrolle | ...
    massnahme       TEXT NOT NULL,
    beschreibung    TEXT NOT NULL DEFAULT '',
    umsetzungsstatus TEXT NOT NULL DEFAULT 'geplant',  -- geplant | umgesetzt | review
    verantwortlich  TEXT NOT NULL DEFAULT '',
    review_datum    TEXT,
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, kategorie, massnahme)
);
CREATE INDEX IF NOT EXISTS idx_dsgvo_tom_projekt ON dsgvo_tom(projekt_name);

-- D3: Datenschutz-Folgenabschätzung / DPIA (Art. 35)
CREATE TABLE IF NOT EXISTS dsgvo_dpia (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    dpia_id         TEXT NOT NULL,
    bezug_vvt       TEXT NOT NULL DEFAULT '',     -- vvt_id (lose Verknüpfung)
    titel           TEXT NOT NULL,
    notwendigkeit_grund TEXT NOT NULL DEFAULT '',  -- z.B. "systematische Überwachung"
    beschreibung_verarbeitung TEXT NOT NULL DEFAULT '',
    risiken         TEXT NOT NULL DEFAULT '',
    massnahmen      TEXT NOT NULL DEFAULT '',
    restrisiko      TEXT NOT NULL DEFAULT 'niedrig',  -- niedrig | mittel | hoch
    konsultation_dsb TEXT NOT NULL DEFAULT '',
    konsultation_aufsicht INTEGER NOT NULL DEFAULT 0, -- 0/1 (Art. 36)
    durchfuehrung_datum TEXT,
    naechstes_review TEXT,
    status          TEXT NOT NULL DEFAULT 'in-bearbeitung',
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, dpia_id)
);
CREATE INDEX IF NOT EXISTS idx_dsgvo_dpia_projekt ON dsgvo_dpia(projekt_name);

-- D4: AVV-Tracker für Auftragsverarbeiter (Art. 28)
CREATE TABLE IF NOT EXISTS dsgvo_avv_tracker (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    auftragsverarbeiter TEXT NOT NULL,            -- Name
    leistung        TEXT NOT NULL DEFAULT '',
    avv_vorhanden   INTEGER NOT NULL DEFAULT 0,
    avv_url         TEXT NOT NULL DEFAULT '',
    avv_datum       TEXT,
    avv_version     TEXT NOT NULL DEFAULT '',
    sub_avv         TEXT NOT NULL DEFAULT '',     -- Unter-AVs aufgelistet
    drittland       INTEGER NOT NULL DEFAULT 0,
    drittland_garantie TEXT NOT NULL DEFAULT '',  -- SCC | Adäquanz-Beschluss | BCR
    review_datum    TEXT,
    status          TEXT NOT NULL DEFAULT 'gueltig',  -- gueltig | review-faellig | gekuendigt
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, auftragsverarbeiter)
);
CREATE INDEX IF NOT EXISTS idx_dsgvo_avv_projekt ON dsgvo_avv_tracker(projekt_name);

-- D5: Datenpannen-Register (Art. 33-34)
CREATE TABLE IF NOT EXISTS dsgvo_datenpannen (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    panne_id        TEXT NOT NULL,                -- z.B. DSGVO-P-2026-001
    titel           TEXT NOT NULL,
    beschreibung    TEXT NOT NULL DEFAULT '',
    art             TEXT NOT NULL DEFAULT 'vertraulichkeit',  -- vertraulichkeit | integritaet | verfuegbarkeit
    festgestellt_am TEXT NOT NULL,
    betroffene_anzahl INTEGER NOT NULL DEFAULT 0,
    datenkategorien TEXT NOT NULL DEFAULT '',
    risikoeinschaetzung TEXT NOT NULL DEFAULT 'gering',  -- gering | mittel | hoch
    meldung_aufsicht_pflicht INTEGER NOT NULL DEFAULT 0, -- Art. 33 (72h)
    meldung_aufsicht_datum TEXT,
    meldung_betroffene_pflicht INTEGER NOT NULL DEFAULT 0, -- Art. 34
    meldung_betroffene_datum TEXT,
    sofortmassnahmen TEXT NOT NULL DEFAULT '',
    ursache         TEXT NOT NULL DEFAULT '',
    lessons_learned TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'offen',  -- offen | gemeldet | abgeschlossen
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, panne_id)
);
CREATE INDEX IF NOT EXISTS idx_dsgvo_panne_projekt ON dsgvo_datenpannen(projekt_name);
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


# ═══════════════════════════════════════════════════════════════════════════
# Sprint δ Phase A — DSGVO Pflicht-Doku-Helper (Issue #584)
# ═══════════════════════════════════════════════════════════════════════════

import json as _json


# Generisches CRUD-Pattern für 1:n Tabellen mit projekt_name + sub_id

def _generic_list(db_path: Path, table: str, projekt_name: str, order_by: str = 'updated_at DESC') -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            f"SELECT * FROM {table} WHERE projekt_name=? ORDER BY {order_by}",
            (projekt_name,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def _generic_delete(db_path: Path, table: str, row_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(f"DELETE FROM {table} WHERE id=?", (int(row_id),))
        con.commit()
    finally:
        con.close()


# ─── D1: VVT ───────────────────────────────────────────────────────────────

def list_vvt(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    return _generic_list(db_path, 'dsgvo_vvt_pflicht', projekt_name, 'vvt_id')


def save_vvt(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_db(db_path)
    if not data.get('id') and not data.get('vvt_id'):
        raise ValueError("'vvt_id' ist Pflicht")
    if not data.get('name'):
        raise ValueError("'name' ist Pflicht")
    con = _connect(db_path)
    try:
        vid = data.get('id')
        cols = ('vvt_id', 'name', 'zweck', 'rechtsgrundlage', 'betroffene_kategorien',
                'datenkategorien', 'empfaenger', 'drittland', 'loeschfrist',
                'tom_referenz', 'verantwortlich', 'notizen')
        if vid:
            sets = ', '.join(f"{c}=?" for c in cols)
            con.execute(f"UPDATE dsgvo_vvt_pflicht SET {sets}, updated_at=datetime('now') WHERE id=?",
                        [data.get(c, '') for c in cols] + [int(vid)])
            con.commit(); return int(vid)
        placeholders = ','.join('?' for _ in cols)
        cur = con.execute(
            f"INSERT INTO dsgvo_vvt_pflicht (projekt_name, {','.join(cols)}) VALUES (?, {placeholders})",
            [projekt_name] + [data.get(c, '') for c in cols])
        con.commit(); return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_vvt(db_path: Path, vvt_id: int) -> None:
    _generic_delete(db_path, 'dsgvo_vvt_pflicht', vvt_id)


# ─── D2: TOM ───────────────────────────────────────────────────────────────

def list_tom(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    return _generic_list(db_path, 'dsgvo_tom', projekt_name, 'kategorie, massnahme')


def save_tom(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_db(db_path)
    if not data.get('id') and (not data.get('kategorie') or not data.get('massnahme')):
        raise ValueError("'kategorie' und 'massnahme' sind Pflicht")
    con = _connect(db_path)
    try:
        tid = data.get('id')
        cols = ('kategorie', 'massnahme', 'beschreibung', 'umsetzungsstatus',
                'verantwortlich', 'review_datum', 'notizen')
        if tid:
            sets = ', '.join(f"{c}=?" for c in cols)
            con.execute(f"UPDATE dsgvo_tom SET {sets}, updated_at=datetime('now') WHERE id=?",
                        [data.get(c, '') for c in cols] + [int(tid)])
            con.commit(); return int(tid)
        placeholders = ','.join('?' for _ in cols)
        cur = con.execute(
            f"INSERT INTO dsgvo_tom (projekt_name, {','.join(cols)}) VALUES (?, {placeholders})",
            [projekt_name] + [data.get(c, '') for c in cols])
        con.commit(); return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_tom(db_path: Path, tom_id: int) -> None:
    _generic_delete(db_path, 'dsgvo_tom', tom_id)


# ─── D3: DPIA ──────────────────────────────────────────────────────────────

def list_dpia(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    return _generic_list(db_path, 'dsgvo_dpia', projekt_name, 'dpia_id')


def save_dpia(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_db(db_path)
    if not data.get('id') and not data.get('dpia_id'):
        raise ValueError("'dpia_id' ist Pflicht")
    if not data.get('titel'):
        raise ValueError("'titel' ist Pflicht")
    con = _connect(db_path)
    try:
        did = data.get('id')
        cols = ('dpia_id', 'bezug_vvt', 'titel', 'notwendigkeit_grund',
                'beschreibung_verarbeitung', 'risiken', 'massnahmen', 'restrisiko',
                'konsultation_dsb', 'konsultation_aufsicht', 'durchfuehrung_datum',
                'naechstes_review', 'status', 'notizen')
        values = [data.get(c, '') for c in cols]
        values[cols.index('konsultation_aufsicht')] = int(bool(data.get('konsultation_aufsicht')))
        if did:
            sets = ', '.join(f"{c}=?" for c in cols)
            con.execute(f"UPDATE dsgvo_dpia SET {sets}, updated_at=datetime('now') WHERE id=?",
                        values + [int(did)])
            con.commit(); return int(did)
        placeholders = ','.join('?' for _ in cols)
        cur = con.execute(
            f"INSERT INTO dsgvo_dpia (projekt_name, {','.join(cols)}) VALUES (?, {placeholders})",
            [projekt_name] + values)
        con.commit(); return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_dpia(db_path: Path, dpia_id: int) -> None:
    _generic_delete(db_path, 'dsgvo_dpia', dpia_id)


# ─── D4: AVV-Tracker ───────────────────────────────────────────────────────

def list_avv(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    return _generic_list(db_path, 'dsgvo_avv_tracker', projekt_name, 'auftragsverarbeiter')


def save_avv(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_db(db_path)
    if not data.get('id') and not data.get('auftragsverarbeiter'):
        raise ValueError("'auftragsverarbeiter' ist Pflicht")
    con = _connect(db_path)
    try:
        aid = data.get('id')
        cols = ('auftragsverarbeiter', 'leistung', 'avv_vorhanden', 'avv_url',
                'avv_datum', 'avv_version', 'sub_avv', 'drittland',
                'drittland_garantie', 'review_datum', 'status', 'notizen')
        values = [data.get(c, '') for c in cols]
        values[cols.index('avv_vorhanden')] = int(bool(data.get('avv_vorhanden')))
        values[cols.index('drittland')] = int(bool(data.get('drittland')))
        if aid:
            sets = ', '.join(f"{c}=?" for c in cols)
            con.execute(f"UPDATE dsgvo_avv_tracker SET {sets}, updated_at=datetime('now') WHERE id=?",
                        values + [int(aid)])
            con.commit(); return int(aid)
        placeholders = ','.join('?' for _ in cols)
        cur = con.execute(
            f"INSERT INTO dsgvo_avv_tracker (projekt_name, {','.join(cols)}) VALUES (?, {placeholders})",
            [projekt_name] + values)
        con.commit(); return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_avv(db_path: Path, avv_id: int) -> None:
    _generic_delete(db_path, 'dsgvo_avv_tracker', avv_id)


# ─── D5: Datenpannen ───────────────────────────────────────────────────────

def list_pannen(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    return _generic_list(db_path, 'dsgvo_datenpannen', projekt_name, 'festgestellt_am DESC, panne_id')


def save_panne(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_db(db_path)
    if not data.get('id') and not data.get('panne_id'):
        raise ValueError("'panne_id' ist Pflicht")
    if not data.get('titel'):
        raise ValueError("'titel' ist Pflicht")
    if not data.get('festgestellt_am'):
        raise ValueError("'festgestellt_am' ist Pflicht")
    con = _connect(db_path)
    try:
        pid = data.get('id')
        cols = ('panne_id', 'titel', 'beschreibung', 'art', 'festgestellt_am',
                'betroffene_anzahl', 'datenkategorien', 'risikoeinschaetzung',
                'meldung_aufsicht_pflicht', 'meldung_aufsicht_datum',
                'meldung_betroffene_pflicht', 'meldung_betroffene_datum',
                'sofortmassnahmen', 'ursache', 'lessons_learned', 'status', 'notizen')
        values = [data.get(c, '') for c in cols]
        values[cols.index('betroffene_anzahl')] = int(data.get('betroffene_anzahl', 0))
        values[cols.index('meldung_aufsicht_pflicht')] = int(bool(data.get('meldung_aufsicht_pflicht')))
        values[cols.index('meldung_betroffene_pflicht')] = int(bool(data.get('meldung_betroffene_pflicht')))
        if pid:
            sets = ', '.join(f"{c}=?" for c in cols)
            con.execute(f"UPDATE dsgvo_datenpannen SET {sets}, updated_at=datetime('now') WHERE id=?",
                        values + [int(pid)])
            con.commit(); return int(pid)
        placeholders = ','.join('?' for _ in cols)
        cur = con.execute(
            f"INSERT INTO dsgvo_datenpannen (projekt_name, {','.join(cols)}) VALUES (?, {placeholders})",
            [projekt_name] + values)
        con.commit(); return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_panne(db_path: Path, panne_id: int) -> None:
    _generic_delete(db_path, 'dsgvo_datenpannen', panne_id)
