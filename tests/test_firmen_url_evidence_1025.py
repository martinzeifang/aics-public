"""#1025 — Firmen URL-Nachweis darf keinen 500 mehr werfen.

fetch_page wird gemockt (kein Netz).
"""
import pytest

from server.api.firmen import DB_PATH
from firmen.db import ensure_db, save_firma, delete_firma

FIRMA = 'pytest-firma-url-1025'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def firma():
    ensure_db(DB_PATH)
    save_firma(DB_PATH, FIRMA, unternehmen='ACME')
    yield FIRMA
    try:
        delete_firma(DB_PATH, FIRMA)
    except Exception:
        pass


def test_evidence_url_no_500(client, auth_headers, monkeypatch, firma):
    import evidence.web_fetch as wf

    class _Res:
        url = 'https://example.com/policy'
        title = 'Policy'
        text = 'Sicherheitsrichtlinie Inhalt.'
    monkeypatch.setattr(wf, 'fetch_page', lambda url, **k: _Res())

    r = client.post(f'/api/firmen/{FIRMA}/evidence/url', headers=auth_headers,
                    json={'url': 'https://example.com/policy', 'doc_type': 'web', 'tags': ['policy']})
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body['url'] == 'https://example.com/policy'


def test_evidence_url_fetch_error_400(client, auth_headers, monkeypatch, firma):
    import evidence.web_fetch as wf

    def _boom(url, **k):
        raise wf.WebFetchError('nicht erreichbar')
    monkeypatch.setattr(wf, 'fetch_page', _boom)
    r = client.post(f'/api/firmen/{FIRMA}/evidence/url', headers=auth_headers,
                    json={'url': 'https://bad.example'})
    assert r.status_code == 400  # nicht 500


def test_evidence_url_missing_url_400(client, auth_headers, firma):
    r = client.post(f'/api/firmen/{FIRMA}/evidence/url', headers=auth_headers, json={})
    assert r.status_code == 400
