"""Tests für server/auth/users_db.py — User-CRUD + Token-Blacklist."""

import pytest

from server.auth.users_db import (
    ensure_db,
    create_user,
    get_user_by_email,
    update_user,
    delete_user,
    list_users,
    verify_password,
    revoke_token,
    is_token_revoked,
    cleanup_expired_revocations,
)


@pytest.fixture
def fresh_db(tmp_path):
    """Frische users.sqlite pro Test."""
    db = tmp_path / 'users.sqlite'
    ensure_db(db)
    return db


class TestUserCRUD:
    def test_create_and_get(self, fresh_db):
        u = create_user(email='alice@test.com', password='SecretPass123', roles=['admin'], db_path=fresh_db)
        assert u['email'] == 'alice@test.com'
        assert 'id' in u

        loaded = get_user_by_email('alice@test.com', db_path=fresh_db)
        assert loaded is not None
        assert loaded['email'] == 'alice@test.com'
        assert 'admin' in loaded['roles']

    def test_verify_password(self, fresh_db):
        create_user(email='bob@test.com', password='MyPassword!', roles=['cra_viewer'], db_path=fresh_db)
        u = get_user_by_email('bob@test.com', db_path=fresh_db)
        assert verify_password(u, 'MyPassword!') is True
        assert verify_password(u, 'wrongpass') is False

    def test_get_unknown_user(self, fresh_db):
        assert get_user_by_email('unknown@test.com', db_path=fresh_db) is None

    def test_update_user_password(self, fresh_db):
        u = create_user(email='charlie@test.com', password='OldPass123', roles=['admin'], db_path=fresh_db)
        update_user(u['id'], password='NewPass456', db_path=fresh_db)
        loaded = get_user_by_email('charlie@test.com', db_path=fresh_db)
        assert verify_password(loaded, 'NewPass456') is True
        assert verify_password(loaded, 'OldPass123') is False

    def test_update_user_roles(self, fresh_db):
        u = create_user(email='dave@test.com', password='Pass123abc', roles=['cra_viewer'], db_path=fresh_db)
        update_user(u['id'], roles=['admin', 'cra_editor'], db_path=fresh_db)
        loaded = get_user_by_email('dave@test.com', db_path=fresh_db)
        assert set(loaded['roles']) == {'admin', 'cra_editor'}

    def test_deactivate_user(self, fresh_db):
        u = create_user(email='eve@test.com', password='Pass123abc', roles=['admin'], db_path=fresh_db)
        update_user(u['id'], active=False, db_path=fresh_db)
        # get_user_by_email filtert active=1
        assert get_user_by_email('eve@test.com', db_path=fresh_db) is None

    def test_delete_user(self, fresh_db):
        u = create_user(email='frank@test.com', password='Pass123abc', roles=['admin'], db_path=fresh_db)
        assert delete_user(u['id'], db_path=fresh_db) is True
        assert get_user_by_email('frank@test.com', db_path=fresh_db) is None
        assert delete_user('nonexistent-id', db_path=fresh_db) is False

    def test_list_users(self, fresh_db):
        create_user(email='u1@test.com', password='Pass123abc', roles=['admin'], db_path=fresh_db)
        create_user(email='u2@test.com', password='Pass456def', roles=['cra_viewer'], db_path=fresh_db)
        users = list_users(db_path=fresh_db)
        emails = [u['email'] for u in users]
        assert 'u1@test.com' in emails
        assert 'u2@test.com' in emails


class TestTokenBlacklist:
    def test_revoke_and_check(self, fresh_db):
        jti = 'test-jti-1234'
        assert is_token_revoked(jti, db_path=fresh_db) is False
        revoke_token(jti, user_id='user-001', expires_at=9999999999, db_path=fresh_db)
        assert is_token_revoked(jti, db_path=fresh_db) is True

    def test_unknown_jti_not_revoked(self, fresh_db):
        revoke_token('jti-A', expires_at=9999999999, db_path=fresh_db)
        assert is_token_revoked('jti-B', db_path=fresh_db) is False

    def test_empty_jti(self, fresh_db):
        revoke_token('', db_path=fresh_db)  # No-op
        assert is_token_revoked('', db_path=fresh_db) is False

    def test_cleanup_expired(self, fresh_db):
        revoke_token('past-jti', expires_at=1, db_path=fresh_db)
        revoke_token('future-jti', expires_at=9999999999, db_path=fresh_db)
        deleted = cleanup_expired_revocations(db_path=fresh_db)
        assert deleted >= 1
        assert is_token_revoked('past-jti', db_path=fresh_db) is False
        assert is_token_revoked('future-jti', db_path=fresh_db) is True
