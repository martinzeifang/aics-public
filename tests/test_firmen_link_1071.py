"""S1 (#1071) — Firmen-FK-Härtung: firmen_id-Spalte + Name-Match-Backfill."""
import sqlite3
from pathlib import Path

import pytest

from shared.firmen_link import (ensure_firmen_id_column, backfill_firmen_ids,
                                firmen_name_to_id)

_DB_DIR = Path("data/db")


@pytest.fixture
def dbs():
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    firmen = _DB_DIR / "_pytest_fk_firmen.sqlite"
    module = _DB_DIR / "_pytest_fk_module.sqlite"
    for p in (firmen, module):
        for sfx in ("", "-wal", "-shm"):
            Path(str(p) + sfx).unlink(missing_ok=True)
    fc = sqlite3.connect(str(firmen))
    fc.execute("CREATE TABLE firmen (id INTEGER PRIMARY KEY, name TEXT UNIQUE, is_deleted INTEGER DEFAULT 0)")
    fc.executemany("INSERT INTO firmen(id,name,is_deleted) VALUES(?,?,?)",
                   [(7, "Cyberwoks", 0), (8, "AI Compliance Suite", 0), (9, "Alt GmbH", 1)])
    fc.commit(); fc.close()
    mc = sqlite3.connect(str(module))
    mc.execute("CREATE TABLE rb_projekte (name TEXT PRIMARY KEY, unternehmen TEXT NOT NULL DEFAULT '')")
    mc.executemany("INSERT INTO rb_projekte(name,unternehmen) VALUES(?,?)",
                   [("P1", "Cyberwoks"), ("P2", "cyberwoks"),  # case-insensitive
                    ("P3", "Unbekannt GmbH"), ("P4", ""),       # unmatched / empty
                    ("P5", "Alt GmbH")])                          # gelöschte Firma → kein Match
    mc.commit(); mc.close()
    yield module, firmen
    for p in (firmen, module):
        for sfx in ("", "-wal", "-shm"):
            Path(str(p) + sfx).unlink(missing_ok=True)


def test_name_map_skips_deleted(dbs):
    _module, firmen = dbs
    m = firmen_name_to_id(firmen)
    assert m == {"cyberwoks": 7, "ai compliance suite": 8}  # 'Alt GmbH' (deleted) fehlt


def test_ensure_column_idempotent(dbs):
    module, _firmen = dbs
    con = sqlite3.connect(str(module))
    ensure_firmen_id_column(con, "rb_projekte")
    ensure_firmen_id_column(con, "rb_projekte")  # 2. Aufruf darf nicht fehlschlagen
    cols = [r[1] for r in con.execute("PRAGMA table_info(rb_projekte)")]
    con.close()
    assert "firmen_id" in cols


def test_backfill_matches_and_reports_unmatched(dbs):
    module, firmen = dbs
    res = backfill_firmen_ids(module, "rb_projekte", firmen_db=firmen)
    assert res["matched"] == 2  # P1 + P2 (case-insensitive)
    # P3 (Unbekannt) + P5 (gelöschte Firma) bleiben unmatched; P4 (leer) zählt nicht
    assert set(res["unmatched"]) == {"Unbekannt GmbH", "Alt GmbH"}
    con = sqlite3.connect(str(module))
    rows = dict(con.execute("SELECT name, firmen_id FROM rb_projekte").fetchall())
    con.close()
    assert rows["P1"] == 7 and rows["P2"] == 7
    assert rows["P3"] is None and rows["P4"] is None and rows["P5"] is None


def test_backfill_idempotent(dbs):
    module, firmen = dbs
    backfill_firmen_ids(module, "rb_projekte", firmen_db=firmen)
    res2 = backfill_firmen_ids(module, "rb_projekte", firmen_db=firmen)
    assert res2["matched"] == 0  # bereits zugeordnete werden nicht erneut angefasst
