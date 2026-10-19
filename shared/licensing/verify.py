"""Offline-Token-Validierung mit dem eingebetteten Public-Key.

Bewusst kein externer HTTP-Call — damit funktioniert die Lizenz-Prüfung
auch ohne Server-Verbindung. Der Server-Heartbeat liefert Revocation-Status
separat (siehe client.py).
"""

from __future__ import annotations

import base64
import enum
import json
import time
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from shared.licensing.config import KNOWN_PUBLIC_KEYS


class LicenseState(str, enum.Enum):
    OK = 'ok'                        # Voll funktional
    DEMO = 'demo'                    # Demo aktiv, läuft bald aus
    READ_ONLY = 'read-only'          # Verstoß — kein Schreiben mehr
    NO_LICENSE = 'no-license'        # Kein Token vorhanden
    GRACE_OFFLINE = 'grace-offline'  # Offline > max_offline_days — Warnung


@dataclass(frozen=True)
class VerifyResult:
    valid: bool
    state: LicenseState
    reason: str
    payload: dict[str, Any]

    @property
    def modules(self) -> list[str]:
        m = self.payload.get('mods')
        return list(m) if isinstance(m, list) else []

    @property
    def expires_at(self) -> int:
        return int(self.payload.get('exp') or 0)

    @property
    def max_users(self) -> int:
        return int(self.payload.get('usr') or 0)

    @property
    def is_demo(self) -> bool:
        return self.payload.get('plan') == 'demo'


def _b64url_decode(s: str) -> bytes:
    pad = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _load_pubkey(kid: str) -> Ed25519PublicKey | None:
    pem = KNOWN_PUBLIC_KEYS.get(kid)
    if not pem:
        return None
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, Ed25519PublicKey):
        return None
    return key


def verify_token(
    token: str,
    *,
    fingerprint: str | None = None,
    now_ts: int | None = None,
    clock_skew_seconds: int = 60,
) -> VerifyResult:
    """Verifiziert einen License-Token offline.

    - Signaturen-Check mit dem Pubkey passend zum `kid`-Header
    - exp / nbf
    - fp-Match (wenn fingerprint übergeben)
    """
    if not token:
        return VerifyResult(False, LicenseState.NO_LICENSE, 'no-token', {})

    try:
        h_b, p_b, s_b = token.split('.')
        header = json.loads(_b64url_decode(h_b))
        payload = json.loads(_b64url_decode(p_b))
        sig = _b64url_decode(s_b)
    except (ValueError, json.JSONDecodeError) as e:
        return VerifyResult(False, LicenseState.READ_ONLY, f'malformed: {e}', {})

    if header.get('typ') != 'AICS-LIC' or header.get('alg') != 'Ed25519':
        return VerifyResult(False, LicenseState.READ_ONLY, 'bad-header', payload)

    kid = header.get('kid') or 'v1'
    pubkey = _load_pubkey(kid)
    if pubkey is None:
        return VerifyResult(False, LicenseState.READ_ONLY, f'unknown-kid:{kid}', payload)

    signing_input = f'{h_b}.{p_b}'.encode('ascii')
    try:
        pubkey.verify(sig, signing_input)
    except InvalidSignature:
        return VerifyResult(False, LicenseState.READ_ONLY, 'bad-signature', payload)
    except Exception as e:  # noqa: BLE001
        return VerifyResult(False, LicenseState.READ_ONLY, f'verify-error: {e}', payload)

    now = now_ts if now_ts is not None else int(time.time())
    exp = int(payload.get('exp') or 0)
    nbf = int(payload.get('nbf') or 0)

    # clock_skew_seconds toleriert geringen Client-Server-Drift
    if nbf and nbf > (now + clock_skew_seconds):
        return VerifyResult(False, LicenseState.READ_ONLY, 'not-yet-valid', payload)
    if exp and exp < (now - clock_skew_seconds):
        return VerifyResult(False, LicenseState.READ_ONLY, 'expired', payload)

    if fingerprint is not None and payload.get('fp') != fingerprint:
        return VerifyResult(False, LicenseState.READ_ONLY, 'fingerprint-mismatch', payload)

    state = LicenseState.DEMO if payload.get('plan') == 'demo' else LicenseState.OK
    return VerifyResult(True, state, '', payload)
