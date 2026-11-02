"""Tests N-REG (#1203): NIS2 Art. 27 BSI-Registrierungs-Stammdatensatz.

Test-Isolation: ``DB_PATH`` des Blueprints per monkeypatch auf repo-lokale
temporäre DB (kein /tmp wegen ``shared.db_security``-Root-Guard).
"""
import pytest

REG = '/api/nis2-registrierung'
PROJ = 'pytest-nis2-reg-1203'

FULL = {
    'name': 'Acme Energy AG', 'sektor': 'Energie', 'anschrift': 'Berlin, DE',
    'kontakt_email': 'soc@acme.de', 'mitgliedstaaten': 'DE, AT',
    'ip_bereiche': '203.0.113.0/24',
}


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
    db = db_dir / f'_test_reg_{uuid.uuid4().hex}.sqlite'
    import server.api.nis2_registrierung as bp
    monkeypatch.setattr(bp, 'DB_PATH', db)
    yield db
    for p in db_dir.glob(db.name + '*'):
        try:
            p.unlink()
        except OSError:
            pass


class TestCrud:
    def test_constants_six_fields(self, client, auth_headers):
        r = client.get(f'{REG}/constants', headers=auth_headers)
        assert r.status_code == 200
        assert len(r.get_json()['pflichtfelder']) == 6

    def test_save_draft_incomplete(self, client, auth_headers):
        r = client.post(f'{REG}/projekte/{PROJ}/registrierung', headers=auth_headers,
                        json={'name': 'nur name', 'status': 'offen'})
        assert r.status_code == 201, r.get_json()
        reg = r.get_json()['registrierung']
        assert reg['vollstaendig'] is False
        assert 'sektor' in reg['fehlende_pflichtfelder']

    def test_save_full_complete(self, client, auth_headers):
        r = client.post(f'{REG}/projekte/{PROJ}/registrierung', headers=auth_headers,
                        json={**FULL, 'status': 'offen'})
        assert r.status_code == 201
        assert r.get_json()['registrierung']['vollstaendig'] is True


class TestSubmitValidation:
    def test_cannot_submit_incomplete(self, client, auth_headers):
        r = client.post(f'{REG}/projekte/{PROJ}/registrierung', headers=auth_headers,
                        json={'name': 'x', 'status': 'eingereicht'})
        assert r.status_code == 400
        assert 'Pflichtangaben' in r.get_json()['error']

    def test_can_submit_complete(self, client, auth_headers):
        r = client.post(f'{REG}/projekte/{PROJ}/registrierung', headers=auth_headers,
                        json={**FULL, 'status': 'eingereicht'})
        assert r.status_code == 201
        assert r.get_json()['registrierung']['status'] == 'eingereicht'


class TestWiedervorlage:
    def test_overdue_confirmation(self, client, auth_headers):
        r = client.post(f'{REG}/projekte/{PROJ}/registrierung', headers=auth_headers,
                        json={**FULL, 'naechste_jahres_bestaetigung': '2020-01-01'})
        assert r.get_json()['registrierung']['bestaetigung']['ampel'] == 'red'

    def test_due_soon_confirmation(self, client, auth_headers):
        from datetime import date, timedelta
        soon = (date.today() + timedelta(days=30)).isoformat()
        r = client.post(f'{REG}/projekte/{PROJ}/registrierung', headers=auth_headers,
                        json={**FULL, 'naechste_jahres_bestaetigung': soon})
        assert r.get_json()['registrierung']['bestaetigung']['ampel'] == 'amber'


class TestExport:
    def test_export_404(self, client, auth_headers):
        r = client.get(f'{REG}/projekte/{PROJ}/registrierung/export', headers=auth_headers)
        assert r.status_code == 404

    def test_export_md(self, client, auth_headers):
        client.post(f'{REG}/projekte/{PROJ}/registrierung', headers=auth_headers, json=FULL)
        r = client.get(f'{REG}/projekte/{PROJ}/registrierung/export', headers=auth_headers)
        assert r.status_code == 200
        assert b'Art. 27' in r.data
        assert b'Acme Energy' in r.data
