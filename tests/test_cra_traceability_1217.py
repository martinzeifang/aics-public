"""Tests #1217: CRA Art. 13(1)/Annex VII Traceability + Vollständigkeitsmatrix.

- cra_dokumente um anforderung_id/owasp_id/annex_baustein erweitert + befüllt.
- Per-Requirement Nachweis↔Anforderung-Verknüpfung (belegt/fehlt).
- Granulare Annex-VII-Content-Matrix (Einzel-Zeilen) mit Ampel.
- Endpoints /requirement-traceability + /annex-vii-status.
"""
import pytest

CRA = '/api/cra'
TRC = '/api/cra-traceability'
FIRMA = 'pytest-firma-1217'
PROJ = 'pytest-cra-1217'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': PROJ, 'unternehmen': FIRMA})
    yield PROJ
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)


# ── DB-Ebene (tmp-DB) ─────────────────────────────────────────────────────────

def test_dokumente_columns_migration(tmp_path):
    """cra_dokumente besitzt die #1217-Spalten (Migration/Schema)."""
    from cra import traceability_db as tdb
    db = tmp_path / 'cra.sqlite'
    tdb.ensure_db(db)
    con = tdb._connect(db)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(cra_dokumente)").fetchall()}
    finally:
        con.close()
    assert {'anforderung_id', 'owasp_id', 'annex_baustein'} <= cols


def test_dokumente_columns_migration_legacy(tmp_path):
    """Bestehende alte cra_dokumente-Tabelle wird idempotent migriert."""
    from cra import traceability_db as tdb
    db = tmp_path / 'cra.sqlite'
    con = tdb._connect(db)
    con.execute("CREATE TABLE cra_dokumente (id INTEGER PRIMARY KEY, "
                "projekt_name TEXT, doc_name TEXT, doc_path TEXT, doc_type TEXT)")
    con.commit()
    con.close()
    tdb.ensure_db(db)  # fügt die fehlenden Spalten per ALTER hinzu
    con = tdb._connect(db)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(cra_dokumente)").fetchall()}
    finally:
        con.close()
    assert {'anforderung_id', 'owasp_id', 'annex_baustein'} <= cols


def test_requirement_traceability(tmp_path):
    from cra import traceability_db as tdb
    db = tmp_path / 'cra.sqlite'
    trace = tdb.requirement_traceability(db, PROJ)
    assert trace and all(r['ampel'] == 'fehlt' for r in trace)  # noch nichts belegt
    rid = trace[0]['anforderung_id']
    tdb.create_dokument(db, PROJ, 'Nachweis A', doc_type='testbericht',
                        anforderung_id=rid)
    trace2 = tdb.requirement_traceability(db, PROJ)
    belegt = [r for r in trace2 if r['anforderung_id'] == rid][0]
    assert belegt['ampel'] == 'belegt'
    assert belegt['nachweis_count'] == 1


def test_annex_vii_status(tmp_path):
    from cra import traceability_db as tdb
    db = tmp_path / 'cra.sqlite'
    st = tdb.annex_vii_status(db, PROJ)
    assert st['gesamt_count'] == len(tdb.ANNEX_VII_BAUSTEINE)
    assert st['belegt_count'] == 0 and st['vollstaendig'] is False
    # SBOM-Baustein per doc_type belegen
    tdb.create_dokument(db, PROJ, 'sbom.json', doc_type='sbom')
    # Testberichte per annex_baustein-Schlüssel belegen
    tdb.create_dokument(db, PROJ, 'pentest', annex_baustein='testberichte')
    st2 = tdb.annex_vii_status(db, PROJ)
    rows = {b['key']: b for b in st2['bausteine']}
    assert rows['sbom']['ampel'] == 'belegt'
    assert rows['testberichte']['ampel'] == 'belegt'
    assert st2['belegt_count'] == 2


# ── Endpoints ─────────────────────────────────────────────────────────────────

def test_traceability_api(client, auth_headers, projekt):
    # Annex-VII-Status leer
    r = client.get(f'{TRC}/projekte/{projekt}/annex-vii-status', headers=auth_headers)
    assert r.status_code == 200, r.json
    assert r.json['belegt_count'] == 0

    # Nachweis anlegen + zuordnen
    r = client.post(f'{TRC}/projekte/{projekt}/dokumente', headers=auth_headers,
                    json={'doc_name': 'DoC-2026', 'doc_type': 'doc',
                          'annex_baustein': 'doc'})
    assert r.status_code == 201, r.json
    did = r.json['id']

    r = client.get(f'{TRC}/projekte/{projekt}/annex-vii-status', headers=auth_headers)
    rows = {b['key']: b for b in r.json['bausteine']}
    assert rows['doc']['ampel'] == 'belegt'

    # Link auf Anforderung
    r = client.put(f'{TRC}/projekte/{projekt}/dokumente/{did}/link', headers=auth_headers,
                   json={'anforderung_id': 'ART13-01'})
    assert r.status_code == 200, r.json
    assert r.json['anforderung_id'] == 'ART13-01'

    r = client.get(f'{TRC}/projekte/{projekt}/requirement-traceability', headers=auth_headers)
    art = [x for x in r.json if x['anforderung_id'] == 'ART13-01'][0]
    assert art['ampel'] == 'belegt'


def test_idor_scoped(client, auth_headers, projekt):
    r = client.post(f'{TRC}/projekte/{projekt}/dokumente', headers=auth_headers,
                    json={'doc_name': 'X', 'doc_type': 'resource'})
    did = r.json['id']
    # Link aus fremdem Projekt → 404
    r = client.put(f'{TRC}/projekte/fremd-projekt/dokumente/{did}/link',
                   headers=auth_headers, json={'anforderung_id': 'ART13-01'})
    assert r.status_code == 404
