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
