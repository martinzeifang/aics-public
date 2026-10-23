"""WebAuthn / Passkey-API — Sprint ε.

Phase B (#708): Registrierung + Verwaltung für eingeloggte User.
Phase C (#709): Login-Flow (passwortlos + 2. Faktor) — ergänzt hier.

Endpoints unter /api/auth/webauthn:
  POST   /register/options   (jwt) — Optionen für navigator.credentials.create
  POST   /register/verify    (jwt) — speichert neue Passkey-Credential
  GET    /credentials        (jwt) — Liste der Passkeys des Users
  PATCH  /credentials/<id>   (jwt) — Nickname ändern
  DELETE /credentials/<id>   (jwt) — Passkey entfernen
"""

from __future__ import annotations

import os
import time

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import require_permission
from server.auth import webauthn as wa
from server.auth.users_db import (
    add_webauthn_credential,
    consume_webauthn_challenge,
    delete_webauthn_credential,
    get_user_by_id,
    get_webauthn_credential_by_cred_id,
    list_webauthn_credentials,
    rename_webauthn_credential,
    store_webauthn_challenge,
    update_last_login,
    update_webauthn_sign_count,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

from shared.audit import audit_event

webauthn_bp = Blueprint('webauthn', __name__)


def _audit(action: str, outcome: str = 'success', **details):
    """Semantisches Audit-Event für Passkey-Aktionen (Sprint ε Phase E)."""
    try:
        audit_event(action, module='auth.webauthn', outcome=outcome, details=details)
    except Exception:
        pass  # Audit darf den Auth-Flow nie blockieren


# Rate-Limiting für unauthentifizierte WebAuthn-Login-Endpoints (Sprint ε Phase E).
# In-Process pro Client-IP — analog zu auth.py. Schützt vor Challenge-Flooding +
# Credential-Enumeration-Brute-Force.
_WEBAUTHN_RL_WINDOW = 300   # 5 min
_WEBAUTHN_RL_MAX = 20       # Versuche pro Fenster


def _client_ip() -> str:
    # #739 (AUTH-3): remote_addr wird durch ProxyFix (TRUSTED_PROXY_COUNT) aus
    # X-Forwarded-For auf die echte Client-IP gesetzt. Den rohen, vom Client
    # fälschbaren XFF-Header NICHT mehr direkt verwenden (war Limit-Bypass).
    return request.remote_addr or 'unknown'


def _rate_limited() -> bool:
    """True, wenn die aktuelle Client-IP ihr Limit überschritten hat."""
    store = getattr(current_app, '_webauthn_attempts', None)
    if store is None:
        store = {}
        current_app._webauthn_attempts = store
    ip = _client_ip()
    now = time.time()
    count, ts = store.get(ip, (0, now))
    if now - ts > _WEBAUTHN_RL_WINDOW:
        store[ip] = (1, now)
        return False
    if count >= _WEBAUTHN_RL_MAX:
        return True
    store[ip] = (count + 1, ts)
    return False


def _rp_guard():
    """Prüft, ob die RP-ID für Passkeys taugt. Returns Fehler-Response oder None.

    WebAuthn verbietet IP-Adressen als RP-ID. Bei IP-Zugriff (häufig: Aufruf über
    https://<IP>:port) eine klare Meldung statt der kryptischen Browser-Fehlermeldung
    'rp.id cannot be used with the current origin'.
    """
    cfg = wa.get_rp_config()
    rp_id = cfg['rp_id']
    if wa.host_is_ip(rp_id):
        return ({'error': (
            f"Passkeys benötigen einen Hostnamen — der Zugriff über die IP-Adresse "
            f"'{rp_id}' wird von WebAuthn nicht unterstützt. Bitte die Anwendung über "
            f"einen Hostnamen aufrufen (z.B. aics.intern.local per DNS/hosts) und ggf. "
            f"unter Einstellungen → Passkey/WebAuthn die RP-ID setzen."
        )}, 400)
    return None


@webauthn_bp.get('/debug')
@require_permission('admin:config')
def webauthn_debug():
    """Diagnose: effektive RP-Konfiguration + empfangene Request-Header.

    Macht Reverse-Proxy-Probleme sofort sichtbar (welche RP-ID wird genutzt,
    kommt der Origin-Header an, was steht in X-Forwarded-Host).

    #746-Härtung: nur mit admin:config-Permission erreichbar und in
    FLASK_ENV=production komplett deaktiviert (Endpoint exponiert interne
    Konfig + Request-Header → unnötige Angriffsfläche in Produktion).
    """
    if os.getenv('FLASK_ENV', '').lower() == 'production':
        return {'error': 'Debug-Endpoint in Produktion deaktiviert'}, 404
    cfg = wa.get_rp_config()
    return jsonify({
        'effective_rp_id': cfg['rp_id'],
        'effective_origins': cfg['origins'],
        'rp_id_is_ip': wa.host_is_ip(cfg['rp_id']),
        'settings_configured': bool(wa._settings_rp_config()),
        'request_headers': {
            'Origin': request.headers.get('Origin'),
            'Host': request.host,
            'X-Forwarded-Host': request.headers.get('X-Forwarded-Host'),
            'X-Forwarded-Proto': request.headers.get('X-Forwarded-Proto'),
        },
    }), 200


def _serialize_credential(c: dict) -> dict:
    """Public-Key nicht nach außen geben — nur Metadaten."""
    return {
        'id': c['id'],
        'nickname': c['nickname'] or '(unbenannt)',
        'transports': c['transports'],
        'aaguid': c['aaguid'],
        'backup_state': c['backup_state'],
        'created_at': c['created_at'],
        'last_used_at': c['last_used_at'],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Registrierung (eingeloggt)
# ─────────────────────────────────────────────────────────────────────────────


@webauthn_bp.post('/register/options')
@jwt_required()
def register_options():
    """Erzeugt Registrierungs-Options + legt Challenge ab.

    Returns: { "challenge_id": "...", "options": { ... PublicKeyCredentialCreationOptions } }
    """
    guard = _rp_guard()
    if guard:
        return guard
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    if not user:
        return {'error': 'User not found'}, 404

    # #1183: Step-up — Passkey-Registrierung erfordert Re-Auth (Passwort/TOTP).
    from server.auth.stepup import step_up_or_403
    blocked = step_up_or_403(user_id, request.get_json(silent=True) or {})
    if blocked:
        return blocked

    existing = list_webauthn_credentials(user_id)
    options_json, challenge = wa.build_registration_options(
        user_id=user_id,
        user_email=user['email'],
        user_display_name=user.get('display_name', '') or user['email'],
        existing_credentials=existing,
    )
    challenge_id = store_webauthn_challenge(
        bytes_to_base64url(challenge), 'register', user_id=user_id,
    )
    import json as _json
    return jsonify({'challenge_id': challenge_id, 'options': _json.loads(options_json)}), 200


@webauthn_bp.post('/register/verify')
@jwt_required()
def register_verify():
    """Verifiziert die Authenticator-Antwort und speichert die Credential.

    Body: { "challenge_id": "...", "credential": { ... }, "nickname": "..." }
    """
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    challenge_id = data.get('challenge_id', '')
    credential = data.get('credential')
    nickname = str(data.get('nickname', '')).strip()[:120]

    if not challenge_id or not credential:
        return {'error': 'challenge_id und credential sind erforderlich'}, 400

    stored = consume_webauthn_challenge(challenge_id, 'register')
    if not stored or stored.get('user_id') != user_id:
        return {'error': 'Challenge ungültig oder abgelaufen'}, 400

    from webauthn.helpers import base64url_to_bytes
    try:
        result = wa.verify_registration(
            credential, base64url_to_bytes(stored['challenge']),
        )
    except Exception as e:
        return {'error': f'Registrierung fehlgeschlagen: {e}'}, 400

    # Duplikat-Schutz
    if get_webauthn_credential_by_cred_id(result['credential_id']):
        return {'error': 'Dieser Passkey ist bereits registriert'}, 409

    add_webauthn_credential(
        user_id=user_id,
        credential_id=result['credential_id'],
        public_key=result['public_key'],
        sign_count=result['sign_count'],
        transports=credential.get('response', {}).get('transports') if isinstance(credential, dict) else None,
        aaguid=result['aaguid'],
        nickname=nickname or 'Passkey',
        backup_eligible=result['backup_eligible'],
        backup_state=result['backup_state'],
    )
    _audit('passkey.registered', user_id=user_id, aaguid=result['aaguid'])
    return jsonify({'registered': True}), 201


# ─────────────────────────────────────────────────────────────────────────────
# Verwaltung
# ─────────────────────────────────────────────────────────────────────────────


@webauthn_bp.get('/credentials')
@jwt_required()
def credentials_list():
    user_id = get_jwt_identity()
    creds = list_webauthn_credentials(user_id)
    return jsonify({'credentials': [_serialize_credential(c) for c in creds]}), 200


@webauthn_bp.patch('/credentials/<int:cred_db_id>')
@jwt_required()
def credentials_rename(cred_db_id: int):
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    nickname = str(data.get('nickname', '')).strip()
    if not nickname:
        return {'error': 'nickname erforderlich'}, 400
    if not rename_webauthn_credential(cred_db_id, user_id, nickname):
        return {'error': 'Passkey nicht gefunden'}, 404
    return jsonify({'renamed': True}), 200


@webauthn_bp.delete('/credentials/<int:cred_db_id>')
@jwt_required()
def credentials_delete(cred_db_id: int):
    user_id = get_jwt_identity()

    # #1183: Lockout-Schutz — den letzten verbleibenden Anmeldefaktor nicht löschen.
    from server.auth.users_db import get_totp_state
    user = get_user_by_id(user_id)
    creds = list_webauthn_credentials(user_id)
    has_pw = bool(user and user.get('password_hash'))
    has_totp = bool(get_totp_state(user_id).get('enabled'))
    if len(creds) <= 1 and not has_pw and not has_totp:
        return {'error': 'Letzter Anmeldefaktor — das Löschen würde den Account aussperren. '
                'Bitte zuerst ein Passwort setzen oder TOTP aktivieren.'}, 409

    # #1183: Step-up — Passkey-Löschung erfordert Re-Auth (Passwort/TOTP).
    from server.auth.stepup import step_up_or_403
    blocked = step_up_or_403(user_id, request.get_json(silent=True) or {})
    if blocked:
        return blocked

    if not delete_webauthn_credential(cred_db_id, user_id):
        return {'error': 'Passkey nicht gefunden'}, 404
    _audit('passkey.deleted', user_id=user_id, credential_db_id=cred_db_id)
    return jsonify({'deleted': True}), 200


# ─────────────────────────────────────────────────────────────────────────────
# Phase C — Login-Flow (passwortlos + 2. Faktor)
# ─────────────────────────────────────────────────────────────────────────────


def _verify_and_issue(credential: dict, expected_challenge_b64: str, *,
                      restrict_user_id: str | None = None):
    """Gemeinsame Verifikation: findet Credential, prüft Signatur + sign_count,
    aktualisiert sign_count und gibt den zugehörigen User zurück.

    restrict_user_id: wenn gesetzt (2-Faktor-Pfad), muss die Credential diesem
    User gehören. Returns (user_dict, error_tuple|None).
    """
    cred_id = wa.extract_credential_id(credential)
    if not cred_id:
        return None, ({'error': 'Credential ohne id'}, 400)
    stored = get_webauthn_credential_by_cred_id(cred_id)
    if not stored:
        return None, ({'error': 'Passkey nicht registriert'}, 401)
    if restrict_user_id and stored['user_id'] != restrict_user_id:
        return None, ({'error': 'Passkey gehört nicht zu diesem Konto'}, 401)

    try:
        result = wa.verify_authentication(
            credential,
            base64url_to_bytes(expected_challenge_b64),
            stored['public_key'],
            stored['sign_count'],
        )
    except Exception as e:
        return None, ({'error': f'Authentifizierung fehlgeschlagen: {e}'}, 401)

    # Replay-Schutz: neuer sign_count muss > gespeichertem sein (außer beide 0).
    new_count = result['new_sign_count']
    if stored['sign_count'] != 0 and new_count != 0 and new_count <= stored['sign_count']:
        return None, ({'error': 'Sicherheitswarnung: möglicher Replay (sign_count)'}, 401)
    update_webauthn_sign_count(cred_id, new_count)

    user = get_user_by_id(stored['user_id'])
    if not user:
        return None, ({'error': 'User nicht gefunden'}, 404)
    return user, None


@webauthn_bp.post('/login/options')
def login_options():
    """Passwortloser Login — discoverable credentials (kein Session, kein Email).

    Returns: { "challenge_id": "...", "options": {...} }
    """
    if _rate_limited():
        return {'error': 'Zu viele Versuche. Bitte später erneut.'}, 429
    guard = _rp_guard()
    if guard:
        return guard
    options_json, challenge = wa.build_authentication_options()
    challenge_id = store_webauthn_challenge(
        bytes_to_base64url(challenge), 'authenticate', user_id=None,
    )
    import json as _json
    return jsonify({'challenge_id': challenge_id, 'options': _json.loads(options_json)}), 200


@webauthn_bp.post('/login/verify')
def login_verify():
    """Passwortloser Login — verifiziert Assertion, liefert Access-Token.

    Body: { "challenge_id": "...", "credential": {...} }
    """
    if _rate_limited():
        return {'error': 'Zu viele Versuche. Bitte später erneut.'}, 429
    data = request.get_json() or {}
    challenge_id = data.get('challenge_id', '')
    credential = data.get('credential')
    if not challenge_id or not credential:
        return {'error': 'challenge_id und credential erforderlich'}, 400

    stored = consume_webauthn_challenge(challenge_id, 'authenticate')
    if not stored:
        return {'error': 'Challenge ungültig oder abgelaufen'}, 400

    user, err = _verify_and_issue(credential, stored['challenge'])
    if err:
        _audit('passkey.login', outcome='fail', mode='passwordless')
        return err[0], err[1]

    update_last_login(user['id'])
    _audit('passkey.login', user_id=user['id'], mode='passwordless')
    from server.api.auth import build_login_response
    return jsonify(build_login_response(user)), 200


@webauthn_bp.post('/login/2fa-options')
def login_2fa_options():
    """Passkey als 2. Faktor — Options für einen bereits per Passwort
    identifizierten User (Challenge-Token aus dem Passwort-Schritt).

    Body: { "challenge_token": "<twofa_challenge JWT>" }
    """
    if _rate_limited():
        return {'error': 'Zu viele Versuche. Bitte später erneut.'}, 429
    data = request.get_json() or {}
    challenge_token = str(data.get('challenge_token', '')).strip()
    if not challenge_token:
        return {'error': 'challenge_token erforderlich'}, 400

    from flask_jwt_extended import decode_token
    try:
        decoded = decode_token(challenge_token)
    except Exception:
        return {'error': 'Challenge-Token ungültig oder abgelaufen'}, 401
    if not decoded.get('twofa_challenge'):
        return {'error': 'Falscher Token-Typ'}, 401

    user_id = decoded.get('sub')
    creds = list_webauthn_credentials(user_id) if user_id else []
    if not creds:
        return {'error': 'Keine Passkeys für dieses Konto'}, 400

    options_json, challenge = wa.build_authentication_options(allow_credentials=creds)
    challenge_id = store_webauthn_challenge(
        bytes_to_base64url(challenge), 'authenticate', user_id=user_id,
    )
    import json as _json
    return jsonify({'challenge_id': challenge_id, 'options': _json.loads(options_json)}), 200


@webauthn_bp.post('/login/2fa-verify')
def login_2fa_verify():
    """Passkey als 2. Faktor — verifiziert Assertion gegen die Credentials des
    durch den Challenge-Token identifizierten Users, liefert Access-Token.

    Body: { "challenge_token": "...", "challenge_id": "...", "credential": {...} }
    """
    if _rate_limited():
        return {'error': 'Zu viele Versuche. Bitte später erneut.'}, 429
    data = request.get_json() or {}
    challenge_token = str(data.get('challenge_token', '')).strip()
    challenge_id = data.get('challenge_id', '')
    credential = data.get('credential')
    if not challenge_token or not challenge_id or not credential:
        return {'error': 'challenge_token, challenge_id und credential erforderlich'}, 400

    from flask_jwt_extended import decode_token
    try:
        decoded = decode_token(challenge_token)
    except Exception:
        return {'error': 'Challenge-Token ungültig oder abgelaufen'}, 401
    if not decoded.get('twofa_challenge'):
        return {'error': 'Falscher Token-Typ'}, 401
    user_id = decoded.get('sub')

    stored = consume_webauthn_challenge(challenge_id, 'authenticate')
    if not stored or stored.get('user_id') != user_id:
        return {'error': 'Challenge ungültig oder abgelaufen'}, 400

    user, err = _verify_and_issue(credential, stored['challenge'], restrict_user_id=user_id)
    if err:
        _audit('passkey.login', outcome='fail', mode='2fa', user_id=user_id)
        return err[0], err[1]

    update_last_login(user['id'])
    _audit('passkey.login', user_id=user['id'], mode='2fa')
    from server.api.auth import build_login_response
    return jsonify(build_login_response(user)), 200
