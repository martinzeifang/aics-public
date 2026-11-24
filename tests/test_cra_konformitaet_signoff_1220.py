"""Tests #1220-A: CRA Governance-Sign-off + Lock auf Konformitäts-Records.

- freigeben() nur bei abgeschlossener Bewertung; setzt Freigeber/Zeit + Lock.
- Lock: save_konformitaet auf freigegebenem Record verboten; reopen entsperrt.
- CRA_APPROVE-Permission existiert + ist im cra-Modul-Set.
- Endpoints /freigeben + /reopen (CRA_APPROVE).
"""
import pytest

CRA = '/api/cra'
KONF = '/api/cra-konformitaet'
FIRMA = 'pytest-firma-1220'
PROJ = 'pytest-cra-1220'


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


def test_permission_exists():
    from server.models.permission import Permission, MODULE_PERMISSIONS
    assert Permission.CRA_APPROVE.value == 'cra:approve'
    assert Permission.CRA_APPROVE in MODULE_PERMISSIONS['cra']


def test_freigabe_gate_and_lock(tmp_path):
    from cra import konformitaet_db as kdb
    db = tmp_path / 'cra.sqlite'
    kdb.save_konformitaet(db, PROJ, {'bewertungsweg': 'H', 'nb_kennnummer': '0123'})
    # Gate: Bewertung nicht abgeschlossen → Freigabe verboten
    with pytest.raises(ValueError):
        kdb.freigeben(db, PROJ, '', von='gf@example.com')
    # abschließen → Freigabe möglich
    kdb.save_konformitaet(db, PROJ, {'bewertungsweg': 'H', 'nb_kennnummer': '0123',
                                     'bewertung_abgeschlossen': True})
    rec = kdb.freigeben(db, PROJ, '', von='gf@example.com')
    assert rec['freigabe_status'] == 'freigegeben'
    assert rec['gesperrt'] is True
    assert rec['freigegeben_von'] == 'gf@example.com'
    assert rec['freigegeben_am']
    # Lock: erneutes Speichern verboten
    with pytest.raises(ValueError):
        kdb.save_konformitaet(db, PROJ, {'bewertungsweg': 'A', 'bewertung_abgeschlossen': True})
    # doppelte Freigabe verboten
    with pytest.raises(ValueError):
        kdb.freigeben(db, PROJ, '', von='gf@example.com')
    # reopen entsperrt → wieder editierbar
    rec = kdb.reopen(db, PROJ, '')
    assert rec['freigabe_status'] == 'entwurf' and rec['gesperrt'] is False
    rec = kdb.save_konformitaet(db, PROJ, {'bewertungsweg': 'A', 'bewertung_abgeschlossen': True})
    assert rec['bewertungsweg'] == 'A'


def test_signoff_api(client, auth_headers, projekt):
    client.put(f'{KONF}/projekte/{projekt}/konformitaet', headers=auth_headers,
               json={'bewertungsweg': 'H', 'nb_kennnummer': '0123',
                     'bewertung_abgeschlossen': True})
    r = client.post(f'{KONF}/projekte/{projekt}/konformitaet/freigeben',
                    headers=auth_headers, json={})
    assert r.status_code == 200, r.json
    assert r.json['freigabe_status'] == 'freigegeben' and r.json['gesperrt'] is True
    # Lock greift über die API (save → 400/409)
    r2 = client.put(f'{KONF}/projekte/{projekt}/konformitaet', headers=auth_headers,
                    json={'bewertungsweg': 'A', 'bewertung_abgeschlossen': True})
    assert r2.status_code in (400, 409)
    # reopen → wieder editierbar
    r3 = client.post(f'{KONF}/projekte/{projekt}/konformitaet/reopen',
                     headers=auth_headers, json={})
    assert r3.status_code == 200 and r3.json['freigabe_status'] == 'entwurf'
