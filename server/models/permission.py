"""RBAC Models: Permission, Role, User.

Definiert Rollen und Permissions für alle Module der Web-API.
"""

from __future__ import annotations

from enum import Enum
from typing import List


class RoleEnum(str, Enum):
    """Rollen der Web-API."""
    ADMIN = "admin"
    EDITOR = "editor"          # Vollzugriff auf alle Module (lesen+schreiben+export)
    VIEWER = "viewer"          # Nur-Lese-Zugriff auf alle Module
    AUDITOR = "auditor"        # Nur-Lese + Audit-Log
    # Modul-spezifische Editor-Rollen (für feinere Aufteilung):
    CRA_EDITOR = "cra_editor"
    CRA_VIEWER = "cra_viewer"
    NIS2_EDITOR = "nis2_editor"
    DORA_EDITOR = "dora_editor"
    AIACT_EDITOR = "aiact_editor"
    DSGVO_EDITOR = "dsgvo_editor"
    GUTACHTEN_EDITOR = "gutachten_editor"
    RISIKOBEWERTUNG_EDITOR = "risikobewertung_editor"
    FIRMEN_EDITOR = "firmen_editor"
    WIBA_EDITOR = "wiba_editor"
    GESCHAEFTSFUEHRER = "geschaeftsfuehrer"  # Jahresbericht-Freigabe
    DSB = "dsb"  # Datenschutzbeauftragte:r — Signatur


# ── Module ──────────────────────────────────────────────────────────────────
MODULES = [
    'firmen',
    'risikobewertung',
    'cra',
    'nis2',
    'dora',
    'aiact',
    'dsgvo',
    'gutachten',
    'wiba',
]


# ── Granulare Permissions ───────────────────────────────────────────────────
class Permission(str, Enum):
    # Firmen
    FIRMEN_READ = "firmen:read"
    FIRMEN_WRITE = "firmen:write"

    # Risikobewertung
    RB_READ = "risikobewertung:read"
    RB_WRITE = "risikobewertung:write"
    RB_EXPORT = "risikobewertung:export"

    # CRA
    CRA_READ = "cra:read"
    CRA_WRITE = "cra:write"
    CRA_PREFILL = "cra:prefill"
    CRA_ISSUE_LINK = "cra:issue_link"
    CRA_EXPORT = "cra:export"

    # NIS2
    NIS2_READ = "nis2:read"
    NIS2_WRITE = "nis2:write"
    NIS2_EXPORT = "nis2:export"

    # DORA
    DORA_READ = "dora:read"
    DORA_WRITE = "dora:write"
    DORA_EXPORT = "dora:export"

    # AI-Act
    AIACT_READ = "aiact:read"
    AIACT_WRITE = "aiact:write"
    AIACT_EXPORT = "aiact:export"

    # DSGVO
    DSGVO_READ = "dsgvo:read"
    DSGVO_WRITE = "dsgvo:write"
    DSGVO_EXPORT = "dsgvo:export"
    DSGVO_APPROVE = "dsgvo:approve"   # Jahresbericht/Kontrolle freigeben (GF)
    DSGVO_SIGN = "dsgvo:sign"         # Jahresbericht signieren (DSB)

    # Gutachten
    GUTACHTEN_READ = "gutachten:read"
    GUTACHTEN_WRITE = "gutachten:write"
    GUTACHTEN_EXPORT = "gutachten:export"
    GUTACHTEN_FRAMEWORKS = "gutachten:frameworks"   # Framework-Bibliothek (Download/Ingest)
    GUTACHTEN_FINAL_DELETE = "gutachten:final_delete"  # #969 — Final-Archiv löschen (nur Admin)

    # WiBA (BSI Weg in die Basis-Absicherung)
    WIBA_READ = "wiba:read"
    WIBA_WRITE = "wiba:write"
    WIBA_EXPORT = "wiba:export"
    WIBA_CATALOG = "wiba:catalog"   # Prüffragen-Katalog Download/Ingest (Admin)

    # Admin
    ADMIN_USERS = "admin:users"
    ADMIN_ROLES = "admin:roles"
    ADMIN_AUDIT = "admin:audit"
    ADMIN_CONFIG = "admin:config"

    # Template-Engine (#991) — Verwaltung der Word-Vorlagen (nur Admin)
    TEMPLATE_MANAGE = "template:manage"


# ── Permission-Sets pro Modul (für UI + Defaults) ──────────────────────────
MODULE_PERMISSIONS: dict[str, list[Permission]] = {
    'firmen': [Permission.FIRMEN_READ, Permission.FIRMEN_WRITE],
    'risikobewertung': [Permission.RB_READ, Permission.RB_WRITE, Permission.RB_EXPORT],
    'cra': [Permission.CRA_READ, Permission.CRA_WRITE, Permission.CRA_PREFILL,
            Permission.CRA_ISSUE_LINK, Permission.CRA_EXPORT],
    'nis2': [Permission.NIS2_READ, Permission.NIS2_WRITE, Permission.NIS2_EXPORT],
    'dora': [Permission.DORA_READ, Permission.DORA_WRITE, Permission.DORA_EXPORT],
    'aiact': [Permission.AIACT_READ, Permission.AIACT_WRITE, Permission.AIACT_EXPORT],
    'dsgvo': [Permission.DSGVO_READ, Permission.DSGVO_WRITE, Permission.DSGVO_EXPORT,
             Permission.DSGVO_APPROVE, Permission.DSGVO_SIGN],
    'gutachten': [Permission.GUTACHTEN_READ, Permission.GUTACHTEN_WRITE,
                  Permission.GUTACHTEN_EXPORT, Permission.GUTACHTEN_FRAMEWORKS],
    'wiba': [Permission.WIBA_READ, Permission.WIBA_WRITE, Permission.WIBA_EXPORT,
             Permission.WIBA_CATALOG],
}


