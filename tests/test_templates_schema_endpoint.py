"""B1 (#1092) — Variablen-Schema-Endpoint pro Modul (ohne Template-ID)."""
import pytest


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


MODULES = ['cra', 'nis2', 'aiact', 'dsgvo', 'risikobewertung']


@pytest.mark.parametrize('modul', MODULES)
def test_schema_returns_variables(client, auth_headers, modul):
    r = client.get(f'/api/templates/schema/{modul}', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['modul'] == modul
    assert isinstance(body['schema'], list) and len(body['schema']) > 0
    # menschenlesbare Einträge mit key + beschreibung
    first = body['schema'][0]
    assert 'key' in first and 'beschreibung' in first


def test_unknown_module_404(client, auth_headers):
    r = client.get('/api/templates/schema/gibtsnicht', headers=auth_headers)
    assert r.status_code == 404


def test_requires_auth(client):
    r = client.get('/api/templates/schema/cra')
    assert r.status_code in (401, 422)
