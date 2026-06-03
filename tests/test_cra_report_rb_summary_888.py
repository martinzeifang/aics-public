"""Tests #888: CRA-Report bindet Risikobewertungs-Summary ein.

Testet die reine Summary-Funktion build_rb_risk_summary (AI1-01-Nachweis):
- ohne Verknüpfung: linked=False (Report weist Lücke aus, keine stille Lücke)
- mit Verknüpfung: total/Verteilung/Top-Risiken.
"""

import pytest

CRA = '/api/cra'
RB = '/api/risikobewertung'
KUNDE = 'pytest-kunde-rep888'
CRA_PROJ = 'pytest-cra-rep888'
RB_PROJ = 'pytest-rb-rep888'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _cra_db():
    from server.api.cra import DB_PATH
    return DB_PATH


def test_summary_unlinked(client, auth_headers):
    from cra.report_export import build_rb_risk_summary
    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': CRA_PROJ, 'unternehmen': KUNDE})
    summary = build_rb_risk_summary(_cra_db(), CRA_PROJ)
    assert summary['linked'] is False
    assert summary['total'] == 0
    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)


def test_summary_linked_with_risks(client, auth_headers):
    from cra.report_export import build_rb_risk_summary
    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)
    client.delete(f'{RB}/projekte/{RB_PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': CRA_PROJ, 'unternehmen': KUNDE})
    client.post(f'{RB}/projekte', headers=auth_headers,
                json={'name': RB_PROJ, 'framework': 'STRIDE', 'unternehmen': KUNDE})
    client.put(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers,
               json={'risk_projekt': RB_PROJ})
    # Risiko mit Score anlegen (STRIDE: Wahrscheinlichkeit × Impact)
    client.post(f'{RB}/projekte/{RB_PROJ}/risiken', headers=auth_headers, json={
        'risk_name': 'Top-Risiko', 'framework': 'STRIDE',
        'felder': {'eintrittswahrscheinlichkeit': 'Sehr wahrscheinlich',
                   'auswirkung': 'Kritisch'}})

    summary = build_rb_risk_summary(_cra_db(), CRA_PROJ)
    assert summary['linked'] is True
    assert summary['rb_projekt'] == RB_PROJ
    assert summary['framework'] == 'STRIDE'
    assert summary['total'] == 1
    assert summary['top'] and summary['top'][0]['name'] == 'Top-Risiko'
    assert sum(summary['by_label'].values()) == 1

    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)
    client.delete(f'{RB}/projekte/{RB_PROJ}', headers=auth_headers)
