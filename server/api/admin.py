"""Admin REST API - User Management, Settings, Audit, DB-Viewer, Backup."""

from flask import current_app, Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from pathlib import Path
from contextlib import closing
import json
import zipfile
import shutil
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from server.models.permission import require_permission
from ai_compliance_suite.config import load_config, save_config, DEFAULT_CONFIG_PATH
from shared import db as _sdb

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

DB_DIR = Path('data/db')
BACKUP_DIR = Path('out/backup')
AUDIT_DB = DB_DIR / 'audit.sqlite'

# Whitelist for DB-Viewer to prevent path traversal
ALLOWED_DBS = {
    'firmen': 'firmen.sqlite',
    'cra': 'cra.sqlite',
    'risikobewertung': 'risikobewertung.sqlite',
    'nis2': 'nis2.sqlite',
    'dsgvo': 'dsgvo.sqlite',
    'aiact': 'ai_act.sqlite',
    'gutachten': 'gutachten.sqlite',
    'soc': 'soc.sqlite',
    'compliance': 'compliance.sqlite',
    'audit': 'audit.sqlite',
    'evidence': 'evidence.sqlite',
    'users': 'users.sqlite',
}


def _serialize_user(u: dict) -> dict:
    """User-Dict → API-Response (ohne password_hash)."""
    from server.models.permission import resolve_permissions, allowed_modules_for
    roles = u.get('roles') or []
    extra = u.get('extra_permissions') or []
    return {
        'id': u.get('id'),
        'email': u.get('email'),
        'display_name': u.get('display_name', ''),
        'roles': roles,
        'extra_permissions': extra,
        'allowed_modules': u.get('allowed_modules'),
        'effective_permissions': resolve_permissions(roles, extra),
        'effective_modules': allowed_modules_for(roles, extra, u.get('allowed_modules')),
        'active': bool(u.get('active', 1)),
        'created_at': u.get('created_at'),
        'updated_at': u.get('updated_at'),
        'last_login': u.get('last_login'),
    }


@admin_bp.get('/users')
@require_permission('admin:users')
def get_users():
    """Liste alle Benutzer (echte DB-Daten)."""
    from server.auth.users_db import list_users
    users = list_users()
    return [_serialize_user(u) for u in users], 200


@admin_bp.get('/users/<user_id>')
@require_permission('admin:users')
def get_user(user_id: str):
    from server.auth.users_db import get_user_by_id
    u = get_user_by_id(user_id)
    if not u:
        return {'error': 'User not found'}, 404
    return _serialize_user(u), 200


@admin_bp.post('/users')
@require_permission('admin:users')
def create_user():
    """Erstelle einen neuen Benutzer."""
    from server.auth.users_db import create_user as db_create_user, get_user_by_email
    from server.auth.password_policy import validate_password, PasswordPolicyError
    data = request.json or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    if not email or not password:
        return {'error': 'Email und Passwort sind Pflicht'}, 400
    try:
        validate_password(password, email=email)
    except PasswordPolicyError as e:
        return {'error': str(e)}, 400
    if get_user_by_email(email):
        return {'error': 'E-Mail existiert bereits'}, 409

    roles = data.get('roles') or []
    if isinstance(roles, str):
        roles = [r.strip() for r in roles.split(',') if r.strip()]

    # Issue #393 (C1b-1): Named-User-Lizenz-Check.
    # Admin-Accounts werden NICHT gegen das Limit gezählt.
    if 'admin' not in roles:
        try:
            from server import license_state as _ls
            from server.auth.users_db import list_users as _list
            st = _ls.get_state()
            if st.max_users > 0:
                active_non_admin = sum(
                    1 for u in _list()
                    if u.get('active') and 'admin' not in (u.get('roles') or [])
                )
                if active_non_admin >= st.max_users:
                    return {
                        'error': 'license-user-limit',
                        'message': (
                            f'Lizenz erlaubt max. {st.max_users} Named-User '
                            f'(aktuell aktiv: {active_non_admin}). Admin-Konten '
                            'zählen NICHT zum Limit.'
                        ),
                        'max_users': st.max_users,
                        'active_users': active_non_admin,
                    }, 423
        except Exception:
            pass

    user = db_create_user(
        email=email,
        password=password,
        roles=roles,
        allowed_modules=data.get('allowed_modules'),
        extra_permissions=data.get('extra_permissions') or [],
        display_name=data.get('display_name') or '',
    )
    return _serialize_user(user), 201


@admin_bp.put('/users/<user_id>')
@require_permission('admin:users')
def update_user(user_id: str):
    """Update einen Benutzer."""
    from server.auth.users_db import update_user as db_update_user, get_user_by_id
    if not get_user_by_id(user_id):
        return {'error': 'User not found'}, 404
    data = request.json or {}

    # 'allowed_modules' in payload kann None bedeuten "alle erlauben (Whitelist entfernen)"
    kwargs = {}
    if 'email' in data:
        kwargs['email'] = data['email']
    if 'password' in data and data['password']:
        from server.auth.password_policy import validate_password, PasswordPolicyError
        try:
            validate_password(data['password'], email=data.get('email', ''))
        except PasswordPolicyError as e:
            return {'error': str(e)}, 400
        kwargs['password'] = data['password']
    if 'roles' in data:
        kwargs['roles'] = data['roles']
    if 'allowed_modules' in data:
        kwargs['allowed_modules'] = data['allowed_modules']  # None erlaubt
    if 'extra_permissions' in data:
        kwargs['extra_permissions'] = data['extra_permissions']
    if 'display_name' in data:
        kwargs['display_name'] = data['display_name']
    if 'active' in data:
        kwargs['active'] = bool(data['active'])

    db_update_user(user_id, **kwargs)
    # #738 (AUTH-13): Bei Rechte-/Status-Änderung bestehende Tokens invalidieren,
    # damit Rollenentzug/Deaktivierung sofort greift (nicht erst nach Ablauf).
    if any(k in kwargs for k in ('roles', 'allowed_modules', 'extra_permissions', 'active', 'password')):
        from server.auth.users_db import bump_token_version
        bump_token_version(user_id)
    u = get_user_by_id(user_id)
    return _serialize_user(u), 200


@admin_bp.delete('/users/<user_id>')
@require_permission('admin:users')
def delete_user(user_id: str):
    """Lösche einen Benutzer."""
    from server.auth.users_db import delete_user as db_delete_user
    ok = db_delete_user(user_id)
    return {'id': user_id, 'deleted': ok}, (200 if ok else 404)


@admin_bp.post('/users/<user_id>/disable')
@require_permission('admin:users')
def disable_user(user_id: str):
    from server.auth.users_db import update_user as db_update_user, bump_token_version
    db_update_user(user_id, active=False)
    bump_token_version(user_id)  # #738 (AUTH-13): bestehende Tokens sofort ungültig
    return {'id': user_id, 'active': False}, 200


@admin_bp.post('/users/<user_id>/unlock')
@require_permission('admin:users')
def unlock_user_account(user_id: str):
    """Account-Sperre aufheben (Phase 6.2 Lockout)."""
    from server.auth.users_db import unlock_account
    ok = unlock_account(user_id)
    return {'id': user_id, 'unlocked': ok}, (200 if ok else 404)


@admin_bp.get('/password-policy')
@require_permission('admin:users')
def get_password_policy_endpoint():
    """Liefert aktuelle Password-Policy für UI-Anzeige."""
    from server.auth.password_policy import get_policy
    return get_policy(), 200


@admin_bp.get('/webauthn-config')
@require_permission('admin:config')
def get_webauthn_config_endpoint():
    """Liefert die aktuelle Passkey/WebAuthn-RP-Konfiguration (über Web pflegbar).

    Liefert die effektiven Werte (Settings > ENV > Default) plus die Quelle,
    damit das UI anzeigen kann, ob ENV/Default greift.
    """
    from server.auth.webauthn import get_rp_config, _settings_rp_config
    eff = get_rp_config()
    raw = _settings_rp_config()
    return {
        'rp_id': eff['rp_id'],
        'rp_name': eff['rp_name'],
        'rp_origin': ','.join(eff['origins']),
        'from_settings': bool(raw),
    }, 200


