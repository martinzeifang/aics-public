"""#1509 — Support-Bundle (ZIP aller relevanten Logs + Diagnose, Secrets redigiert)."""
import io
import json
import os
import zipfile

import pytest


@pytest.fixture
def admin_headers(client):
    r = client.post('/api/auth/login',
                    json={'email': 'admin@example.com', 'password': 'admin-password'})
    assert r.status_code == 200, r.json
    return {'Authorization': f"Bearer {r.json['access_token']}"}


def test_support_bundle_returns_zip(client, admin_headers):
    r = client.get('/api/admin/support-bundle', headers=admin_headers)
    assert r.status_code == 200, r.data[:200]
    assert r.mimetype == 'application/zip'
    cd = r.headers.get('Content-Disposition', '')
    assert 'support-bundle_' in cd and cd.endswith('.zip')

    zf = zipfile.ZipFile(io.BytesIO(r.data))
    names = zf.namelist()
    # Manifest + redigierte Config sind immer dabei.
    assert 'MANIFEST.json' in names
    assert 'config.redacted.json' in names

    manifest = json.loads(zf.read('MANIFEST.json'))
    assert manifest.get('app_version')
    assert 'databases' in manifest and isinstance(manifest['databases'], list)
    # Env-Whitelist enthält keine Secrets.
    env = manifest.get('env_whitelist', {})
    assert 'DATABASE_URL' not in env
    assert not any('SECRET' in k or 'TOKEN' in k or 'KEY' in k for k in env)


def test_support_bundle_redacts_secrets(client, admin_headers):
    r = client.get('/api/admin/support-bundle', headers=admin_headers)
    assert r.status_code == 200
    blob = r.data

    # Kein users.sqlite (PII/Passwort-Hashes) im Bundle.
    zf = zipfile.ZipFile(io.BytesIO(blob))
    assert not any('users.sqlite' in n for n in zf.namelist())

    # Der DATABASE_URL-Wert (inkl. Passwort) darf nirgends im Bundle stehen.
    dburl = os.environ.get('DATABASE_URL')
    if dburl:
        assert dburl.encode() not in blob

    # In der redigierten Config sind sensible Felder maskiert (kein Klartext-Hash/Token).
    cfg = json.loads(zf.read('config.redacted.json'))

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ('password_hash', 'token', 'api_key') and isinstance(v, str) and v:
                    assert v == '***', f'{k} nicht maskiert'
                _walk(v)
        elif isinstance(obj, list):
            for x in obj:
                _walk(x)

    _walk(cfg)


def test_support_bundle_requires_admin(client):
    # Editor (ohne admin:config) darf das Bundle nicht ziehen.
    r = client.post('/api/auth/login',
                    json={'email': 'editor@example.com', 'password': 'editor-password'})
    if r.status_code != 200:
        pytest.skip('editor demo user nicht verfügbar')
    headers = {'Authorization': f"Bearer {r.json['access_token']}"}
    rr = client.get('/api/admin/support-bundle', headers=headers)
    assert rr.status_code in (401, 403)
