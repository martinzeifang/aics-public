"""DORA SQLite DB — Projekte, Bewertungen, Custom-Anforderungen, TPP-Register, Testing-Plan."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from shared import db as _sdb

DEFAULT_DB_PATH = Path('data/db/dora.sqlite')


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer."""
    return _sdb.connect(db_path)


def ensure_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Tabellen anlegen falls nicht vorhanden."""
    con = _connect(db_path)
    cur = con.cursor()

    # Projekte
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dora_projekte (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            unternehmen TEXT DEFAULT '',
            finanzeinrichtung_klasse TEXT DEFAULT '',  -- bank | insurer | investment | other
            beschreibung TEXT DEFAULT '',
            berater TEXT DEFAULT '',
            meta_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (aics_now()),
            updated_at TEXT DEFAULT (aics_now())
        )
    """)

    # Bewertungen
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dora_bewertungen (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            projekt_name TEXT NOT NULL,
            anforderung_id TEXT NOT NULL,
            bewertung INTEGER DEFAULT 0,
            kommentar TEXT DEFAULT '',
            massnahme TEXT DEFAULT '',
            verantwortlich TEXT DEFAULT '',
            zieldatum TEXT DEFAULT '',
            updated_at TEXT DEFAULT (aics_now()),
            UNIQUE(projekt_name, anforderung_id)
        )
    """)
    cur.execute('CREATE INDEX IF NOT EXISTS idx_dora_bew_projekt ON dora_bewertungen(projekt_name)')

    # Custom-Anforderungen (analog NIS2/CRA)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dora_anforderungen_custom (
            id TEXT PRIMARY KEY,
            pfeiler TEXT DEFAULT 'ICT-RM',
            ref TEXT DEFAULT '',
            titel TEXT DEFAULT '',
            beschreibung TEXT DEFAULT '',
            hinweise TEXT DEFAULT '',
            gewichtung INTEGER DEFAULT 1,
            ist_override INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (aics_now()),
            updated_at TEXT DEFAULT (aics_now())
        )
    """)

    # TPP-Register (Third-Party-Provider)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dora_tpp_register (
            id TEXT PRIMARY KEY,
            projekt_name TEXT NOT NULL,
            name TEXT NOT NULL,
            kategorie TEXT DEFAULT 'cloud',
            kritisch INTEGER DEFAULT 0,
            beschreibung TEXT DEFAULT '',
            vertrag_url TEXT DEFAULT '',
            ansprechpartner TEXT DEFAULT '',
            risiko_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            meta_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (aics_now()),
            updated_at TEXT DEFAULT (aics_now())
        )
    """)
    cur.execute('CREATE INDEX IF NOT EXISTS idx_dora_tpp_projekt ON dora_tpp_register(projekt_name)')

    # Testing-Plan (TLPT + Vulnerability-Tests)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dora_testing_plan (
            id TEXT PRIMARY KEY,
            projekt_name TEXT NOT NULL,
            test_typ TEXT NOT NULL,
            scope TEXT DEFAULT '',
            frequenz TEXT DEFAULT '',
            naechster_termin TEXT DEFAULT '',
            status TEXT DEFAULT 'planned',
            verantwortlich TEXT DEFAULT '',
            ergebnis TEXT DEFAULT '',
            created_at TEXT DEFAULT (aics_now()),
            updated_at TEXT DEFAULT (aics_now())
        )
    """)
    cur.execute('CREATE INDEX IF NOT EXISTS idx_dora_test_projekt ON dora_testing_plan(projekt_name)')

    con.commit()
    con.close()


# ============================================================
# Projekte
# ============================================================

