"""DS1 (#1101) — DB-Level-Tests für das praxistaugliche VVT (Art. 30).

Verwendet eine temporäre dsgvo-SQLite unter ``data/db/_pytest_*.sqlite`` (innerhalb
des Repo-Roots, von ``connect_sqlite`` zugelassen) und räumt sie hinterher auf.
Das Blueprint wird NICHT benötigt — getestet wird der DB-Layer in ``dsgvo/db.py``.
"""
import sqlite3
import uuid
from pathlib import Path

import pytest

from dsgvo.db import (
    ensure_db,
    save_vvt,
    list_vvt,
    delete_vvt,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# #1101: neue Art.-30-Praxisfelder, die garantiert vorhanden sein müssen.
NEW_FIELDS = (
    'rolle', 'art9_grundlage', 'datenfluss',
    'loeschfrist_ref', 'tom_ref', 'dsfa_trigger',
)


@pytest.fixture()
def db_path():
    p = REPO_ROOT / 'data' / 'db' / f'_pytest_vvt_{uuid.uuid4().hex}.sqlite'
    p.parent.mkdir(parents=True, exist_ok=True)
    yield p
    for suffix in ('', '-wal', '-shm'):
        f = Path(str(p) + suffix)
        if f.exists():
            f.unlink()


def _columns(db_path: Path) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        return {r[1] for r in con.execute("PRAGMA table_info(dsgvo_vvt_pflicht)")}
    finally:
        con.close()


def test_ensure_db_idempotent_and_new_columns(db_path):
    ensure_db(db_path)
    ensure_db(db_path)  # zweiter Aufruf darf nicht scheitern
    cols = _columns(db_path)
    for field in NEW_FIELDS:
        assert field in cols, f"Spalte {field} fehlt im VVT-Schema"


def test_save_and_list_with_new_fields(db_path):
    ensure_db(db_path)
    rid = save_vvt(db_path, 'P1', {
        'vvt_id': 'VVT-001', 'name': 'CRM',
        'zweck': 'Vertragsabwicklung', 'loeschfrist': '10 Jahre',
        'rolle': 'verantwortlicher', 'art9_grundlage': 'Art. 9(2)(a)',
        'datenfluss': 'Web -> CRM', 'loeschfrist_ref': 'LK-3.2',
        'tom_ref': 'TOM-003', 'dsfa_trigger': 1,
    })
    assert rid > 0
    rows = list_vvt(db_path, 'P1')
    assert len(rows) == 1
    r = rows[0]
    assert r['rolle'] == 'verantwortlicher'
    assert r['art9_grundlage'] == 'Art. 9(2)(a)'
    assert r['datenfluss'] == 'Web -> CRM'
    assert r['loeschfrist_ref'] == 'LK-3.2'
    assert r['tom_ref'] == 'TOM-003'
    assert int(r['dsfa_trigger']) == 1


def test_dsfa_trigger_coercion(db_path):
    ensure_db(db_path)
    # String '1' / True / leer korrekt auf 0/1 normalisieren
    save_vvt(db_path, 'P1', {'vvt_id': 'V-A', 'name': 'A', 'loeschfrist': 'x', 'dsfa_trigger': '1'})
    save_vvt(db_path, 'P1', {'vvt_id': 'V-B', 'name': 'B', 'loeschfrist': 'x', 'dsfa_trigger': True})
    save_vvt(db_path, 'P1', {'vvt_id': 'V-C', 'name': 'C', 'loeschfrist': 'x'})
    by_id = {r['vvt_id']: int(r['dsfa_trigger']) for r in list_vvt(db_path, 'P1')}
    assert by_id == {'V-A': 1, 'V-B': 1, 'V-C': 0}


def test_rolle_default_and_validation(db_path):
    ensure_db(db_path)
    # ungültige Rolle -> Default 'verantwortlicher'
    save_vvt(db_path, 'P1', {'vvt_id': 'V-1', 'name': 'X', 'loeschfrist': 'x', 'rolle': 'quatsch'})
    save_vvt(db_path, 'P1', {'vvt_id': 'V-2', 'name': 'Y', 'loeschfrist': 'x', 'rolle': 'auftragsverarbeiter'})
    by_id = {r['vvt_id']: r['rolle'] for r in list_vvt(db_path, 'P1')}
    assert by_id['V-1'] == 'verantwortlicher'
    assert by_id['V-2'] == 'auftragsverarbeiter'


def test_rolle_filter(db_path):
    ensure_db(db_path)
    save_vvt(db_path, 'P1', {'vvt_id': 'V-1', 'name': 'X', 'loeschfrist': 'x', 'rolle': 'verantwortlicher'})
    save_vvt(db_path, 'P1', {'vvt_id': 'V-2', 'name': 'Y', 'loeschfrist': 'x', 'rolle': 'auftragsverarbeiter'})
    assert {r['vvt_id'] for r in list_vvt(db_path, 'P1')} == {'V-1', 'V-2'}
    v = list_vvt(db_path, 'P1', rolle='verantwortlicher')
    assert {r['vvt_id'] for r in v} == {'V-1'}
    av = list_vvt(db_path, 'P1', rolle='auftragsverarbeiter')
    assert {r['vvt_id'] for r in av} == {'V-2'}


def test_existing_rows_preserved_after_migration(db_path):
    """Alte DB ohne neue Spalten: Migration in ensure_db darf bestehende Zeilen
    nicht zerstören und neue Spalten mit Defaults nachrüsten."""
    # Minimal-DB im 'alten' Schema (ohne #1101-Felder) anlegen + Zeile einfügen.
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE dsgvo_vvt_pflicht (
            id INTEGER PRIMARY KEY,
            projekt_name TEXT NOT NULL,
            vvt_id TEXT NOT NULL,
            name TEXT NOT NULL,
            zweck TEXT NOT NULL DEFAULT '',
            rechtsgrundlage TEXT NOT NULL DEFAULT '',
            betroffene_kategorien TEXT NOT NULL DEFAULT '',
            datenkategorien TEXT NOT NULL DEFAULT '',
            empfaenger TEXT NOT NULL DEFAULT '',
            drittland TEXT NOT NULL DEFAULT '',
            loeschfrist TEXT NOT NULL DEFAULT '',
            tom_referenz TEXT NOT NULL DEFAULT '',
            verantwortlich TEXT NOT NULL DEFAULT '',
            notizen TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(projekt_name, vvt_id)
        )
    """)
    con.execute(
        "INSERT INTO dsgvo_vvt_pflicht (projekt_name, vvt_id, name, zweck) VALUES (?,?,?,?)",
        ('P1', 'OLD-1', 'Bestand', 'Altzweck'))
    con.commit()
    con.close()

    ensure_db(db_path)  # Migration

    rows = list_vvt(db_path, 'P1')
    assert len(rows) == 1
    r = rows[0]
    assert r['vvt_id'] == 'OLD-1'
    assert r['name'] == 'Bestand'
    assert r['zweck'] == 'Altzweck'
    # neue Spalten mit Defaults vorhanden
    assert r['rolle'] == 'verantwortlicher'
    assert int(r['dsfa_trigger']) == 0
    assert r['art9_grundlage'] == ''


def test_delete_vvt(db_path):
    ensure_db(db_path)
    rid = save_vvt(db_path, 'P1', {'vvt_id': 'V-1', 'name': 'X', 'loeschfrist': 'x'})
    assert len(list_vvt(db_path, 'P1')) == 1
    delete_vvt(db_path, rid)
    assert list_vvt(db_path, 'P1') == []
