"""Tests für Rate-Limiting + Auth-Auditing (#739 / WP-06).

AUTH-8  Rate-Limit zählt NUR Fehlschläge (erfolgreiche Logins erhöhen nicht).
AUTH-11 forgot-password ist volumengedrosselt (429 nach Limit, 200 sonst).
CFG-3   Semantische Audit-Events feuern bei fail/success/rate_limited.
"""

import pytest

import server.api.auth as auth_mod
from server.auth.users_db import unlock_account


@pytest.fixture(autouse=True)
def _reset_rate_limit(app):
    """login_attempts ist app-global (session-scoped) → vor/nach jedem Test leeren.

    Außerdem das DB-Account-Lockout der Demo-User zurücksetzen, damit der
    per-IP-Rate-Limit-Test nicht mit dem per-User-Lockout kollidiert.
    """
    def _clean():
        with app.app_context():
            app.login_attempts.clear()
        for uid in ('user-001', 'user-002'):
            unlock_account(uid)
    _clean()
    yield
    _clean()


def _login(client, pw='admin-password'):
    return client.post('/api/auth/login',
                       json={'email': 'admin@example.com', 'password': pw})


def _login_unknown(client):
    """Fehlschlag ohne Account-Lockout (nicht-existente E-Mail → 401)."""
    return client.post('/api/auth/login',
                       json={'email': 'nobody-xyz@example.com',
                             'password': 'wrong-password-123'})


class TestRateLimitCountsOnlyFailures:
    def test_repeated_success_never_rate_limited(self, client):
        # AUTH-8: deutlich mehr als MAX_LOGIN_ATTEMPTS erfolgreiche Logins
        for _ in range(auth_mod.MAX_LOGIN_ATTEMPTS + 3):
            r = _login(client)
            assert r.status_code == 200, r.get_json()

    def test_failures_eventually_rate_limited(self, client):
        # MAX fehlerhafte Versuche sind 401, danach 429 (per-IP, ohne Account-Lockout)
        for _ in range(auth_mod.MAX_LOGIN_ATTEMPTS):
            assert _login_unknown(client).status_code == 401
        assert _login_unknown(client).status_code == 429

    def test_success_resets_counter(self, client):
        for _ in range(auth_mod.MAX_LOGIN_ATTEMPTS - 1):
            assert _login_unknown(client).status_code == 401
        # Erfolg setzt den Zähler zurück …
        assert _login(client).status_code == 200
        # … also wieder volle Fehlversuche möglich, kein sofortiges 429
        assert _login_unknown(client).status_code == 401


class TestForgotPasswordThrottle:
    def test_forgot_throttled_after_limit(self, client):
        for _ in range(auth_mod.MAX_LOGIN_ATTEMPTS):
            r = client.post('/api/auth/password/forgot',
                            json={'email': 'admin@example.com'})
            assert r.status_code == 200
        r = client.post('/api/auth/password/forgot',
                        json={'email': 'admin@example.com'})
        assert r.status_code == 429


class TestAuditEvents:
    def test_failed_login_emits_audit(self, client, monkeypatch):
        events = []
        import shared.audit as audit_mod
        monkeypatch.setattr(audit_mod, 'audit_event',
                            lambda *a, **k: events.append((a, k)))
        _login_unknown(client)
        outcomes = [k.get('outcome') for _, k in events]
        actions = [a[0] if a else k.get('action') for a, k in events]
        assert 'auth.login' in actions
        assert 'fail' in outcomes

    def test_successful_login_emits_audit(self, client, monkeypatch):
        events = []
        import shared.audit as audit_mod
        monkeypatch.setattr(audit_mod, 'audit_event',
                            lambda *a, **k: events.append((a, k)))
        _login(client)
        outcomes = [k.get('outcome') for _, k in events]
        assert 'success' in outcomes
