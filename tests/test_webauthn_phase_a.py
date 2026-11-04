"""Tests für Sprint ε Phase A — WebAuthn-Foundation.

Deckt ab:
- DB: webauthn_credentials CRUD + sign_count + ownership-Schutz
- DB: ephemere Challenges (store/consume single-use, Ablauf, Typ-Mismatch)
- Wrapper: Options-Generierung (Registrierung + Authentifizierung) + RP-Config
"""

import json
import time

import pytest

from server.auth import webauthn as wa
from server.auth.users_db import (
    add_webauthn_credential,
    consume_webauthn_challenge,
    count_webauthn_credentials,
    delete_webauthn_credential,
    ensure_db,
    get_webauthn_credential_by_cred_id,
    list_webauthn_credentials,
    rename_webauthn_credential,
    store_webauthn_challenge,
    update_webauthn_sign_count,
    cleanup_expired_webauthn_challenges,
)


@pytest.fixture
def fresh_db(tmp_path):
    db = tmp_path / 'users.sqlite'
    ensure_db(db)
    return db


class TestCredentialCRUD:
    def test_add_and_list(self, fresh_db):
        cid = add_webauthn_credential(
            user_id='u1', credential_id='cred-abc', public_key='pk-xyz',
            sign_count=0, transports=['internal'], nickname='MacBook',
            db_path=fresh_db,
        )
        assert cid > 0
        creds = list_webauthn_credentials('u1', db_path=fresh_db)
        assert len(creds) == 1
        assert creds[0]['credential_id'] == 'cred-abc'
        assert creds[0]['nickname'] == 'MacBook'
        assert creds[0]['transports'] == ['internal']

    def test_get_by_cred_id(self, fresh_db):
        add_webauthn_credential(user_id='u1', credential_id='cred-1', public_key='pk', db_path=fresh_db)
        c = get_webauthn_credential_by_cred_id('cred-1', db_path=fresh_db)
        assert c is not None and c['user_id'] == 'u1'
        assert get_webauthn_credential_by_cred_id('missing', db_path=fresh_db) is None

    def test_unique_credential_id(self, fresh_db):
        add_webauthn_credential(user_id='u1', credential_id='dup', public_key='pk', db_path=fresh_db)
        with pytest.raises(Exception):
            add_webauthn_credential(user_id='u2', credential_id='dup', public_key='pk2', db_path=fresh_db)

    def test_count(self, fresh_db):
        assert count_webauthn_credentials('u1', db_path=fresh_db) == 0
        add_webauthn_credential(user_id='u1', credential_id='c1', public_key='pk', db_path=fresh_db)
        add_webauthn_credential(user_id='u1', credential_id='c2', public_key='pk', db_path=fresh_db)
        assert count_webauthn_credentials('u1', db_path=fresh_db) == 2

    def test_update_sign_count(self, fresh_db):
        add_webauthn_credential(user_id='u1', credential_id='c1', public_key='pk', sign_count=5, db_path=fresh_db)
        update_webauthn_sign_count('c1', 9, db_path=fresh_db)
        c = get_webauthn_credential_by_cred_id('c1', db_path=fresh_db)
        assert c['sign_count'] == 9
        assert c['last_used_at'] is not None

    def test_rename_ownership(self, fresh_db):
        cid = add_webauthn_credential(user_id='owner', credential_id='c1', public_key='pk', db_path=fresh_db)
        assert rename_webauthn_credential(cid, 'owner', 'NeuerName', db_path=fresh_db) is True
        # fremder User darf nicht umbenennen
        assert rename_webauthn_credential(cid, 'stranger', 'Hack', db_path=fresh_db) is False
        c = get_webauthn_credential_by_cred_id('c1', db_path=fresh_db)
        assert c['nickname'] == 'NeuerName'

    def test_delete_ownership(self, fresh_db):
        cid = add_webauthn_credential(user_id='owner', credential_id='c1', public_key='pk', db_path=fresh_db)
        # fremder User darf nicht löschen
        assert delete_webauthn_credential(cid, 'stranger', db_path=fresh_db) is False
        assert count_webauthn_credentials('owner', db_path=fresh_db) == 1
        assert delete_webauthn_credential(cid, 'owner', db_path=fresh_db) is True
        assert count_webauthn_credentials('owner', db_path=fresh_db) == 0


