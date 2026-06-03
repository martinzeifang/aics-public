"""Unit-Tests für shared/licensing/ (C0).

Kein Live-Server nötig — verwendet eigenen Test-Keypair, signierte Tokens
und Mock-Patch für HTTP-Aufrufe.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


@pytest.fixture(scope='module')
def test_keypair():
    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv, pub_pem


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode('ascii')


def _make_token(priv: Ed25519PrivateKey, payload: dict, kid: str = 'v1') -> str:
    header = {'typ': 'AICS-LIC', 'alg': 'Ed25519', 'kid': kid}
    h = _b64u(json.dumps(header, separators=(',', ':')).encode())
    p = _b64u(json.dumps(payload, separators=(',', ':')).encode())
    sig = priv.sign(f'{h}.{p}'.encode())
    return f'{h}.{p}.{_b64u(sig)}'


@pytest.fixture
def patched_pubkey(test_keypair, monkeypatch):
    """Tauscht den eingebetteten Pubkey gegen unseren Test-Pubkey."""
    _, pub_pem = test_keypair
    monkeypatch.setitem(
        __import__('shared.licensing.config', fromlist=['KNOWN_PUBLIC_KEYS']).KNOWN_PUBLIC_KEYS,
        'v1', pub_pem,
    )


# ── verify.py ──────────────────────────────────────────────────────────


def test_verify_valid_token(test_keypair, patched_pubkey):
    from shared.licensing.verify import verify_token, LicenseState

    priv, _ = test_keypair
    now = int(time.time())
    token = _make_token(priv, {
        'lic': 'lic-1', 'key': 'ABC', 'cust': 'Test',
        'plan': 'yearly', 'mods': ['cra', 'nis2'],
        'iss': now - 60, 'nbf': now - 60, 'exp': now + 3600,
        'fp': 'a' * 64, 'usr': 5, 'ver': 1,
    })
    r = verify_token(token, fingerprint='a' * 64)
    assert r.valid is True
    assert r.state == LicenseState.OK
    assert r.modules == ['cra', 'nis2']
    assert r.max_users == 5


def test_verify_demo_state(test_keypair, patched_pubkey):
    from shared.licensing.verify import verify_token, LicenseState

    priv, _ = test_keypair
    now = int(time.time())
    token = _make_token(priv, {
        'lic': 'lic-demo', 'plan': 'demo', 'mods': ['*'],
        'exp': now + 3600, 'fp': 'b' * 64, 'ver': 1,
    })
    r = verify_token(token, fingerprint='b' * 64)
    assert r.valid is True
    assert r.state == LicenseState.DEMO
    assert r.is_demo


def test_verify_expired(test_keypair, patched_pubkey):
    from shared.licensing.verify import verify_token, LicenseState

    priv, _ = test_keypair
    # 1h Vergangenheit — außerhalb clock_skew-Toleranz
    token = _make_token(priv, {'exp': int(time.time()) - 3600, 'fp': 'c' * 64})
    r = verify_token(token, fingerprint='c' * 64)
    assert r.valid is False
    assert r.state == LicenseState.READ_ONLY
    assert r.reason == 'expired'


def test_verify_fingerprint_mismatch(test_keypair, patched_pubkey):
    from shared.licensing.verify import verify_token

    priv, _ = test_keypair
    token = _make_token(priv, {'exp': int(time.time()) + 3600, 'fp': 'a' * 64})
    r = verify_token(token, fingerprint='b' * 64)
    assert r.valid is False
    assert r.reason == 'fingerprint-mismatch'


def test_verify_tampered_signature(test_keypair, patched_pubkey):
    from shared.licensing.verify import verify_token

    priv, _ = test_keypair
    token = _make_token(priv, {'exp': int(time.time()) + 3600, 'fp': 'a' * 64})
    h, p, s = token.split('.')
    tampered = f'{h}.{p}.{s[:-4]}AAAA'
    r = verify_token(tampered)
    assert r.valid is False
    assert r.reason == 'bad-signature'


def test_verify_no_token():
    from shared.licensing.verify import verify_token, LicenseState

    r = verify_token('')
    assert r.valid is False
    assert r.state == LicenseState.NO_LICENSE


def test_verify_unknown_kid(test_keypair):
    from shared.licensing.verify import verify_token

    priv, _ = test_keypair
    token = _make_token(priv, {'exp': int(time.time()) + 3600, 'fp': 'a' * 64}, kid='v99')
    r = verify_token(token)
    assert r.valid is False
    assert 'unknown-kid' in r.reason


# ── fingerprint.py ─────────────────────────────────────────────────────


def test_fingerprint_deterministic():
    from shared.licensing.fingerprint import compute_fingerprint

    a = compute_fingerprint()
    b = compute_fingerprint()
    assert a == b
    assert len(a) == 64
    assert all(c in '0123456789abcdef' for c in a)


def test_machine_label_nonempty():
    from shared.licensing.fingerprint import machine_label

    assert machine_label()
    assert '(' in machine_label() and ')' in machine_label()


# ── cache.py ───────────────────────────────────────────────────────────


def test_cache_roundtrip(tmp_path):
    from shared.licensing.config import LicenseClientConfig
    from shared.licensing.cache import load_cached_token, save_cached_token, delete_cached_token

    cache = tmp_path / 'license.token'
    cfg = LicenseClientConfig(
        server_url='http://x', request_timeout=5, heartbeat_interval=3600,
        verify_tls=False, cache_path=cache, app_version='test',
    )
    assert load_cached_token(cfg) == ''
    save_cached_token(cfg, 'abc.def.ghi')
    assert load_cached_token(cfg) == 'abc.def.ghi'
    delete_cached_token(cfg)
    assert load_cached_token(cfg) == ''


def test_cache_corrupted_returns_empty(tmp_path):
    from shared.licensing.config import LicenseClientConfig
    from shared.licensing.cache import load_cached_token

    cache = tmp_path / 'license.token'
    cache.write_text('garbage without header')
    cfg = LicenseClientConfig(
        server_url='http://x', request_timeout=5, heartbeat_interval=3600,
        verify_tls=False, cache_path=cache, app_version='test',
    )
    assert load_cached_token(cfg) == ''


# ── client.py (mit Mocking) ────────────────────────────────────────────


@pytest.fixture
def cfg(tmp_path):
    from shared.licensing.config import LicenseClientConfig
    return LicenseClientConfig(
        server_url='https://lic.example.de:8444', request_timeout=5,
        heartbeat_interval=3600, verify_tls=False,
        cache_path=tmp_path / 'license.token', app_version='test',
    )


def test_client_activate_calls_correct_endpoint(cfg):
    from shared.licensing.client import LicenseClient

    with patch('shared.licensing.client.requests.post') as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'token': 'tok', 'plan': 'demo'}
        LicenseClient(cfg).activate('SOMEKEY')

    args, kwargs = mock_post.call_args
    assert args[0] == 'https://lic.example.de:8444/api/v1/activate'
    body = kwargs['json']
    assert body['license_key'] == 'SOMEKEY'
    assert len(body['fingerprint']) == 64


def test_client_heartbeat_with_user_count(cfg):
    from shared.licensing.client import LicenseClient

    with patch('shared.licensing.client.requests.post') as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'ok': True, 'over_limit': False}
        LicenseClient(cfg).heartbeat('tok123', user_count=5, admin_count=2)

    body = mock_post.call_args.kwargs['json']
    assert body['user_count'] == 5
    assert body['admin_count'] == 2


def test_client_error_on_http_failure(cfg):
    from shared.licensing.client import LicenseClient, LicenseClientError

    with patch('shared.licensing.client.requests.post') as mock_post:
        mock_post.return_value.status_code = 423
        mock_post.return_value.json.return_value = {'error': 'license-suspended', 'message': 'foo'}

        with pytest.raises(LicenseClientError) as exc_info:
            LicenseClient(cfg).heartbeat('tok')

    assert exc_info.value.http_status == 423
    assert exc_info.value.code == 'license-suspended'


def test_client_network_error_wrapped(cfg):
    from shared.licensing.client import LicenseClient, LicenseClientError

    with patch('shared.licensing.client.requests.post') as mock_post:
        import requests
        mock_post.side_effect = requests.ConnectionError('boom')

        with pytest.raises(LicenseClientError) as exc_info:
            LicenseClient(cfg).activate('K')

    assert exc_info.value.code == 'network-error'


def test_offline_request_payload(cfg):
    from shared.licensing.client import LicenseClient

    payload = LicenseClient(cfg).build_offline_request('KEY-123')
    assert payload['license_key'] == 'KEY-123'
    assert len(payload['fingerprint']) == 64
    assert payload['nonce']
    assert payload['version'] == 1
