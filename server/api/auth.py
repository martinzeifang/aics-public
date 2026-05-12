"""Authentication API (#214 - Auth & RBAC).

JWT-basierte Authentifizierung mit User/Role/Permission-Management.
"""

from __future__ import annotations

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


def _check_rate_limit(client_ip: str) -> tuple[bool, str | None]:
    """Prüfe Login-Versuche Rate Limit."""
    attempts_dict = current_app.login_attempts
    now = datetime.now().timestamp()

    if client_ip in attempts_dict:
        count, timestamp = attempts_dict[client_ip]
        # Reset nach Zeitfenster
        if now - timestamp > LOGIN_ATTEMPT_WINDOW:
            attempts_dict[client_ip] = (1, now)
            return True, None
        # Zu viele Versuche
        if count >= MAX_LOGIN_ATTEMPTS:
            return False, 'Too many login attempts. Try again later.'
        # Inkrementiere Counter
        attempts_dict[client_ip] = (count + 1, timestamp)
    else:
        attempts_dict[client_ip] = (1, now)

    return True, None


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
              example: admin@example.com
            password:
              type: string
              format: password
              example: admin-password
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
    # Rate Limit Check
    client_ip = request.remote_addr or 'unknown'
    rate_ok, rate_error = _check_rate_limit(client_ip)
    if not rate_ok:
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
                if locked_for > 0:
                    return {
                        'error': f'Zu viele Fehlversuche. Account für {locked_for // 60} Min. gesperrt.',
                        'locked': True,
                    }, 423

    if not user:
        return {'error': 'Invalid email or password'}, 401

    # 2FA-Check (Phase 7.3): nur für lokale Accounts; LDAP-User haben kein totp-Feld
    if user.get('id') and not ldap_user_info:
        totp_state = get_totp_state(user['id'])
        if totp_state['enabled']:
            totp_code = str(data.get('totp_code', '')).strip()
            if not totp_code:
                # Zweistufiger Login: Challenge-Token mit kurzer Lebensdauer (5 min)
                challenge = create_access_token(
                    identity=user['id'],
                    additional_claims={'twofa_challenge': True, 'email': user['email']},
                    expires_delta=timedelta(minutes=5),
                )
                return jsonify({
                    'totp_required': True,
                    'challenge_token': challenge,
                }), 200

            # Code oder Backup-Code prüfen
            verified = totp_helper.verify_code(totp_state['secret'] or '', totp_code)
            if not verified:
                matched, remaining_hashes = totp_helper.consume_backup_code(
                    totp_state['backup_code_hashes'], totp_code,
                )
                if matched:
                    update_totp_backup_codes(user['id'], remaining_hashes)
                    verified = True
            if not verified:
                return {'error': 'Ungültiger Authenticator-Code'}, 401

    # Effektive Permissions aus Rollen + extra_permissions
    from server.models.permission import resolve_permissions, allowed_modules_for
    extra_perms = user.get('extra_permissions', []) or []
    permissions = resolve_permissions(user['roles'], extra_perms)
    allowed_modules = allowed_modules_for(
        user['roles'], extra_perms, user.get('allowed_modules'),
    )

    # Reset rate limit on successful login
    _reset_rate_limit(client_ip)

    # Token expiration from config (default: 24h)
    token_expires = os.getenv('JWT_EXPIRES_HOURS', '24')
    try:
        expires_hours = int(token_expires)
    except ValueError:
        expires_hours = 24

    access_token = create_access_token(
        identity=user['id'],  # PyJWT 2.10+: sub muss String sein
        additional_claims={
            'email': user['email'],
            'roles': user['roles'],
            'permissions': permissions,
            'extra_permissions': extra_perms,
            'allowed_modules': allowed_modules,
            'display_name': user.get('display_name', ''),
        },
        expires_delta=timedelta(hours=expires_hours),
    )

    return jsonify({
        'access_token': access_token,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'roles': user['roles'],
            'permissions': permissions,
            'extra_permissions': extra_perms,
            'allowed_modules': allowed_modules,
            'display_name': user.get('display_name', ''),
        }
    }), 200


@auth_bp.post('/login/verify-2fa')
def login_verify_2fa():
    """Zweiter Schritt des 2FA-Logins: tauscht Challenge-Token + Code → Access-Token.

    Body: { "challenge_token": "...", "code": "123456" }
    """
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
        return {'error': 'Code ungültig oder abgelaufen'}, 401

    update_last_login(user_id)

    from server.models.permission import resolve_permissions, allowed_modules_for
    extra_perms = user.get('extra_permissions', []) or []
    permissions = resolve_permissions(user['roles'], extra_perms)
    allowed_modules = allowed_modules_for(
        user['roles'], extra_perms, user.get('allowed_modules'),
    )

    token_expires = os.getenv('JWT_EXPIRES_HOURS', '24')
    try:
        expires_hours = int(token_expires)
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
        },
        expires_delta=timedelta(hours=expires_hours),
    )

    return jsonify({
        'access_token': access_token,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'roles': user['roles'],
            'permissions': permissions,
            'extra_permissions': extra_perms,
            'allowed_modules': allowed_modules,
            'display_name': user.get('display_name', ''),
        }
    }), 200


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
        pass

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
        pass

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


@auth_bp.get('/public-config')
def public_config():
    """#417: Frontend-Config, vor Login lesbar. Kein Auth — bewusst public.

    Liefert nur Boolean-Flags, keine sensitiven Daten.
    """
    return jsonify({
        'demo_users_enabled': os.getenv('ENABLE_DEMO_USERS', 'false').lower() in ('true', '1', 'yes'),
        'sso_enabled': False,  # noch nicht implementiert
        'env': 'production' if os.getenv('FLASK_ENV', '').lower() == 'production' else 'development',
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

    if not email or not re.match(EMAIL_REGEX, email):
        return jsonify(response_payload), 200

    user = get_user_by_email(email)
    if not user:
        return jsonify(response_payload), 200

    token = create_password_reset_token(user['id'], ttl_seconds=3600)
    log.warning('Password-Reset-Token für %s: /account/reset?token=%s', email, token)

    # In DEV-Modus den Token mit zurückgeben, damit man ohne SMTP testen kann
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

    return jsonify({'ok': True, 'user_id': user_id}), 200


@auth_bp.post('/refresh')
@jwt_required()
def refresh():
    """Refresh Access Token."""
    user_id = get_jwt_identity()
    claims = get_jwt()
    new_token = create_access_token(
        identity=user_id,
        additional_claims={
            'email': claims.get('email', ''),
            'roles': claims.get('roles', []),
            'permissions': claims.get('permissions', []),
            'extra_permissions': claims.get('extra_permissions', []),
            'allowed_modules': claims.get('allowed_modules'),
            'display_name': claims.get('display_name', ''),
        },
        expires_delta=timedelta(hours=24),
    )
    return jsonify({'access_token': new_token}), 200