class TestChallenges:
    def test_store_and_consume(self, fresh_db):
        chid = store_webauthn_challenge('chal-bytes', 'register', user_id='u1', db_path=fresh_db)
        assert chid
        got = consume_webauthn_challenge(chid, 'register', db_path=fresh_db)
        assert got is not None and got['challenge'] == 'chal-bytes' and got['user_id'] == 'u1'

    def test_single_use(self, fresh_db):
        chid = store_webauthn_challenge('c', 'authenticate', db_path=fresh_db)
        assert consume_webauthn_challenge(chid, 'authenticate', db_path=fresh_db) is not None
        # zweiter Consume schlägt fehl
        assert consume_webauthn_challenge(chid, 'authenticate', db_path=fresh_db) is None

    def test_type_mismatch(self, fresh_db):
        chid = store_webauthn_challenge('c', 'register', db_path=fresh_db)
        assert consume_webauthn_challenge(chid, 'authenticate', db_path=fresh_db) is None

    def test_expiry(self, fresh_db):
        chid = store_webauthn_challenge('c', 'register', ttl_seconds=-1, db_path=fresh_db)
        assert consume_webauthn_challenge(chid, 'register', db_path=fresh_db) is None

    def test_cleanup(self, fresh_db):
        store_webauthn_challenge('c', 'register', ttl_seconds=-1, db_path=fresh_db)
        store_webauthn_challenge('c2', 'register', ttl_seconds=300, db_path=fresh_db)
        deleted = cleanup_expired_webauthn_challenges(db_path=fresh_db)
        assert deleted >= 1


class TestWrapper:
    def test_rp_config_default(self, monkeypatch):
        # Isolation: keine Web-Settings (sonst überschreibt on-disk-Config den Default)
        monkeypatch.setattr(wa, '_settings_rp_config', lambda: {})
        monkeypatch.delenv('WEBAUTHN_RP_ID', raising=False)
        monkeypatch.delenv('WEBAUTHN_RP_ORIGIN', raising=False)
        cfg = wa.get_rp_config()
        assert cfg['rp_id'] == 'localhost'
        assert cfg['origins'] == ['https://localhost:8443']

    def test_rp_config_env(self, monkeypatch):
        monkeypatch.setattr(wa, '_settings_rp_config', lambda: {})
        monkeypatch.setenv('WEBAUTHN_RP_ID', 'aics.example.com')
        monkeypatch.setenv('WEBAUTHN_RP_ORIGIN', 'https://aics.example.com,https://www.aics.example.com')
        cfg = wa.get_rp_config()
        assert cfg['rp_id'] == 'aics.example.com'
        assert len(cfg['origins']) == 2

    def test_registration_options(self):
        opts_json, challenge = wa.build_registration_options(
            user_id='u1', user_email='a@b.com', user_display_name='Alice',
        )
        data = json.loads(opts_json)
        assert data['rp']['id'] == wa.get_rp_config()['rp_id']
        assert data['user']['name'] == 'a@b.com'
        assert 'challenge' in data
        assert isinstance(challenge, bytes) and len(challenge) > 0

    def test_registration_options_excludes(self):
        from webauthn.helpers import bytes_to_base64url
        existing = [{'credential_id': bytes_to_base64url(b'somecredid'), 'transports': ['internal']}]
        opts_json, _ = wa.build_registration_options(
            user_id='u1', user_email='a@b.com', user_display_name='Alice',
            existing_credentials=existing,
        )
        data = json.loads(opts_json)
        assert len(data.get('excludeCredentials', [])) == 1

    def test_authentication_options_discoverable(self):
        opts_json, challenge = wa.build_authentication_options()
        data = json.loads(opts_json)
        assert 'challenge' in data
        # discoverable: keine allowCredentials
        assert not data.get('allowCredentials')
        assert isinstance(challenge, bytes)

    def test_authentication_options_with_allow(self):
        from webauthn.helpers import bytes_to_base64url
        allow = [{'credential_id': bytes_to_base64url(b'mycred'), 'transports': ['internal']}]
        opts_json, _ = wa.build_authentication_options(allow_credentials=allow)
        data = json.loads(opts_json)
        assert len(data.get('allowCredentials', [])) == 1

    def test_extract_credential_id(self):
        assert wa.extract_credential_id({'id': 'abc', 'rawId': 'abc'}) == 'abc'
        assert wa.extract_credential_id('{"id": "xyz"}') == 'xyz'
        assert wa.extract_credential_id('not json') is None
