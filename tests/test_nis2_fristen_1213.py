"""Tests N-FRIST (#1213): NIS2 Kontrollzyklus-/Wiedervorlage-Dashboard.

Test-Isolation: Blueprint-``DB_PATH`` per monkeypatch auf repo-lokale temporäre
DB; alle Seed-Aufrufe nutzen denselben Pfad (Aggregation ist db_path-parametrisiert).
"""
from datetime import date, timedelta

import pytest

FR = '/api/nis2-fristen'
PROJ = 'pytest-nis2-fristen-1213'


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
    p = db_dir / f'_test_fristen_{uuid.uuid4().hex}.sqlite'
    import server.api.nis2_fristen as bp
    monkeypatch.setattr(bp, 'DB_PATH', p)
    yield p
    for f in db_dir.glob(p.name + '*'):
        try:
            f.unlink()
        except OSError:
            pass


def _past(days):
    return (date.today() - timedelta(days=days)).isoformat()


def _future(days):
    return (date.today() + timedelta(days=days)).isoformat()


class TestEmpty:
    def test_no_fristen(self, client, auth_headers, db):
        r = client.get(f'{FR}/projekte/{PROJ}/fristen', headers=auth_headers)
        assert r.status_code == 200
        body = r.get_json()
        assert body['items'] == []
        assert body['overall_ampel'] == 'grey'


class TestAggregation:
    def test_overdue_risk_review(self, client, auth_headers, db):
        from nis2 import db as ndb
        ndb.save_risiko(db, PROJ, {'risiko_id': 'R-1', 'titel': 'Test-Risiko',
                                   'review_datum': _past(10)})
        r = client.get(f'{FR}/projekte/{PROJ}/fristen', headers=auth_headers)
        body = r.get_json()
        assert body['counts']['ueberfaellig'] == 1
        assert body['overall_ampel'] == 'red'
        top = body['items'][0]
        assert top['bereich'] == 'N2 Risiko'
        assert top['status'] == 'ueberfaellig'

    def test_due_soon_vendor(self, client, auth_headers, db):
        from nis2 import db as ndb
        ndb.save_vendor(db, PROJ, {'vendor_name': 'Cloud AG', 'leistung': 'IaaS',
                                   'review_datum': _future(10)})
        body = client.get(f'{FR}/projekte/{PROJ}/fristen', headers=auth_headers).get_json()
        assert body['counts']['faellig'] == 1
        assert any(i['bereich'] == 'N4 Lieferant' for i in body['items'])

    def test_bcp_cycle_from_test_datum(self, client, auth_headers, db):
        from nis2 import db as ndb
        # Letzter Test vor 13 Monaten, jährlich → nächster Soll überfällig.
        ndb.save_bcp(db, PROJ, {'test_datum': _past(400), 'test_frequenz': 'jaehrlich'})
        body = client.get(f'{FR}/projekte/{PROJ}/fristen', headers=auth_headers).get_json()
        bcp = [i for i in body['items'] if i['bereich'] == 'N5 BCP-Test']
        assert bcp and bcp[0]['status'] == 'ueberfaellig'

    def test_audit_and_registrierung_included(self, client, auth_headers, db):
        from nis2 import audit_db as adb
        from nis2 import registrierung_db as rdb
        adb.save_audit(db, PROJ, {'titel': 'Audit', 'durchgefuehrt_am': _past(5),
                                  'naechster_audit_soll': _future(20)})
        rdb.save_registrierung(db, PROJ, {
            'name': 'X', 'sektor': 'Energie', 'anschrift': 'a',
            'kontakt_email': 'a@b.de', 'mitgliedstaaten': 'DE', 'ip_bereiche': '1.1.1.0/24',
            'naechste_jahres_bestaetigung': _future(40)})
        body = client.get(f'{FR}/projekte/{PROJ}/fristen', headers=auth_headers).get_json()
        bereiche = {i['bereich'] for i in body['items']}
        assert 'Audit' in bereiche
        assert 'Registrierung' in bereiche

    def test_sorting_overdue_first(self, client, auth_headers, db):
        from nis2 import db as ndb
        ndb.save_risiko(db, PROJ, {'risiko_id': 'R-future', 'titel': 'f',
                                   'review_datum': _future(50)})
        ndb.save_risiko(db, PROJ, {'risiko_id': 'R-overdue', 'titel': 'o',
                                   'review_datum': _past(5)})
        body = client.get(f'{FR}/projekte/{PROJ}/fristen', headers=auth_headers).get_json()
        assert body['items'][0]['status'] == 'ueberfaellig'
