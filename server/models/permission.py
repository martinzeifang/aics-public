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
    KUNDEN_EDITOR = "kunden_editor"


# ── Module ──────────────────────────────────────────────────────────────────
MODULES = [
    'kunden',
    'risikobewertung',
    'cra',
    'nis2',
    'dora',
    'aiact',
    'dsgvo',
    'gutachten',
]


# ── Granulare Permissions ───────────────────────────────────────────────────
class Permission(str, Enum):
    # Kunden
    KUNDEN_READ = "kunden:read"
    KUNDEN_WRITE = "kunden:write"

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

    # Gutachten
    GUTACHTEN_READ = "gutachten:read"
    GUTACHTEN_WRITE = "gutachten:write"
    GUTACHTEN_EXPORT = "gutachten:export"
    GUTACHTEN_FRAMEWORKS = "gutachten:frameworks"   # Framework-Bibliothek (Download/Ingest)
    GUTACHTEN_FINAL_DELETE = "gutachten:final_delete"  # #969 — Final-Archiv löschen (nur Admin)

    # Admin
    ADMIN_USERS = "admin:users"
    ADMIN_ROLES = "admin:roles"
    ADMIN_AUDIT = "admin:audit"
    ADMIN_CONFIG = "admin:config"


# ── Permission-Sets pro Modul (für UI + Defaults) ──────────────────────────
MODULE_PERMISSIONS: dict[str, list[Permission]] = {
    'kunden': [Permission.KUNDEN_READ, Permission.KUNDEN_WRITE],
    'risikobewertung': [Permission.RB_READ, Permission.RB_WRITE, Permission.RB_EXPORT],
    'cra': [Permission.CRA_READ, Permission.CRA_WRITE, Permission.CRA_PREFILL,
            Permission.CRA_ISSUE_LINK, Permission.CRA_EXPORT],
    'nis2': [Permission.NIS2_READ, Permission.NIS2_WRITE, Permission.NIS2_EXPORT],
    'dora': [Permission.DORA_READ, Permission.DORA_WRITE, Permission.DORA_EXPORT],
    'aiact': [Permission.AIACT_READ, Permission.AIACT_WRITE, Permission.AIACT_EXPORT],
    'dsgvo': [Permission.DSGVO_READ, Permission.DSGVO_WRITE, Permission.DSGVO_EXPORT],
    'gutachten': [Permission.GUTACHTEN_READ, Permission.GUTACHTEN_WRITE,
                  Permission.GUTACHTEN_EXPORT, Permission.GUTACHTEN_FRAMEWORKS],
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
    RoleEnum.GUTACHTEN_EDITOR: MODULE_PERMISSIONS['gutachten'],
    RoleEnum.RISIKOBEWERTUNG_EDITOR: MODULE_PERMISSIONS['risikobewertung'],
    RoleEnum.KUNDEN_EDITOR: MODULE_PERMISSIONS['kunden'],
}


def resolve_permissions(roles: list[str], extra_permissions: list[str] | None = None) -> list[str]:
    """Effektive Permissions aus Rollen + extra_permissions (additiv)."""
    result: set[str] = set()
    for role_str in roles or []:
        try:
            role = RoleEnum(role_str)
        except ValueError:
            continue
        for p in ROLE_PERMISSIONS.get(role, []):
            result.add(p.value)
    for p in (extra_permissions or []):
        result.add(p)
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
