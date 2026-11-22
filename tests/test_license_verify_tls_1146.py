"""#1146 / #1172: TLS-Verify-Default für den Lizenz-Client.

#1172 (Security-Härtung): TLS-Verifikation ist **secure-by-default für ALLE Hosts**
(auch Intranet/RFC1918) — der frühere #1146-Carve-out für private Hosts wurde
entfernt. Self-Signed-Intranet-Server brauchen einen expliziten Opt-out
(``AICS_LICENSE_VERIFY_TLS=false``) oder CA-Pinning (``AICS_LICENSE_CA_BUNDLE``).
"""
from __future__ import annotations

import pytest

from shared.licensing import config as lc


def test_default_verify_tls_secure_by_default(monkeypatch):
    # Kein Datei-Override, keine ENV → True für ALLE Hosts (auch privat).
    monkeypatch.setattr(lc, "load_settings", lambda: {})
    monkeypatch.delenv("AICS_LICENSE_VERIFY_TLS", raising=False)
    monkeypatch.delenv("AICS_LICENSE_CA_BUNDLE", raising=False)
    for url in ("https://licensing.example.com:8444", "https://lic.intern:8444",
                "https://localhost:8444", "https://lic.example.com:8444"):
        assert lc.get_client_config(server_url=url).verify_tls is True, url


def test_explicit_opt_out(monkeypatch):
    monkeypatch.setattr(lc, "load_settings", lambda: {})
    monkeypatch.delenv("AICS_LICENSE_CA_BUNDLE", raising=False)
    monkeypatch.setenv("AICS_LICENSE_VERIFY_TLS", "false")
    assert lc.get_client_config(server_url="https://licensing.example.com:8444").verify_tls is False
    # Datei-Override gewinnt ebenfalls
    monkeypatch.delenv("AICS_LICENSE_VERIFY_TLS", raising=False)
    monkeypatch.setattr(lc, "load_settings", lambda: {"verify_tls": False})
    assert lc.get_client_config(server_url="https://1.2.3.4:8444").verify_tls is False


def test_ca_bundle_pinning(monkeypatch, tmp_path):
    pem = tmp_path / "ca.pem"
    pem.write_text("-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n")
    monkeypatch.setattr(lc, "load_settings", lambda: {})
    monkeypatch.delenv("AICS_LICENSE_VERIFY_TLS", raising=False)
    monkeypatch.setenv("AICS_LICENSE_CA_BUNDLE", str(pem))
    cfg = lc.get_client_config(server_url="https://licensing.example.com:8444")
    assert cfg.verify_tls == str(pem)  # CA-Bundle-Pfad statt bool