@admin_bp.put('/webauthn-config')
@require_permission('admin:config')
def update_webauthn_config_endpoint():
    """Setzt die Passkey/WebAuthn-RP-Konfiguration über die Weboberfläche.

    Body: { "rp_id": "aics.intern.local", "rp_name": "...", "rp_origin": "https://..." }
    Validierung: rp_id darf keine IP/kein Schema/Port sein.
    """
    from server.auth.webauthn import save_rp_config
    data = request.get_json(silent=True) or {}
    rp_id = (data.get('rp_id') or '').strip()
    rp_origin = (data.get('rp_origin') or '').strip()

    import re as _re
    if rp_id:
        if '://' in rp_id or ':' in rp_id or '/' in rp_id:
            return {'error': 'RP-ID ohne Schema/Port/Pfad angeben (z.B. aics.intern.local)'}, 400
        if _re.fullmatch(r'\d{1,3}(\.\d{1,3}){3}', rp_id):
            return {'error': 'RP-ID darf keine IP-Adresse sein — Hostname verwenden'}, 400
    if rp_origin and not rp_origin.startswith(('https://', 'http://localhost')):
        return {'error': 'Origin muss mit https:// beginnen (Ausnahme: http://localhost)'}, 400

    # Härtung #729: rp_id MUSS ein registrierbares Suffix des Origin-Hostnamens sein
    # (verhindert den Vorfall rp_id='compliancesuite' bei Origin
    # 'compliancesuite.c99781.intern' → 'rp.id cannot be used with the current origin').
    if rp_id and rp_origin:
        from urllib.parse import urlparse
        origin_host = (urlparse(rp_origin).hostname or '').lower().strip('.')
        rid = rp_id.lower().strip('.')
        if origin_host and not (origin_host == rid or origin_host.endswith('.' + rid)):
            return {'error': (
                f"RP-ID '{rp_id}' passt nicht zum Origin-Host '{origin_host}'. "
                f"Die RP-ID muss der vollständige Hostname oder ein registrierbares "
                f"Suffix sein (z.B. '{origin_host}' oder die übergeordnete Domain)."
            )}, 400

    try:
        saved = save_rp_config(rp_id, data.get('rp_name', ''), rp_origin)
        try:
            from shared.audit import audit_event
            audit_event('webauthn.config.changed', module='auth.admin',
                        details={'rp_id': saved['rp_id'], 'rp_origin': saved['rp_origin']})
        except Exception:
            pass
        return {'updated': True, 'config': saved}, 200
    except Exception as e:
        current_app.logger.exception('update_webauthn_config: %s', e)
        return {'error': str(e)}, 500


@admin_bp.get('/mfa-policy')
@require_permission('admin:config')
def get_mfa_policy_endpoint():
    """Liefert die aktuelle MFA-Policy (Sprint ε Phase D)."""
    from server.auth.mfa_policy import get_policy
    return get_policy(), 200


@admin_bp.put('/mfa-policy')
@require_permission('admin:config')
def update_mfa_policy_endpoint():
    """Setzt die MFA-Policy.

    Body: { "mode": "optional|required_all|required_roles",
            "required_roles": [...], "grace_days": int }
    """
    from server.auth.mfa_policy import save_policy
    data = request.get_json(silent=True) or {}
    try:
        policy = save_policy(
            mode=data.get('mode', 'optional'),
            required_roles=data.get('required_roles', []),
            grace_days=int(data.get('grace_days', 7)),
        )
        try:
            from shared.audit import audit_event
            audit_event('mfa.policy.changed', module='auth.admin',
                        details={'mode': policy['mode'],
                                 'required_roles': policy['required_roles'],
                                 'grace_days': policy['grace_days']})
        except Exception:
            pass
        return {'updated': True, 'policy': policy}, 200
    except ValueError as e:
        return {'error': str(e)}, 400
    except Exception as e:
        current_app.logger.exception('update_mfa_policy: %s', e)
        return {'error': str(e)}, 500


@admin_bp.get('/permissions/catalog')
@require_permission('admin:users')
def permissions_catalog():
    """Liefert Module + Permissions + Rollen für UI-Auswahl."""
    from server.models.permission import (
        MODULES, MODULE_PERMISSIONS, RoleEnum, ROLE_PERMISSIONS,
    )

    module_labels = {
        'firmen': 'Firmen',
        'risikobewertung': 'Risikobewertung',
        'cra': 'CRA – Cyber Resilience Act',
        'nis2': 'NIS2',
        'dora': 'DORA',
        'aiact': 'AI Act',
        'dsgvo': 'DSGVO',
        'gutachten': 'Gutachten',
        'wiba': 'WiBA',
        'soc': 'SOC – Security Operations Center',
    }
    perm_labels = {
        ':read': 'Lesen',
        ':write': 'Bearbeiten',
        ':export': 'Export',
        ':prefill': 'Prefill (KI-Vorbefüllung)',
        ':issue_link': 'Issue-Verknüpfung',
        ':frameworks': 'Framework-Bibliothek',
        ':catalog': 'Katalog (Download/Ingest)',
        ':triage': 'Triage (Alarm-Status)',
        ':incident': 'Incidents & Meldetracks',
        ':config': 'Verbindung/Einrichtung',
    }

    def _label(perm_value: str) -> str:
        suffix = ':' + perm_value.split(':', 1)[1]
        return perm_labels.get(suffix, perm_value)

    modules = []
    for mid in MODULES:
        modules.append({
            'id': mid,
            'label': module_labels.get(mid, mid),
            'permissions': [
                {'value': p.value, 'label': _label(p.value)}
                for p in MODULE_PERMISSIONS.get(mid, [])
            ],
        })

    roles = []
    for r in RoleEnum:
        roles.append({
            'value': r.value,
            'permissions': [p.value for p in ROLE_PERMISSIONS.get(r, [])],
        })

    admin_perms = [
        {'value': 'admin:users',  'label': 'Benutzerverwaltung'},
        {'value': 'admin:roles',  'label': 'Rollen verwalten'},
        {'value': 'admin:audit',  'label': 'Audit-Log einsehen'},
        {'value': 'admin:config', 'label': 'Konfiguration / Framework-Bibliothek'},
    ]

    return {
        'modules': modules,
        'roles': roles,
        'admin_permissions': admin_perms,
    }, 200


@admin_bp.post('/users/<user_id>/enable')
@require_permission('admin:users')
def enable_user(user_id: str):
    """Aktiviere einen Benutzer."""
    return {
        'id': user_id,
        'active': True,
        'updated': True
    }, 200


# ============================================================
# F0b — Settings (KI-Provider, Module, Backup, Appearance, Auth)
# ============================================================

@admin_bp.get('/settings')
@require_permission('admin:config')
def get_settings():
    """Globale Settings holen (Desktop-config-kompatibel)."""
    try:
        cfg = load_config()
        # Sensitive Felder maskieren
        cfg = _mask_sensitive(cfg)
        return cfg, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@admin_bp.put('/settings')
