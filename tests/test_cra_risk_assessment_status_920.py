"""Tests #920: Risikobewertung als Nachweis für die 5 risiko-relevanten
CRA-Anforderungen — Status-Vorschlag aus der Vollständigkeit der Bewertung."""

import pytest

CRA = '/api/cra'
RB = '/api/risikobewertung'
KUNDE = 'pytest-kunde-ra920'
CRA_PROJ = 'pytest-cra-ra920'
RB_PROJ = 'pytest-rb-ra920'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _status(client, auth_headers):
    r = client.get(f'{CRA}/projekte/{CRA_PROJ}/risk-assessment-status', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


@pytest.fixture
def projekte(client, auth_headers):
    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)
    client.delete(f'{RB}/projekte/{RB_PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': CRA_PROJ, 'unternehmen': KUNDE})
    client.post(f'{RB}/projekte', headers=auth_headers,
                json={'name': RB_PROJ, 'framework': 'STRIDE', 'unternehmen': KUNDE})
    yield
    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)
    client.delete(f'{RB}/projekte/{RB_PROJ}', headers=auth_headers)


def test_unlinked_suggests_offen(client, auth_headers, projekte):
    body = _status(client, auth_headers)
    assert body['linked_risk_projekt'] is None
    ids = [r['id'] for r in body['requirements']]
    assert 'ART13-01' in ids and 'AI1-01' in ids and len(body['requirements']) == 5
    assert all(r['suggested_status'] == 'offen' for r in body['requirements'])


def test_linked_incomplete_suggests_teilerfuellt(client, auth_headers, projekte):
    client.put(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers,
               json={'risk_projekt': RB_PROJ})
    # Risiko ohne Bewertung (leere Felder -> kein risiko_label)
    client.post(f'{RB}/projekte/{RB_PROJ}/risiken', headers=auth_headers,
                json={'risk_name': 'Unbewertet', 'framework': 'STRIDE', 'felder': {}})
    body = _status(client, auth_headers)
    assert body['linked_risk_projekt'] == RB_PROJ
    assert body['completeness']['total'] == 1 and body['completeness']['bewertet'] == 0
    assert all(r['suggested_status'] == 'teilerfüllt' for r in body['requirements'])


def test_linked_complete_suggests_erfuellt_and_apply(client, auth_headers, projekte):
    client.put(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers,
               json={'risk_projekt': RB_PROJ})
    # Vollständig bewertetes Risiko (Felder ergeben risikowert/label)
    client.post(f'{RB}/projekte/{RB_PROJ}/risiken', headers=auth_headers, json={
        'risk_name': 'Bewertet', 'framework': 'STRIDE',
        'felder': {'eintrittswahrscheinlichkeit': 'Möglich', 'auswirkung': 'Hoch'}})
    body = _status(client, auth_headers)
    assert body['completeness']['bewertet'] == body['completeness']['total'] == 1
    assert all(r['suggested_status'] == 'erfüllt' for r in body['requirements'])
    art13 = next(r for r in body['requirements'] if r['id'] == 'ART13-01')
    assert art13['differs'] is True and art13['suggested_score'] == 5

    # Vorschlag übernehmen → Bewertung wird gesetzt
    client.post(f'{CRA}/projekte/{CRA_PROJ}/bewertungen', headers=auth_headers,
                json={'anforderung_id': 'ART13-01', 'bewertung': art13['suggested_score']})
    body2 = _status(client, auth_headers)
    art13b = next(r for r in body2['requirements'] if r['id'] == 'ART13-01')
    assert art13b['current_status'] == 'erfüllt' and art13b['current_score'] == 5
    assert art13b['differs'] is False
