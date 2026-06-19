"""Tests #1201: CRA Art. 32/Annex VIII Konformitätsbewertung + DoC/CE.

- cra_konformitaet-Register mit Bewertungsweg + NB-Kennnummer + CE-Status.
- Nachweis-Checkliste je Modul (A/B+C/H/EUCC).
- Gate: DoC ausstellbar erst bei abgeschlossenem Bewertungsweg.
- Endpoints GET/PUT /konformitaet (+/doc).
"""
import pytest

CRA = '/api/cra'
KONF = '/api/cra-konformitaet'
FIRMA = 'pytest-firma-1201'
PROJ = 'pytest-cra-1201'


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


def test_checkliste_constants(client, auth_headers):
    r = client.get(f'{KONF}/constants', headers=auth_headers)
    assert r.status_code == 200
    assert 'A' in r.json['wege'] and 'EUCC' in r.json['wege']
    assert 'nb_zertifikat' in r.json['checkliste']['H']


def test_doc_gate(tmp_path):
    from cra import konformitaet_db as kdb
    db = tmp_path / 'cra.sqlite'
    kdb.save_konformitaet(db, PROJ, {'bewertungsweg': 'H', 'nb_kennnummer': '0123'})
    # Gate: Bewertung nicht abgeschlossen → DoC verboten
    with pytest.raises(ValueError):
        kdb.issue_doc(db, PROJ, {'modell': 'X'})
    kdb.save_konformitaet(db, PROJ, {'bewertungsweg': 'H', 'nb_kennnummer': '0123',
                                     'bewertung_abgeschlossen': True})
    rec = kdb.issue_doc(db, PROJ, {'modell': 'X', 'hersteller': FIRMA})
    assert rec['doc_ausgestellt'] is True
    assert rec['doc_version'] == 1
    assert rec['ce_status'] == 'doc_ausgestellt'
    assert rec['soll_nachweise']  # Checkliste für H


def test_konformitaet_api(client, auth_headers, projekt):
    r = client.put(f'{KONF}/projekte/{projekt}/konformitaet', headers=auth_headers,
                   json={'bewertungsweg': 'B+C', 'nb_kennnummer': '0456',
                         'ce_status': 'in_bewertung'})
    assert r.status_code == 200, r.json
    assert r.json['bewertungsweg'] == 'B+C'
    assert r.json['nb_kennnummer'] == '0456'

    # DoC ohne abgeschlossene Bewertung → 409 (Gate)
    r = client.post(f'{KONF}/projekte/{projekt}/konformitaet/doc', headers=auth_headers,
                    json={'doc': {'modell': 'Y'}})
    assert r.status_code == 409

    client.put(f'{KONF}/projekte/{projekt}/konformitaet', headers=auth_headers,
               json={'bewertungsweg': 'B+C', 'bewertung_abgeschlossen': True})
    r = client.post(f'{KONF}/projekte/{projekt}/konformitaet/doc', headers=auth_headers,
                    json={'doc': {'modell': 'Y'}})
    assert r.status_code == 200, r.json
    assert r.json['doc_ausgestellt'] is True
