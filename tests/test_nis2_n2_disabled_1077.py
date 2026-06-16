"""Tests für S7 (#1077): Manuelle N2-Risikoverwaltung im NIS2-Modul deaktiviert.

Ab Sprint #21 werden NIS2-Risiken zentral in der Risikobewertung gepflegt und im
Risiko-Cockpit aggregiert. Der manuelle Create/Save-Endpoint refusiert neue
Einträge mit 409; Lese-Endpoints bleiben verfügbar und bestehende Einträge im
``nis2_risiko_register`` bleiben sichtbar (read-only).
"""

import pytest

BASE = '/api/nis2'
PROJ = 'pytest-n2-disabled-1077'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _clear_register():
    # delete_projekt cascadet nis2_risiko_register nicht → Testisolation hier sichern.
    import sqlite3
    from server.api.nis2 import DB_PATH
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.execute("DELETE FROM nis2_risiko_register WHERE projekt_name=?", (PROJ,))
        con.commit(); con.close()
    except sqlite3.OperationalError:
        pass


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_register()
    client.post(f'{BASE}/projekte', headers=auth_headers,
                json={'name': PROJ, 'unternehmen': 'TestOrg'})
    yield PROJ
    _clear_register()
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)


class TestN2ManualDisabled:
    def test_create_risk_returns_409(self, client, auth_headers, projekt):
        r = client.post(
            f'{BASE}/projekte/{projekt}/risiken', headers=auth_headers,
            json={'risiko_id': 'NIS2-R-001', 'titel': 'Manueller Versuch',
                  'auswirkung': 'hoch', 'eintrittswkt': 'wahrscheinlich'})
        assert r.status_code == 409, r.get_json()
        body = r.get_json()
        assert 'Risikobewertung' in (body.get('error') or '')

    def test_update_existing_risk_also_409(self, client, auth_headers, projekt):
        # Auch ein "Update" (mit id) über den Endpoint ist gesperrt — die Liste ist
        # read-only; Bestands-Pflege passiert nur noch über die Risikobewertung.
        r = client.post(
            f'{BASE}/projekte/{projekt}/risiken', headers=auth_headers,
            json={'id': 1, 'titel': 'X', 'status': 'mitigiert'})
        assert r.status_code == 409, r.get_json()

    def test_read_endpoint_still_works(self, client, auth_headers, projekt):
        # Lese-Endpoint bleibt verfügbar (leere Liste für frisches Projekt).
        r = client.get(f'{BASE}/projekte/{projekt}/risiken', headers=auth_headers)
        assert r.status_code == 200, r.get_json()
        assert isinstance(r.get_json(), list)

    def test_legacy_rows_remain_readable(self, client, auth_headers, projekt):
        # Bestehende Einträge (z.B. via RB-Import / db.save_risiko direkt) bleiben
        # über den Lese-Endpoint sichtbar — die Sperre betrifft nur den HTTP-Save.
        from server.api.nis2 import DB_PATH
        from nis2.db import save_risiko as db_save_risiko
        db_save_risiko(DB_PATH, projekt, {
            'risiko_id': 'RB-0001', 'titel': 'Alt-Bestand aus RB',
            'auswirkung': 'mittel', 'eintrittswkt': 'gelegentlich',
            'status': 'offen',
        })
        r = client.get(f'{BASE}/projekte/{projekt}/risiken', headers=auth_headers)
        assert r.status_code == 200
        ids = [row.get('risiko_id') for row in r.get_json()]
        assert 'RB-0001' in ids
