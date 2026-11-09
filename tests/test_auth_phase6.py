"""Tests für Phase 6.1 Security-Hardening: User-DB + Token-Blacklist."""

import pytest


class TestLogin:
    def test_login_valid_credentials(self, client):
        response = client.post(
            '/api/auth/login',
            json={'email': 'admin@example.com', 'password': 'admin-password'},
        )
        assert response.status_code == 200
        assert 'access_token' in response.json
        assert response.json['user']['email'] == 'admin@example.com'
        assert 'admin' in response.json['user']['roles']

    def test_login_invalid_password(self, client):
        response = client.post(
            '/api/auth/login',
            json={'email': 'admin@example.com', 'password': 'wrong-password'},
        )
        assert response.status_code == 401

    def test_login_unknown_email(self, client):
        response = client.post(
            '/api/auth/login',
            json={'email': 'nobody@example.com', 'password': 'admin-password'},
        )
        assert response.status_code == 401

    def test_login_invalid_email_format(self, client):
        response = client.post(
            '/api/auth/login',
            json={'email': 'not-an-email', 'password': 'pwd123456'},
        )
        assert response.status_code == 400

    def test_login_short_password(self, client):
        response = client.post(
            '/api/auth/login',
            json={'email': 'admin@example.com', 'password': 'short'},
        )
        assert response.status_code == 400


class TestProfile:
    def test_profile_with_valid_token(self, client, auth_headers):
        response = client.get('/api/auth/profile', headers=auth_headers)
        assert response.status_code == 200
        assert response.json['email'] == 'admin@example.com'
        assert 'permissions' in response.json

    def test_profile_without_token(self, client):
        response = client.get('/api/auth/profile')
        assert response.status_code == 401

    def test_profile_with_invalid_token(self, client):
        response = client.get('/api/auth/profile',
                              headers={'Authorization': 'Bearer invalid.token.here'})
        assert response.status_code in (401, 422)


class TestTokenBlacklist:
    """Phase 6.1: Token-Blacklist nach Logout."""

    def test_logout_revokes_token(self, client):
        # Login
        login = client.post('/api/auth/login',
                            json={'email': 'admin@example.com', 'password': 'admin-password'})
        token = login.json['access_token']
        headers = {'Authorization': f'Bearer {token}'}

        # Profile vor Logout: 200
        before = client.get('/api/auth/profile', headers=headers)
        assert before.status_code == 200

        # Logout
        logout = client.post('/api/auth/logout', headers=headers)
        assert logout.status_code == 200

        # Profile nach Logout: 401 "Token has been revoked"
        after = client.get('/api/auth/profile', headers=headers)
        assert after.status_code == 401
        # JWT-Extended liefert "Token has been revoked"
        assert 'revoked' in str(after.json).lower() or after.json.get('msg', '')


class TestHealth:
    def test_health_no_auth(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json['status'] == 'healthy'