def save_projekt(
    db_path: Path,
    *,
    name: str,
    unternehmen: str = '',
    finanzeinrichtung_klasse: str = '',
    beschreibung: str = '',
    berater: str = '',
    meta_json: str = '{}',
) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    cur = con.cursor()
    existing = cur.execute('SELECT id FROM dora_projekte WHERE name=?', (name,)).fetchone()
    if existing:
        cur.execute("""
            UPDATE dora_projekte
            SET unternehmen=?, finanzeinrichtung_klasse=?, beschreibung=?, berater=?,
                meta_json=?, updated_at=aics_now()
            WHERE name=?
        """, (unternehmen, finanzeinrichtung_klasse, beschreibung, berater, meta_json, name))
    else:
        cur.execute("""
            INSERT INTO dora_projekte (name, unternehmen, finanzeinrichtung_klasse,
                                       beschreibung, berater, meta_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, unternehmen, finanzeinrichtung_klasse, beschreibung, berater, meta_json))
    con.commit()
    con.close()


def load_projekt(db_path: Path, name: str) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    cur = con.cursor()
    row = cur.execute('SELECT * FROM dora_projekte WHERE name=?', (name,)).fetchone()
    con.close()
    return dict(row) if row else None


def list_projekte(db_path: Path) -> list[str]:
    ensure_db(db_path)
    con = _connect(db_path)
    cur = con.cursor()
    rows = cur.execute('SELECT name FROM dora_projekte ORDER BY updated_at DESC, name').fetchall()
    con.close()
    return [r['name'] for r in rows]


def delete_projekt(db_path: Path, name: str) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    cur = con.cursor()
    cur.execute('DELETE FROM dora_bewertungen WHERE projekt_name=?', (name,))
    cur.execute('DELETE FROM dora_tpp_register WHERE projekt_name=?', (name,))
    cur.execute('DELETE FROM dora_testing_plan WHERE projekt_name=?', (name,))
    cur.execute('DELETE FROM dora_projekte WHERE name=?', (name,))
    con.commit()
    con.close()


# ============================================================
# Bewertungen
# ============================================================

def save_bewertung(
    db_path: Path,
    *,
    projekt_name: str,
    anforderung_id: str,
    bewertung: int,
    kommentar: str = '',
    massnahme: str = '',
    verantwortlich: str = '',
    zieldatum: str = '',
) -> None:
    ensure_db(db_path)
    bewertung = max(0, min(5, int(bewertung)))
    con = _connect(db_path)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO dora_bewertungen (projekt_name, anforderung_id, bewertung,
                                       kommentar, massnahme, verantwortlich, zieldatum, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, aics_now())
        ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET
            bewertung=excluded.bewertung,
            kommentar=excluded.kommentar,
            massnahme=excluded.massnahme,
            verantwortlich=excluded.verantwortlich,
            zieldatum=excluded.zieldatum,
            updated_at=aics_now()
    """, (projekt_name, anforderung_id, bewertung, kommentar, massnahme, verantwortlich, zieldatum))
    con.commit()
    con.close()


