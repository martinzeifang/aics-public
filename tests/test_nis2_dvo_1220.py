"""Tests N-DVO (#1220 Teil B): NIS2 DVO (EU) 2024/2690 Sektor-Set + Triage.

Test-Isolation: Blueprint-``DB_PATH`` per monkeypatch auf repo-lokale temporäre
DB (custom Anforderungen sind global → Isolation zwingend).
"""
import json

import pytest

DVO = '/api/nis2-dvo'
PROJ = 'pytest-nis2-dvo-1220'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def db(monkeypatch):
    import uuid
    from pathlib import Path
    db_dir = Path('data/db')
    db_dir.mkdir(parents=True, exist_ok=True)
    p = db_dir / f'_test_dvo_{uuid.uuid4().hex}.sqlite'
    import server.api.nis2_dvo as bp
    monkeypatch.setattr(bp, 'DB_PATH', p)
    yield p
    for f in db_dir.glob(p.name + '*'):
        try:
            f.unlink()
        except OSError:
            pass


def _seed_projekt(db, sektor):
    from nis2 import db as ndb
    ndb.ensure_db(db)
    meta = {'nis2': {'klassifikator': {'klasse': 'essential', 'sektor': sektor}}}
    ndb.save_projekt(db, PROJ, 'TestOrg', 'wesentlich', '', '', meta)


class TestSchwellenwerte:
    def test_catalog(self, client, auth_headers, db):
        r = client.get(f'{DVO}/schwellenwerte', headers=auth_headers)
        assert r.status_code == 200
        body = r.get_json()
        assert len(body['sections']) == 13
        assert any(s['diensttyp'] == 'DNS-Diensteanbieter' for s in body['schwellenwerte'])
        assert all('kriterien' in s for s in body['schwellenwerte'])


class TestStatusRelevance:
    def test_relevant_for_cloud(self, client, auth_headers, db):
        _seed_projekt(db, 'Cloud-Computing')
        r = client.get(f'{DVO}/projekte/{PROJ}/status', headers=auth_headers)
        assert r.get_json()['relevant'] is True

    def test_not_relevant_for_energie(self, client, auth_headers, db):
        _seed_projekt(db, 'Energie')
        r = client.get(f'{DVO}/projekte/{PROJ}/status', headers=auth_headers)
        assert r.get_json()['relevant'] is False


class TestActivation:
    def test_activate_creates_13(self, client, auth_headers, db):
        r = client.post(f'{DVO}/projekte/{PROJ}/activate', headers=auth_headers)
        assert r.status_code == 201, r.get_json()
        assert r.get_json()['anzahl_controls'] == 13
        # In nis2_anforderungen_custom als Kapitel DVO2690 sichtbar.
        from nis2 import db as ndb
        custom = ndb.load_custom_anforderungen(db)
        assert sum(1 for c in custom if c['kapitel'] == 'DVO2690') == 13

    def test_activate_idempotent(self, client, auth_headers, db):
        client.post(f'{DVO}/projekte/{PROJ}/activate', headers=auth_headers)
        client.post(f'{DVO}/projekte/{PROJ}/activate', headers=auth_headers)
        from nis2 import db as ndb
        custom = ndb.load_custom_anforderungen(db)
        assert sum(1 for c in custom if c['kapitel'] == 'DVO2690') == 13

    def test_deactivate(self, client, auth_headers, db):
        client.post(f'{DVO}/projekte/{PROJ}/activate', headers=auth_headers)
        r = client.post(f'{DVO}/projekte/{PROJ}/deactivate', headers=auth_headers)
        assert r.status_code == 200
        assert r.get_json()['entfernt'] == 13
        s = client.get(f'{DVO}/projekte/{PROJ}/status', headers=auth_headers).get_json()
        assert s['aktiv'] is False
