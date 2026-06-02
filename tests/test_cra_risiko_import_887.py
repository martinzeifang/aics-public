"""Tests #887: CRA Threat-Model/CVEs als Risiko-Quelle (Import ins RB-Modul).

Idempotenz (Re-Import dupliziert nicht), Provenienz in felder_json, nur auf
verknüpftem Projektpaar. Bezug: #562 (Threats), #482 (CVEs)."""

import pytest

CRA = '/api/cra'
RB = '/api/risikobewertung'
KUNDE = 'pytest-kunde-imp887'
CRA_PROJ = 'pytest-cra-imp887'
RB_PROJ = 'pytest-rb-imp887'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def setup(client, auth_headers):
    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)
    client.delete(f'{RB}/projekte/{RB_PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': CRA_PROJ, 'unternehmen': KUNDE, 'produkt': 'P'})
    client.post(f'{RB}/projekte', headers=auth_headers,
                json={'name': RB_PROJ, 'framework': 'STRIDE', 'unternehmen': KUNDE})
    client.put(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers,
               json={'risk_projekt': RB_PROJ})
    # Threat-Model mit zwei STRIDE-Threats
    client.post(f'{CRA}/projekte/{CRA_PROJ}/threatmodel', headers=auth_headers, json={
        'framework': 'STRIDE',
        'threats': [
            {'id': 'T1', 'kategorie': 'Spoofing (S) – Identitätsfälschung',
             'title': 'Login-Bypass', 'mitigation': 'MFA erzwingen'},
            {'id': 'T2', 'title': 'Datenmanipulation', 'description': 'Tampering'},
        ],
    })
    # Zwei CVEs (eine offen, eine fixed → nur offene wird importiert)
    client.post(f'{CRA}/projekte/{CRA_PROJ}/vuln', headers=auth_headers, json={
        'cve_id': 'CVE-2024-0001', 'titel': 'RCE', 'schwere': 'critical',
        'cvss_score': 9.8, 'status': 'open'})
    client.post(f'{CRA}/projekte/{CRA_PROJ}/vuln', headers=auth_headers, json={
        'cve_id': 'CVE-2024-0002', 'titel': 'Fixed bug', 'schwere': 'low',
        'cvss_score': 2.0, 'status': 'fixed'})
    yield
    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)
    client.delete(f'{RB}/projekte/{RB_PROJ}', headers=auth_headers)


def _risiken(client, auth_headers):
    r = client.get(f'{RB}/projekte/{RB_PROJ}/risiken', headers=auth_headers)
    return r.get_json() or []


def test_import_preview(client, auth_headers, setup):
    r = client.get(f'{CRA}/projekte/{CRA_PROJ}/risk-link/import-preview', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['counts']['threats'] == 2
    assert body['counts']['cves'] == 1  # nur die offene CVE


def test_import_threats_idempotent(client, auth_headers, setup):
    r1 = client.post(f'{CRA}/projekte/{CRA_PROJ}/risk-link/import-threats', headers=auth_headers)
    assert r1.status_code == 200, r1.get_json()
    assert r1.get_json()['created'] == 2
    n1 = len(_risiken(client, auth_headers))
    # Re-Import: aktualisiert statt dupliziert
    r2 = client.post(f'{CRA}/projekte/{CRA_PROJ}/risk-link/import-threats', headers=auth_headers)
    assert r2.get_json()['created'] == 0 and r2.get_json()['updated'] == 2
    assert len(_risiken(client, auth_headers)) == n1


def test_import_cves_provenance_and_score(client, auth_headers, setup):
    r = client.post(f'{CRA}/projekte/{CRA_PROJ}/risk-link/import-cves', headers=auth_headers)
    assert r.status_code == 200 and r.get_json()['created'] == 1
    risiken = _risiken(client, auth_headers)
    cve_risk = [x for x in risiken if (x.get('felder') or {}).get('_source') == 'cra-cve']
    assert len(cve_risk) == 1
    felder = cve_risk[0]['felder']
    assert felder['_source_id'] == 'CVE-2024-0001'
    # critical/9.8 → hohe Bewertung
    assert cve_risk[0]['risikowert'] and cve_risk[0]['risikowert'] >= 20


def test_import_requires_link(client, auth_headers):
    # Projekt ohne Verknüpfung → 400
    client.delete(f'{CRA}/projekte/pytest-cra-nolink887', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': 'pytest-cra-nolink887', 'unternehmen': 'x'})
    r = client.post(f'{CRA}/projekte/pytest-cra-nolink887/risk-link/import-threats',
                    headers=auth_headers)
    assert r.status_code == 400
    client.delete(f'{CRA}/projekte/pytest-cra-nolink887', headers=auth_headers)
