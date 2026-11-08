"""#1511 — Risiko-Cockpit „Firmen nicht zugeordnet" bei Neuinstallation.

Deckt die beiden Fixes ab:
1. ``assign_firmen_id_on_save`` setzt firmen_id bei Projektanlage per Name-Match.
2. Der Cockpit-Resolver (``/by-projekt``) ist PG-sicher (kein .exists()-Guard) und
   liefert die firmen_id eines frisch angelegten Projekts (nicht „unassigned").
"""
from pathlib import Path

import pytest

from shared import db as _sdb
from shared.firmen_link import assign_firmen_id_on_save

_DB_DIR = Path("data/db")


@pytest.fixture
def dbs(pg):
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    firmen = _DB_DIR / "_pytest_1511_firmen.sqlite"
    module = _DB_DIR / "_pytest_1511_module.sqlite"
    # drop_schema truncatet bestehende Tabellen (löscht sie nicht) → IF NOT EXISTS
    # passt zur Harness-Semantik (#1396) und ist über mehrere Tests hinweg stabil.
    for p in (firmen, module):
        pg.drop_schema(p)
    fc = _sdb.connect(firmen)
    fc.execute("CREATE TABLE IF NOT EXISTS firmen (id INTEGER PRIMARY KEY, name TEXT UNIQUE, is_deleted INTEGER DEFAULT 0)")
    fc.executemany("INSERT INTO firmen(id,name,is_deleted) VALUES(?,?,?)",
                   [(7, "Cyberwoks", 0)])
    fc.commit(); fc.close()
    mc = _sdb.connect(module)
    mc.execute("CREATE TABLE IF NOT EXISTS rb_projekte (name TEXT PRIMARY KEY, unternehmen TEXT NOT NULL DEFAULT '')")
    mc.commit(); mc.close()
    yield module, firmen


def _firmen_id(module, name):
    con = _sdb.connect(module)
    try:
        row = con.execute("SELECT firmen_id FROM rb_projekte WHERE name=?", (name,)).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def test_assign_sets_firmen_id_on_match(dbs):
    module, firmen = dbs
    con = _sdb.connect(module)
    try:
        con.execute("INSERT INTO rb_projekte(name, unternehmen) VALUES(?,?)", ("P1", "Cyberwoks"))
        con.commit()
        assign_firmen_id_on_save(con, module, "rb_projekte", "P1", "Cyberwoks", firmen_db=firmen)
    finally:
        con.close()
    assert _firmen_id(module, "P1") == 7


def test_assign_case_insensitive(dbs):
    module, firmen = dbs
    con = _sdb.connect(module)
    try:
        con.execute("INSERT INTO rb_projekte(name, unternehmen) VALUES(?,?)", ("P2", "cyberwoks"))
        con.commit()
        assign_firmen_id_on_save(con, module, "rb_projekte", "P2", "cyberwoks", firmen_db=firmen)
    finally:
        con.close()
    assert _firmen_id(module, "P2") == 7


def test_assign_noop_without_match_or_name(dbs):
    module, firmen = dbs
    con = _sdb.connect(module)
    try:
        con.execute("INSERT INTO rb_projekte(name, unternehmen) VALUES(?,?)", ("P3", "Unbekannt GmbH"))
        con.execute("INSERT INTO rb_projekte(name, unternehmen) VALUES(?,?)", ("P4", ""))
        con.commit()
        assign_firmen_id_on_save(con, module, "rb_projekte", "P3", "Unbekannt GmbH", firmen_db=firmen)
        assign_firmen_id_on_save(con, module, "rb_projekte", "P4", "", firmen_db=firmen)
    finally:
        con.close()
    assert _firmen_id(module, "P3") is None
    assert _firmen_id(module, "P4") is None


# ── Integration über die echte API (CRA-Projekt + Cockpit-Resolver) ─────────

@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def test_unassigned_endpoint_always_returns_lists(client, auth_headers):
    """#1511-Regression (Firefox-Smoke): /firmen-link/unassigned darf NIE einen
    Fehler-Dict pro Modul liefern (z. B. SOC soc_assets ohne 'name'-Spalte) — sonst
    crasht die FirmenLinkView mit 'list is not iterable'. Immer Listen."""
    r = client.get('/api/admin/firmen-link/unassigned', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    unassigned = r.get_json()['unassigned']
    for dbfile, val in unassigned.items():
        assert isinstance(val, list), f'{dbfile} ist kein list: {val!r}'


def test_cockpit_by_projekt_resolves_fresh_firma(client, auth_headers):
    firma = 'ACME-1511-Cockpit'
    proj = 'pytest-1511-cra'
    # Firma anlegen.
    client.post('/api/firmen', headers=auth_headers, json={'name': firma})
    # CRA-Projekt mit passendem Firmennamen anlegen → firmen_id sollte auto-gesetzt werden.
    client.delete(f'/api/cra/projekte/{proj}', headers=auth_headers)
    r = client.post('/api/cra/projekte', headers=auth_headers,
                    json={'name': proj, 'unternehmen': firma})
    assert r.status_code in (200, 201), r.get_json()
    try:
        # Cockpit-Resolver darf NICHT „unassigned" liefern.
        rc = client.get(f'/api/risk-cockpit/by-projekt/cra/{proj}', headers=auth_headers)
        assert rc.status_code == 200, rc.get_json()
        body = rc.get_json()
        assert body.get('unassigned') is not True, body
        assert body.get('firmen_id'), body
    finally:
        client.delete(f'/api/cra/projekte/{proj}', headers=auth_headers)
        client.delete(f'/api/firmen/{firma}', headers=auth_headers)
