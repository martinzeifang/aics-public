"""Authentication API (#214 - Auth & RBAC).

JWT-basierte Authentifizierung mit User/Role/Permission-Management.
"""

from __future__ import annotations

import logging
import os
import re
import json
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from werkzeug.security import generate_password_hash, check_password_hash

from server.config.database import transaction
from server.models import RoleEnum, Permission, ROLE_PERMISSIONS
from server.auth import get_ldap_authenticator
from server.auth import totp as totp_helper
from server.auth.users_db import (
    ensure_db as users_ensure_db,
    get_user_by_email,
    get_user_by_id,
    verify_password,
    revoke_token,
    update_last_login,
    get_totp_state,
    update_totp_backup_codes,
    create_password_reset_token,
    consume_password_reset_token,
)

log = logging.getLogger(__name__)

EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
MIN_PASSWORD_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW = 300  # 5 minutes in seconds


auth_bp = Blueprint('auth', __name__)


# ─────────────────────────────────────────────────────────────────────────────
# Models (SQLAlchemy würde hier verwendet, für jetzt: Mocks)
# ─────────────────────────────────────────────────────────────────────────────

# Users werden jetzt aus users.sqlite geladen (siehe server/auth/users_db.py).
# Demo-Users werden nur angelegt wenn ENABLE_DEMO_USERS=true gesetzt ist.
users_ensure_db()


def build_login_response(user: dict) -> dict:
    """Erzeugt Access-Token + User-Payload für einen erfolgreich authentifizierten User.

    Gemeinsamer Helper für Passwort-Login, 2FA-Login und Passkey-Login (Sprint ε),
    damit Permission-Auflösung + Token-Claims an genau einer Stelle leben.
    """
    from server.models.permission import resolve_permissions, allowed_modules_for
    extra_perms = user.get('extra_permissions', []) or []
    permissions = resolve_permissions(user['roles'], extra_perms)
    allowed_modules = allowed_modules_for(
        user['roles'], extra_perms, user.get('allowed_modules'),
    )
    try:
        expires_hours = int(os.getenv('JWT_EXPIRES_HOURS', '24'))
    except ValueError:
        expires_hours = 24

    access_token = create_access_token(
        identity=user['id'],
        additional_claims={
            'email': user['email'],
            'roles': user['roles'],
            'permissions': permissions,
            'extra_permissions': extra_perms,
            'allowed_modules': allowed_modules,
            'display_name': user.get('display_name', ''),
            # #738 (AUTH-13): Token-Version für sofortige Revocation
            'tv': int(user.get('token_version', 0) or 0),
        },
        expires_delta=timedelta(hours=expires_hours),
    )
    # Sprint ε Phase D: MFA-Enforcement-Status anhängen (lockout-sicher — Flag,
    # kein Block; Frontend erzwingt Einrichtung nach Ablauf der Grace-Period).
    mfa: dict = {}
    try:
        from server.auth.mfa_policy import evaluate_enforcement
        mfa = evaluate_enforcement(user)
    except Exception:
        log.warning("MFA-Enforcement-Status konnte nicht ermittelt werden", exc_info=True)
        mfa = {}
    return {
        'access_token': access_token,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'roles': user['roles'],
            'permissions': permissions,
            'extra_permissions': extra_perms,
            'allowed_modules': allowed_modules,
            'display_name': user.get('display_name', ''),
        },
        'mfa': mfa,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


def _validate_email(email: str) -> tuple[bool, str | None]:
    """Validiere Email-Format."""
    if not email or len(email) > 254:
        return False, 'Invalid email format'
    if not re.match(EMAIL_REGEX, email):
        return False, 'Invalid email format'
    return True, None


def _validate_password(password: str) -> tuple[bool, str | None]:
    """Validiere Password."""
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return False, f'Password must be at least {MIN_PASSWORD_LENGTH} characters'
    return True, None


