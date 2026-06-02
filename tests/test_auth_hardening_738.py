"""Tests für MFA-/Token-Härtung (#738 / WP-05).

AUTH-4 Passkey-only-MFA erzwungen · AUTH-5 Challenge-Token-Rejection ·
AUTH-6 Refresh aus DB · AUTH-13 Token-Version-Revocation.
"""

from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token

from server.auth.users_db import (
    add_webauthn_credential, list_webauthn_credentials, delete_webauthn_credential,
    bump_token_version,
)


def _login(client, email='admin@example.com', pw='admin-password'):
    return client.post('/api/auth/login', json={'email': email, 'password': pw})


class TestChallengeTokenRejection:
    def test_challenge_token_rejected_on_refresh(self, client, app):
        with app.app_context():
            ch = create_access_token(identity='user-001',
                                     additional_claims={'twofa_challenge': True},
                                     expires_delta=timedelta(minutes=5))
        r = client.post('/api/auth/refresh', headers={'Authorization': f'Bearer {ch}'})
        assert r.status_code == 401

    def test_challenge_token_rejected_on_profile(self, client, app):
        with app.app_context():
            ch = create_access_token(identity='user-001',
                                     additional_claims={'twofa_challenge': True},
                                     expires_delta=timedelta(minutes=5))
        r = client.get('/api/auth/profile', headers={'Authorization': f'Bearer {ch}'})
        assert r.status_code == 401


class TestRefreshHardening:
    def test_refresh_valid(self, client):
        tok = _login(client).get_json()['access_token']
        r = client.post('/api/auth/refresh', headers={'Authorization': f'Bearer {tok}'})
        assert r.status_code == 200
        assert 'access_token' in r.get_json()


class TestTokenVersionRevocation:
    def test_bump_invalidates_existing_token(self, client):
        tok = _login(client).get_json()['access_token']
        h = {'Authorization': f'Bearer {tok}'}
        assert client.get('/api/auth/profile', headers=h).status_code == 200
        bump_token_version('user-001')
        try:
            assert client.get('/api/auth/profile', headers=h).status_code == 401
        finally:
            # Folgetests nicht beeinträchtigen: frischer Login holt neuen tv
            pass


class TestPasskeyOnlyMfaEnforced:
    def test_passkey_only_requires_second_factor(self, client):
        # editor (user-002) einen Passkey geben, KEIN TOTP
        add_webauthn_credential(user_id='user-002', credential_id='mfa-test-cred',
                                public_key='pk-test')
        try:
            r = _login(client, 'editor@example.com', 'editor-password')
            assert r.status_code == 200
            body = r.get_json()
            # Kein direkter Access-Token — 2. Faktor (Passkey) wird verlangt
            assert 'access_token' not in body
            assert body.get('mfa_required') is True
            assert 'passkey' in body.get('methods', [])
        finally:
            for c in list_webauthn_credentials('user-002'):
                if c['credential_id'] == 'mfa-test-cred':
                    delete_webauthn_credential(c['id'], 'user-002')
