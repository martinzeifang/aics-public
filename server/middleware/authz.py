"""Zentrale serverseitige Autorisierung für Fach-Module (#734 / WP-01).

Bislang waren alle Fach-Endpunkte nur per `@jwt_required` geschützt, aber ohne
Berechtigungsprüfung — das RBAC-Modell wurde nur im Frontend gefiltert. Dieser
App-weite `before_request`-Guard erzwingt pro Request:

  1. Authentifizierung (gültiges JWT),
  2. Modul-Freigabe (`allowed_modules`-Whitelist aus den Claims),
  3. Aktion (Methode→read/write/export) gegen die granulare Permission
     `<modul>:<aktion>`.

Mapping Pfad→Modul über das URL-Prefix. Nicht-modulare Routen (auth, admin,
license, certificates, webauthn, health, …) werden übersprungen — sie haben
eigene Guards (`require_permission`) bzw. sind bewusst öffentlich.

OWASP A01 · ASVS V4.1.1/V4.1.3 · ISO 27001 A.5.15/A.5.18 · BSI ORP.4.
"""

from __future__ import annotations

import logging

from flask import Flask, request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt

from server.models.permission import resolve_permissions

log = logging.getLogger(__name__)

# URL-Prefix → Modul-Schlüssel (entspricht MODULE_PERMISSIONS)
_MODULE_PREFIXES: list[tuple[str, str]] = [
    ('/api/risikobewertung', 'risikobewertung'),
    ('/api/firmen', 'firmen'),
    ('/api/kunden', 'firmen'),  # Deprecation-Alias (#1003) — wie firmen geschützt
    ('/api/gutachten', 'gutachten'),
    ('/api/aiact', 'aiact'),
    ('/api/dsgvo', 'dsgvo'),
    ('/api/nis2', 'nis2'),
    ('/api/cra', 'cra'),
    ('/api/wiba', 'wiba'),
    ('/api/soc', 'soc'),
    ('/api/risk-cockpit', 'risikobewertung'),
]

# Legacy-Modulnamen aus alten JWTs/Rollen, die weiterhin akzeptiert werden (#1003)
_LEGACY_MODULE_ALIASES: dict[str, str] = {'firmen': 'kunden'}

# Pfad-Marker, die eine Export/Download-Aktion kennzeichnen (auch bei POST)
_EXPORT_MARKERS = ('/export', '/download', '/docx', '/pdf', '/xlsx', '/report')


# Bekannte Basis-Module (für die Bindestrich-Area-Blueprints, #1169).
_KNOWN_MODULES = {m for _, m in _MODULE_PREFIXES}


def _module_for_path(path: str) -> str | None:
    for prefix, module in _MODULE_PREFIXES:
        if path == prefix or path.startswith(prefix + '/'):
            return module
    # #1169: Geschwister-Prefixe `/api/<modul>-<bereich>/...` (z.B. dsgvo-tom,
    # dsgvo-kontrollen, cra-dokumente, aiact-dokumente) demselben Modul-Guard
    # unterstellen — sonst umgehen sie die allowed_modules-Whitelist + Lizenz-Gate.
    if path.startswith('/api/'):
        seg = path[len('/api/'):].split('/', 1)[0]
        if '-' in seg:
            base = seg.split('-', 1)[0]
            if base in _KNOWN_MODULES:
                return base
    return None


def _action_for(path: str, method: str) -> str:
    if method in ('GET', 'HEAD'):
        return 'read'
    p = path.lower()
    if any(m in p for m in _EXPORT_MARKERS):
        return 'export'
    return 'write'


def register_module_authz(app: Flask) -> None:
    """Registriert den modulweiten Autorisierungs-Guard als before_request."""

    @app.before_request
    def _module_authz():  # noqa: ANN202
        if request.method == 'OPTIONS':
            return None  # CORS-Preflight nicht blockieren

        module = _module_for_path(request.path or '')
        if module is None:
            return None  # nicht-modulare Route → eigene Guards greifen

        # 1. Authentifizierung
        try:
            verify_jwt_in_request()
            claims = get_jwt()
        except Exception:
            log.debug("JWT-Verifikation fehlgeschlagen für %s %s",
                      request.method, request.path, exc_info=True)
            return jsonify({'error': 'Authentication required'}), 401

        # Permissions: bevorzugt aufgelöster Claim, sonst aus Rollen ableiten
        perms = set(claims.get('permissions') or [])
        roles = claims.get('roles') or []
        extra = claims.get('extra_permissions') or []
        if not perms:
            perms = set(resolve_permissions(roles, extra))

        # Legacy-Alias (#1003): alte Tokens/Rollen mit 'kunden' weiter akzeptieren
        legacy = _LEGACY_MODULE_ALIASES.get(module)

        # 2. Modul-Freigabe (Whitelist)
        allowed = claims.get('allowed_modules', None)
        if isinstance(allowed, list) and module not in allowed and (
                legacy is None or legacy not in allowed):
            return jsonify({'error': 'Forbidden: Modul nicht freigegeben',
                            'module': module}), 403

        # 3. Aktion → benötigte Permission
        action = _action_for(request.path or '', request.method)
        needed = f'{module}:{action}'
        ok = (
            needed in perms
            or f'{module}:*' in perms
            # Export ist auch durch Schreibrecht abgedeckt (Editor kann exportieren)
            or (action == 'export' and f'{module}:write' in perms)
            # Legacy-Permissions aus alten Tokens (kunden:*)
            or (legacy is not None and (
                f'{legacy}:{action}' in perms
                or f'{legacy}:*' in perms
                or (action == 'export' and f'{legacy}:write' in perms)))
        )
        if not ok:
            return jsonify({'error': 'Forbidden', 'required': needed}), 403

        # 4. Objekt-RBAC (#1185): Firmen-Whitelist gegen die Objekt-Firma prüfen.
        # Best-effort/fail-open — greift nur bei expliziter Whitelist + auflösbarer Firma.
        try:
            from server.middleware.firma_acl import access_denied_for_firma
            if access_denied_for_firma(claims, module, request.view_args or {}):
                return jsonify({'error': 'Forbidden: Firma nicht freigegeben'}), 403
        except Exception:
            pass

        return None
