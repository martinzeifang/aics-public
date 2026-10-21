"""Sprint #25 — OWASP Secure-by-Design & Datenschutz-Härtung (#1183–#1190).

Reine Logik-Tests (ohne DB) für LDAP-TLS-Härtung und Objekt-RBAC-Helfer +
PG-gestützte Tests für Step-up und die allowed_firmen-Persistenz.
"""
from __future__ import annotations

import pytest


# ── #1184 LDAP fail-closed / TLS ─────────────────────────────────────────────

def test_ldap_plaintext_is_rejected(monkeypatch):
    from server.auth.ldap import LDAPConfig
    monkeypatch.setenv('LDAP_SERVER_URI', 'ldap://localhost:389')
    monkeypatch.delenv('LDAP_USE_STARTTLS', raising=False)
    monkeypatch.delenv('LDAP_ALLOW_INSECURE', raising=False)
    cfg = LDAPConfig()
    assert cfg.is_secure is False
    assert cfg.security_error() is not None  # fail-closed


def test_ldaps_is_secure(monkeypatch):
    from server.auth.ldap import LDAPConfig
    monkeypatch.setenv('LDAP_SERVER_URI', 'ldaps://ldap.example.com:636')
    cfg = LDAPConfig()
    assert cfg.is_secure is True
    assert cfg.security_error() is None


def test_starttls_is_secure(monkeypatch):
    from server.auth.ldap import LDAPConfig
    monkeypatch.setenv('LDAP_SERVER_URI', 'ldap://localhost:389')
    monkeypatch.setenv('LDAP_USE_STARTTLS', 'true')
    cfg = LDAPConfig()
    assert cfg.is_secure is True
    assert cfg.security_error() is None


def test_plaintext_with_explicit_risk_acceptance(monkeypatch):
    from server.auth.ldap import LDAPConfig
    monkeypatch.setenv('LDAP_SERVER_URI', 'ldap://localhost:389')
    monkeypatch.setenv('LDAP_ALLOW_INSECURE', 'true')
    cfg = LDAPConfig()
    assert cfg.security_error() is None  # Risikoakzeptanz hebt fail-closed auf


# ── #1185 Objekt-RBAC (firma_acl) ────────────────────────────────────────────

def test_firma_acl_denies_foreign_firma_by_id():
    from server.middleware.firma_acl import access_denied_for_firma
    claims = {'allowed_firmen': [1, 2]}
    # firmen_id direkt im Pfad → kein DB-Zugriff nötig
    assert access_denied_for_firma(claims, 'risikobewertung', {'firmen_id': 3}) is True
    assert access_denied_for_firma(claims, 'risikobewertung', {'firmen_id': 1}) is False


def test_firma_acl_admin_unrestricted():
    from server.middleware.firma_acl import access_denied_for_firma
    # None = alle Firmen (Admin) → nie blockiert
    assert access_denied_for_firma({'allowed_firmen': None}, 'cra', {'firmen_id': 99}) is False
    assert access_denied_for_firma({}, 'cra', {'firmen_id': 99}) is False


def test_firma_acl_fail_open_when_unresolvable():
    from server.middleware.firma_acl import access_denied_for_firma
    # Keine firmen_id/Name im Pfad ableitbar → fail-open (nicht blockieren)
    assert access_denied_for_firma({'allowed_firmen': [1]}, 'cra', {}) is False


def test_filter_allowed_firmen_ids():
    from server.middleware.firma_acl import filter_allowed_firmen_ids
    assert filter_allowed_firmen_ids({'allowed_firmen': [1, 3]}, [1, 2, 3, 4]) == [1, 3]
    assert filter_allowed_firmen_ids({'allowed_firmen': None}, [1, 2]) == [1, 2]  # None = alle


# ── #1183 Step-up (PG-gestützt: braucht User-DB) ─────────────────────────────

def test_step_up_requires_correct_password(pg):
    from server.auth.users_db import create_user
    from server.auth.stepup import verify_step_up
    u = create_user(email='stepup@example.com', password='Correct-Horse-9!', roles=['cra_viewer'])
    ok, _ = verify_step_up(u['id'], {'current_password': 'Correct-Horse-9!'})
    assert ok is True
    ok2, err = verify_step_up(u['id'], {'current_password': 'wrong'})
    assert ok2 is False and err
    ok3, err3 = verify_step_up(u['id'], {})  # kein Nachweis
    assert ok3 is False


# ── #1185 allowed_firmen-Persistenz (PG-gestützt) ────────────────────────────

def test_allowed_firmen_roundtrip(pg):
    from server.auth.users_db import create_user, get_user_by_id, update_user
    u = create_user(email='rbac@example.com', password='Correct-Horse-9!',
                    roles=['cra_viewer'], allowed_firmen=[1, 2])
    loaded = get_user_by_id(u['id'])
    assert loaded['allowed_firmen'] == [1, 2]
    update_user(u['id'], allowed_firmen=None)  # Whitelist entfernen = alle Firmen
    assert get_user_by_id(u['id'])['allowed_firmen'] is None
