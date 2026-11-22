"""Tests N-AUD (#1204): NIS2 Art. 32 Audit-Register + CAPA-Findings.

Test-Isolation: ``DB_PATH`` per monkeypatch auf repo-lokale temporäre DB.
"""
import pytest

AUD = '/api/nis2-audit'
PROJ = 'pytest-nis2-audit-1204'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture(autouse=True)
def _temp_db(monkeypatch):
    import uuid
    from pathlib import Path
    db_dir = Path('data/db')
    db_dir.mkdir(parents=True, exist_ok=True)
    db = db_dir / f'_test_audit_{uuid.uuid4().hex}.sqlite'
    import server.api.nis2_audit as bp
    monkeypatch.setattr(bp, 'DB_PATH', db)
    yield db
    for p in db_dir.glob(db.name + '*'):
        try:
            p.unlink()
        except OSError:
            pass


def _new_audit(client, headers, **kw):
    body = {'titel': 'ISO 27001 Re-Zert', 'audit_typ': 'zertifizierung',
            'durchgefuehrt_am': '2026-01-15', **kw}
    return client.post(f'{AUD}/projekte/{PROJ}/audits', headers=headers, json=body)


class TestAuditCrud:
    def test_constants(self, client, auth_headers):
        r = client.get(f'{AUD}/constants', headers=auth_headers)
        assert r.status_code == 200
        assert r.get_json()['zyklus_monate'] == 36

    def test_create_and_list(self, client, auth_headers):
        r = _new_audit(client, auth_headers)
        assert r.status_code == 201, r.get_json()
        a = r.get_json()['audit']
        assert a['titel'] == 'ISO 27001 Re-Zert'
        lr = client.get(f'{AUD}/projekte/{PROJ}/audits', headers=auth_headers)
        assert any(x['id'] == a['id'] for x in lr.get_json())

    def test_three_year_cycle_derived(self, client, auth_headers):
        a = _new_audit(client, auth_headers).get_json()['audit']
        # 2026-01-15 + 36 Monate = 2029-01-15
        assert a['naechster_audit_soll'] == '2029-01-15'

    def test_manual_cycle_kept(self, client, auth_headers):
        a = _new_audit(client, auth_headers,
                       naechster_audit_soll='2028-06-01').get_json()['audit']
        assert a['naechster_audit_soll'] == '2028-06-01'

    def test_update(self, client, auth_headers):
        a = _new_audit(client, auth_headers).get_json()['audit']
        r = client.post(f'{AUD}/projekte/{PROJ}/audits', headers=auth_headers,
                        json={'id': a['id'], 'titel': 'Geändert',
                              'durchgefuehrt_am': '2026-01-15'})
        assert r.get_json()['audit']['titel'] == 'Geändert'

    def test_delete(self, client, auth_headers):
        a = _new_audit(client, auth_headers).get_json()['audit']
        r = client.delete(f'{AUD}/projekte/{PROJ}/audits/{a["id"]}', headers=auth_headers)
        assert r.status_code == 200
        assert client.get(f'{AUD}/projekte/{PROJ}/audits/{a["id"]}',
                          headers=auth_headers).status_code == 404


class TestZyklusAmpel:
    def test_overdue_red(self, client, auth_headers):
        a = _new_audit(client, auth_headers,
                       naechster_audit_soll='2020-01-01').get_json()['audit']
        assert a['zyklus']['ampel'] == 'red'


class TestFindingsCapa:
    def test_finding_with_link(self, client, auth_headers):
        a = _new_audit(client, auth_headers).get_json()['audit']
        r = client.post(f'{AUD}/projekte/{PROJ}/audits/{a["id"]}/findings',
                        headers=auth_headers,
                        json={'beschreibung': 'Patch-Mgmt lückenhaft',
                              'schweregrad': 'hoch', 'massnahme': 'Patch-SLA',
                              'status': 'in_bearbeitung',
                              'objekt_typ': 'anforderung', 'objekt_ref': 'NIS3-02'})
        assert r.status_code == 201, r.get_json()
        f = r.get_json()['audit']['findings'][0]
        assert f['objekt_typ'] == 'anforderung'
        assert f['objekt_ref'] == 'NIS3-02'
        assert f['status'] == 'in_bearbeitung'

    def test_finding_requires_existing_audit(self, client, auth_headers):
        r = client.post(f'{AUD}/projekte/{PROJ}/audits/99999/findings',
                        headers=auth_headers, json={'beschreibung': 'x'})
        assert r.status_code == 404

    def test_delete_finding(self, client, auth_headers):
        a = _new_audit(client, auth_headers).get_json()['audit']
        fid = client.post(f'{AUD}/projekte/{PROJ}/audits/{a["id"]}/findings',
                          headers=auth_headers,
                          json={'beschreibung': 'x'}).get_json()['audit']['findings'][0]['id']
        r = client.delete(
            f'{AUD}/projekte/{PROJ}/audits/{a["id"]}/findings/{fid}', headers=auth_headers)
        assert r.status_code == 200


class TestIDOR:
    def test_other_project_404(self, client, auth_headers):
        a = _new_audit(client, auth_headers).get_json()['audit']
        r = client.get(f'{AUD}/projekte/other-xyz/audits/{a["id"]}', headers=auth_headers)
        assert r.status_code == 404


class TestExport:
    def test_export_report(self, client, auth_headers):
        a = _new_audit(client, auth_headers).get_json()['audit']
        client.post(f'{AUD}/projekte/{PROJ}/audits/{a["id"]}/findings',
                    headers=auth_headers,
                    json={'beschreibung': 'Finding-X', 'schweregrad': 'kritisch'})
        r = client.get(f'{AUD}/projekte/{PROJ}/audits/{a["id"]}/export', headers=auth_headers)
        assert r.status_code == 200
        assert b'Art. 32' in r.data
        assert b'Finding-X' in r.data
