"""Regression: Firmen-Anlage initialisiert Modul-DBs (Docker-Bug).

In einem frischen Volume schrieb das Firmen-Blueprint in cra/nis2/dsgvo/ai_act-DBs,
ohne deren Tabellen via ensure_db() anzulegen → "no such table: cra_projekte".
Anders als risikobewertung self-initialisieren diese Module beim Connect NICHT.

Hinweis: Die DB-Security (shared/db_security) erlaubt nur Pfade unterhalb des
Repo-Roots — daher legen wir die Test-DBs unter data/db/ an (mit Cleanup), nicht
in tmp_path.
"""

import uuid
from pathlib import Path

import pytest

from cra.db import ensure_db as cra_ensure, save_projekt as cra_save
from nis2.db import ensure_db as nis2_ensure, save_projekt as nis2_save
from dsgvo.db import ensure_db as dsgvo_ensure, save_projekt as dsgvo_save
from ai_act.db import ensure_db as aiact_ensure, save_projekt as aiact_save

_DB_DIR = Path('data/db')


@pytest.fixture
def fresh_repo_db():
    """Liefert einen frischen, eindeutigen DB-Pfad unter data/db/ + räumt auf."""
    created: list[Path] = []

    def _make(label: str) -> Path:
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        p = _DB_DIR / f'_test_{label}_{uuid.uuid4().hex[:8]}.sqlite'
        created.append(p)
        return p

    yield _make
    for p in created:
        try:
            p.unlink()
        except FileNotFoundError:
            pass


@pytest.mark.parametrize('label,ensure,save', [
    ('cra', cra_ensure, lambda p: cra_save(p, name='K', unternehmen='U', produkt='P',
                                           produktklasse='default', beschreibung='', berater='')),
    ('nis2', nis2_ensure, lambda p: nis2_save(p, name='K', unternehmen='U', beschreibung='', berater='')),
    ('dsgvo', dsgvo_ensure, lambda p: dsgvo_save(p, name='K', unternehmen='U', beschreibung='', berater='')),
    ('ai_act', aiact_ensure, lambda p: aiact_save(p, name='K', organisation='U', produkt='P', beschreibung='')),
])
def test_ensure_db_then_save_on_fresh_db(fresh_repo_db, label, ensure, save):
    """ensure_db legt Tabellen an; save_projekt danach ohne 'no such table'."""
    db = fresh_repo_db(label)
    ensure(db)
    save(db)  # darf nicht werfen


def test_firmen_blueprint_initializes_module_dbs():
    """Import des Firmen-Blueprints löst die idempotente Modul-DB-Init aus."""
    import importlib
    mod = importlib.import_module('server.api.firmen')
    assert hasattr(mod, 'firmen_bp')
    assert hasattr(mod, 'cra_ensure_db')  # Teil des Fixes


@pytest.mark.skip(reason='SQLite-spezifischer Legacy-Migrationspfad, unter Postgres '
                         'gegenstandslos (#15): _migrate_legacy_db_file benennt eine '
                         'kunden.sqlite-DATEI um — unter Postgres gibt es nur Schemata, '
                         'keine .sqlite-Dateien.')
def test_legacy_kunden_db_migration(fresh_repo_db):
    """#1003: alte kunden.sqlite / Tabelle kunden / Spalte kunden_id werden
    verlustfrei nach firmen migriert (idempotent)."""


def test_legacy_evidence_kunden_id_migration(fresh_repo_db, pg):
    """#1003: evidence.kunden_id → firmen_id (Daten erhalten)."""
    from shared import db as _sdb
    import evidence.db as edb

    ev = fresh_repo_db('evmig')
    pg.drop_schema(ev)
    con = _sdb.connect(ev)
    con.executescript(
        "CREATE TABLE evidence_documents (id INTEGER PRIMARY KEY, filename TEXT, "
        "title TEXT, source_type TEXT, mime TEXT, sha256 TEXT, size_bytes INTEGER, "
        "version TEXT, tags_json TEXT, added_at INTEGER, updated_at INTEGER, "
        "kunden_id TEXT DEFAULT '');"
        "CREATE TABLE evidence_mappings_approved (id INTEGER PRIMARY KEY, "
        "requirement_id TEXT, doc_id INTEGER, snippet TEXT, score REAL, "
        "approved_by TEXT, approved_at INTEGER, kunden_id TEXT DEFAULT '');"
        "INSERT INTO evidence_documents (id,filename,kunden_id) VALUES (1,'f.pdf','Acme GmbH');"
    )
    con.commit(); con.close()
    edb.ensure_db(ev)
    con = _sdb.connect(ev)
    cols = {r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema=current_schema() AND table_name='evidence_documents'")}
    assert 'firmen_id' in cols and 'kunden_id' not in cols
    assert con.execute("SELECT firmen_id FROM evidence_documents WHERE id=1").fetchone()[0] == 'Acme GmbH'
    con.close()