def load_bewertungen(db_path: Path, projekt_name: str) -> dict[str, dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    cur = con.cursor()
    rows = cur.execute(
        'SELECT * FROM dora_bewertungen WHERE projekt_name=?', (projekt_name,)
    ).fetchall()
    con.close()
    return {r['anforderung_id']: dict(r) for r in rows}


def bulk_save_bewertungen(db_path: Path, projekt_name: str, items: list[dict[str, Any]]) -> None:
    for item in items:
        save_bewertung(
            db_path,
            projekt_name=projekt_name,
            anforderung_id=item.get('anforderung_id') or item.get('id', ''),
            bewertung=int(item.get('bewertung', 0)),
            kommentar=item.get('kommentar', ''),
            massnahme=item.get('massnahme', ''),
            verantwortlich=item.get('verantwortlich', ''),
            zieldatum=item.get('zieldatum', ''),
        )


# ============================================================
# Custom-Anforderungen
# ============================================================

def save_custom_anforderung(db_path: Path, req: dict[str, Any]) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO dora_anforderungen_custom
            (id, pfeiler, ref, titel, beschreibung, hinweise, gewichtung, ist_override, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, aics_now())
        ON CONFLICT(id) DO UPDATE SET
            pfeiler=excluded.pfeiler,
            ref=excluded.ref,
            titel=excluded.titel,
            beschreibung=excluded.beschreibung,
            hinweise=excluded.hinweise,
            gewichtung=excluded.gewichtung,
            ist_override=excluded.ist_override,
            updated_at=aics_now()
    """, (
        req['id'], req.get('pfeiler', 'ICT-RM'), req.get('ref', ''),
        req.get('titel', ''), req.get('beschreibung', ''), req.get('hinweise', ''),
        int(req.get('gewichtung', 1)), 1 if req.get('ist_override') else 0,
    ))
    con.commit()
    con.close()


def delete_custom_anforderung(db_path: Path, req_id: str) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    con.execute('DELETE FROM dora_anforderungen_custom WHERE id=?', (req_id,))
    con.commit()
    con.close()


def load_custom_anforderungen(db_path: Path) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    rows = con.execute('SELECT * FROM dora_anforderungen_custom ORDER BY pfeiler, id').fetchall()
    con.close()
    return [dict(r) for r in rows]


# ============================================================
# TPP-Register (Third-Party-Provider)
# ============================================================

def save_tpp(
    db_path: Path,
    *,
    projekt_name: str,
    tpp: dict[str, Any],
) -> str:
    ensure_db(db_path)
    tid = tpp.get('id') or str(uuid.uuid4())
    con = _connect(db_path)
    con.execute("""
        INSERT INTO dora_tpp_register
            (id, projekt_name, name, kategorie, kritisch, beschreibung, vertrag_url,
             ansprechpartner, risiko_score, status, meta_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, aics_now())
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, kategorie=excluded.kategorie,
            kritisch=excluded.kritisch, beschreibung=excluded.beschreibung,
            vertrag_url=excluded.vertrag_url, ansprechpartner=excluded.ansprechpartner,
            risiko_score=excluded.risiko_score, status=excluded.status,
            meta_json=excluded.meta_json, updated_at=aics_now()
    """, (
        tid, projekt_name, tpp.get('name', ''), tpp.get('kategorie', 'cloud'),
        1 if tpp.get('kritisch') else 0, tpp.get('beschreibung', ''),
        tpp.get('vertrag_url', ''), tpp.get('ansprechpartner', ''),
        int(tpp.get('risiko_score', 0)), tpp.get('status', 'active'),
        tpp.get('meta_json', '{}'),
    ))
    con.commit()
    con.close()
    return tid


def list_tpp(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    rows = con.execute(
        'SELECT * FROM dora_tpp_register WHERE projekt_name=? ORDER BY kritisch DESC, name',
        (projekt_name,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def delete_tpp(db_path: Path, tpp_id: str) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    con.execute('DELETE FROM dora_tpp_register WHERE id=?', (tpp_id,))
    con.commit()
    con.close()


# ============================================================
# Testing-Plan (TLPT + Vulnerability-Tests)
# ============================================================

def save_test(
    db_path: Path,
    *,
    projekt_name: str,
    test: dict[str, Any],
) -> str:
    ensure_db(db_path)
    tid = test.get('id') or str(uuid.uuid4())
    con = _connect(db_path)
    con.execute("""
        INSERT INTO dora_testing_plan
            (id, projekt_name, test_typ, scope, frequenz, naechster_termin,
             status, verantwortlich, ergebnis, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, aics_now())
        ON CONFLICT(id) DO UPDATE SET
            test_typ=excluded.test_typ, scope=excluded.scope,
            frequenz=excluded.frequenz, naechster_termin=excluded.naechster_termin,
            status=excluded.status, verantwortlich=excluded.verantwortlich,
            ergebnis=excluded.ergebnis, updated_at=aics_now()
    """, (
        tid, projekt_name, test.get('test_typ', 'TLPT'), test.get('scope', ''),
        test.get('frequenz', ''), test.get('naechster_termin', ''),
        test.get('status', 'planned'), test.get('verantwortlich', ''),
        test.get('ergebnis', ''),
    ))
    con.commit()
    con.close()
    return tid


def list_tests(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    rows = con.execute(
        'SELECT * FROM dora_testing_plan WHERE projekt_name=? ORDER BY naechster_termin, test_typ',
        (projekt_name,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def delete_test(db_path: Path, test_id: str) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    con.execute('DELETE FROM dora_testing_plan WHERE id=?', (test_id,))
    con.commit()
    con.close()
