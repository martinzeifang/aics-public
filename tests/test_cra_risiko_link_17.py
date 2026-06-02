"""Tests Stufe 1: CRA↔Risikobewertung Projekt-Verknüpfung (#880/#881).

Bidirektionale meta-Verknüpfung, Link-Kandidaten nach Kunde, Risiko-Summary.
"""

import pytest

CRA = '/api/cra'
RB = '/api/risikobewertung'
KUNDE = 'pytest-kunde-link17'
CRA_PROJ = 'pytest-cra-link17'
RB_PROJ = 'pytest-rb-link17'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def projekte(client, auth_headers):
    # CRA-Projekt + RB-Projekt mit gleichem Kunden
    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)
    client.delete(f'{RB}/projekte/{RB_PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': CRA_PROJ, 'unternehmen': KUNDE, 'produkt': 'P'})
    client.post(f'{RB}/projekte', headers=auth_headers,
                json={'name': RB_PROJ, 'framework': 'STRIDE', 'unternehmen': KUNDE})
    yield
    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)
    client.delete(f'{RB}/projekte/{RB_PROJ}', headers=auth_headers)


def test_candidates_by_customer(client, auth_headers, projekte):
    r = client.get(f'{CRA}/projekte/{CRA_PROJ}/risk-link/candidates', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['kunde'] == KUNDE
    names = [c['name'] for c in body['candidates']]
    assert RB_PROJ in names


def test_set_and_get_link_bidirectional(client, auth_headers, projekte):
    # verknüpfen
    r = client.put(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers,
                   json={'risk_projekt': RB_PROJ})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['linked_risk_projekt'] == RB_PROJ

    # CRA-Seite kennt die Verknüpfung
    g = client.get(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers)
    assert g.get_json()['linked_risk_projekt'] == RB_PROJ
    assert 'summary' in g.get_json()

    # RB-Seite ist zurückverknüpft (meta.linked_cra_projekt)
    from server.api.risikobewertung import DB_PATH as RB_DB
    from risikobewertung.db import load_projekt as rb_load
    meta = (rb_load(RB_DB, RB_PROJ) or {}).get('meta') or {}
    assert meta.get('linked_cra_projekt') == CRA_PROJ


def test_summary_counts_risks(client, auth_headers, projekte):
    # zwei Risiken im RB-Projekt anlegen
    for i in range(2):
        client.post(f'{RB}/projekte/{RB_PROJ}/risiken', headers=auth_headers,
                    json={'risk_name': f'R{i}', 'framework': 'STRIDE', 'felder': {}})
    client.put(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers,
               json={'risk_projekt': RB_PROJ})
    g = client.get(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers)
    s = g.get_json()['summary']
    assert s['total'] == 2 and s['offen'] == 2 and s['geloest'] == 0


def test_delete_link_clears_both_sides(client, auth_headers, projekte):
    client.put(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers,
               json={'risk_projekt': RB_PROJ})
    d = client.delete(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers)
    assert d.status_code == 200 and d.get_json()['linked_risk_projekt'] is None
    g = client.get(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers)
    assert g.get_json()['linked_risk_projekt'] is None
    from server.api.risikobewertung import DB_PATH as RB_DB
    from risikobewertung.db import load_projekt as rb_load
    meta = (rb_load(RB_DB, RB_PROJ) or {}).get('meta') or {}
    assert 'linked_cra_projekt' not in meta


def test_set_link_unknown_rb_404(client, auth_headers, projekte):
    r = client.put(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers,
                   json={'risk_projekt': 'gibt-es-nicht'})
    assert r.status_code == 404
