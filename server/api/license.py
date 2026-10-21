"""License-API für AICS-Web (Issues #367/#368).

- GET  /api/license/status     — aktueller Lizenz-State
- POST /api/license/activate   — Aktivierung mit License-Key
- POST /api/license/deactivate — Aktivierung am Server zurückgeben
- POST /api/license/import     — Offline-License-Datei hochladen (.aics-license)
- POST /api/license/offline-request — Request-Datei generieren für Offline-Flow
"""

from __future__ import annotations

import json
from datetime import datetime

from flask import Blueprint, jsonify, request, Response
from flask_jwt_extended import jwt_required

from server.license_state import get_state, _apply_token
from server.models.permission import require_permission

license_bp = Blueprint('license', __name__)


@license_bp.get('/status')
@jwt_required()
def status():
    return jsonify(get_state().to_dict()), 200


@license_bp.post('/activate')
@require_permission('admin:config')
def activate():
    """Aktiviert mit einem License-Key beim Lizenzserver."""
    from shared.licensing import (
        get_client_config, LicenseClient, save_cached_token, LicenseClientError,
    )

    data = request.get_json(silent=True) or {}
    key = str(data.get('license_key') or '').strip()

    cfg = get_client_config(app_version='aics-web 1.0')
    client = LicenseClient(cfg=cfg)
    try:
        result = client.activate(key)
    except LicenseClientError as e:
        return {'error': e.code or 'activation-failed', 'message': str(e)}, e.http_status or 502

    token = result.get('token') or ''
    save_cached_token(cfg, token)
    _apply_token(token)
    return jsonify(get_state().to_dict()), 200


@license_bp.post('/refresh')
@require_permission('admin:config')
def refresh():
    """Manueller Heartbeat — direkt vom Lizenzserver aktuelle Claims holen (#409).

    Nach Demo→Voll-Umwandlung oder Modul-/Plan-Änderung am Lizenzserver
    sind die neuen Felder sofort verfügbar, ohne 6h auf den nächsten
    automatischen Heartbeat zu warten.
    """
    from shared.licensing import (
        get_client_config, LicenseClient, save_cached_token, LicenseClientError,
    )
    state_before = get_state().to_dict()
    state = get_state()
    if not state.token:
        return {'error': 'no-token', 'message': 'Keine aktive Lizenz — bitte erst aktivieren.'}, 400
    cfg = get_client_config(app_version='aics-web 1.0')
    try:
        result = LicenseClient(cfg=cfg).heartbeat(state.token)
    except LicenseClientError as e:
        return {'error': e.code or 'refresh-failed', 'message': str(e)}, e.http_status or 502

    new_token = result.get('token') or state.token
    if new_token != state.token:
        save_cached_token(cfg, new_token)
        _apply_token(new_token)
    state_after = get_state().to_dict()

    # Diff für UI-Feedback
    changes = {}
    for key in ('plan', 'modules', 'expires_at', 'customer', 'license_key', 'max_users', 'read_only'):
        if state_before.get(key) != state_after.get(key):
            changes[key] = {'from': state_before.get(key), 'to': state_after.get(key)}

    return jsonify({
        'state': state_after,
        'changes': changes,
        'token_renewed': new_token != state_before.get('token'),
    }), 200


@license_bp.post('/deactivate')
@require_permission('admin:config')
def deactivate():
    from shared.licensing import (
        get_client_config, LicenseClient, delete_cached_token, LicenseClientError,
    )
    state = get_state()
    if not state.token:
        return {'error': 'no-token'}, 400
    cfg = get_client_config(app_version='aics-web 1.0')
    try:
        LicenseClient(cfg=cfg).deactivate(state.token)
    except LicenseClientError as e:
        return {'error': e.code or 'deactivation-failed', 'message': str(e)}, e.http_status or 502
    delete_cached_token(cfg)
    _apply_token('')
    return jsonify(get_state().to_dict()), 200


