"""TOTP (Time-based One-Time Password) helpers — RFC 6238.

Wird verwendet für 2-Faktor-Authentifizierung. Secrets werden Base32-codiert
in der users-DB gespeichert. Backup-Codes werden gehasht abgelegt (gleicher
werkzeug.security-Hash wie Passwörter), nach Einlösung gelöscht.
"""

from __future__ import annotations

import base64
import io
import os
import secrets
from typing import Iterable

import pyotp
import qrcode
from werkzeug.security import generate_password_hash, check_password_hash

ISSUER = 'AI Compliance Suite'
BACKUP_CODE_COUNT = 10


def generate_secret() -> str:
    """Generiert ein 32-Zeichen Base32-Secret (160 Bit)."""
    return pyotp.random_base32(length=32)


def provisioning_uri(secret: str, email: str, issuer: str = ISSUER) -> str:
    """`otpauth://`-URI für Authenticator-Apps (Google Authenticator, Authy, 1Password)."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def qr_code_png_data_url(uri: str) -> str:
    """Rendert die provisioning_uri als PNG und gibt eine data:image/png;base64-URL zurück."""
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def verify_code(secret: str, code: str, *, valid_window: int = 1) -> bool:
    """Verifiziert einen 6-stelligen Code. `valid_window=1` toleriert ±30s Clock-Drift."""
    if not secret or not code:
        return False
    code = code.replace(' ', '').strip()
    if not code.isdigit() or len(code) != 6:
        return False
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=valid_window)
    except Exception:
        return False


def generate_backup_codes(n: int = BACKUP_CODE_COUNT) -> list[str]:
    """Erzeugt n kryptographisch zufällige Backup-Codes im Format `XXXX-XXXX` (8 Hex-Zeichen).

    Codes werden im Klartext zurückgegeben (für Anzeige beim Setup) — gespeichert
    werden nur deren Hashes.
    """
    codes = []
    for _ in range(n):
        raw = secrets.token_hex(4).upper()  # 8 Zeichen
        codes.append(f'{raw[:4]}-{raw[4:]}')
    return codes


def hash_backup_codes(codes: Iterable[str]) -> list[str]:
    """Hasht eine Liste von Backup-Codes (werkzeug PBKDF2)."""
    return [generate_password_hash(c.upper().replace('-', '')) for c in codes]


def consume_backup_code(stored_hashes: list[str], code: str) -> tuple[bool, list[str]]:
    """Prüft ob `code` gegen einen der gehashten Codes verifiziert.

    Bei Erfolg wird der Hash aus der Liste entfernt (single-use).
    Returns: (matched, updated_hashes)
    """
    if not stored_hashes or not code:
        return False, stored_hashes
    normalized = code.upper().replace('-', '').replace(' ', '').strip()
    if len(normalized) != 8 or not all(c in '0123456789ABCDEF' for c in normalized):
        return False, stored_hashes
    for i, h in enumerate(stored_hashes):
        try:
            if check_password_hash(h, normalized):
                return True, stored_hashes[:i] + stored_hashes[i + 1:]
        except Exception:
            continue
    return False, stored_hashes
