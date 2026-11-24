"""Tests für Issue #746 (WP-13: Housekeeping & kleinere Härtungen).

Deckt die backend-testbaren Punkte ab:
  (a) Das umbenannte Modul ``server.api.workspace_tmp`` importiert und
      ``workspace_tmpdir`` funktioniert weiterhin.
  (b) ``/api/auth/webauthn/debug`` erfordert admin:config und ist in
      FLASK_ENV=production deaktiviert.
  (c) Das Parsen von CERT_RELOAD_CMD liefert eine Argumentliste (shell=False).
"""

import os

import pytest


@pytest.fixture(autouse=True)
def _full_license():
    """Schreibzugriffe auf lizenzierte Module sonst → 423 in CI."""
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


# ─────────────────────────────────────────────────────────────────────────────
# (a) Umbenanntes Modul
# ─────────────────────────────────────────────────────────────────────────────

def test_workspace_tmp_module_renamed_and_importable():
    """Das neue Modul ist importierbar; das alte gibt es nicht mehr."""
    from server.api import workspace_tmp
    assert hasattr(workspace_tmp, 'workspace_tmpdir')

    import importlib
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module('server.api._tmp')


def test_workspace_tmpdir_still_works(tmp_path, monkeypatch):
    """workspace_tmpdir legt weiterhin ein temporäres Verzeichnis an."""
    monkeypatch.setenv('AICS_TMP_DIR', str(tmp_path))
    from server.api.workspace_tmp import workspace_tmpdir
    d = workspace_tmpdir('test_746_')
    assert d.exists() and d.is_dir()
    assert d.name.startswith('test_746_')
    assert str(d).startswith(str(tmp_path))


def test_importers_use_new_module_name():
    """Die bekannten Importer beziehen workspace_tmpdir aus dem neuen Modul."""
    from server.api import risikobewertung
    # gleiches Funktionsobjekt wie im umbenannten Modul
    from server.api.workspace_tmp import workspace_tmpdir as canonical
    assert risikobewertung.workspace_tmpdir is canonical


# ─────────────────────────────────────────────────────────────────────────────
# (b) /webauthn/debug — Permission + Produktions-Gate
# ─────────────────────────────────────────────────────────────────────────────

DEBUG_URL = '/api/auth/webauthn/debug'


def test_webauthn_debug_requires_auth(client):
    """Ohne Token kein Zugriff."""
    resp = client.get(DEBUG_URL)
    assert resp.status_code in (401, 422)


def test_webauthn_debug_forbidden_for_non_admin(client):
    """Editor (ohne admin:config) → 403."""
    login = client.post(
        '/api/auth/login',
        json={'email': 'editor@example.com', 'password': 'editor-password'},
    )
    assert login.status_code == 200, login.json
    token = login.json['access_token']
    resp = client.get(DEBUG_URL, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 403


def test_webauthn_debug_ok_for_admin(client, auth_headers):
    """Admin (admin:config) darf zugreifen (außerhalb production)."""
    resp = client.get(DEBUG_URL, headers=auth_headers)
    assert resp.status_code == 200
    assert 'effective_rp_id' in resp.json


def test_webauthn_debug_blocked_in_production(client, auth_headers, monkeypatch):
    """In FLASK_ENV=production ist der Debug-Endpoint deaktiviert (404)."""
    monkeypatch.setenv('FLASK_ENV', 'production')
    resp = client.get(DEBUG_URL, headers=auth_headers)
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# (c) CERT_RELOAD_CMD — Argumentliste statt shell=True
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_reload_cmd_returns_arg_list():
    from server.api.certificates import parse_reload_cmd
    argv = parse_reload_cmd('nginx -s reload')
    assert argv == ['nginx', '-s', 'reload']
    assert isinstance(argv, list)


def test_parse_reload_cmd_empty():
    from server.api.certificates import parse_reload_cmd
    assert parse_reload_cmd('') == []
    assert parse_reload_cmd(None) == []


def test_parse_reload_cmd_quoting_no_shell_injection():
    """Quoting wird respektiert; ein Semikolon ist NUR Argumenttext, kein
    Shell-Separator (es wird shell=False mit dieser Liste ausgeführt)."""
    from server.api.certificates import parse_reload_cmd
    argv = parse_reload_cmd("systemctl reload 'my service'")
    assert argv == ['systemctl', 'reload', 'my service']
    # Ein injizierter Befehl bleibt ein einzelnes Argument-Token, keine 2 Kommandos.
    argv2 = parse_reload_cmd("echo 'a; rm -rf /'")
    assert argv2 == ['echo', 'a; rm -rf /']


def test_certificates_module_uses_shell_false():
    """Quellcode-Smoke: subprocess wird mit shell=False ausgeführt."""
    import server.api.certificates as mod
    src = open(mod.__file__, encoding='utf-8').read()
    # Der echte subprocess.run-Aufruf nutzt shell=False (kein shell=True-Call).
    assert 'shell=False' in src
    assert 'shell=True,' not in src
    assert 'shell=True)' not in src
