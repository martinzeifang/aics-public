"""Tests N-SCOPE (#1210/#1211): NIS2 Art. 2/3 Betroffenheitsanalyse + Art. 26.

Test-Isolation: ``DB_PATH`` des Blueprints wird per monkeypatch auf eine
temporäre SQLite-Datei umgebogen, damit Asserts nicht von ``data/db/nis2.sqlite``
beeinflusst werden.
"""
import pytest

SCOPE = '/api/nis2-scoping'
PROJ = 'pytest-nis2-scoping-1210'


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
    """Blueprint-DB_PATH auf temporäre DB umbiegen (Isolation).

    Die DB muss innerhalb des Workspace-Roots liegen (``shared.db_security``
    erlaubt keine /tmp-Pfade), daher repo-lokal unter ``data/db/`` mit
    eindeutigem Namen + Cleanup.
    """
    import uuid
    from pathlib import Path
    db_dir = Path('data/db')
    db_dir.mkdir(parents=True, exist_ok=True)
    db = db_dir / f'_test_scoping_{uuid.uuid4().hex}.sqlite'
    import server.api.nis2_scoping as bp
    monkeypatch.setattr(bp, 'DB_PATH', db)
    yield db
    for p in db_dir.glob(db.name + '*'):
        try:
            p.unlink()
        except OSError:
            pass


class TestScopingCrud:
    def test_constants(self, client, auth_headers):
        r = client.get(f'{SCOPE}/constants', headers=auth_headers)
        assert r.status_code == 200
        assert 'I' in r.get_json()['anhang']

    def test_empty_initially(self, client, auth_headers):
        r = client.get(f'{SCOPE}/projekte/{PROJ}/scoping', headers=auth_headers)
        assert r.status_code == 200
        assert r.get_json() == {}

    def test_save_and_get(self, client, auth_headers):
        r = client.post(f'{SCOPE}/projekte/{PROJ}/scoping', headers=auth_headers,
                        json={'mitarbeiterzahl': 300, 'jahresumsatz': 60,
                              'bilanzsumme': 50, 'anhang': 'I', 'sektor': 'Energie'})
        assert r.status_code == 201, r.get_json()
        sc = r.get_json()['scoping']
        assert sc['size_class'] == 'wesentlich'
        assert sc['version'] == 1
        g = client.get(f'{SCOPE}/projekte/{PROJ}/scoping', headers=auth_headers)
        assert g.get_json()['sektor'] == 'Energie'

    def test_version_increments(self, client, auth_headers):
        client.post(f'{SCOPE}/projekte/{PROJ}/scoping', headers=auth_headers,
                    json={'mitarbeiterzahl': 60, 'anhang': 'II'})
        r = client.post(f'{SCOPE}/projekte/{PROJ}/scoping', headers=auth_headers,
                        json={'mitarbeiterzahl': 70, 'anhang': 'II'})
        assert r.get_json()['scoping']['version'] == 2


class TestSizeClass:
    def test_wesentlich_by_headcount(self, client, auth_headers):
        r = client.post(f'{SCOPE}/preview-size-class', headers=auth_headers,
                        json={'mitarbeiterzahl': 250, 'anhang': 'I'})
        assert r.get_json()['size_class'] == 'wesentlich'

    def test_wichtig_by_headcount(self, client, auth_headers):
        r = client.post(f'{SCOPE}/preview-size-class', headers=auth_headers,
                        json={'mitarbeiterzahl': 60, 'anhang': 'II'})
        assert r.get_json()['size_class'] == 'wichtig'

    def test_out_of_scope_no_anhang(self, client, auth_headers):
        r = client.post(f'{SCOPE}/preview-size-class', headers=auth_headers,
                        json={'mitarbeiterzahl': 5000, 'anhang': 'keiner'})
        assert r.get_json()['size_class'] == 'out-of-scope'

    def test_out_of_scope_small(self, client, auth_headers):
        r = client.post(f'{SCOPE}/preview-size-class', headers=auth_headers,
                        json={'mitarbeiterzahl': 10, 'jahresumsatz': 2, 'anhang': 'I'})
        assert r.get_json()['size_class'] == 'out-of-scope'


class TestArt26:
    def test_eu_vertreter_required(self, client, auth_headers):
        r = client.post(f'{SCOPE}/projekte/{PROJ}/scoping', headers=auth_headers,
                        json={'eu_niedergelassen': False, 'eu_vertreter': '',
                              'anhang': 'I', 'mitarbeiterzahl': 300})
        assert r.status_code == 400
        assert 'EU-Vertreter' in r.get_json()['error']

    def test_eu_vertreter_ok_when_provided(self, client, auth_headers):
        r = client.post(f'{SCOPE}/projekte/{PROJ}/scoping', headers=auth_headers,
                        json={'eu_niedergelassen': False,
                              'eu_vertreter': 'Vertreter GmbH, Berlin, DE',
                              'anhang': 'I', 'mitarbeiterzahl': 300})
        assert r.status_code == 201
        assert r.get_json()['scoping']['eu_vertreter'].startswith('Vertreter')


class TestExport:
    def test_export_404_when_empty(self, client, auth_headers):
        r = client.get(f'{SCOPE}/projekte/{PROJ}/scoping/export', headers=auth_headers)
        assert r.status_code == 404

    def test_export_md(self, client, auth_headers):
        client.post(f'{SCOPE}/projekte/{PROJ}/scoping', headers=auth_headers,
                    json={'mitarbeiterzahl': 300, 'anhang': 'I'})
        r = client.get(f'{SCOPE}/projekte/{PROJ}/scoping/export', headers=auth_headers)
        assert r.status_code == 200
        assert b'Art. 2/3' in r.data
        assert b'Art. 26' in r.data


class TestKlassenMappingBugfix:
    def test_canonical_klasse(self):
        from nis2.scoping_db import canonical_klasse
        assert canonical_klasse('essential') == 'wesentlich'
        assert canonical_klasse('important') == 'wichtig'
        assert canonical_klasse('out-of-scope') == 'out-of-scope'
        assert canonical_klasse('Wesentlich') == 'wesentlich'
        assert canonical_klasse(None) == 'out-of-scope'
