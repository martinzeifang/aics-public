"""Negative Security-Tests (#745 / WP-12).

Fokus: bewusst NEGATIVE Pfade, die robust grün bleiben sollen:

  1. Authentifizierte, aber NICHT berechtigte User erhalten 403 auf
     Modul-Schreiboperationen (RBAC-Guard aus #734 greift unabhängig von der
     Lizenz — geprüft mit einem Rollen-Token ohne `<modul>:write`).
  2. Injection-artige Payloads werden abgewiesen:
       (a) SQL-Injection im Tabellennamen des Admin-DB-Viewers → 400,
       (b) LDAP-Filter-Injection wird vom Escaper neutralisiert.

Wichtig: Für (1) wird BEWUSST KEINE Voll-Lizenz gesetzt — der Modul-Guard
erzwingt die Permission unabhängig vom Lizenzstatus; ein 423 (License) würde
die eigentliche 403-Aussage verschleiern.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token

from server.models.permission import resolve_permissions, allowed_modules_for


def _token(app, roles):
    with app.app_context():
        perms = resolve_permissions(roles, [])
        mods = allowed_modules_for(roles, [], None)
        return create_access_token(
            identity='u-neg-test',
            additional_claims={
                'roles': roles,
                'permissions': perms,
                'extra_permissions': [],
                'allowed_modules': mods,
            },
            expires_delta=timedelta(hours=1),
        )


def _h(app, roles):
    return {'Authorization': f'Bearer {_token(app, roles)}'}


# ---------------------------------------------------------------------------
# 1. Authentifiziert, aber nicht berechtigt → 403 (kein 401, kein 423)
# ---------------------------------------------------------------------------

class TestAuthorizationDenied:
    def test_viewer_write_module_forbidden(self, client, app):
        """Ein 'viewer' (nur read) darf nicht in cra schreiben → 403."""
        r = client.post('/api/cra/projekte', headers=_h(app, ['viewer']), json={})
        assert r.status_code == 403, r.get_json()
        body = r.get_json() or {}
        # Guard meldet die fehlende konkrete Permission.
        assert body.get('required') == 'cra:write'

    def test_cross_module_editor_forbidden(self, client, app):
        """Ein cra_editor darf NICHT in ein fremdes Modul (nis2) schreiben."""
        r = client.post('/api/nis2/projekte', headers=_h(app, ['cra_editor']), json={})
        assert r.status_code == 403, r.get_json()

    def test_denied_is_not_auth_challenge(self, client, app):
        """Ein berechtigungsloser, aber authentifizierter Request ist 403, nicht 401."""
        r = client.post('/api/dsgvo/projekte', headers=_h(app, ['viewer']), json={})
        assert r.status_code == 403
        assert r.status_code != 401


# ---------------------------------------------------------------------------
# 2a. SQL-Injection im Admin-DB-Viewer-Tabellennamen → 400
# ---------------------------------------------------------------------------

class TestInjectionRejected:
    def test_sql_injection_table_name_rejected(self, client, app):
        """Tabellenname mit SQL-Injection-Payload wird vor DB-Zugriff abgelehnt."""
        payload = "users; DROP TABLE users;--"
        r = client.get(
            f'/api/admin/db/users/{payload}',
            headers=_h(app, ['admin']),
        )
        # Validierung greift VOR jeglichem DB-Zugriff → 400 (oder 404 vom Router,
        # falls der Pfad gar nicht matched). Niemals 200/500.
        assert r.status_code in (400, 404), r.get_json()
        if r.status_code == 400:
            assert (r.get_json() or {}).get('error') == 'Invalid table name'

    def test_unknown_db_key_rejected(self, client, app):
        """Unbekannter DB-Key (Pfad-Traversal-Versuch) → 404, kein DB-Zugriff."""
        r = client.get(
            '/api/admin/db/__evil__/users',
            headers=_h(app, ['admin']),
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 2b. LDAP-Filter-Injection wird neutralisiert (reiner Unit-Test des Escapers)
# ---------------------------------------------------------------------------

def test_ldap_filter_injection_escaped():
    """`*)(uid=*`-Injection darf nach Escaping keine Filter-Metazeichen mehr roh
    enthalten (RFC 4515)."""
    from server.auth.ldap import escape_filter_chars

    raw = '*)(uid=*'
    escaped = escape_filter_chars(raw)
    # Kein rohes Sternchen / Klammern mehr → Injection neutralisiert.
    assert '*' not in escaped
    assert '(' not in escaped
    assert ')' not in escaped
