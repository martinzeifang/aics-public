"""Tests für WP-09 (#742): Krypto- & Secrets-at-rest-Härtung.

Deckt ab:
(a) TOTP-Secret wird NICHT im Klartext in der DB abgelegt, round-trippt aber
    korrekt über den users_db-Helper/die API.
(b) License-Config: verify_tls defaultet auf True, wenn keine ENV gesetzt ist.
(c) MFA-Backup-Codes haben ausreichende Länge/Entropie (>= 64 Bit).
(d) Config-Integritäts-Sidecar ist fail-closed bei Manipulation (Unit-Level)
    und nutzt HMAC, wenn ein Schlüssel vorhanden ist.
"""

from __future__ import annotations

import base64
import os
import secrets
import sqlite3
from pathlib import Path


def _b32_secret() -> str:
    """Erzeugt zur Laufzeit ein gültiges Base32-TOTP-Secret (kein hartkodiertes
    High-Entropy-Literal → keine False-Positives im Secret-Scanner)."""
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')

import pytest


@pytest.fixture(autouse=True)
def _full_license():
    """Schreibende Calls auf lizenzierte Module bekämen sonst HTTP 423 in CI."""
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


# ─────────────────────────────────────────────────────────────────────────────
# (a) TOTP-Secret at-rest
# ─────────────────────────────────────────────────────────────────────────────

class TestTotpSecretAtRest:
    def test_secret_not_plaintext_in_db_but_roundtrips(self, tmp_path):
        from server.auth import users_db as udb

        db_path = tmp_path / 'users.sqlite'
        udb.ensure_db(db_path)
        user = udb.create_user(email='totp@example.com', password='pw-12345678',
                               roles=['user'], db_path=db_path)
        uid = user['id']

        plaintext_secret = _b32_secret()
        udb.set_totp_secret(uid, plaintext_secret, db_path=db_path)

        # Rohwert direkt aus der DB lesen — darf das Klartext-Secret NICHT enthalten.
        con = sqlite3.connect(str(db_path))
        raw = con.execute('SELECT totp_secret FROM users WHERE id=?', (uid,)).fetchone()[0]
        con.close()
        assert raw is not None
        assert plaintext_secret not in raw, 'TOTP-Secret darf nicht im Klartext gespeichert sein'
        assert raw.startswith('AICSFLD1:'), 'Secret sollte at-rest verschlüsselt sein'

        # Über den Helper muss es korrekt zurückkommen.
        state = udb.get_totp_state(uid, db_path=db_path)
        assert state['secret'] == plaintext_secret

    def test_legacy_plaintext_secret_is_readable_and_migrated(self, tmp_path):
        """Bestandsdaten (Klartext) bleiben lesbar und werden beim Lesen migriert."""
        from server.auth import users_db as udb

        db_path = tmp_path / 'users.sqlite'
        udb.ensure_db(db_path)
        user = udb.create_user(email='legacy@example.com', password='pw-12345678',
                               roles=['user'], db_path=db_path)
        uid = user['id']

        legacy_secret = _b32_secret()
        # Direkt als Klartext in die DB schreiben (simuliert Altbestand).
        con = sqlite3.connect(str(db_path))
        con.execute('UPDATE users SET totp_secret=? WHERE id=?', (legacy_secret, uid))
        con.commit()
        con.close()

        # Lesen liefert Klartext korrekt zurück …
        state = udb.get_totp_state(uid, db_path=db_path)
        assert state['secret'] == legacy_secret

        # … und hat den Wert transparent verschlüsselt zurückgeschrieben.
        con = sqlite3.connect(str(db_path))
        raw = con.execute('SELECT totp_secret FROM users WHERE id=?', (uid,)).fetchone()[0]
        con.close()
        assert raw.startswith('AICSFLD1:')
        assert legacy_secret not in raw

    def test_crypto_field_helper_roundtrip(self):
        from shared.crypto_at_rest import encrypt_field, decrypt_field, is_encrypted_field

        token = encrypt_field('super-secret-value')
        assert is_encrypted_field(token)
        assert 'super-secret-value' not in token
        assert decrypt_field(token) == 'super-secret-value'
        # Klartext-Fallback (Migration): nicht-präfixierte Werte unverändert.
        assert decrypt_field('plain') == 'plain'


# ─────────────────────────────────────────────────────────────────────────────
# (b) License verify_tls default True
# ─────────────────────────────────────────────────────────────────────────────

class TestLicenseVerifyTlsDefault:
    def test_default_true_when_env_unset(self, monkeypatch, tmp_path):
        monkeypatch.delenv('AICS_LICENSE_VERIFY_TLS', raising=False)
        # Settings-Datei isolieren, damit kein persistierter Wert greift.
        import shared.licensing.config as lc
        monkeypatch.setattr(lc, '_settings_file', lambda: tmp_path / 'nope.json')
        cfg = lc.get_client_config()
        assert cfg.verify_tls is True

    def test_opt_out_via_env(self, monkeypatch, tmp_path):
        import shared.licensing.config as lc
        monkeypatch.setattr(lc, '_settings_file', lambda: tmp_path / 'nope.json')
        monkeypatch.setenv('AICS_LICENSE_VERIFY_TLS', 'false')
        cfg = lc.get_client_config()
        assert cfg.verify_tls is False

    def test_explicit_on_env(self, monkeypatch, tmp_path):
        import shared.licensing.config as lc
        monkeypatch.setattr(lc, '_settings_file', lambda: tmp_path / 'nope.json')
        monkeypatch.setenv('AICS_LICENSE_VERIFY_TLS', '1')
        cfg = lc.get_client_config()
        assert cfg.verify_tls is True