def _audit_auth(action: str, outcome: str = 'success', **details):
    """Semantisches Auth-Audit-Event (#739 / CFG-3). Darf den Flow nie blockieren."""
    try:
        from shared.audit import audit_event
        audit_event(action, module='auth', outcome=outcome, details=details)
    except Exception:
        # Audit-Schreibfehler dürfen den Auth-Flow nicht blockieren, aber NICHT
        # still verschluckt werden (Nachvollziehbarkeit/Compliance).
        log.exception("Auth-Audit-Event '%s' konnte nicht geschrieben werden", action)


def _check_rate_limit(client_ip: str) -> tuple[bool, str | None]:
    """Prüft (ohne zu zählen), ob die IP ihr Limit erreicht hat.

    #739 (AUTH-8): zählt NUR fehlgeschlagene Versuche (via _record_failed_attempt),
    nicht jeden Aufruf — erfolgreiche Logins erhöhen das Limit nicht.
    """
    attempts_dict = current_app.login_attempts
    now = datetime.now().timestamp()
    entry = attempts_dict.get(client_ip)
    if not entry:
        return True, None
    count, timestamp = entry
    if now - timestamp > LOGIN_ATTEMPT_WINDOW:
        attempts_dict.pop(client_ip, None)  # Fenster abgelaufen
        return True, None
    if count >= MAX_LOGIN_ATTEMPTS:
        return False, 'Too many attempts. Try again later.'
    return True, None


def _record_failed_attempt(client_ip: str):
    """Zählt einen fehlgeschlagenen Auth-/Reset-Versuch der IP (#739)."""
    attempts_dict = current_app.login_attempts
    now = datetime.now().timestamp()
    entry = attempts_dict.get(client_ip)
    if not entry or (now - entry[1] > LOGIN_ATTEMPT_WINDOW):
        attempts_dict[client_ip] = (1, now)
    else:
        attempts_dict[client_ip] = (entry[0] + 1, entry[1])


def _reset_rate_limit(client_ip: str):
    """Setze Rate Limit nach erfolgreichem Login zurück."""
    current_app.login_attempts.pop(client_ip, None)


