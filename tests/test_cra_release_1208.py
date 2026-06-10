"""Tests #1208: CRA Art. 13(4) Wesentliche Änderung + Release-Versionierung.

- Release/Version-Achse über cra_projekte.
- 'Wesentliche Änderung' setzt Nachweise auf Re-Assessment + friert alte Version.
- Endpoint POST /projekte/<p>/substantial-modification.
"""
import pytest

CRA = '/api/cra'
REL = '/api/cra-release'
FIRMA = 'pytest-firma-1208'
PROJ = 'pytest-cra-1208'


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


def test_substantial_modification_db(tmp_path):
    from cra import release_db as rdb
    db = tmp_path / 'cra.sqlite'
    rdb.save_release(db, PROJ, {'aktuelle_version': 'v1.0'})
    res = rdb.substantial_modification(db, PROJ, neue_version='v2.0',
                                       grund='Neue Krypto-Bibliothek')
    assert res['eingefrorene_version'] == 'v1.0'
    assert res['release']['aktuelle_version'] == 'v2.0'
    # Re-Assessment-Checkliste auf offen gesetzt
    assert res['release']['reassess']['risikobewertung'] == 'offen'
    assert res['release']['reassess']['doc'] == 'offen'
    # alte Version als Snapshot eingefroren
    assert any(s['version'] == 'v1.0' for s in res['snapshots'])


def test_substantial_modification_api(client, auth_headers, projekt):
    r = client.post(f'{REL}/projekte/{projekt}/substantial-modification',
                    headers=auth_headers,
                    json={'neue_version': 'v2.0', 'grund': 'Wesentliche Funktionsänderung'})
    assert r.status_code == 201, r.json
    assert r.json['release']['aktuelle_version'] == 'v2.0'

    r = client.get(f'{REL}/projekte/{projekt}/release', headers=auth_headers)
    assert r.status_code == 200
    assert r.json['snapshots']
    assert r.json['reassess']['konformitaetsbewertung'] == 'offen'


def test_substantial_modification_validation(client, auth_headers, projekt):
    r = client.post(f'{REL}/projekte/{projekt}/substantial-modification',
                    headers=auth_headers, json={'neue_version': 'v2'})
    assert r.status_code == 400  # Grund fehlt
    r = client.post(f'{REL}/projekte/{projekt}/substantial-modification',
                    headers=auth_headers, json={'grund': 'lang genug'})
    assert r.status_code == 400  # version fehlt
