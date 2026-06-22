"""Tests #1209: CRA Art. 13(9)/(13)/(16) Retention-/Update-Fristen + Art. 14(8) Advisory.

- update_availability_until + doku_retention_until + doc_retention_until berechnet.
- support_end_kaufhinweis-Nachweisfeld (13(16)) persistiert.
- Nutzer-Advisory je Meldung (14(8)) — siehe auch test_cra_meldung_1192.
"""
import pytest

CRA = '/api/cra'
FIRMA = 'pytest-firma-1209'
PROJ = 'pytest-cra-1209'


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


def test_retention_computed():
    import uuid
    from pathlib import Path
    from cra.db import save_support_period, load_support_period
    # cra.db._connect erzwingt Workspace-Root → DB innerhalb data/db ablegen.
    db = Path('data/db') / f'pytest-1209-{uuid.uuid4().hex}.sqlite'
    db.parent.mkdir(parents=True, exist_ok=True)
    save_support_period(db, PROJ, {
        'markteintritt_datum': '2026-01-01', 'support_jahre': 7,
        'support_end_kaufhinweis_url': 'https://example.com/eol',
        'support_end_kaufhinweis_nachweis': 'Screenshot Produktseite',
    })
    sp = load_support_period(db, PROJ)
    # Update-Verfügbarkeit = max(10, 7) Jahre ab Markteintritt
    assert sp['update_availability_until'].startswith('2035')
    # Doku/DoC-Retention = 10 Jahre
    assert sp['doku_retention_until'].startswith('2035')
    assert sp['doc_retention_until'].startswith('2035')
    assert sp['support_end_kaufhinweis_url'] == 'https://example.com/eol'
    assert sp['support_end_kaufhinweis_nachweis'] == 'Screenshot Produktseite'
    for suffix in ('', '-wal', '-shm'):
        p = db.with_name(db.name + suffix)
        if p.exists():
            p.unlink()


def test_retention_via_api(client, auth_headers, projekt):
    r = client.post(f'{CRA}/projekte/{projekt}/support-period', headers=auth_headers,
                    json={'markteintritt_datum': '2026-03-01', 'support_jahre': 5,
                          'support_end_kaufhinweis_nachweis': 'Datenblatt §13(16)'})
    assert r.status_code == 200, r.json
    data = r.json['data']
    # Support 5 J < 10 → Update-Verfügbarkeit 10 J
    assert data['update_availability_until'].startswith('2036')
    assert data['support_end_kaufhinweis_nachweis'] == 'Datenblatt §13(16)'


def test_advisory_record(tmp_path):
    from cra import meldung_db as mdb
    db = tmp_path / 'cra.sqlite'
    mid = mdb.create_meldung(db, PROJ, {'typ': 'vuln_exploited', 'titel': 'CVE'})
    m = mdb.set_advisory(db, mid, PROJ, {
        'empfohlene_massnahmen': 'Update', 'schweregrad': 'critical',
        'betroffene_produkte': ['ProdX 1.0'], 'veroeffentlichungskanal': 'CSAF'})
    assert m['advisory']['schweregrad'] == 'critical'
    assert m['advisory']['betroffene_produkte'] == ['ProdX 1.0']