def _all_module_permissions(action: str | None = None) -> list[Permission]:
    """Alle Permissions, optional nur 'read'/'write'/'export'."""
    out: list[Permission] = []
    for perms in MODULE_PERMISSIONS.values():
        for p in perms:
            if action is None or p.value.endswith(f':{action}'):
                out.append(p)
    return out


# Read-Only-Set über alle Module
_ALL_READ = _all_module_permissions('read') + _all_module_permissions('export')
_ALL_WRITE = _all_module_permissions()  # alle


# ── Role → Permissions Mapping ─────────────────────────────────────────────
ROLE_PERMISSIONS: dict[RoleEnum, list[Permission]] = {
    RoleEnum.ADMIN: list(Permission),  # alle
    RoleEnum.EDITOR: list(set(_ALL_WRITE)),
    RoleEnum.VIEWER: list(set(_ALL_READ)),
    RoleEnum.AUDITOR: list(set(_ALL_READ + [Permission.ADMIN_AUDIT])),
    # Modul-spezifische Editor-Rollen
    RoleEnum.CRA_EDITOR: MODULE_PERMISSIONS['cra'],
    RoleEnum.CRA_VIEWER: [Permission.CRA_READ, Permission.CRA_EXPORT],
    RoleEnum.NIS2_EDITOR: MODULE_PERMISSIONS['nis2'],
    RoleEnum.DORA_EDITOR: MODULE_PERMISSIONS['dora'],
    RoleEnum.AIACT_EDITOR: MODULE_PERMISSIONS['aiact'],
    RoleEnum.DSGVO_EDITOR: MODULE_PERMISSIONS['dsgvo'],
    RoleEnum.GESCHAEFTSFUEHRER: [Permission.DSGVO_READ, Permission.DSGVO_EXPORT, Permission.DSGVO_APPROVE],
    RoleEnum.DSB: [Permission.DSGVO_READ, Permission.DSGVO_WRITE, Permission.DSGVO_EXPORT, Permission.DSGVO_SIGN],
    RoleEnum.GUTACHTEN_EDITOR: MODULE_PERMISSIONS['gutachten'],
    RoleEnum.RISIKOBEWERTUNG_EDITOR: MODULE_PERMISSIONS['risikobewertung'],
    RoleEnum.FIRMEN_EDITOR: MODULE_PERMISSIONS['firmen'],
    RoleEnum.WIBA_EDITOR: MODULE_PERMISSIONS['wiba'],
}


# Legacy-Rollen-/Permission-Strings aus der Zeit vor der Umbenennung
# „Kunden" → „Firmen" (#1003), die weiterhin akzeptiert werden.
_LEGACY_ROLE_ALIASES: dict[str, str] = {'kunden_editor': 'firmen_editor'}
_LEGACY_PERMISSION_ALIASES: dict[str, str] = {
    'kunden:read': 'firmen:read',
    'kunden:write': 'firmen:write',
}


def resolve_permissions(roles: list[str], extra_permissions: list[str] | None = None) -> list[str]:
    """Effektive Permissions aus Rollen + extra_permissions (additiv)."""
    result: set[str] = set()
    for role_str in roles or []:
        role_str = _LEGACY_ROLE_ALIASES.get(role_str, role_str)
        try:
            role = RoleEnum(role_str)
        except ValueError:
            continue
        for p in ROLE_PERMISSIONS.get(role, []):
            result.add(p.value)
    for p in (extra_permissions or []):
        # Legacy-Permission-Strings auf neue Namen mappen (additiv: beide behalten)
        result.add(_LEGACY_PERMISSION_ALIASES.get(p, p))
    return sorted(result)


def has_permission(user_roles: list[str], permission: str | Permission,
                   extra_permissions: list[str] | None = None) -> bool:
    """Prüfe, ob User die Permission hat (über Rollen oder extra_permissions)."""
    perm_value = permission.value if isinstance(permission, Permission) else permission
    effective = resolve_permissions(user_roles, extra_permissions)
    return perm_value in effective


def allowed_modules_for(user_roles: list[str], extra_permissions: list[str] | None = None,
                         allowed_modules: list[str] | None = None) -> list[str]:
    """Module, die der User sehen darf.

    - Wenn `allowed_modules` explizit gesetzt: dieser Filter (Whitelist).
    - Sonst: alle Module, für die mindestens eine Read-Permission vorliegt.
    """
    if allowed_modules is not None:
        return [m for m in allowed_modules if m in MODULES]

    effective = set(resolve_permissions(user_roles, extra_permissions))
    out = []
    for m, perms in MODULE_PERMISSIONS.items():
        # mindestens eine Permission aus dem Modul vorhanden?
        if any(p.value in effective for p in perms):
            out.append(m)
    return out


def require_permission(permission: str | Permission):
    """Decorator für Flask-Routes mit Permission-Check.

    Liest extra_permissions zusätzlich aus dem JWT-sub.
    """
    from functools import wraps
    from flask import jsonify
    from flask_jwt_extended import get_jwt

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from flask_jwt_extended import verify_jwt_in_request
            verify_jwt_in_request()
            claims = get_jwt()
            # Neuer Style: additional_claims sind direkt im claims-Dict
            user_roles = claims.get('roles', [])
            extra = claims.get('extra_permissions', [])
            # Fallback Legacy (sub als Dict)
            if not user_roles:
                sub = claims.get('sub')
                if isinstance(sub, dict):
                    user_roles = sub.get('roles', [])
                    extra = sub.get('extra_permissions', extra)
            if not has_permission(user_roles, permission, extra):
                return jsonify({'error': 'Forbidden', 'required': str(permission)}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
