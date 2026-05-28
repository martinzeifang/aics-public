"""WebAuthn / FIDO2 / Passkey-Wrapper (Sprint ε, Phase A).

Dünne Schicht um die `webauthn`-Library (py_webauthn, Duo Labs). Kapselt
RP-Konfiguration und liefert JSON-serialisierbare Options für das Frontend
(@simplewebauthn/browser) sowie Verify-Helfer.

Konfiguration über Umgebungsvariablen (RP-ID/Origin MÜSSEN zur ausliefernden
Domain passen — lokal 'localhost', in Docker hinter nginx-TLS die echte Domain):

    WEBAUTHN_RP_ID      Default: 'localhost'
    WEBAUTHN_RP_NAME    Default: 'AI Compliance Suite'
    WEBAUTHN_RP_ORIGIN  Default: 'https://localhost:8443'
                        (mehrere Origins komma-separiert erlaubt)

Hinweis: Diese Library wirft bei Verifikationsfehlern Exceptions; die API-Schicht
fängt sie ab und liefert 400/401.
"""

from __future__ import annotations

import json
import os
from typing import Any

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

DEFAULT_RP_ID = 'localhost'
DEFAULT_RP_NAME = 'AI Compliance Suite'
DEFAULT_RP_ORIGIN = 'https://localhost:8443'


def get_rp_config() -> dict[str, Any]:
    """Liest die RP-Konfiguration aus der Umgebung (zur Request-Zeit, nicht Import-Zeit)."""
    rp_id = (os.getenv('WEBAUTHN_RP_ID') or DEFAULT_RP_ID).strip()
    rp_name = (os.getenv('WEBAUTHN_RP_NAME') or DEFAULT_RP_NAME).strip()
    origins_raw = (os.getenv('WEBAUTHN_RP_ORIGIN') or DEFAULT_RP_ORIGIN).strip()
    origins = [o.strip() for o in origins_raw.split(',') if o.strip()]
    return {'rp_id': rp_id, 'rp_name': rp_name, 'origins': origins}


def _expected_origin() -> str | list[str]:
    """py_webauthn akzeptiert str oder list[str] für expected_origin."""
    origins = get_rp_config()['origins']
    return origins[0] if len(origins) == 1 else origins


def _transports_to_enum(transports: list[str] | None) -> list[AuthenticatorTransport] | None:
    if not transports:
        return None
    out: list[AuthenticatorTransport] = []
    for t in transports:
        try:
            out.append(AuthenticatorTransport(t))
        except ValueError:
            continue
    return out or None


# ─────────────────────────────────────────────────────────────────────────────
# Registrierung
# ─────────────────────────────────────────────────────────────────────────────


def build_registration_options(
    user_id: str,
    user_email: str,
    user_display_name: str,
    existing_credentials: list[dict[str, Any]] | None = None,
) -> tuple[str, bytes]:
    """Erzeugt Registrierungs-Options.

    Returns (options_json, challenge_bytes). options_json geht ans Frontend,
    challenge_bytes wird serverseitig in der Challenge-Tabelle abgelegt.
    """
    cfg = get_rp_config()
    exclude = []
    for c in existing_credentials or []:
        exclude.append(PublicKeyCredentialDescriptor(
            id=base64url_to_bytes(c['credential_id']),
            transports=_transports_to_enum(c.get('transports')),
        ))

    options = generate_registration_options(
        rp_id=cfg['rp_id'],
        rp_name=cfg['rp_name'],
        user_id=user_id.encode('utf-8'),
        user_name=user_email,
        user_display_name=user_display_name or user_email,
        exclude_credentials=exclude or None,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    return options_to_json(options), options.challenge


def verify_registration(
    credential_json: dict[str, Any] | str,
    expected_challenge: bytes,
) -> dict[str, Any]:
    """Verifiziert die Registrierungs-Antwort des Authenticators.

    Returns dict mit base64url-codierten Feldern für die DB-Speicherung.
    Wirft bei ungültiger Antwort eine Exception (von py_webauthn).
    """
    cfg = get_rp_config()
    verified = verify_registration_response(
        credential=credential_json if isinstance(credential_json, str) else json.dumps(credential_json),
        expected_challenge=expected_challenge,
        expected_rp_id=cfg['rp_id'],
        expected_origin=_expected_origin(),
    )
    return {
        'credential_id': bytes_to_base64url(verified.credential_id),
        'public_key': bytes_to_base64url(verified.credential_public_key),
        'sign_count': verified.sign_count,
        'aaguid': verified.aaguid or '',
        'backup_eligible': bool(verified.credential_device_type == 'multi_device'),
        'backup_state': bool(verified.credential_backed_up),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Authentifizierung
# ─────────────────────────────────────────────────────────────────────────────


def build_authentication_options(
    allow_credentials: list[dict[str, Any]] | None = None,
) -> tuple[str, bytes]:
    """Erzeugt Authentifizierungs-Options.

    allow_credentials leer = discoverable credentials (passwortloser Login,
    Authenticator wählt selbst). Returns (options_json, challenge_bytes).
    """
    cfg = get_rp_config()
    allow = []
    for c in allow_credentials or []:
        allow.append(PublicKeyCredentialDescriptor(
            id=base64url_to_bytes(c['credential_id']),
            transports=_transports_to_enum(c.get('transports')),
        ))

    options = generate_authentication_options(
        rp_id=cfg['rp_id'],
        allow_credentials=allow or None,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    return options_to_json(options), options.challenge


def verify_authentication(
    credential_json: dict[str, Any] | str,
    expected_challenge: bytes,
    stored_public_key: str,
    stored_sign_count: int,
) -> dict[str, Any]:
    """Verifiziert die Authentifizierungs-Antwort.

    stored_public_key: base64url (aus DB). Returns {'new_sign_count': int, 'user_verified': bool}.
    Wirft bei ungültiger Antwort eine Exception.
    """
    cfg = get_rp_config()
    verified = verify_authentication_response(
        credential=credential_json if isinstance(credential_json, str) else json.dumps(credential_json),
        expected_challenge=expected_challenge,
        expected_rp_id=cfg['rp_id'],
        expected_origin=_expected_origin(),
        credential_public_key=base64url_to_bytes(stored_public_key),
        credential_current_sign_count=stored_sign_count,
        require_user_verification=False,
    )
    return {
        'new_sign_count': verified.new_sign_count,
        'user_verified': verified.user_verified,
    }


def extract_credential_id(credential_json: dict[str, Any] | str) -> str | None:
    """Liest die credential id (base64url) aus der Client-Antwort, um die DB-Credential zu finden."""
    try:
        data = json.loads(credential_json) if isinstance(credential_json, str) else credential_json
        return data.get('id') or data.get('rawId')
    except (json.JSONDecodeError, AttributeError):
        return None
