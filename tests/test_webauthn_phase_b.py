"""Tests für Sprint ε Phase B — Passkey-Registrierung + Verwaltung (API).

Deckt Endpoint-Plumbing ab (Auth-Schutz, Options-Generierung, Fehlerpfade,
CRUD). Der vollständige kryptografische Roundtrip benötigt einen (virtuellen)
Authenticator und wird in Phase E via Browser-E2E ergänzt.
"""

import pytest


class TestAuthRequired:
    @pytest.mark.parametrize('method,path', [
        ('post', '/api/auth/webauthn/register/options'),
        ('post', '/api/auth/webauthn/register/verify'),
        ('get', '/api/auth/webauthn/credentials'),
        ('patch', '/api/auth/webauthn/credentials/1'),
        ('delete', '/api/auth/webauthn/credentials/1'),
    ])
    def test_requires_jwt(self, client, method, path):
        resp = getattr(client, method)(path)
        assert resp.status_code in (401, 422)


class TestRegisterOptions:
    def test_options_shape(self, client, auth_headers):
        resp = client.post('/api/auth/webauthn/register/options', headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'challenge_id' in data
        assert 'options' in data
        opts = data['options']
        assert 'challenge' in opts
        assert 'rp' in opts and 'id' in opts['rp']
        assert opts['user']['name']  # email


class TestRegisterVerify:
    def test_missing_fields(self, client, auth_headers):
        resp = client.post('/api/auth/webauthn/register/verify', json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_invalid_challenge(self, client, auth_headers):
        resp = client.post(
            '/api/auth/webauthn/register/verify',
            json={'challenge_id': 'does-not-exist', 'credential': {'id': 'x'}},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert 'Challenge' in (resp.get_json().get('error') or '')


class TestCredentialManagement:
    def test_list_shape(self, client, auth_headers):
        resp = client.get('/api/auth/webauthn/credentials', headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'credentials' in data
        assert isinstance(data['credentials'], list)
        # Public-Key darf NICHT exponiert werden
        for c in data['credentials']:
            assert 'public_key' not in c

    def test_rename_missing_nickname(self, client, auth_headers):
        resp = client.patch('/api/auth/webauthn/credentials/999999',
                            json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_rename_nonexistent(self, client, auth_headers):
        resp = client.patch('/api/auth/webauthn/credentials/999999',
                            json={'nickname': 'X'}, headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_nonexistent(self, client, auth_headers):
        resp = client.delete('/api/auth/webauthn/credentials/999999', headers=auth_headers)
        assert resp.status_code == 404
