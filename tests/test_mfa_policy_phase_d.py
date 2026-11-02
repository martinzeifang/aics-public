"""Tests für Sprint ε Phase D — MFA-Policy + Enforcement."""

import time

import pytest

from server.auth import mfa_policy as mp
from server.auth.users_db import (
    ensure_db,
    create_user,
    add_webauthn_credential,
    set_totp_secret,
    enable_totp,
    user_has_mfa,
    get_mfa_grace_until,
    set_mfa_grace_until,
)


@pytest.fixture
def fresh_db(tmp_path):
    db = tmp_path / 'users.sqlite'
    ensure_db(db)
    return db


class TestPolicyLogic:
    def test_optional_never_required(self):
        pol = {'mode': 'optional', 'required_roles': [], 'grace_days': 7}
        assert mp.is_mfa_required_for(['admin'], pol) is False

    def test_required_all(self):
        pol = {'mode': 'required_all', 'required_roles': [], 'grace_days': 7}
        assert mp.is_mfa_required_for(['cra_viewer'], pol) is True
        assert mp.is_mfa_required_for([], pol) is True

    def test_required_roles(self):
        pol = {'mode': 'required_roles', 'required_roles': ['admin'], 'grace_days': 7}
        assert mp.is_mfa_required_for(['admin'], pol) is True
        assert mp.is_mfa_required_for(['cra_viewer'], pol) is False
        assert mp.is_mfa_required_for(['admin', 'cra_viewer'], pol) is True


class TestUserHasMfa:
    def test_no_mfa(self, fresh_db):
        u = create_user(email='a@b.com', password='SecretPass1', roles=['admin'], db_path=fresh_db)
        assert user_has_mfa(u['id'], db_path=fresh_db) is False

    def test_with_totp(self, fresh_db):
        u = create_user(email='b@b.com', password='SecretPass1', roles=['admin'], db_path=fresh_db)
        set_totp_secret(u['id'], 'SECRET', db_path=fresh_db)
        enable_totp(u['id'], [], db_path=fresh_db)
        assert user_has_mfa(u['id'], db_path=fresh_db) is True

    def test_with_passkey(self, fresh_db):
        u = create_user(email='c@b.com', password='SecretPass1', roles=['admin'], db_path=fresh_db)
        add_webauthn_credential(user_id=u['id'], credential_id='c1', public_key='pk', db_path=fresh_db)
        assert user_has_mfa(u['id'], db_path=fresh_db) is True


class TestGraceColumn:
    def test_default_zero(self, fresh_db):
        u = create_user(email='g@b.com', password='SecretPass1', roles=['admin'], db_path=fresh_db)
        assert get_mfa_grace_until(u['id'], db_path=fresh_db) == 0

    def test_set_and_get(self, fresh_db):
        u = create_user(email='g2@b.com', password='SecretPass1', roles=['admin'], db_path=fresh_db)
        ts = int(time.time()) + 1000
        set_mfa_grace_until(u['id'], ts, db_path=fresh_db)
        assert get_mfa_grace_until(u['id'], db_path=fresh_db) == ts


class TestEvaluateEnforcement:
    def test_not_required_when_optional(self, fresh_db, monkeypatch):
        monkeypatch.setattr(mp, 'get_policy', lambda: {'mode': 'optional', 'required_roles': [], 'grace_days': 7})
        u = create_user(email='e1@b.com', password='SecretPass1', roles=['admin'], db_path=fresh_db)
        r = mp.evaluate_enforcement({'id': u['id'], 'roles': ['admin']}, db_path=fresh_db)
        assert r['required'] is False
        assert r['setup_required'] is False

    def test_satisfied_when_has_mfa(self, fresh_db, monkeypatch):
        monkeypatch.setattr(mp, 'get_policy', lambda: {'mode': 'required_all', 'required_roles': [], 'grace_days': 7})
        u = create_user(email='e2@b.com', password='SecretPass1', roles=['admin'], db_path=fresh_db)
        add_webauthn_credential(user_id=u['id'], credential_id='ck', public_key='pk', db_path=fresh_db)
        r = mp.evaluate_enforcement({'id': u['id'], 'roles': ['admin']}, db_path=fresh_db)
        assert r['required'] is True
        assert r['satisfied'] is True
        assert r['setup_required'] is False

    def test_within_grace_recommends(self, fresh_db, monkeypatch):
        monkeypatch.setattr(mp, 'get_policy', lambda: {'mode': 'required_all', 'required_roles': [], 'grace_days': 7})
        u = create_user(email='e3@b.com', password='SecretPass1', roles=['admin'], db_path=fresh_db)
        r = mp.evaluate_enforcement({'id': u['id'], 'roles': ['admin']}, db_path=fresh_db)
        assert r['required'] is True and r['satisfied'] is False
        assert r['recommended'] is True
        assert r['setup_required'] is False
        assert r['grace_until'] > int(time.time())  # Grace-Fenster gesetzt

    def test_grace_expired_forces_setup(self, fresh_db, monkeypatch):
        monkeypatch.setattr(mp, 'get_policy', lambda: {'mode': 'required_all', 'required_roles': [], 'grace_days': 0})
        u = create_user(email='e4@b.com', password='SecretPass1', roles=['admin'], db_path=fresh_db)
        # grace_days=0 → grace_until = now → sofort abgelaufen
        r = mp.evaluate_enforcement({'id': u['id'], 'roles': ['admin']}, db_path=fresh_db)
        assert r['setup_required'] is True
        assert r['grace_expired'] is True
