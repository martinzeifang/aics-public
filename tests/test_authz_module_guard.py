"""Tests für den zentralen Modul-Autorisierungs-Guard (#734 / WP-01).

Stellt sicher, dass das RBAC-Modell serverseitig durchgesetzt wird:
- read/write/export-Aktionen erfordern die passende Permission,
- Modul-Whitelist (allowed_modules) wird erzwungen,
- Nicht-authentifizierte Requests werden abgelehnt.
"""

from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token

from server.models.permission import resolve_permissions, allowed_modules_for


def _token(app, roles):
    with app.app_context():
        perms = resolve_permissions(roles, [])
        mods = allowed_modules_for(roles, [], None)
        return create_access_token(
            identity='u-test',
            additional_claims={'roles': roles, 'permissions': perms,
                               'extra_permissions': [], 'allowed_modules': mods},
            expires_delta=timedelta(hours=1),
        )


def _h(app, roles):
    return {'Authorization': f'Bearer {_token(app, roles)}'}


class TestModuleAuthz:
    def test_unauthenticated_blocked(self, client):
        assert client.get('/api/cra/projekte').status_code in (401, 422)

    def test_admin_full_read(self, client, app):
        assert client.get('/api/cra/projekte', headers=_h(app, ['admin'])).status_code == 200

    def test_viewer_can_read(self, client, app):
        assert client.get('/api/risikobewertung/projekte', headers=_h(app, ['viewer'])).status_code == 200

    def test_viewer_cannot_write(self, client, app):
        # viewer hat kein risikobewertung:write → POST muss 403 sein
        r = client.post('/api/risikobewertung/projekte', headers=_h(app, ['viewer']), json={})
        assert r.status_code == 403
        assert r.get_json().get('required') == 'risikobewertung:write'

    def test_module_isolation_read(self, client, app):
        # cra_editor darf NICHT auf nis2 zugreifen
        r = client.get('/api/nis2/projekte', headers=_h(app, ['cra_editor']))
        assert r.status_code == 403

    def test_module_isolation_write(self, client, app):
        r = client.post('/api/gutachten/projekte', headers=_h(app, ['cra_editor']), json={})
        assert r.status_code == 403

    def test_module_editor_own_module_passes_guard(self, client, app):
        # cra_editor auf cra: Guard lässt durch (Status nicht 401/403)
        r = client.get('/api/cra/projekte', headers=_h(app, ['cra_editor']))
        assert r.status_code == 200

    def test_kunden_viewer_write_blocked(self, client, app):
        # 'viewer' hat kunden:read aber nicht kunden:write
        r = client.post('/api/kunden', headers=_h(app, ['viewer']), json={'name': 'x'})
        assert r.status_code == 403

    def test_admin_can_write(self, client, app):
        # admin: Guard lässt POST durch (nicht 401/403; 400/200/422 = Guard ok)
        r = client.post('/api/risikobewertung/projekte', headers=_h(app, ['admin']), json={})
        assert r.status_code not in (401, 403)
