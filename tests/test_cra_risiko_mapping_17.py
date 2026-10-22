"""Tests Stufe 2: Risiko↔CRA-Anforderung-Mapping + Abdeckungs-Sicht (#884/#885)."""

import pytest

CRA = '/api/cra'
RB = '/api/risikobewertung'
FIRMA = 'pytest-firma-map17'
CRA_PROJ = 'pytest-cra-map17'
RB_PROJ = 'pytest-rb-map17'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _clear_links():
    import sqlite3
    from server.api.risikobewertung import DB_PATH as RB_DB
    try:
        con = sqlite3.connect(str(RB_DB))
        con.execute("DELETE FROM risk_requirement_links WHERE rb_projekt_name=?", (RB_PROJ,))
        con.commit(); con.close()
    except Exception:
        pass


@pytest.fixture
def setup(client, auth_headers):
    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)
    client.delete(f'{RB}/projekte/{RB_PROJ}', headers=auth_headers)
    _clear_links()
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': CRA_PROJ, 'unternehmen': FIRMA})
    client.post(f'{RB}/projekte', headers=auth_headers,
                json={'name': RB_PROJ, 'framework': 'STRIDE', 'unternehmen': FIRMA})
    client.put(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers,
               json={'risk_projekt': RB_PROJ})
    r = client.post(f'{RB}/projekte/{RB_PROJ}/risiken', headers=auth_headers,
                    json={'risk_name': 'Mapping-Risiko', 'framework': 'STRIDE', 'felder': {}})
    risk_id = r.get_json()['id']
    yield risk_id
    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)
    client.delete(f'{RB}/projekte/{RB_PROJ}', headers=auth_headers)
    _clear_links()


def test_set_get_mapping(client, auth_headers, setup):
    risk_id = setup
    # leer am Anfang
    g0 = client.get(f'{RB}/projekte/{RB_PROJ}/risiken/{risk_id}/cra-requirements', headers=auth_headers)
    assert g0.status_code == 200 and g0.get_json()['anforderungen'] == []

    # setzen
    s = client.post(f'{RB}/projekte/{RB_PROJ}/risiken/{risk_id}/cra-requirements',
                    headers=auth_headers, json={'anforderungen': ['AI1-01', 'AI1-02']})
    assert s.status_code == 200, s.get_json()
    assert sorted(s.get_json()['anforderungen']) == ['AI1-01', 'AI1-02']

    # lesen
    g = client.get(f'{RB}/projekte/{RB_PROJ}/risiken/{risk_id}/cra-requirements', headers=auth_headers)
    assert sorted(g.get_json()['anforderungen']) == ['AI1-01', 'AI1-02']


def test_mapping_replace_removes_old(client, auth_headers, setup):
    risk_id = setup
    client.post(f'{RB}/projekte/{RB_PROJ}/risiken/{risk_id}/cra-requirements',
                headers=auth_headers, json={'anforderungen': ['AI1-01', 'AI1-02']})
    # ersetzen durch andere Menge
    client.post(f'{RB}/projekte/{RB_PROJ}/risiken/{risk_id}/cra-requirements',
                headers=auth_headers, json={'anforderungen': ['AI1-03']})
    g = client.get(f'{RB}/projekte/{RB_PROJ}/risiken/{risk_id}/cra-requirements', headers=auth_headers)
    assert g.get_json()['anforderungen'] == ['AI1-03']


def test_coverage_view(client, auth_headers, setup):
    risk_id = setup
    client.post(f'{RB}/projekte/{RB_PROJ}/risiken/{risk_id}/cra-requirements',
                headers=auth_headers, json={'anforderungen': ['AI1-01']})
    r = client.get(f'{CRA}/projekte/{CRA_PROJ}/risk-coverage', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['linked_risk_projekt'] == RB_PROJ
    assert body['coverage'].get('AI1-01') == 1
    assert body['abgedeckt'] == 1
    assert body['gesamt'] >= 1
