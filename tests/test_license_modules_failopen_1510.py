"""#1510 — „Modul nicht lizenziert"-Race: Profile darf leeres [] nicht als
toxisches Signal senden. Unbestätigter/kalter Lizenz-State → license_modules=null
(Frontend fail-open), nicht [] (fail-closed)."""
import pytest


@pytest.fixture
def admin_headers(client):
    r = client.post('/api/auth/login',
                    json={'email': 'admin@example.com', 'password': 'admin-password'})
    assert r.status_code == 200, r.json
    return {'Authorization': f"Bearer {r.json['access_token']}"}


@pytest.fixture
def license_override():
    """Setzt den globalen Lizenz-State temporär und stellt ihn wieder her."""
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))

    def _set(state, modules):
        cur.state, cur.modules = state, list(modules)

    yield _set
    cur.state, cur.modules = prev[0], prev[1]


def _profile(client, headers):
    r = client.get('/api/auth/profile', headers=headers)
    assert r.status_code == 200, r.json
    return r.get_json()


def test_no_license_sends_null_not_empty_list(client, admin_headers, license_override):
    # Kalt/keine Lizenz → modules leer. Früher: [] (toxisch). Jetzt: null (fail-open).
    license_override('no-license', [])
    body = _profile(client, admin_headers)
    assert body['license_modules'] is None


def test_read_only_sends_null(client, admin_headers, license_override):
    license_override('read-only', [])
    body = _profile(client, admin_headers)
    assert body['license_modules'] is None


def test_ok_wildcard_sends_list(client, admin_headers, license_override):
    license_override('ok', ['*'])
    body = _profile(client, admin_headers)
    assert body['license_modules'] == ['*']


def test_ok_explicit_modules_sends_list(client, admin_headers, license_override):
    license_override('ok', ['cra', 'nis2'])
    body = _profile(client, admin_headers)
    assert body['license_modules'] == ['cra', 'nis2']


def test_demo_with_zero_modules_sends_empty_list(client, admin_headers, license_override):
    # Bestätigt aktive Lizenz mit 0 Modulen → echtes [] ist hier korrekt.
    license_override('demo', [])
    body = _profile(client, admin_headers)
    assert body['license_modules'] == []