@require_permission('admin:config')
def update_settings():
    """Globale Settings aktualisieren.

    #416: vorher überschrieb das die ganze Config — inkl. maskierter
    Tokens ('***'). Jetzt:
      1. Bestehende Config laden
      2. Sensitive Felder mit Wert '***' aus dem Request entfernen
         (User hat sie nicht editiert; sie wurden nur maskiert ausgeliefert)
      3. Tiefen-Merge: Request-Daten überschreiben nur was sie explizit setzen
    """
    import logging as _logging
    _log = _logging.getLogger(__name__)
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return {'error': 'Body must be a JSON object'}, 400

        # Cloud-Egress nur wenn explizit erlaubt
        ai = data.get('ai', {})
        if ai.get('provider') == 'cloud':
            cloud = ai.get('cloud', {})
            if not cloud.get('allow_data_egress'):
                return {'error': 'Cloud-Provider braucht allow_data_egress=true'}, 400
            # #741 (SSRF): Cloud-Base-URL gegen Provider-Allowlist (nur HTTPS,
            # bekannte Hosts) — verhindert Exfiltration an beliebige Endpoints.
            cloud_url = str(cloud.get('base_url') or '').strip()
            if cloud_url:
                from shared.net_validation import enforce_cloud_llm_base_url
                try:
                    enforce_cloud_llm_base_url(cloud_url, context='settings.ai.cloud')
                except ValueError as e:
                    return {'error': str(e)}, 400

        # Härtung #730: auth.* (Passkey/WebAuthn, MFA-Policy) wird AUSSCHLIESSLICH
        # über die dedizierten Endpoints /webauthn-config und /mfa-policy verwaltet.
        # Aus dem allgemeinen Settings-Save entfernen, damit ein veralteter
        # Client-Stand diese Werte nicht überschreibt (Clobbering).
        data.pop('auth', None)

        # 'Maskierungs-Müll' aus dem Request entfernen — sonst werden echte
        # Werte mit '***' überschrieben.
        _strip_masked(data)
        # Defensive (#416 reopen #2): bekannte sensitive Felder mit LEEREM Wert
        # auch entfernen — Client darf einen frisch gesetzten Token nicht durch
        # einen veralteten leeren Wert überschreiben.
        _strip_empty_sensitive(data)
        # Response-only Felder (z.B. token_set, token_masked, source) aus
        # geschicktem Body entfernen — sie haben in der Persistenz nichts verloren.
        _strip_response_only(data)

        # Tiefen-Merge gegen bestehende Config
        from copy import deepcopy
        existing = deepcopy(load_config())
        merged = _deep_merge(existing, data)
        _encrypt_github_token_in_place(merged)  # #1174

        _log.info(
            'update_settings: keys=%s github.token_kept=%s',
            list(data.keys()),
            bool((existing.get('integrations') or {}).get('github', {}).get('token')) and
            ((merged.get('integrations') or {}).get('github', {}).get('token') ==
             (existing.get('integrations') or {}).get('github', {}).get('token')),
        )
        save_config(merged)
        return {'updated': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


def _encrypt_github_token_in_place(cfg: Dict[str, Any]) -> None:
    """#1174: GitHub-PAT vor der Persistenz at-rest verschlüsseln.

    Idempotent — bereits verschlüsselte Werte (AICSFLD1-Prefix) bleiben
    unangetastet, leere Werte werden nicht verschlüsselt.
    """
    gh = (cfg.get('integrations') or {}).get('github') or {}
    tok = str(gh.get('token') or '').strip()
    if not tok:
        return
    try:
        from shared.crypto_at_rest import encrypt_field, is_encrypted_field
        if not is_encrypted_field(tok):
            cfg['integrations']['github']['token'] = encrypt_field(tok)
    except Exception:
        current_app.logger.warning('GitHub-Token konnte nicht verschlüsselt werden (#1174)')


def _strip_masked(d: Any) -> None:
    """Entfernt Felder mit Wert '***' rekursiv (vom _mask_sensitive maskiert).

    Damit überschreibt ein Frontend, das das ganze Settings-Object zurückschickt,
    KEINE sensitiven Felder mehr — sondern lässt sie unverändert.
    """
    if isinstance(d, dict):
        for k in list(d.keys()):
            if d[k] == '***':
                del d[k]
            elif isinstance(d[k], (dict, list)):
                _strip_masked(d[k])
    elif isinstance(d, list):
        for item in d:
            _strip_masked(item)


# Bekannte sensitive Pfade (dotted) — leere Strings werden nicht persistiert.
# Damit ein veraltetes "" aus dem Frontend-Form niemals einen frisch gesetzten
# Token überschreibt (#416 reopen #2).
_SENSITIVE_PATHS = {
    'integrations.github.token',
    'auth.password_hash',
    'ai.cloud.api_key',
}

# Reine Response-Felder, die niemals persistiert werden dürfen.
_RESPONSE_ONLY_FIELDS = {
    'integrations.github.token_set',
    'integrations.github.token_masked',
    'integrations.github.source',
}


def _walk_path(d: Any, dotted: str):
    """Yields (parent_dict, last_key) for every match of dotted path."""
    parts = dotted.split('.')
    def _go(cur: Any, idx: int):
        if idx == len(parts) - 1:
            if isinstance(cur, dict) and parts[idx] in cur:
                yield cur, parts[idx]
            return
        if isinstance(cur, dict) and parts[idx] in cur:
            yield from _go(cur[parts[idx]], idx + 1)
    yield from _go(d, 0)


def _strip_empty_sensitive(d: Any) -> None:
    for path in _SENSITIVE_PATHS:
        for parent, key in list(_walk_path(d, path)):
            v = parent.get(key)
            if v == '' or v is None:
                del parent[key]


def _strip_response_only(d: Any) -> None:
    for path in _RESPONSE_ONLY_FIELDS:
        for parent, key in list(_walk_path(d, path)):
            del parent[key]


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Rekursives Merge: overlay-Werte überschreiben, Listen werden ersetzt."""
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _mask_sensitive(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Maskiert sensitive Felder für Read-Endpoint.

    #416: ALLE bekannten Token-Felder werden IMMER mit '***' ersetzt — auch wenn
    leer. Sonst sendet der Client beim Save ein leeres Token zurück, das den
    serverseitig frisch gespeicherten Token überschreibt (kein '***' = wird
    nicht durch _strip_masked entfernt).
    """
    out = json.loads(json.dumps(cfg))  # deep copy
    auth = out.get('auth', {})
    if 'password_hash' in auth:
        auth['password_hash'] = '***'
    # GitHub-Token: IMMER maskieren, damit der Client niemals echte Werte zurückspielt
    out.setdefault('integrations', {}).setdefault('github', {})
    gh = out['integrations']['github']
    gh['token_set'] = bool(gh.get('token'))
    gh['token'] = '***'  # immer maskieren — auch wenn leer
    return out


# ============================================================
# GitHub-Integration (Settings + Verbindungstest)
# ============================================================

@admin_bp.get('/github')
@require_permission('admin:config')
def github_get():
    """Liefert (maskiert) Token-Status + Username + Default-Repo + source."""
    from shared.github_config import get_github_config
    gc = get_github_config()
    return {
        'token_set': bool(gc.token),
        'token_masked': (gc.token[:4] + '…' + gc.token[-4:]) if gc.token else '',
        'username': gc.username,
        'default_repo': gc.default_repo,
        'source': gc.source,
    }, 200


@admin_bp.put('/github')
@require_permission('admin:config')
def github_set():
    """Speichert GitHub-Konfig in der globalen Suite-Config.

    Body: { token: str, username?: str, default_repo?: str }
    Leerer token = Token löschen.
    """
    import logging as _logging
    _log = _logging.getLogger(__name__)

    data = request.get_json(silent=True) or {}
    token = str(data.get('token') or '').strip()
    username = str(data.get('username') or '').strip()
    default_repo = str(data.get('default_repo') or '').strip()

    # Diagnose: jeden PUT mit Token-Länge protokollieren (nicht den Token selbst!)
    _log.info(
        'github_set: token_in_body=%s token_len=%d username=%r repo=%r',
        'token' in data, len(token), username, default_repo,
    )

    # Sanity-Check: ein realer GH-Token ist mindestens 20 Zeichen lang
    if 'token' in data and token and len(token) < 20:
        _log.warning('github_set: rejected token of suspicious length %d', len(token))
        return {
            'error': 'token-too-short',
            'message': f'Token ist nur {len(token)} Zeichen — Browser-Autofill? '
                       'GitHub-Tokens sind 40+ Zeichen (classic) bzw. 80+ (fine-grained).',
        }, 400

    cfg = load_config()
    cfg.setdefault('integrations', {}).setdefault('github', {})
    if 'token' in data:
        cfg['integrations']['github']['token'] = token
    cfg['integrations']['github']['username'] = username
    cfg['integrations']['github']['default_repo'] = default_repo
    _encrypt_github_token_in_place(cfg)  # #1174: PAT at-rest verschlüsseln
    save_config(cfg)
    _log.info('github_set: gespeichert token_set=%s', bool(token))
    return {'saved': True, 'token_set': bool(token), 'token_len': len(token)}, 200


@admin_bp.get('/ollama/models')
@require_permission('admin:config')
def ollama_models():
    """Listet installierte Modelle vom Ollama-Server + kuratierte Empfehlungen."""
    import requests
    from shared.ollama_config import get_ollama_config

    override_url = request.args.get('base_url', '').strip()
    oc = get_ollama_config()
    base_url = (override_url or oc.base_url).rstrip('/')

    installed: list[Dict[str, Any]] = []
    error = None
    try:
        r = requests.get(f'{base_url}/api/tags', timeout=5)
        if r.status_code == 200:
            for m in (r.json().get('models') or []):
                installed.append({
                    'name': m.get('name', ''),
                    'size_bytes': m.get('size', 0),
                    'modified_at': m.get('modified_at'),
                    'family': (m.get('details') or {}).get('family', ''),
                    'parameter_size': (m.get('details') or {}).get('parameter_size', ''),
                })
        else:
            error = f'HTTP {r.status_code}'
    except Exception as e:
        error = f'{type(e).__name__}: {e}'

    # Kuratierte Empfehlungen — nach RAM-Bedarf sortiert
    recommendations = [
        {'tag': 'llama3.2:1b', 'size_gb': 1.3, 'desc': 'Sehr schnell, gut für leichte Tasks (≥ 2 GB RAM)'},
        {'tag': 'qwen2.5:3b', 'size_gb': 2.0, 'desc': 'Gute Balance Speed/Qualität (≥ 4 GB RAM)'},
        {'tag': 'phi3.5:3.8b', 'size_gb': 2.3, 'desc': 'Microsoft Phi-3.5, kompakt + stark (≥ 4 GB RAM)'},
        {'tag': 'mistral:7b', 'size_gb': 4.1, 'desc': 'Mistral 7B — allround (≥ 8 GB RAM)'},
        {'tag': 'llama3.1:8b', 'size_gb': 4.7, 'desc': 'Meta Llama 3.1 8B — Standard (≥ 8 GB RAM)'},
        {'tag': 'qwen2.5:7b', 'size_gb': 4.4, 'desc': 'Qwen 2.5 7B — sehr stark im Reasoning (≥ 8 GB RAM)'},
        {'tag': 'llama3.1:70b', 'size_gb': 40.0, 'desc': 'Großes Modell — nur mit ≥ 64 GB RAM oder GPU'},
    ]

    return {
        'base_url': base_url,
        'installed': installed,
        'recommendations': recommendations,
        'error': error,
    }, 200


@admin_bp.get('/ollama/diagnose')
@require_permission('admin:config')
def ollama_diagnose():
    """Diagnose-Suite für Ollama-Konfiguration.

    Query-Args (optional, überschreiben gespeicherte Config für Test-vor-Speichern):
      - base_url
      - model
      - timeout_s (default 10)
      - gen_timeout (default 60)

    Returns: { config, checks: [{name, ok, detail, meta}] }
    """
    import time
    import requests
    from shared.ollama_config import get_ollama_config

    override_url = request.args.get('base_url', '').strip()
    override_model = request.args.get('model', '').strip()
    timeout_s = int(request.args.get('timeout_s', '10'))
    gen_timeout = int(request.args.get('gen_timeout', '60'))

    oc = get_ollama_config()
    base_url = (override_url or oc.base_url).rstrip('/')
    model = override_model or oc.model

    out: Dict[str, Any] = {
        'config': {
            'base_url': base_url, 'model': model,
            'source': oc.source, 'override': bool(override_url or override_model),
        },
        'checks': [],
    }

    def add(name: str, ok: bool, detail: str = '', meta: Dict[str, Any] | None = None):
        out['checks'].append({'name': name, 'ok': ok, 'detail': detail, 'meta': meta or {}})

    # 1. URL-Format
    if not base_url:
        add('Konfiguration: Base-URL', False, 'Keine Base-URL gesetzt.')
        return out, 200
    if not base_url.startswith(('http://', 'https://')):
        add('Konfiguration: Base-URL', False, f'Ungültige URL (http/https erwartet): {base_url}')
        return out, 200
    add('Konfiguration: Base-URL', True, base_url)

    # 2. Modell konfiguriert
    if model:
        add('Konfiguration: Modell', True, model)
    else:
        add('Konfiguration: Modell', False, 'Kein Modell konfiguriert')

    # 3. TCP/HTTP-Erreichbarkeit
    t0 = time.monotonic()
    try:
        r = requests.get(f'{base_url}/', timeout=timeout_s)
        lat = int((time.monotonic() - t0) * 1000)
        ok = r.status_code < 500
        add('Netzwerk: Erreichbarkeit', ok,
            f'HTTP {r.status_code} in {lat} ms',
            {'latency_ms': lat, 'http_status': r.status_code})
    except requests.exceptions.ConnectionError as e:
        add('Netzwerk: Erreichbarkeit', False,
            f'Verbindung verweigert / Host nicht erreichbar — Ollama läuft? ({e.__class__.__name__})',
            {'error_type': 'connection-refused'})
        return out, 200
    except requests.exceptions.Timeout:
        add('Netzwerk: Erreichbarkeit', False,
            f'Timeout nach {timeout_s}s', {'error_type': 'timeout'})
        return out, 200
    except Exception as e:
        add('Netzwerk: Erreichbarkeit', False, f'{type(e).__name__}: {e}')
        return out, 200

    # 4. /api/tags → installierte Modelle
    t0 = time.monotonic()
    installed: list[str] = []
    try:
        r = requests.get(f'{base_url}/api/tags', timeout=timeout_s)
        if r.status_code == 200:
            data = r.json()
            installed = [m.get('name', '') for m in (data.get('models') or [])]
            lat = int((time.monotonic() - t0) * 1000)
            add('API: /api/tags', True,
                f'{len(installed)} Modelle installiert ({lat} ms)',
                {'models': installed, 'latency_ms': lat})
        else:
            add('API: /api/tags', False,
                f'HTTP {r.status_code} — Ollama-API antwortet nicht wie erwartet')
            return out, 200
    except Exception as e:
        add('API: /api/tags', False, f'{type(e).__name__}: {e}')
        return out, 200

    def _exact(installed_name: str, requested: str) -> bool:
        return (installed_name == requested
                or installed_name.startswith(requested + ':'))

    def _family(installed_name: str, requested: str) -> bool:
        return installed_name.split(':')[0] == requested.split(':')[0]

    # 5. Modell installiert? (exact vs family-match)
    effective_model = None
    if model:
        exact_hit = next((m for m in installed if _exact(m, model)), None)
        family_hit = next((m for m in installed if _family(m, model)), None) if not exact_hit else None
        if exact_hit:
            effective_model = exact_hit
            add('Modell verfügbar', True, f'{model} ist installiert',
                {'installed': installed, 'effective_model': exact_hit})
        elif family_hit:
            # Family-Match: anderer Tag derselben Modell-Familie
            effective_model = family_hit
            add('Modell verfügbar', False,
                f'Exakt {model} fehlt, aber {family_hit} (gleiche Familie) ist da. '
                f'Generation-Test nutzt {family_hit}. Empfehlung: in Config auf {family_hit} '
                f'umstellen ODER mit "ollama pull {model}" exakt installieren.',
                {'installed': installed, 'effective_model': family_hit,
                 'install_hint': f'ollama pull {model}'})
        else:
            add('Modell verfügbar', False,
                f'{model} fehlt. Vorhanden: {", ".join(installed[:5]) or "(keine)"}',
                {'installed': installed, 'install_hint': f'ollama pull {model}'})

    # 6. Test-Generation — nutzt den effektiv installierten Tag
    if effective_model:
        test_model = effective_model
        t0 = time.monotonic()
        try:
            r = requests.post(
                f'{base_url}/api/generate',
                json={
                    'model': test_model,
                    'prompt': 'Antworte nur mit dem Wort "OK". Nichts anderes.',
                    'stream': False,
                    'options': {'temperature': 0.0, 'num_predict': 10},
                },
                timeout=gen_timeout,
            )
            lat = int((time.monotonic() - t0) * 1000)
            if r.status_code == 200:
                data = r.json()
                response_text = (data.get('response') or '').strip()
                eval_count = int(data.get('eval_count') or 0)
                eval_dur_ns = int(data.get('eval_duration') or 0)
                tokens_per_s = (eval_count * 1e9 / eval_dur_ns) if eval_dur_ns else 0
                add('Generation-Test', True,
                    f'Antwort von {test_model}: "{response_text[:60]}" — {lat} ms, ~{tokens_per_s:.1f} Token/s',
                    {'latency_ms': lat, 'response': response_text,
                     'tokens_per_second': round(tokens_per_s, 1),
                     'eval_count': eval_count, 'total_duration_ns': data.get('total_duration'),
                     'tested_model': test_model})
            else:
                add('Generation-Test', False,
                    f'HTTP {r.status_code}: {r.text[:200]}')
        except requests.exceptions.Timeout:
            add('Generation-Test', False,
                f'Timeout nach {gen_timeout}s. Erstes Laden eines Modells dauert oft mehrere Minuten.')
        except Exception as e:
            add('Generation-Test', False, f'{type(e).__name__}: {e}')

    return out, 200


@admin_bp.post('/ollama/echo-test')
@require_permission('admin:config')
def ollama_echo_test():
    """Live-Streaming-"Hello World"-Test: schickt einen Mini-Prompt an Ollama
    und streamt die Antwort tokenweise. Zeigt im UI sofort, ob das Modell
    überhaupt antwortet (vs. hängt). Mit Time-To-First-Token (TTFT) und
    Token/s-Messung.

    Body: { base_url?, model?, prompt? }
    """
    import json as _json
    import time as _time
    import urllib.request as _ur
    import urllib.error as _ue
    from flask import Response, stream_with_context
    from shared.ollama_config import get_ollama_config

    data = request.get_json(silent=True) or {}
    oc = get_ollama_config()
    base_url = (str(data.get('base_url') or '').strip() or oc.base_url).rstrip('/')
    model = str(data.get('model') or '').strip() or oc.model
    prompt = (str(data.get('prompt') or '').strip()
              or 'Sag "Hello, World!" und nichts anderes.')

    @stream_with_context
    def _gen():
        def _ev(name, payload):
            return f'event: {name}\ndata: {_json.dumps(payload, ensure_ascii=False)}\n\n'

        yield _ev('status', {'message': f'Verbinde mit {base_url} (Modell {model}) …'})
        t_start = _time.monotonic()
        try:
            req = _ur.Request(
                base_url + '/api/generate',
                data=_json.dumps({
                    'model': model, 'prompt': prompt, 'stream': True,
                    'options': {'temperature': 0.0, 'num_predict': 60},
                }).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            yield _ev('status', {'message': 'Sende Anfrage …'})
            chunks = []
            first_token_at = None
            with _ur.urlopen(req, timeout=oc.timeout_s) as resp:
                yield _ev('status', {'message': 'Warte auf erstes Token …'})
                for raw_line in resp:
                    line = raw_line.decode('utf-8', errors='replace').strip()
                    if not line:
                        continue
                    try:
                        obj = _json.loads(line)
                    except Exception:
                        continue
                    chunk = obj.get('response', '')
                    if chunk:
                        if first_token_at is None:
                            first_token_at = _time.monotonic() - t_start
                            yield _ev('first-token', {'ttft_ms': int(first_token_at * 1000)})
                        chunks.append(chunk)
                        yield _ev('chunk', {'text': chunk})
                    if obj.get('done'):
                        total_dur = _time.monotonic() - t_start
                        eval_count = int(obj.get('eval_count') or 0)
                        eval_dur_ns = int(obj.get('eval_duration') or 0)
                        tok_per_s = (eval_count * 1e9 / eval_dur_ns) if eval_dur_ns else 0
                        yield _ev('done', {
                            'ok': True,
                            'response': ''.join(chunks),
                            'eval_count': eval_count,
                            'tokens_per_second': round(tok_per_s, 1),
                            'total_duration_ms': int(total_dur * 1000),
                            'ttft_ms': int((first_token_at or 0) * 1000),
                            'model': model, 'base_url': base_url,
                        })
                        return
            yield _ev('done', {
                'ok': True,
                'response': ''.join(chunks),
                'total_duration_ms': int((_time.monotonic() - t_start) * 1000),
            })
        except _ue.HTTPError as e:
            try:
                body = e.read().decode('utf-8', errors='replace')
            except Exception:
                body = ''
            yield _ev('done', {
                'ok': False,
                'error': f'HTTP {e.code} {e.reason}: {body[:300]}',
                'base_url': base_url, 'model': model,
            })
        except OSError as e:
            yield _ev('done', {
                'ok': False,
                'error': f'Verbindung fehlgeschlagen: {e}',
                'base_url': base_url, 'model': model,
            })
        except Exception as e:
            yield _ev('done', {'ok': False, 'error': f'{type(e).__name__}: {e}'})

    return Response(_gen(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
    })


@admin_bp.post('/ollama/pull')
@require_permission('admin:config')
def ollama_pull():
    """Streamt einen Pull als SSE — vermeidet nginx-504-Timeouts bei großen
    Modellen (10–60 min möglich).

    Body: { "model": "llama3.1:8b" }
    Events: status, progress {completed, total, percent}, done {ok, error?}.
    """
    import json as _json
    import requests as _requests
    from flask import Response, stream_with_context
    from shared.ollama_config import get_ollama_config

    data = request.get_json(silent=True) or {}
    model = str(data.get('model') or '').strip()
    if not model:
        return {'error': 'model fehlt'}, 400

    oc = get_ollama_config()
    url = f'{oc.base_url.rstrip("/")}/api/pull'

    @stream_with_context
    def _gen():
        def _ev(name, payload):
            return f'event: {name}\ndata: {_json.dumps(payload, ensure_ascii=False)}\n\n'

        yield _ev('status', {'message': f'Starte pull für {model} …'})
        try:
            # Stream=True bei Ollama → newline-delimited JSON mit Progress
            with _requests.post(url, json={'model': model, 'stream': True},
                                stream=True, timeout=(10, None)) as r:
                if r.status_code != 200:
                    yield _ev('done', {'ok': False, 'error': f'HTTP {r.status_code}: {r.text[:200]}'})
                    return
                last_pct = -1
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        obj = _json.loads(line)
                    except Exception:
                        continue
                    status_msg = obj.get('status') or ''
                    completed = int(obj.get('completed') or 0)
                    total = int(obj.get('total') or 0)
                    if total > 0:
                        pct = int(completed * 100 / total)
                        if pct != last_pct:
                            last_pct = pct
                            yield _ev('progress', {
                                'status': status_msg,
                                'completed': completed, 'total': total, 'percent': pct,
                            })
                    elif status_msg:
                        yield _ev('status', {'message': status_msg})
                yield _ev('done', {'ok': True, 'model': model})
        except _requests.exceptions.ConnectionError as e:
            yield _ev('done', {'ok': False, 'error': f'Ollama nicht erreichbar: {e}'})
        except Exception as e:
            yield _ev('done', {'ok': False, 'error': f'{type(e).__name__}: {e}'})

    return Response(_gen(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',  # nginx: kein Buffering
    })


@admin_bp.delete('/ollama/models/<path:model>')
@require_permission('admin:config')
def ollama_delete_model(model: str):
    """Löscht ein installiertes Ollama-Modell (#401)."""
    import requests as _requests
    from shared.ollama_config import get_ollama_config

    oc = get_ollama_config()
    url = f'{oc.base_url.rstrip("/")}/api/delete'
    try:
        r = _requests.delete(url, json={'name': model}, timeout=30)
        if r.status_code in (200, 204):
            return {'ok': True, 'model': model}, 200
        return {'error': f'HTTP {r.status_code}: {r.text[:200]}'}, 502
    except Exception as e:
        return {'error': f'{type(e).__name__}: {e}'}, 502


@admin_bp.post('/github/test')
@require_permission('admin:config')
def github_test():
    """Verifiziert die GitHub-Verbindung mit dem aktuell konfigurierten Token.

    Macht GET /user gegen die GitHub-API; gibt user-login, scopes (falls verfügbar)
    und das Default-Repo-Existenz-Check zurück.
    Optional: Body { token: ... } um einen *noch nicht gespeicherten* Token zu testen.
    """
    import requests
    from shared.github_config import get_github_config

    data = request.get_json(silent=True) or {}
    override_token = str(data.get('token') or '').strip()

    if override_token:
        token = override_token
        gc_source = 'request'
    else:
        gc = get_github_config()
        token = gc.token
        gc_source = gc.source

    if not token:
        return {
            'ok': False, 'error': 'Kein Token konfiguriert',
            'hint': 'Token unter Einstellungen → GitHub eintragen oder ENV GH_TOKEN setzen.',
        }, 400

    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'aics-compliance-suite',
    }
    try:
        r = requests.get('https://api.github.com/user', headers=headers, timeout=10)
    except requests.RequestException as e:
        return {'ok': False, 'error': f'Netzwerkfehler: {e}'}, 502

    if r.status_code == 401:
        return {'ok': False, 'error': 'Token ungültig (401 Unauthorized)'}, 200
    if r.status_code >= 300:
        return {'ok': False, 'error': f'HTTP {r.status_code}: {r.text[:200]}'}, 200

    body = r.json()
    scopes_header = r.headers.get('X-OAuth-Scopes', '').strip()

    # Default-Repo prüfen falls gesetzt
    cfg = get_github_config()
    repo_status = None
    repo_to_check = data.get('default_repo') or cfg.default_repo
    if repo_to_check and '/' in repo_to_check:
        try:
            rr = requests.get(
                f'https://api.github.com/repos/{repo_to_check}',
                headers=headers, timeout=10,
            )
            repo_status = {
                'repo': repo_to_check,
                'exists': rr.status_code == 200,
                'private': bool(rr.json().get('private')) if rr.status_code == 200 else None,
            }
        except requests.RequestException:
            repo_status = {'repo': repo_to_check, 'exists': None, 'error': 'request-failed'}

    # #563: Probe-Read auf /contents um Fine-Grained-PAT-Permissions zu prüfen
    contents_permission = None
    if repo_to_check and '/' in repo_to_check:
        try:
            cr = requests.get(
                f'https://api.github.com/repos/{repo_to_check}/contents/README.md',
                headers=headers, timeout=10,
            )
            if cr.status_code == 200 or cr.status_code == 404:
                contents_permission = {'ok': True, 'note': 'Contents:Read funktioniert'}
            elif cr.status_code == 403:
                contents_permission = {
                    'ok': False, 'status': 403,
                    'note': "Token hat KEINE 'Contents:Read'-Permission — Repo-Scan und Pflicht-Doku-Detect funktionieren nicht. "
                            "Fix: Token bei GitHub editieren → Repository permissions → Contents: Read-only.",
                }
            else:
                contents_permission = {'ok': False, 'status': cr.status_code, 'note': cr.text[:200]}
        except requests.RequestException:
            contents_permission = {'ok': None, 'note': 'Probe-Request fehlgeschlagen'}

    return {
        'ok': True,
        'source': gc_source,
        'login': body.get('login'),
        'name': body.get('name'),
        'avatar_url': body.get('avatar_url'),
        'scopes': [s.strip() for s in scopes_header.split(',')] if scopes_header else [],
        'rate_limit_remaining': r.headers.get('X-RateLimit-Remaining'),
        'default_repo_check': repo_status,
        'contents_permission': contents_permission,
    }, 200


# ============================================================
# F0c — Audit-Log-Viewer
# ============================================================

@admin_bp.get('/audit/events')
@require_permission('admin:audit')
def list_audit_events():
    """Audit-Events listen mit Filter und Pagination."""
    module = request.args.get('module')
    outcome = request.args.get('outcome')
    since = request.args.get('since')  # ISO-Datum
    limit = min(int(request.args.get('limit', 200)), 1000)
    offset = int(request.args.get('offset', 0))

    if not AUDIT_DB.exists():
        return {'events': [], 'total': 0}, 200

    try:
        with closing(_sdb.connect(str(AUDIT_DB))) as conn:
            cur = conn.cursor()

            # Tabellen-Schema vorsichtig prüfen
            cur.execute("SELECT table_name AS name FROM information_schema.tables WHERE table_schema=current_schema()")
            tables = [r['name'] for r in cur.fetchall()]
            table = 'audit_events' if 'audit_events' in tables else (tables[0] if tables else None)
            if not table:
                return {'events': [], 'total': 0}, 200

            # Spalten dynamisch ermitteln
            cur.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?", (table,))
            cols = [r['name'] for r in cur.fetchall()]

            where_clauses = []
            params: List[Any] = []
            if module and 'module' in cols:
                where_clauses.append('module = ?')
                params.append(module)
            if outcome and 'outcome' in cols:
                where_clauses.append('outcome = ?')
                params.append(outcome)
            if since and 'ts' in cols:
                where_clauses.append('ts >= ?')
                params.append(since)

            where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''
            order_col = 'ts' if 'ts' in cols else cols[0]

            cur.execute(f'SELECT COUNT(*) AS c FROM "{table}" {where_sql}', params)
            total = cur.fetchone()['c']

            cur.execute(
                f'SELECT * FROM "{table}" {where_sql} ORDER BY "{order_col}" DESC LIMIT ? OFFSET ?',
                params + [limit, offset]
            )
            events = [dict(r) for r in cur.fetchall()]
        return {'events': events, 'total': total, 'limit': limit, 'offset': offset}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@admin_bp.get('/audit/export.csv')
@require_permission('admin:audit')
def export_audit_csv():
    """Audit-Events als CSV exportieren."""
    import csv
    from io import StringIO
    module = request.args.get('module')
    outcome = request.args.get('outcome')
    since = request.args.get('since')

    if not AUDIT_DB.exists():
        return '', 200

    with closing(_sdb.connect(str(AUDIT_DB))) as conn:
        cur = conn.cursor()
        cur.execute("SELECT table_name AS name FROM information_schema.tables WHERE table_schema=current_schema()")
        tables = [r['name'] for r in cur.fetchall()]
        table = 'audit_events' if 'audit_events' in tables else (tables[0] if tables else None)
        if not table:
            return '', 200

        cur.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?", (table,))
        cols = [r['name'] for r in cur.fetchall()]
        where_clauses = []
        params: List[Any] = []
        if module and 'module' in cols:
            where_clauses.append('module = ?'); params.append(module)
        if outcome and 'outcome' in cols:
            where_clauses.append('outcome = ?'); params.append(outcome)
        if since and 'ts' in cols:
            where_clauses.append('ts >= ?'); params.append(since)
        where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

        cur.execute(f'SELECT * FROM "{table}" {where_sql} ORDER BY rowid DESC LIMIT 10000', params)
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(cols)
        for row in cur.fetchall():
            writer.writerow([row[c] for c in cols])

    from flask import Response
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=audit.csv'}
    )


