"""#1146: TLS-Verify-Default für den Lizenz-Client.

Private/Intranet-Lizenzserver (RFC1918-IP, localhost, *.local) → Default
``verify_tls=False`` (self-signed üblich); öffentliche Hosts → secure-by-default
``True``. Explizite Datei-/ENV-Werte gewinnen weiterhin.
"""
from __future__ import annotations

import pytest

from shared.licensing import config as lc


@pytest.mark.parametrize("url,private", [
    ("https://licensing.example.com:8444", True),
    ("https://10.0.0.5:8444", True),
    ("https://172.20.1.2:8444", True),
    ("https://localhost:8444", True),
    ("https://lic.intern:8444", True),
    ("https://srv.local:8444", True),
    ("https://lic.example.com:8444", False),
    ("https://8.8.8.8", False),
    ("", False),
])
def test_is_private_license_host(url, private):
    assert lc._is_private_license_host(url) is private


def test_default_verify_tls_private_vs_public(monkeypatch):
    # Keine Datei-Overrides, keine ENV-Vorgabe → kontextabhängiger Default.
    monkeypatch.setattr(lc, "load_settings", lambda: {})
    monkeypatch.delenv("AICS_LICENSE_VERIFY_TLS", raising=False)

    priv = lc.get_client_config(server_url="https://licensing.example.com:8444")
    assert priv.verify_tls is False  # self-signed Intranet → aus

    pub = lc.get_client_config(server_url="https://lic.example.com:8444")
    assert pub.verify_tls is True    # öffentlich → secure-by-default


def test_explicit_settings_win(monkeypatch):
    # Datei-Override gewinnt auch bei privater IP.
    monkeypatch.setattr(lc, "load_settings",
                        lambda: {"server_url": "https://licensing.example.com:8444", "verify_tls": True})
    cfg = lc.get_client_config(server_url="https://licensing.example.com:8444")
    assert cfg.verify_tls is True

    # ENV-Opt-out gewinnt bei öffentlichem Host.
    monkeypatch.setattr(lc, "load_settings", lambda: {})
    monkeypatch.setenv("AICS_LICENSE_VERIFY_TLS", "0")
    cfg2 = lc.get_client_config(server_url="https://lic.example.com:8444")
    assert cfg2.verify_tls is False
