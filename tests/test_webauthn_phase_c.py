"""Tests für Sprint ε Phase C — Passkey-Login (passwortlos + 2. Faktor).

Endpoint-Plumbing + Token-Helper. Kryptografischer Roundtrip via virtuellem
Authenticator folgt als Browser-E2E in Phase E.
"""

import pytest

from server.api.auth import build_login_response


class TestLoginOptions:
    def test_passwordless_options_no_auth(self, client):
        """Passwortlose Options brauchen KEINE Session (discoverable)."""
        resp = client.post('/api/auth/webauthn/login/options')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'challenge_id' in data and 'options' in data
        assert 'challenge' in data['options']
        # discoverable: keine allowCredentials
        assert not data['options'].get('allowCredentials')


class TestLoginVerify:
    def test_missing_fields(self, client):
        resp = client.post('/api/auth/webauthn/login/verify', json={})
        assert resp.status_code == 400

    def test_invalid_challenge(self, client):
        resp = client.post('/api/auth/webauthn/login/verify',
                           json={'challenge_id': 'nope', 'credential': {'id': 'x'}})
        assert resp.status_code == 400

    def test_unknown_credential(self, client):
        # gültige Challenge anlegen, aber unbekannte Credential
        opt = client.post('/api/auth/webauthn/login/options').get_json()
        resp = client.post('/api/auth/webauthn/login/verify',
                           json={'challenge_id': opt['challenge_id'],
                                 'credential': {'id': 'unknown-cred-id'}})
        assert resp.status_code == 401


class TestTwoFactorOptions:
    def test_requires_challenge_token(self, client):
        resp = client.post('/api/auth/webauthn/login/2fa-options', json={})
        assert resp.status_code == 400

    def test_invalid_challenge_token(self, client):
        resp = client.post('/api/auth/webauthn/login/2fa-options',
                           json={'challenge_token': 'garbage'})
        assert resp.status_code == 401

    def test_2fa_verify_missing_fields(self, client):
        resp = client.post('/api/auth/webauthn/login/2fa-verify', json={})
        assert resp.status_code == 400


class TestRateLimit:
    def test_login_options_rate_limited(self, client, app):
        # Limit: 20 Versuche / 5 min pro IP. Reset für isolierten Test.
        if hasattr(app, '_webauthn_attempts'):
            app._webauthn_attempts.clear()
        statuses = []
        for _ in range(25):
            statuses.append(client.post('/api/auth/webauthn/login/options').status_code)
        assert 429 in statuses, 'Rate-Limit (429) sollte nach Überschreitung greifen'
        # die ersten Versuche sind erfolgreich
        assert statuses[0] == 200
        if hasattr(app, '_webauthn_attempts'):
            app._webauthn_attempts.clear()


class TestLoginResponseHelper:
    def test_build_login_response_shape(self, app):
        with app.app_context():
            user = {
                'id': 'u-test', 'email': 'a@b.com', 'roles': ['admin'],
                'extra_permissions': [], 'allowed_modules': None, 'display_name': 'A',
            }
            r = build_login_response(user)
            assert 'access_token' in r and isinstance(r['access_token'], str)
            assert r['user']['id'] == 'u-test'
            assert r['user']['email'] == 'a@b.com'
            assert 'permissions' in r['user']
            assert 'allowed_modules' in r['user']


class TestPasswordLoginUnchanged:
    """Regression: Passwort-Login (ohne 2FA) liefert weiterhin Token direkt."""
    def test_demo_admin_login(self, client):
        resp = client.post('/api/auth/login',
                           json={'email': 'admin@example.com', 'password': 'admin-password'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'access_token' in data
        assert data['user']['email'] == 'admin@example.com'