@auth_bp.post('/login')
def login():
    """Benutzer-Login mit Email + Passwort
    ---
    tags:
      - auth
    security: []
    parameters:
      - in: body
        name: credentials
        required: true
        schema:
          type: object
          required: [email, password]
          properties:
            email:
              type: string
              format: email
            password:
              type: string
              format: password
    responses:
      200:
        description: Login erfolgreich
        schema:
          type: object
          properties:
            access_token:
              type: string
              description: JWT Bearer Token (24h gültig)
            user:
              type: object
              properties:
                id: {type: string}
                email: {type: string}
                roles: {type: array, items: {type: string}}
                permissions: {type: array, items: {type: string}}
      400:
        description: Validierungsfehler (Email/Passwort-Format)
      401:
        description: Ungültige Credentials
      429:
        description: Zu viele Login-Versuche
    """
    # #1474: Im SOC-Portal-Modus + vom Admin deaktiviert → Login sperren.
    # Die Suite-Instanz (kein AICS_PORTAL=soc) ist davon unberührt.
    if _portal_mode() == 'soc' and not _portal_enabled():
        return {'error': 'Das SOC-Operations-Portal ist derzeit deaktiviert.'}, 403

    # Rate Limit Check
    client_ip = request.remote_addr or 'unknown'
    rate_ok, rate_error = _check_rate_limit(client_ip)
    if not rate_ok:
        _audit_auth('auth.login', outcome='rate_limited', ip=client_ip)
        return {'error': rate_error}, 429

    data = request.get_json() or {}
    email = data.get('email', '').strip()
    password = data.get('password', '')

    valid_email, email_error = _validate_email(email)
    if not valid_email:
        return {'error': email_error}, 400

    valid_password, password_error = _validate_password(password)
    if not valid_password:
        return {'error': password_error}, 400

    # Try LDAP authentication first (if enabled)
    user = None
    ldap_user_info = None

    ldap_auth = get_ldap_authenticator()
    if ldap_auth:
        ldap_user_info = ldap_auth.authenticate(email, password)
        if ldap_user_info:
            # Map LDAP groups to roles
            group_mapping_json = os.getenv('LDAP_GROUP_MAPPING', '{}')
            try:
                group_mapping = json.loads(group_mapping_json)
            except json.JSONDecodeError:
                group_mapping = {}

            from server.auth.ldap import map_ldap_groups_to_roles
            roles = map_ldap_groups_to_roles(ldap_user_info.get('groups', []), group_mapping)
            if not roles:
                roles = ['cra_viewer']  # Default role

            ldap_user_info['roles'] = roles
            user = ldap_user_info

    # Fallback to local authentication (SQLite users.sqlite)
    if not user:
        local_user = get_user_by_email(email)
        if local_user:
            # Account-Lockout-Check (Phase 6.2)
            from server.auth.users_db import is_account_locked, record_failed_login
            locked, remaining = is_account_locked(local_user['id'])
            if locked:
                minutes = max(1, remaining // 60)
                _audit_auth('auth.login', outcome='locked', ip=client_ip,
                            user_id=local_user['id'])
                return {
                    'error': f'Account gesperrt. Bitte in {minutes} Min. erneut versuchen oder Admin kontaktieren.',
                    'locked': True,
                    'retry_after_seconds': remaining,
                }, 423  # 423 Locked
            if verify_password(local_user, password):
                user = local_user
                update_last_login(local_user['id'])
            else:
                # Failed-Login-Counter erhöhen
                count, locked_for = record_failed_login(local_user['id'])
                _record_failed_attempt(client_ip)
                if locked_for > 0:
                    _audit_auth('auth.login', outcome='locked', ip=client_ip,
                                user_id=local_user['id'], reason='too_many_failures')
                    return {
                        'error': f'Zu viele Fehlversuche. Account für {locked_for // 60} Min. gesperrt.',
                        'locked': True,
                    }, 423

    if not user:
        # #1177: E-Mail eines Fehlversuchs maskiert ablegen (kein PII-Volltext im Audit).
        from shared.redaction import mask_email
        _audit_auth('auth.login', outcome='fail', ip=client_ip, email=mask_email(email))
        _record_failed_attempt(client_ip)
        return {'error': 'Invalid email or password'}, 401

    # 2FA-Check (Phase 7.3): nur für lokale Accounts; LDAP-User haben kein totp-Feld
    if user.get('id') and not ldap_user_info:
        totp_state = get_totp_state(user['id'])
        # #738 (AUTH-4): MFA ist aktiv, wenn TOTP aktiviert ODER mind. ein Passkey
        # registriert ist. Passkey-only-MFA wurde bislang beim Passwort-Login
        # übersprungen (Bypass) — jetzt wird in beiden Fällen ein 2. Faktor verlangt.
        from server.auth.users_db import count_webauthn_credentials
        passkey_count = count_webauthn_credentials(user['id'])
        mfa_active = totp_state['enabled'] or passkey_count > 0
        if mfa_active:
            totp_code = str(data.get('totp_code', '')).strip()
            # TOTP-Erstfaktor-Pfad nur, wenn TOTP aktiv UND Code mitgeliefert.
            if totp_state['enabled'] and totp_code:
                verified = totp_helper.verify_code(totp_state['secret'] or '', totp_code)
                if not verified:
                    matched, remaining_hashes = totp_helper.consume_backup_code(
                        totp_state['backup_code_hashes'], totp_code,
                    )
                    if matched:
                        update_totp_backup_codes(user['id'], remaining_hashes)
                        verified = True
                if not verified:
                    _audit_auth('auth.login', outcome='fail', ip=client_ip,
                                user_id=user['id'], reason='totp_invalid')
                    _record_failed_attempt(client_ip)
                    return {'error': 'Ungültiger Authenticator-Code'}, 401
            else:
                # Kein gültiger TOTP-Erstfaktor → 2. Faktor zwingend via Challenge.
                # Passkey-only-User MÜSSEN den WebAuthn-2FA-Flow durchlaufen.
                challenge = create_access_token(
                    identity=user['id'],
                    additional_claims={'twofa_challenge': True, 'email': user['email']},
                    expires_delta=timedelta(minutes=5),
                )
                methods = (['totp'] if totp_state['enabled'] else []) + \
                          (['passkey'] if passkey_count > 0 else [])
                return jsonify({
                    'totp_required': True,
                    'mfa_required': True,
                    'challenge_token': challenge,
                    'methods': methods,
                }), 200

    # Reset rate limit on successful login
    _reset_rate_limit(client_ip)
    _audit_auth('auth.login', outcome='success', ip=client_ip, user_id=user.get('id'))

    return jsonify(build_login_response(user)), 200


@auth_bp.post('/login/verify-2fa')
def login_verify_2fa():
    """Zweiter Schritt des 2FA-Logins: tauscht Challenge-Token + Code → Access-Token.

    Body: { "challenge_token": "...", "code": "123456" }
    """
    # #739 (AUTH-8): Rate-Limit auch auf die 2FA-Verifikation (Brute-Force des
    # 6-stelligen Codes verhindern).
    client_ip = request.remote_addr or 'unknown'
    rate_ok, rate_error = _check_rate_limit(client_ip)
    if not rate_ok:
        _audit_auth('auth.2fa_verify', outcome='rate_limited', ip=client_ip)
        return {'error': rate_error}, 429

    data = request.get_json() or {}
    challenge = str(data.get('challenge_token', '')).strip()
    code = str(data.get('code', '')).strip()

    if not challenge or not code:
        return {'error': 'challenge_token und code erforderlich'}, 400

    # Challenge-Token validieren (handled by flask_jwt_extended via header normally —
    # hier dekodieren wir manuell, da es im Body kommt)
    from flask_jwt_extended import decode_token
    try:
        decoded = decode_token(challenge)
    except Exception:
        log.warning("2FA-Challenge-Token ungültig oder abgelaufen", exc_info=True)
        return {'error': 'Challenge-Token ungültig oder abgelaufen'}, 401

    if not decoded.get('twofa_challenge'):
        return {'error': 'Falscher Token-Typ'}, 401

    user_id = decoded.get('sub')
    user = get_user_by_id(user_id) if user_id else None
    if not user:
        return {'error': 'User nicht gefunden'}, 404

    totp_state = get_totp_state(user_id)
    if not totp_state['enabled']:
        return {'error': '2FA ist nicht aktiviert'}, 400

    verified = totp_helper.verify_code(totp_state['secret'] or '', code)
    if not verified:
        matched, remaining_hashes = totp_helper.consume_backup_code(
            totp_state['backup_code_hashes'], code,
        )
        if matched:
            update_totp_backup_codes(user_id, remaining_hashes)
            verified = True
    if not verified:
        _audit_auth('auth.2fa_verify', outcome='fail', ip=client_ip, user_id=user_id)
        _record_failed_attempt(client_ip)
        return {'error': 'Code ungültig oder abgelaufen'}, 401

    update_last_login(user_id)
    _reset_rate_limit(client_ip)
    _audit_auth('auth.2fa_verify', outcome='success', ip=client_ip, user_id=user_id)
    return jsonify(build_login_response(user)), 200


@auth_bp.get('/profile')
@jwt_required()
def get_profile():
    """Aktueller User mit Rollen und Permissions
    ---
    tags:
      - auth
    security:
      - Bearer: []
    responses:
      200:
        description: User-Profil
        schema:
          type: object
          properties:
            id: {type: string}
            email: {type: string}
            roles: {type: array, items: {type: string}}
            permissions: {type: array, items: {type: string}}
      401:
        description: Token fehlt oder ungültig (z.B. revoked)
    """
    user_id = get_jwt_identity()
    claims = get_jwt()
    # Issue #388: globaler Modul-Deaktivierungs-Filter aus app config
    disabled_modules: list[str] = []
    try:
        from ai_compliance_suite.config import load_config
        cfg = load_config()
        disabled_modules = list((cfg.get('modules') or {}).get('disabled') or [])
    except Exception:
        log.warning("Modul-Deaktivierungs-Filter konnte nicht geladen werden", exc_info=True)

    # Modul-Whitelist aus Lizenz (#370 + #413)
    # license_modules ist IMMER eine Liste (nie None), damit das Frontend
    # eindeutig filtern kann:
    #   - leere Liste []        → keine Lizenz aktiv → keine Module
    #   - ['*']                  → Wildcard → alle außer Gutachten (Frontend-Regel)
    #   - explizite Liste        → genau diese Module
    license_state: dict = {}
    license_modules: list[str] = []
    try:
        from server import license_state as _ls
        st = _ls.get_state()
        license_state = st.to_dict()
        if st.state in ('ok', 'demo') and st.modules:
            license_modules = list(st.modules)
    except Exception:
        log.warning("Lizenz-Modul-Whitelist konnte nicht geladen werden", exc_info=True)

    return jsonify({
        'id': user_id,
        'email': claims.get('email', ''),
        'roles': claims.get('roles', []),
        'permissions': claims.get('permissions', []),
        'extra_permissions': claims.get('extra_permissions', []),
        'allowed_modules': claims.get('allowed_modules'),
        'display_name': claims.get('display_name', ''),
        'disabled_modules': disabled_modules,
        'license_modules': license_modules,
        'license_state': license_state,
    }), 200


@auth_bp.post('/logout')
@jwt_required()
def logout():
    """Logout — Token in Blacklist
    ---
    tags:
      - auth
    security:
      - Bearer: []
    responses:
      200:
        description: Logout erfolgreich
        schema:
          type: object
          properties:
            message: {type: string}
    """
    jwt_data = get_jwt()
    jti = jwt_data.get('jti', '')
    expires_at = int(jwt_data.get('exp', 0))
    user_id = get_jwt_identity() or ''
    revoke_token(jti, user_id=user_id if isinstance(user_id, str) else '', expires_at=expires_at)
    return jsonify({'message': 'Successfully logged out'}), 200


def _portal_mode() -> str:
    """#1411: 'soc' wenn die Instanz als SOC-Operations-Portal läuft, sonst 'suite'."""
    return 'soc' if os.getenv('AICS_PORTAL', '').strip().lower() == 'soc' else 'suite'


def _portal_enabled() -> bool:
    """#1474: Admin-Schalter (config soc_portal.enabled, Default True)."""
    try:
        from ai_compliance_suite.config import load_config
        return bool((load_config().get('soc_portal') or {}).get('enabled', True))
    except Exception:
        return True


@auth_bp.get('/public-config')
def public_config():
    """#417: Frontend-Config, vor Login lesbar. Kein Auth — bewusst public.

    Liefert nur Boolean-Flags, keine sensitiven Daten.
    """
    demo_enabled = os.getenv('ENABLE_DEMO_USERS', 'false').lower() in ('true', '1', 'yes')
    # Demo-User aktiv ⇒ per Definition Testumgebung. Dann nie 'production' melden,
    # auch wenn FLASK_ENV=production gesetzt ist (z.B. im Docker-Test-Stack) — sonst
    # zeigt der Login fälschlich "Produktiv-System" statt "Test-Umgebung".
    is_production = (os.getenv('FLASK_ENV', '').lower() == 'production') and not demo_enabled
    # #1410/#1474: SOC-Operations-Portal-Modus + Admin-Schalter fürs Frontend-Gating.
    portal = _portal_mode()
    return jsonify({
        'demo_users_enabled': demo_enabled,
        'sso_enabled': False,  # noch nicht implementiert
        'env': 'production' if is_production else 'development',
        'portal': portal,
        'portal_name': 'SOC Operation Center' if portal == 'soc' else 'AI Compliance Suite',
        'portal_modules': ['soc'] if portal == 'soc' else [],
        'portal_enabled': _portal_enabled() if portal == 'soc' else True,
    }), 200


@auth_bp.post('/password/forgot')
def password_forgot():
    """Self-Service Reset-Anforderung (#407 Option A).

    Liefert immer 200 mit der gleichen Meldung (Enumeration-Schutz). Wenn die
    E-Mail existiert wird intern ein Single-Use-Token erzeugt. Solange kein
    SMTP konfiguriert ist, wird der Reset-Link im app.log + im Response für
    DEV-Modus ausgegeben (nur wenn ENABLE_DEMO_USERS=true).
    """
    import logging
    data = request.get_json(silent=True) or {}
    email = str(data.get('email') or '').strip().lower()
    log = logging.getLogger(__name__)

    response_payload = {
        'ok': True,
        'message': 'Falls die E-Mail existiert, wurde ein Reset-Link versendet.',
    }

    # #739 (AUTH-11): Rate-Limit gegen Token-Generierungs-/Enumeration-Spam.
    # Antwort bleibt einheitlich 200 (Enumeration-Schutz) — bei Überschreitung 429.
    client_ip = request.remote_addr or 'unknown'
    rate_ok, rate_error = _check_rate_limit(client_ip)
    if not rate_ok:
        _audit_auth('auth.password_reset_requested', outcome='rate_limited', ip=client_ip)
        return {'error': rate_error}, 429
    # Jeder Aufruf zählt (Volumen-Drosselung, unabhängig ob E-Mail existiert).
    _record_failed_attempt(client_ip)

    if not email or not re.match(EMAIL_REGEX, email):
        return jsonify(response_payload), 200

    user = get_user_by_email(email)
    if not user:
        return jsonify(response_payload), 200

    token = create_password_reset_token(user['id'], ttl_seconds=3600)
    # #737: Reset-Token ist ein Authentifizierungs-Geheimnis → NIEMALS ins Log
    # (Log-Leser könnten beliebige Accounts übernehmen). Nur Event auditieren.
    try:
        from shared.audit import audit_event
        audit_event('auth.password_reset_requested', module='auth',
                    details={'user_id': user['id']})
    except Exception:
        log.exception("Audit-Event 'auth.password_reset_requested' konnte nicht geschrieben werden")

    # Nur im DEV-/Demo-Modus den Token zurückgeben, damit man ohne SMTP testen kann
    if os.getenv('ENABLE_DEMO_USERS', 'false').lower() in ('true', '1', 'yes'):
        response_payload['reset_url'] = f'/account/reset?token={token}'

    return jsonify(response_payload), 200


@auth_bp.post('/password/reset')
def password_reset():
    """Single-Use-Token einlösen und neues Passwort setzen."""
    from server.auth.password_policy import validate_password as _validate_pw, PasswordPolicyError

    data = request.get_json(silent=True) or {}
    token = str(data.get('token') or '')
    new_pw = str(data.get('new_password') or '')

    if not token or not new_pw:
        return jsonify({'error': 'token + new_password erforderlich'}), 400

    try:
        _validate_pw(new_pw)
    except PasswordPolicyError as e:
        return jsonify({'error': str(e)}), 400

    ok, user_id, err = consume_password_reset_token(token, new_pw)
    if not ok:
        return jsonify({'error': err or 'Token ungültig'}), 400

    # #1182: bestehende Sessions invalidieren (Token-Version erhöhen) + auditieren —
    # nach erfolgreichem Reset dürfen alte JWTs nicht weitergelten.
    try:
        from server.auth.users_db import bump_token_version
        bump_token_version(user_id)
    except Exception:  # noqa: BLE001 — Reset selbst ist erfolgt; Logging unten
        current_app.logger.exception('bump_token_version nach Passwort-Reset fehlgeschlagen')
    try:
        from shared.audit import audit_event
        audit_event('auth.password_reset', module='auth',
                    details={'user_id': user_id, 'sessions_invalidated': True})
    except Exception:  # noqa: BLE001
        pass

    return jsonify({'ok': True, 'user_id': user_id}), 200


@auth_bp.post('/refresh')
@jwt_required()
def refresh():
    """Refresh Access Token.

    #738 (AUTH-6): Rechte/Status werden aus der DB NEU geladen (nicht aus den
    alten Claims kopiert) — entzogene Rechte/deaktivierte Accounts greifen sofort.
    Ablauf respektiert JWT_EXPIRES_HOURS (kein hartkodiertes 24h).
    """
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    if not user or not int(user.get('active', 1) or 0):
        return {'error': 'Account nicht aktiv'}, 401
    return jsonify(build_login_response(user)), 200