# ============================================================
# F0d — DB-Viewer (read-only)
# ============================================================

@admin_bp.get('/db/list')
@require_permission('admin:audit')
def list_dbs():
    """Verfügbare DBs auflisten."""
    result = []
    for key, fname in ALLOWED_DBS.items():
        path = DB_DIR / fname
        if path.exists():
            result.append({
                'key': key,
                'file': fname,
                'size_bytes': path.stat().st_size,
            })
    return result, 200


@admin_bp.get('/db/<db_key>/tables')
@require_permission('admin:audit')
def list_db_tables(db_key: str):
    """Tabellen einer DB auflisten."""
    if db_key not in ALLOWED_DBS:
        return {'error': 'Unknown DB'}, 404
    path = DB_DIR / ALLOWED_DBS[db_key]
    if not path.exists():
        return {'error': 'DB does not exist'}, 404
    with closing(_sdb.connect(str(path))) as conn:
        cur = conn.cursor()
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() ORDER BY table_name")
        tables = [r[0] for r in cur.fetchall()]
    return {'tables': tables}, 200


@admin_bp.get('/db/<db_key>/<table>')
@require_permission('admin:audit')
def query_db_table(db_key: str, table: str):
    """Tabellen-Inhalt mit Suche und Pagination (read-only)."""
    if db_key not in ALLOWED_DBS:
        return {'error': 'Unknown DB'}, 404
    if not table.replace('_', '').replace('-', '').isalnum():
        return {'error': 'Invalid table name'}, 400

    q = (request.args.get('q') or '').strip()
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))

    path = DB_DIR / ALLOWED_DBS[db_key]
    if not path.exists():
        return {'error': 'DB does not exist'}, 404

    try:
        with closing(_sdb.connect(str(path))) as conn:
            cur = conn.cursor()

            # Tabelle existiert?
            cur.execute("SELECT table_name AS name FROM information_schema.tables WHERE table_schema=current_schema() AND table_name = ?", (table,))
            if not cur.fetchone():
                return {'error': 'Table not found'}, 404

            cur.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?", (table,))
            cols = [r['name'] for r in cur.fetchall()]

            where_sql = ''
            params: List[Any] = []
            if q and cols:
                like_clauses = ' OR '.join([f'CAST("{c}" AS TEXT) LIKE ?' for c in cols])
                where_sql = f'WHERE {like_clauses}'
                params = [f'%{q}%' for _ in cols]

            cur.execute(f'SELECT COUNT(*) AS c FROM "{table}" {where_sql}', params)
            total = cur.fetchone()['c']

            cur.execute(
                f'SELECT * FROM "{table}" {where_sql} LIMIT ? OFFSET ?',
                params + [limit, offset]
            )
            rows = [dict(r) for r in cur.fetchall()]

        return {
            'columns': cols,
            'rows': rows,
            'total': total,
            'limit': limit,
            'offset': offset,
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# F0e — Backup (Liste, Erstellen, Restore, Löschen)
# ============================================================

@admin_bp.get('/backup')
@require_permission('admin:config')
def list_backups():
    """Vorhandene Backups auflisten."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for f in sorted(BACKUP_DIR.glob('backup_*.zip'), reverse=True):
        try:
            stat = f.stat()
            result.append({
                'id': f.stem,
                'filename': f.name,
                'size_bytes': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
        except Exception:
            continue
    return result, 200


@admin_bp.post('/backup')
@require_permission('admin:config')
def create_backup():
    """Neues Backup erstellen (synchron)."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_DIR / f'backup_{timestamp}.zip'

    try:
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Alle DBs
            for db_file in DB_DIR.glob('*.sqlite'):
                if not db_file.name.startswith('_tmp_'):
                    zf.write(db_file, f'data/db/{db_file.name}')
            for wal in DB_DIR.glob('*.sqlite-wal'):
                zf.write(wal, f'data/db/{wal.name}')
            for shm in DB_DIR.glob('*.sqlite-shm'):
                zf.write(shm, f'data/db/{shm.name}')
            # Live-Config + Sidecar (Issue #357).
            # Im Docker liegt AICS_CONFIG_PATH=/app/data/..., im Dev = CWD.
            # Wir packen sie unter ihrem Basename ein, damit Restore sie an
            # den dann gültigen Live-Pfad zurückschreibt.
            cfg_paths_seen: set[str] = set()
            live_cfg = Path(DEFAULT_CONFIG_PATH)
            if live_cfg.exists():
                zf.write(live_cfg, live_cfg.name)
                cfg_paths_seen.add(live_cfg.name)
                sidecar = live_cfg.with_suffix(live_cfg.suffix + '.sha256')
                if sidecar.exists():
                    zf.write(sidecar, sidecar.name)
            # Module-Configs (z.B. cra.config.json) liegen weiterhin im CWD
            for cfg in Path('.').glob('*.config.json'):
                if cfg.name not in cfg_paths_seen:
                    zf.write(cfg, cfg.name)
                    side = cfg.with_suffix(cfg.suffix + '.sha256')
                    if side.exists():
                        zf.write(side, side.name)
            # Manifest
            zf.writestr('MANIFEST.json', json.dumps({
                'created_at': datetime.now(tz=timezone.utc).isoformat(),
                'created_by': 'admin',
                'version': '1.0.0',
            }, indent=2))

        # Retention: nur N neueste behalten
        cfg = load_config()
        keep = int(cfg.get('backup', {}).get('backup_retention_count', 5))
        backups = sorted(BACKUP_DIR.glob('backup_*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[keep:]:
            try:
                old.unlink()
            except Exception:
                pass

        stat = backup_path.stat()
        return {
            'id': backup_path.stem,
            'filename': backup_path.name,
            'size_bytes': stat.st_size,
            'created_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@admin_bp.post('/backup/upload')
@require_permission('admin:config')
def upload_backup():
    """Externes Backup-ZIP hochladen (Issue #356).

    Multipart: Feld `file`. Max 200 MB. Akzeptiert nur .zip mit gültiger
    Struktur (MANIFEST.json + mind. eine data/db/*.sqlite).
    """
    MAX_SIZE = 200 * 1024 * 1024
    f = request.files.get('file')
    if not f or not f.filename:
        return {'error': 'Datei-Feld "file" fehlt'}, 400
    if not f.filename.lower().endswith('.zip'):
        return {'error': 'Nur .zip-Dateien werden akzeptiert'}, 400

    # Größe prüfen
    f.stream.seek(0, 2)  # end
    size = f.stream.tell()
    f.stream.seek(0)
    if size > MAX_SIZE:
        return {'error': f'Datei zu groß ({size // (1024*1024)} MB, max 200 MB)'}, 413
    if size < 100:
        return {'error': 'Datei zu klein, vermutlich kein gültiges Backup'}, 400

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    # Sicherer Filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_name = f'backup_{timestamp}_uploaded.zip'
    target = BACKUP_DIR / target_name

    # Erst in temp speichern, dann validieren, dann verschieben
    import tempfile, shutil
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp_path = tmp.name
            f.save(tmp.name)

        # Validierung: ZIP korrekt + MANIFEST + mind. 1 DB
        with zipfile.ZipFile(tmp_path, 'r') as zf:
            try:
                bad = zf.testzip()
                if bad:
                    return {'error': f'ZIP enthält beschädigte Datei: {bad}'}, 400
            except Exception as e:
                return {'error': f'Kein gültiges ZIP-Archiv: {e}'}, 400
            names = zf.namelist()
            has_manifest = any(n.lower() == 'manifest.json' for n in names)
            has_db = any(n.lower().startswith('data/db/') and n.lower().endswith('.sqlite') for n in names)
            if not has_manifest:
                return {'error': 'MANIFEST.json fehlt — vermutlich kein Suite-Backup'}, 400
            if not has_db:
                return {'error': 'Keine data/db/*.sqlite gefunden — vermutlich kein Suite-Backup'}, 400
            # Path-Traversal-Schutz
            for n in names:
                if n.startswith('/') or '..' in Path(n).parts:
                    return {'error': f'Unsicherer Pfad im ZIP: {n}'}, 400

        shutil.move(tmp_path, target)
        tmp_path = None
        stat = target.stat()
        identity = get_jwt_identity()
        user_email = identity if isinstance(identity, str) else identity.get('email', '?')
        current_app.logger.info(
            'Backup uploaded: %s (%d bytes) by %s', target.name, stat.st_size, user_email,
        )
        return {
            'id': target.stem,
            'filename': target.name,
            'size_bytes': stat.st_size,
            'created_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            'uploaded': True,
        }, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)
    finally:
        if tmp_path:
            try: os.unlink(tmp_path)
            except Exception: pass


@admin_bp.delete('/backup/<backup_id>')
@require_permission('admin:config')
def delete_backup(backup_id: str):
    """Backup löschen."""
    if not backup_id.startswith('backup_') or '/' in backup_id or '..' in backup_id:
        return {'error': 'Invalid backup id'}, 400
    path = BACKUP_DIR / f'{backup_id}.zip'
    if not path.exists():
        return {'error': 'Backup not found'}, 404
    try:
        path.unlink()
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@admin_bp.post('/backup/<backup_id>/restore')
@require_permission('admin:config')
def restore_backup(backup_id: str):
    """Backup wiederherstellen (überschreibt aktuelle DBs!).

    Extrahiert nur die DBs nach data/db/ und Config-JSONs in das Daten-Verzeichnis
    (statt CWD, das in Containern root-owned ist).
    """
    if not backup_id.startswith('backup_') or '/' in backup_id or '..' in backup_id:
        return {'error': 'Invalid backup id'}, 400
    path = BACKUP_DIR / f'{backup_id}.zip'
    if not path.exists():
        return {'error': 'Backup not found'}, 404

    confirm = (request.json or {}).get('confirm')
    if confirm != backup_id:
        return {'error': 'Confirmation required: send {"confirm": "<backup_id>"}'}, 400

    try:
        # Aktuelle DBs vorher in Sicherheits-Backup
        safety = BACKUP_DIR / f'pre_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        with zipfile.ZipFile(safety, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in DB_DIR.glob('*.sqlite'):
                zf.write(f, f'data/db/{f.name}')

        # Restore: gezielt entpacken — nur DBs nach DB_DIR, Configs neben DB_DIR
        # (CWD kann in Container root-owned sein → kein extractall(Path('.'))).
        from pathlib import Path as _P
        DB_DIR.mkdir(parents=True, exist_ok=True)
        data_root = DB_DIR.parent  # /app/data
        restored_files = []
        skipped = []

        # Vor Restore: alle stale Config-Sidecars im Ziel löschen (Issue #357).
        # Sonst kollidiert ein altes .sha256 mit der frisch restorten Config.
        live_cfg_path = Path(DEFAULT_CONFIG_PATH)
        cleanup_dirs = {data_root}
        if live_cfg_path.parent != data_root:
            cleanup_dirs.add(live_cfg_path.parent)
        for d in cleanup_dirs:
            try:
                for stale in d.glob('*.config.json.sha256'):
                    stale.unlink()
            except OSError:
                pass

        restored_configs: list[Path] = []
        with zipfile.ZipFile(path, 'r') as zf:
            for member in zf.namelist():
                # Sicherheit: keine Pfade aus dem Archiv extrahieren, die nach oben zeigen
                if member.startswith('/') or '..' in _P(member).parts:
                    skipped.append(member)
                    continue
                lower = member.lower()
                if lower.startswith('data/db/') and (
                    lower.endswith('.sqlite') or lower.endswith('-wal') or lower.endswith('-shm')
                ):
                    target = DB_DIR / _P(member).name
                    with zf.open(member) as src, open(target, 'wb') as dst:
                        dst.write(src.read())
                    restored_files.append(str(target))
                elif lower.endswith('.config.json'):
                    # Live-Config landet an ihrem Live-Pfad (AICS_CONFIG_PATH),
                    # restliche Module-Configs neben data_root.
                    if _P(member).name == live_cfg_path.name:
                        target = live_cfg_path
                    else:
                        target = data_root / _P(member).name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(target, 'wb') as dst:
                        dst.write(src.read())
                    restored_files.append(str(target))
                    restored_configs.append(target)
                elif lower.endswith('.config.json.sha256'):
                    # Sidecar passend zur eben restorten Config legen
                    base = _P(member).name
                    if base == live_cfg_path.name + '.sha256':
                        target = live_cfg_path.with_suffix(live_cfg_path.suffix + '.sha256')
                    else:
                        target = data_root / base
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(target, 'wb') as dst:
                        dst.write(src.read())
                    restored_files.append(str(target))
                else:
                    skipped.append(member)

        # Falls eine Config restored wurde, aber kein passendes Sidecar im ZIP war:
        # Sidecar deterministisch aus dem aktuellen Datei-Hash regenerieren.
        import hashlib as _hashlib
        for cfg in restored_configs:
            side = cfg.with_suffix(cfg.suffix + '.sha256')
            if not side.exists():
                try:
                    h = _hashlib.sha256(cfg.read_bytes()).hexdigest()
                    side.write_text(h + '\n', encoding='utf-8')
                    restored_files.append(str(side))
                except OSError as _e:
                    current_app.logger.warning('Sidecar-regen für %s fehlgeschlagen: %s', cfg, _e)

        # Post-Restore Migrations: alte Backups haben evtl. veraltetes Schema
        # → ensure_db() führt PRAGMA-Migrations aus und repariert Datentypen
        try:
            from server.auth.users_db import ensure_db as _users_ensure_db
            users_db = DB_DIR / 'users.sqlite'
            if users_db.exists():
                _users_ensure_db(users_db)
                # Defensive: aus alten Backups kann active als String 'null' kommen
                # → setze valide Integer-Werte
                with closing(_sdb.connect(str(users_db))) as _con:
                    _con.execute("UPDATE users SET active=1 WHERE typeof(active) != 'integer' OR active IS NULL")
                    _con.execute("UPDATE users SET failed_login_count=0, locked_until=0 "
                                 "WHERE typeof(failed_login_count) != 'integer' OR failed_login_count IS NULL")
                    _con.commit()
                current_app.logger.info('Post-Restore users.sqlite migrated + active repaired')
        except Exception as _e:
            current_app.logger.warning('Post-Restore users-migration failed: %s', _e)

        current_app.logger.info(
            'Backup-Restore: id=%s restored=%d skipped=%d safety=%s',
            backup_id, len(restored_files), len(skipped), safety.stem,
        )
        return {
            'restored': True,
            'safety_backup': safety.stem,
            'restored_count': len(restored_files),
            'skipped': skipped,
            'migration': 'users.sqlite schema + active-flag normalized',
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ════════════════════════════════════════════════════════════════════
# S1 (#1071): Firmen-FK-Härtung — Backfill, Übersicht, manuelle Zuordnung
# ════════════════════════════════════════════════════════════════════

from shared.firmen_link import (  # noqa: E402
    MODULE_PROJECT_TABLES as _FK_TABLES,
    backfill_firmen_ids as _fk_backfill,
    ensure_firmen_id_column as _fk_ensure,
)


@admin_bp.post('/firmen-link/backfill')
@require_permission('admin:users')
def firmen_link_backfill():
    """firmen_id in allen Modul-Projekttabellen per Name-Match befüllen."""
    out: Dict[str, Any] = {}
    for dbfile, (table, name_col) in _FK_TABLES.items():
        p = DB_DIR / dbfile
        if not p.exists():
            out[dbfile] = {'matched': 0, 'unmatched': [], 'skipped': 'db missing'}
            continue
        try:
            out[dbfile] = _fk_backfill(p, table, name_col=name_col)
        except Exception as e:  # pragma: no cover - defensiv
            out[dbfile] = {'error': str(e)}
    return jsonify({'results': out}), 200


@admin_bp.get('/firmen-link/unassigned')
@require_permission('admin:users')
def firmen_link_unassigned():
    """Projekte mit nicht-leerem Firmennamen, aber ohne firmen_id (unklare Fälle)."""
    out: Dict[str, Any] = {}
    for dbfile, (table, name_col) in _FK_TABLES.items():
        p = DB_DIR / dbfile
        if not p.exists():
            continue
        try:
            con = _sdb.connect(str(p))
            try:
                _fk_ensure(con, table)
                rows = con.execute(
                    f"SELECT name, {name_col} FROM {table} "
                    f"WHERE firmen_id IS NULL AND TRIM(COALESCE({name_col},'')) <> ''"
                ).fetchall()
            finally:
                con.close()
            out[dbfile] = [{'projekt': r[0], 'unternehmen': r[1]} for r in rows]
        except Exception as e:  # pragma: no cover - defensiv
            out[dbfile] = {'error': str(e)}
    return jsonify({'unassigned': out}), 200


@admin_bp.post('/firmen-link/assign')
@require_permission('admin:users')
def firmen_link_assign():
    """Manuelle Zuordnung Projekt → Firma (firmen_id)."""
    data = request.get_json(silent=True) or {}
    dbfile = data.get('module')
    projekt = (data.get('projekt') or '').strip()
    firmen_id = data.get('firmen_id')
    entry = _FK_TABLES.get(dbfile)
    if not entry or not projekt or not firmen_id:
        return jsonify({'error': 'module, projekt, firmen_id erforderlich'}), 400
    table = entry[0]
    p = DB_DIR / dbfile
    if not p.exists():
        return jsonify({'error': 'Modul-DB nicht gefunden'}), 404
    con = _sdb.connect(str(p))
    try:
        _fk_ensure(con, table)
        cur = con.execute(
            f"UPDATE {table} SET firmen_id=? WHERE name=?", (int(firmen_id), projekt)
        )
        con.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'Projekt nicht gefunden'}), 404
    finally:
        con.close()
    return jsonify({'ok': True}), 200