@license_bp.post('/import')
@require_permission('admin:config')
def import_offline():
    """Importiert eine `.aics-license`-Datei (signed JSON mit `token`-Feld)."""
    from shared.licensing import get_client_config, save_cached_token

    f = request.files.get('file')
    if not f:
        return {'error': 'no-file'}, 400
    try:
        payload = json.loads(f.read().decode('utf-8'))
    except Exception as e:
        return {'error': f'json-parse: {e}'}, 400

    token = payload.get('token') or payload.get('access_token') or ''
    if not token:
        return {'error': 'kein-token-in-datei'}, 400

    cfg = get_client_config(app_version='aics-web 1.0')
    save_cached_token(cfg, token)
    _apply_token(token)
    return jsonify(get_state().to_dict()), 200


@license_bp.get('/server-config')
@require_permission('admin:config')
def get_server_config():
    """Liefert aktuelle Lizenz-Server-URL + TLS-Settings."""
    from shared.licensing.config import get_client_config, load_settings
    cfg = get_client_config()
    file_overrides = load_settings()
    return jsonify({
        'server_url': cfg.server_url,
        'verify_tls': cfg.verify_tls,
        'request_timeout': cfg.request_timeout,
        'has_file_override': bool(file_overrides),
    }), 200


@license_bp.put('/server-config')
@require_permission('admin:config')
def set_server_config():
    """Speichert eine neue Lizenz-Server-URL persistent.

    Body: { server_url, verify_tls?, request_timeout? }
    Reachability-Probe: ein /health-Call gegen die neue URL — schlägt das fehl,
    wird trotzdem gespeichert, aber im Response markiert.
    """
    import requests as _requests
    from shared.licensing.config import save_settings, get_client_config

    data = request.get_json(silent=True) or {}
    url = str(data.get('server_url') or '').strip()
    if not url.startswith(('http://', 'https://')):
        return {'error': 'server_url muss mit http(s):// beginnen'}, 400
    # #1176: TLS-Verify secure-by-default (True) — konsistent zu #1172.
    verify_tls = bool(data.get('verify_tls', True))
    timeout = int(data.get('request_timeout', 15))
    if timeout < 1 or timeout > 120:
        return {'error': 'request_timeout muss zwischen 1 und 120 liegen'}, 400

    # Probe (best-effort, blockiert Save nicht).
    # #1176 SSRF-Härtung: Der Lizenz-Server darf bewusst im Intranet liegen, daher
    # KEINE RFC1918-Blockade — aber Redirects werden NICHT verfolgt, damit ein
    # bösartiger /health-Endpoint die Probe nicht auf interne Ziele umlenken kann.
    reachable = False
    probe_error = ''
    try:
        r = _requests.get(f'{url.rstrip("/")}/health',
                          timeout=min(timeout, 5), verify=verify_tls,
                          allow_redirects=False)
        reachable = (r.status_code == 200)
        if not reachable:
            probe_error = f'HTTP {r.status_code}'
    except Exception as e:  # noqa: BLE001
        probe_error = f'{type(e).__name__}: {e}'

    path = save_settings(url, verify_tls=verify_tls, request_timeout=timeout)

    cfg = get_client_config()
    return jsonify({
        'ok': True,
        'saved_to': str(path),
        'server_url': cfg.server_url,
        'verify_tls': cfg.verify_tls,
        'reachable': reachable,
        'probe_error': probe_error,
    }), 200


@license_bp.post('/offline-request')
@require_permission('admin:config')
def offline_request():
    """Generiert eine `.aics-request.json`-Datei zum Download.

    Body: { license_key: str }
    """
    from shared.licensing import get_client_config, LicenseClient

    data = request.get_json(silent=True) or {}
    key = str(data.get('license_key') or '').strip()
    if not key:
        return {'error': 'license_key fehlt'}, 400

    cfg = get_client_config(app_version='aics-web 1.0')
    payload = LicenseClient(cfg=cfg).build_offline_request(key)

    filename = f'aics-request-{datetime.utcnow().strftime("%Y%m%d-%H%M%S")}.aics-request.json'
    return Response(
        json.dumps(payload, indent=2, ensure_ascii=False),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
