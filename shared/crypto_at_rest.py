"""At-rest encryption helpers (Fernet) for local artifacts.

Scope (Risks #193/#174):
- Provide optional encryption for backup archives and evidence files.
- Does NOT encrypt live SQLite DB files (would require SQLCipher/SEE).

Key management:
- Key is derived from a passphrase stored in an environment variable.
- Each encrypted file contains its own random salt.

Format:
- b"AICSENC1" + salt(16) + fernet_token
"""

from __future__ import annotations

import os
from dataclasses import dataclass


MAGIC = b"AICSENC1"
SALT_LEN = 16


@dataclass(frozen=True)
class EncryptionConfig:
    enabled: bool
    key_env: str
    encrypt_backups: bool = True
    encrypt_evidence: bool = False


def _get_passphrase(env_name: str) -> bytes:
    name = (env_name or "AICS_AT_REST_KEY").strip() or "AICS_AT_REST_KEY"
    v = (os.environ.get(name) or "").encode("utf-8")
    if not v:
        raise RuntimeError(f"Encryption key env var not set: {name}")
    return v


def _fernet_from_passphrase(passphrase: bytes, *, salt: bytes):
    # lazy import to keep startup light
    from base64 import urlsafe_b64encode

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.fernet import Fernet

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000,
    )
    key = urlsafe_b64encode(kdf.derive(passphrase))
    return Fernet(key)


def encrypt_bytes(data: bytes, *, key_env: str) -> bytes:
    import secrets

    salt = secrets.token_bytes(SALT_LEN)
    f = _fernet_from_passphrase(_get_passphrase(key_env), salt=salt)
    token = f.encrypt(data)
    return MAGIC + salt + token


def decrypt_bytes(blob: bytes, *, key_env: str) -> bytes:
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + SALT_LEN + 10:
        raise ValueError("Not an AICS encrypted blob")
    salt = blob[len(MAGIC) : len(MAGIC) + SALT_LEN]
    token = blob[len(MAGIC) + SALT_LEN :]
    f = _fernet_from_passphrase(_get_passphrase(key_env), salt=salt)
    return f.decrypt(token)


# ─────────────────────────────────────────────────────────────────────────────
# Field-level secret encryption (#742) — für DB-Felder wie TOTP-Secrets.
#
# Im Gegensatz zu den Datei-Helfern oben braucht dies KEINE explizite
# AICS_AT_REST_KEY-Config: fehlt diese, wird eine Passphrase aus dem ohnehin
# vorhandenen JWT_SECRET_KEY abgeleitet. So funktioniert die Verschlüsselung
# transparent in Dev/Tests/Demo, ohne zusätzliche Konfiguration.
#
# Format (str): "AICSFLD1:" + urlsafe_b64(salt(16) + fernet_token)
# ─────────────────────────────────────────────────────────────────────────────

FIELD_PREFIX = "AICSFLD1:"


def _field_passphrase() -> bytes:
    """Passphrase für Feld-Verschlüsselung.

    Priorität: AICS_AT_REST_KEY → JWT_SECRET_KEY (Fallback). Eine der beiden
    ist im Betrieb immer gesetzt; im Notfall ein statischer Dev-Wert, damit
    Importe/Tests ohne ENV nicht hart fehlschlagen.
    """
    for name in ("AICS_AT_REST_KEY", "JWT_SECRET_KEY"):
        v = (os.environ.get(name) or "").strip()
        if v:
            return v.encode("utf-8")
    # Letzter Fallback (nur Dev/Import ohne ENV): deterministisch, nicht geheim.
    return b"aics-field-at-rest-dev-fallback"


def encrypt_field(plaintext: str, *, key_env: str | None = None) -> str:
    """Verschlüsselt einen String für die at-rest-Ablage (z.B. TOTP-Secret)."""
    import secrets
    from base64 import urlsafe_b64encode

    if key_env:
        passphrase = _get_passphrase(key_env)
    else:
        passphrase = _field_passphrase()
    salt = secrets.token_bytes(SALT_LEN)
    f = _fernet_from_passphrase(passphrase, salt=salt)
    token = f.encrypt(plaintext.encode("utf-8"))
    return FIELD_PREFIX + urlsafe_b64encode(salt + token).decode("ascii")


def is_encrypted_field(value: str | None) -> bool:
    return bool(value) and value.startswith(FIELD_PREFIX)


def decrypt_field(value: str, *, key_env: str | None = None) -> str:
    """Entschlüsselt einen mit `encrypt_field` erzeugten String.

    Transparente Migration: ist `value` NICHT mit dem Prefix versehen, wird er
    unverändert (als Klartext) zurückgegeben — so bleiben Bestandsdaten lesbar.
    """
    if not is_encrypted_field(value):
        return value  # Klartext-Fallback (Migration)
    from base64 import urlsafe_b64decode

    raw = urlsafe_b64decode(value[len(FIELD_PREFIX):].encode("ascii"))
    salt, token = raw[:SALT_LEN], raw[SALT_LEN:]
    if key_env:
        passphrase = _get_passphrase(key_env)
    else:
        passphrase = _field_passphrase()
    f = _fernet_from_passphrase(passphrase, salt=salt)
    return f.decrypt(token).decode("utf-8")