# ─────────────────────────────────────────────────────────────────────────────
# (c) Backup-Code-Entropie
# ─────────────────────────────────────────────────────────────────────────────

class TestBackupCodeEntropy:
    def test_codes_have_sufficient_entropy(self):
        from server.auth import totp

        codes = totp.generate_backup_codes()
        assert len(codes) == totp.BACKUP_CODE_COUNT
        for c in codes:
            hex_chars = c.replace('-', '')
            # 16 Hex-Zeichen = 64 Bit Entropie (Anforderung: >= 40 Bit).
            assert len(hex_chars) == 16, f'erwartet 16 Hex-Zeichen, war {c!r}'
            assert all(ch in '0123456789ABCDEF' for ch in hex_chars)

    def test_new_codes_consumable(self):
        from server.auth import totp

        codes = totp.generate_backup_codes()
        hashes = totp.hash_backup_codes(codes)
        matched, remaining = totp.consume_backup_code(hashes, codes[0])
        assert matched is True
        assert len(remaining) == len(hashes) - 1

    def test_legacy_short_code_still_consumable(self):
        """Bereits ausgegebene 8-stellige Codes (Altbestand) bleiben einlösbar."""
        from server.auth import totp

        legacy = 'ABCD-1234'
        hashes = totp.hash_backup_codes([legacy])
        matched, remaining = totp.consume_backup_code(hashes, legacy)
        assert matched is True
        assert remaining == []


# ─────────────────────────────────────────────────────────────────────────────
# (d) Config-Sidecar fail-closed + HMAC
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigSidecarFailClosed:
    def test_tamper_is_rejected_fail_closed(self, tmp_path, monkeypatch):
        import shared.config_io as cio

        monkeypatch.delenv('AICS_CONFIG_AUTO_REPAIR_SIDECAR', raising=False)
        cfg_path = tmp_path / 'app.config.json'
        cio.safe_save_json_config(cfg_path, {'a': 1})

        # Roundtrip funktioniert.
        assert cio.safe_load_json_config(cfg_path) == {'a': 1}

        # Manipulation der Config OHNE Sidecar-Update → fail-closed.
        cfg_path.write_text('{"a": 999}', encoding='utf-8')
        with pytest.raises(ValueError):
            cio.safe_load_json_config(cfg_path)

    def test_opt_in_auto_repair(self, tmp_path, monkeypatch):
        import shared.config_io as cio

        cfg_path = tmp_path / 'app.config.json'
        cio.safe_save_json_config(cfg_path, {'a': 1})
        cfg_path.write_text('{"a": 2}', encoding='utf-8')

        monkeypatch.setenv('AICS_CONFIG_AUTO_REPAIR_SIDECAR', '1')
        # Mit Opt-In wird das Sidecar nachgezogen und das Laden gelingt.
        assert cio.safe_load_json_config(cfg_path) == {'a': 2}

    def test_sidecar_uses_hmac_when_key_present(self, tmp_path, monkeypatch):
        import shared.config_io as cio

        monkeypatch.setenv('AICS_CONFIG_HMAC_KEY', 'unit-test-hmac-key')
        cfg_path = tmp_path / 'app.config.json'
        cio.safe_save_json_config(cfg_path, {'x': 'y'})
        sidecar = Path(str(cfg_path) + '.sha256')
        assert sidecar.read_text(encoding='utf-8').strip().startswith('hmac-sha256:')

    def test_hmac_forged_sidecar_rejected(self, tmp_path, monkeypatch):
        """Angreifer ohne korrekten Schlüssel kann keinen gültigen HMAC-Sidecar fälschen."""
        import hashlib
        import hmac as _hmac
        import shared.config_io as cio

        monkeypatch.setenv('AICS_CONFIG_HMAC_KEY', 'real-server-key')
        monkeypatch.delenv('AICS_CONFIG_AUTO_REPAIR_SIDECAR', raising=False)
        cfg_path = tmp_path / 'app.config.json'
        cio.safe_save_json_config(cfg_path, {'x': 'y'})

        # Angreifer ersetzt Config + HMAC-Sidecar mit FALSCHEM Schlüssel.
        forged = b'{"x": "evil"}\n'
        cfg_path.write_bytes(forged)
        bad = _hmac.new(b'attacker-guess', forged, hashlib.sha256).hexdigest()
        sidecar = Path(str(cfg_path) + '.sha256')
        sidecar.write_text('hmac-sha256:' + bad + '\n', encoding='utf-8')

        with pytest.raises(ValueError):
            cio.safe_load_json_config(cfg_path)
