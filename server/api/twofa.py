"""2-Faktor-Authentifizierung (TOTP) — Phase 7.3.

Endpoints für authentifizierte User, um TOTP zu aktivieren, zu deaktivieren
und Backup-Codes zu verwalten. Der eigentliche Login-Flow (2-stufig) ist
in `server/api/auth.py`.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.auth import totp
from server.auth.users_db import (
    get_user_by_id,
    get_totp_state,
    set_totp_secret,
    enable_totp,
    disable_totp,
    verify_password,
)

twofa_bp = Blueprint('twofa', __name__)


@twofa_bp.get('/status')
@jwt_required()
def status():
    """Status der 2FA für den aktuellen User."""
    user_id = get_jwt_identity()
    state = get_totp_state(user_id)
    return jsonify({
        'enabled': state['enabled'],
        'backup_codes_remaining': len(state['backup_code_hashes']),
    }), 200


@twofa_bp.post('/setup')
@jwt_required()
def setup():
    """Erzeugt ein neues TOTP-Secret + QR-Code für den aktuellen User.

    Aktiviert 2FA **noch nicht** — User muss anschließend `/verify` mit
    einem gültigen Code aufrufen. Bestehende, aber inaktive Secrets
    werden überschrieben (gewollt: neuer Setup-Versuch).
    """
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    if not user:
        return {'error': 'User not found'}, 404

    state = get_totp_state(user_id)
    if state['enabled']:
        return {'error': '2FA ist bereits aktiviert. Bitte zuerst deaktivieren.'}, 409

    secret = totp.generate_secret()
    set_totp_secret(user_id, secret)
    uri = totp.provisioning_uri(secret, user['email'])
    qr = totp.qr_code_png_data_url(uri)

    return jsonify({
        'secret': secret,
        'otpauth_uri': uri,
        'qr_code_data_url': qr,
    }), 200


@twofa_bp.post('/verify')
@jwt_required()
def verify():
    """Verifiziert einen TOTP-Code und aktiviert 2FA endgültig.

    Body: { "code": "123456" }
    Antwort enthält die Backup-Codes (einmalig sichtbar).
    """
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    code = str(data.get('code', '')).strip()

    state = get_totp_state(user_id)
    if state['enabled']:
        return {'error': '2FA ist bereits aktiviert'}, 409
    if not state['secret']:
        return {'error': 'Kein Setup gestartet — bitte zuerst /setup aufrufen'}, 400
    if not totp.verify_code(state['secret'], code):
        return {'error': 'Code ungültig oder abgelaufen'}, 400

    backup_codes = totp.generate_backup_codes()
    hashes = totp.hash_backup_codes(backup_codes)
    enable_totp(user_id, hashes)

    return jsonify({
        'enabled': True,
        'backup_codes': backup_codes,  # Nur hier einmalig im Klartext
    }), 200


@twofa_bp.post('/disable')
@jwt_required()
def disable():
    """Deaktiviert 2FA. Erfordert aktuelles Passwort + (falls aktiv) gültigen Code.

    Body: { "password": "...", "code": "123456" (optional Backup-Code) }
    """
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    if not user:
        return {'error': 'User not found'}, 404

    data = request.get_json() or {}
    password = str(data.get('password', ''))
    code = str(data.get('code', '')).strip()

    if not verify_password(user, password):
        return {'error': 'Passwort ist nicht korrekt'}, 401

    state = get_totp_state(user_id)
    if not state['enabled']:
        return jsonify({'enabled': False}), 200

    # 2FA-Code prüfen (TOTP oder Backup-Code)
    ok = totp.verify_code(state['secret'] or '', code)
    if not ok:
        matched, _ = totp.consume_backup_code(state['backup_code_hashes'], code)
        ok = matched
    if not ok:
        return {'error': 'Ungültiger Authenticator-Code'}, 400

    disable_totp(user_id)
    return jsonify({'enabled': False}), 200


@twofa_bp.post('/regenerate-backup-codes')
@jwt_required()
def regenerate_backup_codes():
    """Erzeugt neue Backup-Codes. Erfordert aktuellen TOTP-Code.

    Body: { "code": "123456" }
    """
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    code = str(data.get('code', '')).strip()

    state = get_totp_state(user_id)
    if not state['enabled']:
        return {'error': '2FA ist nicht aktiviert'}, 400
    if not totp.verify_code(state['secret'] or '', code):
        return {'error': 'Code ungültig'}, 400

    new_codes = totp.generate_backup_codes()
    new_hashes = totp.hash_backup_codes(new_codes)
    enable_totp(user_id, new_hashes)  # ersetzt die Hashes
    return jsonify({'backup_codes': new_codes}), 200
