"""#1512 — Update- & Versionskontrolle: Version-Check + Portainer-Update-Gating."""
import pytest


@pytest.fixture
def admin_headers(client):
    r = client.post('/api/auth/login',
                    json={'email': 'admin@example.com', 'password': 'admin-password'})
    assert r.status_code == 200, r.json
    return {'Authorization': f"Bearer {r.json['access_token']}"}


def test_parse_semver():
    from server.api.admin import _parse_semver
    assert _parse_semver('6.25.0') == (6, 25, 0)
    assert _parse_semver('v6.25') == (6, 25, 0)
    assert _parse_semver('6.26.0-rc1') == (6, 26, 0)
    assert _parse_semver('garbage') is None


def test_version_endpoint_returns_current(client, admin_headers):
    r = client.get('/api/admin/version', headers=admin_headers)
    assert r.status_code == 200, r.json
    body = r.get_json()
    assert body['current'] and body['current'] != 'unknown'
    # Ohne Portainer-Konfig ist der Update-Button nicht aktivierbar.
    assert body['update_configured'] is False
    assert 'checked_at' in body


def test_version_update_available_with_manual_latest(client, admin_headers, monkeypatch):
    import server.api.admin as admin_mod
    cur = admin_mod._app_version()
    cmaj = admin_mod._parse_semver(cur)[0]
    newer = f'{cmaj + 1}.0.0'
    monkeypatch.setattr(admin_mod, 'load_config',
                        lambda *a, **k: {'update': {'latest_version': newer}})
    r = client.get('/api/admin/version', headers=admin_headers)
    body = r.get_json()
    assert body['latest'] == newer
    assert body['update_available'] is True


def test_version_no_update_when_same(client, admin_headers, monkeypatch):
    import server.api.admin as admin_mod
    cur = admin_mod._app_version()
    monkeypatch.setattr(admin_mod, 'load_config',
                        lambda *a, **k: {'update': {'latest_version': cur}})
    r = client.get('/api/admin/version', headers=admin_headers)
    body = r.get_json()
    assert body['update_available'] is False


def test_update_trigger_412_without_portainer(client, admin_headers, monkeypatch):
    import server.api.admin as admin_mod
    monkeypatch.setattr(admin_mod, 'load_config', lambda *a, **k: {})
    r = client.post('/api/admin/update', headers=admin_headers)
    assert r.status_code == 412
    assert 'nicht konfiguriert' in (r.get_json() or {}).get('error', '')


def test_update_configured_true_with_portainer(client, admin_headers, monkeypatch):
    import os
    import server.api.admin as admin_mod
    monkeypatch.setenv('PORTAINER_KEY_TEST', 'ptr_secret')
    monkeypatch.setattr(admin_mod, 'load_config', lambda *a, **k: {
        'integrations': {'portainer': {
            'base_url': 'https://portainer.example:9443',
            'stack_id': 42, 'endpoint_id': 1, 'api_key_env': 'PORTAINER_KEY_TEST',
        }}})
    r = client.get('/api/admin/version', headers=admin_headers)
    assert r.get_json()['update_configured'] is True


def test_update_requires_admin(client):
    r = client.post('/api/auth/login',
                    json={'email': 'editor@example.com', 'password': 'editor-password'})
    if r.status_code != 200:
        pytest.skip('editor demo user nicht verfügbar')
    headers = {'Authorization': f"Bearer {r.json['access_token']}"}
    rr = client.get('/api/admin/version', headers=headers)
    assert rr.status_code in (401, 403)
