"""Tests N-GOV (#1212): NIS2 Art. 20 Governance-Nachweis-Register.

Test-Isolation: ``DB_PATH`` per monkeypatch auf repo-lokale temporäre DB.
"""
import pytest

GOV = '/api/nis2-governance'
PROJ = 'pytest-nis2-gov-1212'


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
    db = db_dir / f'_test_gov_{uuid.uuid4().hex}.sqlite'
    import server.api.nis2_governance as bp
    monkeypatch.setattr(bp, 'DB_PATH', db)
    yield db
    for p in db_dir.glob(db.name + '*'):
        try:
            p.unlink()
        except OSError:
            pass


class TestNachweisCrud:
    def test_constants(self, client, auth_headers):
        r = client.get(f'{GOV}/constants', headers=auth_headers)
        assert r.status_code == 200
        assert 'billigungsbeschluss' in r.get_json()['nachweis_typen']

    def test_create_billigungsbeschluss(self, client, auth_headers):
        r = client.post(f'{GOV}/projekte/{PROJ}/nachweise', headers=auth_headers,
                        json={'typ': 'billigungsbeschluss', 'datum': '2026-03-01',
                              'gremium': 'Geschäftsführung', 'rm_version': 'v2.1'})
        assert r.status_code == 201, r.get_json()
        assert r.get_json()['nachweis']['typ'] == 'billigungsbeschluss'

    def test_invalid_typ(self, client, auth_headers):
        r = client.post(f'{GOV}/projekte/{PROJ}/nachweise', headers=auth_headers,
                        json={'typ': 'unsinn'})
        assert r.status_code == 400

    def test_delete(self, client, auth_headers):
        pk = client.post(f'{GOV}/projekte/{PROJ}/nachweise', headers=auth_headers,
                         json={'typ': 'management_review'}).get_json()['id']
        assert client.delete(f'{GOV}/projekte/{PROJ}/nachweise/{pk}',
                             headers=auth_headers).status_code == 200
        assert client.get(f'{GOV}/projekte/{PROJ}/nachweise/{pk}',
                          headers=auth_headers).status_code == 404


class TestReviewAmpel:
    def test_overdue(self, client, auth_headers):
        n = client.post(f'{GOV}/projekte/{PROJ}/nachweise', headers=auth_headers,
                        json={'typ': 'management_review',
                              'naechster_review': '2020-01-01'}).get_json()['nachweis']
        assert n['review']['ampel'] == 'red'


class TestSchulungTeilnehmer:
    def test_teilnehmer_with_quiz(self, client, auth_headers):
        pk = client.post(f'{GOV}/projekte/{PROJ}/nachweise', headers=auth_headers,
                         json={'typ': 'schulung', 'gremium': 'Leitung'}).get_json()['id']
        r = client.post(f'{GOV}/projekte/{PROJ}/nachweise/{pk}/teilnehmer',
                        headers=auth_headers,
                        json={'name': 'Erika Muster', 'rolle': 'CISO',
                              'status': 'absolviert', 'quiz_score': '95%'})
        assert r.status_code == 201, r.get_json()
        t = r.get_json()['nachweis']['teilnehmer'][0]
        assert t['name'] == 'Erika Muster'
        assert t['status'] == 'absolviert'
        assert t['quiz_score'] == '95%'

    def test_teilnehmer_requires_nachweis(self, client, auth_headers):
        r = client.post(f'{GOV}/projekte/{PROJ}/nachweise/99999/teilnehmer',
                        headers=auth_headers, json={'name': 'x'})
        assert r.status_code == 404

    def test_delete_teilnehmer(self, client, auth_headers):
        pk = client.post(f'{GOV}/projekte/{PROJ}/nachweise', headers=auth_headers,
                         json={'typ': 'schulung'}).get_json()['id']
        tid = client.post(f'{GOV}/projekte/{PROJ}/nachweise/{pk}/teilnehmer',
                          headers=auth_headers,
                          json={'name': 'y'}).get_json()['nachweis']['teilnehmer'][0]['id']
        r = client.delete(f'{GOV}/projekte/{PROJ}/nachweise/{pk}/teilnehmer/{tid}',
                          headers=auth_headers)
        assert r.status_code == 200


class TestIDOR:
    def test_other_project_404(self, client, auth_headers):
        pk = client.post(f'{GOV}/projekte/{PROJ}/nachweise', headers=auth_headers,
                         json={'typ': 'schulung'}).get_json()['id']
        r = client.get(f'{GOV}/projekte/other-xyz/nachweise/{pk}', headers=auth_headers)
        assert r.status_code == 404
