"""Zertifikats-Verwaltung (Web-Wizard) — Self-Signed-Generator + CSR für PKI.

Endpoints unter /api/admin/certificates (Permission admin:config):

  GET  /current               aktives Server-Zertifikat (Metadaten)
  GET  /suggest               Vorschlag Hostname + IPs des Servers (Wizard-Prefill)
  POST /self-signed/generate  Self-Signed-Cert erzeugen → cert_pem + key_pem + info
  POST /apply                 cert_pem + key_pem als aktives TLS-Zertifikat setzen
                              (schreibt ins Cert-Verzeichnis + best-effort nginx-Reload)
  POST /csr/generate          Schlüsselpaar + CSR erzeugen (für PKI), key serverseitig gehalten
  GET  /csr/pending           offene CSRs (deren signiertes Cert noch aussteht)
  POST /csr/import-signed      von PKI signiertes Cert hochladen (gegen Key prüfen)

Alle Krypto-Logik in shared/cert_tools.py.
"""

from __future__ import annotations

import json
import os
import shlex
import socket
import subprocess
import time
import uuid
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app

from server.models.permission import require_permission
from shared import cert_tools as ct

certificates_bp = Blueprint('certificates', __name__)

# Aktives TLS-Cert-Verzeichnis (Docker: /app/certs via CERT_DIR; lokal: ./certs)
_CERT_DIR = Path(os.getenv('CERT_DIR', 'certs'))
# Pending-CSR-Keys (privater Schlüssel bleibt serverseitig bis Signatur zurückkommt)
_PENDING_DIR = Path('data/certs/pending')
# Zertifikats-Store (alle erzeugten/importierten Certs zur Auswahl im Manager)
_STORE_DIR = Path('data/certs/store')


# #746: CERT_RELOAD_CMD ohne Shell ausführen (keine Shell-Injection). Das Kommando
# wird per shlex in eine Argumentliste zerlegt und mit shell=False ausgeführt.
def parse_reload_cmd(cmd: str) -> list[str]:
    """Zerlegt CERT_RELOAD_CMD in eine Argumentliste (POSIX-Quoting).

    Returns eine leere Liste, wenn nichts gesetzt ist. Niemals shell=True nutzen.
    """
    return shlex.split(cmd or '', posix=True)


def _audit(action: str, **details):
    try:
        from shared.audit import audit_event
        audit_event(action, module='certificates', details=details)
    except Exception:
        pass


# #742: Key-Verzeichnisse 0700, private Schlüssel at-rest verschlüsselt.
def _harden_key_dir(d: Path) -> None:
    try:
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o700)
    except OSError:
        pass


def _write_key_at_rest(path: Path, key_pem: bytes) -> None:
    """Schreibt einen privaten Schlüssel at-rest verschlüsselt (#742)."""
    from shared.crypto_at_rest import encrypt_field
    blob = encrypt_field(key_pem.decode('utf-8')).encode('ascii')
    path.write_bytes(blob)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _read_key_at_rest(path: Path) -> bytes:
    """Liest einen privaten Schlüssel; entschlüsselt at-rest, Fallback Klartext (#742)."""
    from shared.crypto_at_rest import decrypt_field
    raw = path.read_bytes()
    try:
        return decrypt_field(raw.decode('utf-8')).encode('utf-8')
    except Exception:
        return raw  # Bestands-Key im Klartext bleibt lesbar


# ─────────────────────────────────────────────────────────────────────────────
# Zertifikats-Store (persistente Ablage aller Zertifikate für den Manager)
# ─────────────────────────────────────────────────────────────────────────────

def _store_save(cert_pem: bytes, key_pem: bytes, source: str, label: str = '') -> str:
    """Legt cert+key im Store ab (idempotent per Fingerprint). Returns Store-ID."""
    _harden_key_dir(_STORE_DIR)  # #742: 0700
    info = ct.parse_cert_info(cert_pem)
    fp = info.get('sha256_fingerprint', '')
    # Duplikat-Schutz: gleicher Fingerprint → bestehende ID zurückgeben
    for meta_path in _STORE_DIR.glob('*.json'):
        try:
            m = json.loads(meta_path.read_text(encoding='utf-8'))
            if m.get('sha256_fingerprint') == fp:
                return m['id']
        except Exception:
            pass
    cid = uuid.uuid4().hex[:12]
    (_STORE_DIR / f'{cid}.crt').write_bytes(cert_pem)
    kp = _STORE_DIR / f'{cid}.key'
    _write_key_at_rest(kp, key_pem)  # #742: at-rest verschlüsselt
    meta = {
        'id': cid,
        'label': label or info.get('common_name', '') or cid,
        'source': source,  # self-signed | csr-signed | imported
        'common_name': info.get('common_name', ''),
        'sans': info.get('sans', []),
        'not_after': info.get('not_after', ''),
        'sha256_fingerprint': fp,
        'created_at': int(time.time()),
    }
    (_STORE_DIR / f'{cid}.json').write_text(json.dumps(meta), encoding='utf-8')
    return cid


def _store_list() -> list[dict]:
    out = []
    if _STORE_DIR.exists():
        for meta_path in _STORE_DIR.glob('*.json'):
            try:
                out.append(json.loads(meta_path.read_text(encoding='utf-8')))
            except Exception:
                pass
    return sorted(out, key=lambda x: x.get('created_at', 0), reverse=True)


def _store_entry(cid: str) -> dict | None:
    p = _STORE_DIR / f'{cid}.json'
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def _active_fingerprint() -> str:
    p = _active_cert_path()
    if not p:
        return ''
    try:
        return ct.parse_cert_info(p.read_bytes()).get('sha256_fingerprint', '')
    except Exception:
        return ''


# ─────────────────────────────────────────────────────────────────────────────
# Status / Vorschläge
# ─────────────────────────────────────────────────────────────────────────────

def _active_cert_path() -> Path | None:
    for name in ('certificate.crt', 'server.crt'):
        p = _CERT_DIR / name
        if p.exists():
            return p
    return None


@certificates_bp.get('/current')
@require_permission('admin:config')
def current_cert():
    p = _active_cert_path()
    if not p:
        return {'present': False}, 200
    try:
        info = ct.parse_cert_info(p.read_bytes())
        info['present'] = True
        info['path'] = str(p)
        return jsonify(info), 200
    except Exception as e:
        return {'present': True, 'error': f'Cert nicht lesbar: {e}'}, 200


@certificates_bp.get('/suggest')
@require_permission('admin:config')
def suggest():
    """Schlägt Hostname + lokale IPs des Servers vor (Wizard-Prefill)."""
    hostname = socket.gethostname()
    fqdn = socket.getfqdn()
    ips: list[str] = []
    try:
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ip not in ips and not ip.startswith('127.') and ip != '::1':
                ips.append(ip)
    except Exception:
        pass
    dns = [h for h in {hostname, fqdn} if h and h != 'localhost']
    return jsonify({'hostnames': sorted(dns), 'ip_addresses': ips}), 200


# ─────────────────────────────────────────────────────────────────────────────
# Self-Signed
# ─────────────────────────────────────────────────────────────────────────────

@certificates_bp.post('/self-signed/generate')
@require_permission('admin:config')
def self_signed_generate():
    data = request.get_json(silent=True) or {}
    sans = data.get('sans') or []
    dns, ips = ct.classify_san(sans)
    try:
        out = ct.generate_self_signed(
            common_name=(data.get('common_name') or '').strip(),
            dns_names=dns,
            ip_addresses=ips,
            validity_days=int(data.get('validity_days', 397)),  # #742: ~13 Monate
            key_size=int(data.get('key_size', 3072)),  # #742: secure default
        )
    except ValueError as e:
        return {'error': str(e)}, 400
    cid = _store_save(out['cert_pem'], out['key_pem'], source='self-signed',
                      label=(data.get('common_name') or '').strip())
    _audit('cert.self_signed.generated', cn=data.get('common_name'), store_id=cid)
    return jsonify({
        'store_id': cid,
        'cert_pem': out['cert_pem'].decode(),
        'key_pem': out['key_pem'].decode(),
        'info': ct.parse_cert_info(out['cert_pem']),
    }), 201


# ─────────────────────────────────────────────────────────────────────────────
# Anwenden (aktives TLS-Zertifikat setzen)
# ─────────────────────────────────────────────────────────────────────────────

@certificates_bp.post('/apply')
@require_permission('admin:config')
def apply_cert():
    """Schreibt cert_pem+key_pem als aktives TLS-Zertifikat + best-effort Reload.

    Schreibt beide Namenskonventionen (certificate.crt/private.key für lokalen
    Dev-Server, server.crt/server.key für nginx/Docker), damit es überall greift.
    """
    data = request.get_json(silent=True) or {}
    cert_pem = (data.get('cert_pem') or '').encode()
    key_pem = (data.get('key_pem') or '').encode()
    return _do_apply(cert_pem, key_pem)


def _do_apply(cert_pem: bytes, key_pem: bytes):
    """Gemeinsame Apply-Logik: validieren, ins Cert-Verzeichnis schreiben, reloaden."""
    if not cert_pem or not key_pem:
        return {'error': 'cert_pem und key_pem erforderlich'}, 400
    if not ct.is_valid_cert_pem(cert_pem):
        return {'error': 'cert_pem ist kein gültiges Zertifikat'}, 400
    if not ct.cert_matches_key(cert_pem, key_pem):
        return {'error': 'Zertifikat und privater Schlüssel passen nicht zusammen'}, 400

    try:
        _CERT_DIR.mkdir(parents=True, exist_ok=True)
        for cert_name, key_name in (('certificate.crt', 'private.key'), ('server.crt', 'server.key')):
            (_CERT_DIR / cert_name).write_bytes(cert_pem)
            kp = _CERT_DIR / key_name
            kp.write_bytes(key_pem)
            os.chmod(kp, 0o600)
    except Exception as e:
        return {'error': f'Schreiben fehlgeschlagen: {e}'}, 500

    # Best-effort Reload: optionaler Hook (z.B. "nginx -s reload" oder ein Skript)
    reload_argv = parse_reload_cmd(os.getenv('CERT_RELOAD_CMD', ''))
    reloaded = False
    reload_note = ''
    if reload_argv:
        try:
            # #746: shell=False + Argumentliste statt shell=True (keine Injection)
            subprocess.run(reload_argv, shell=False, check=True, timeout=20,
                           capture_output=True)
            reloaded = True
        except Exception as e:
            reload_note = f'Reload-Hook fehlgeschlagen: {e}'
    if not reloaded and not reload_note:
        reload_note = ('Zertifikat geschrieben. Damit es aktiv wird: nginx neu laden '
                       "bzw. Container/Dev-Server neu starten "
                       "(oder CERT_RELOAD_CMD setzen für automatischen Reload).")
    _audit('cert.applied', dir=str(_CERT_DIR), reloaded=reloaded)
    return jsonify({'applied': True, 'cert_dir': str(_CERT_DIR),
                    'reloaded': reloaded, 'note': reload_note}), 200


# ─────────────────────────────────────────────────────────────────────────────
# Zertifikatsmanager — Store auflisten / anwenden / löschen / importieren
# ─────────────────────────────────────────────────────────────────────────────

@certificates_bp.get('/store')
@require_permission('admin:config')
def store_list():
    """Alle gespeicherten Zertifikate + Markierung des aktiven."""
    active_fp = _active_fingerprint()
    items = _store_list()
    for it in items:
        it['active'] = bool(active_fp) and it.get('sha256_fingerprint') == active_fp
    return jsonify({'certificates': items, 'active_fingerprint': active_fp}), 200


@certificates_bp.get('/store/<cid>/download')
@require_permission('admin:config')
def store_download(cid: str):
    """Liefert das gespeicherte Zertifikat (PEM, nur Cert — kein Key)."""
    entry = _store_entry(cid)
    if not entry:
        return {'error': 'Zertifikat nicht gefunden'}, 404
    cert_pem = (_STORE_DIR / f'{cid}.crt').read_bytes()
    return jsonify({'cert_pem': cert_pem.decode(), 'info': entry}), 200


@certificates_bp.post('/store/<cid>/apply')
@require_permission('admin:config')
def store_apply(cid: str):
    """Wendet ein gespeichertes Zertifikat als aktives TLS-Zertifikat an."""
    entry = _store_entry(cid)
    if not entry:
        return {'error': 'Zertifikat nicht gefunden'}, 404
    cert_path = _STORE_DIR / f'{cid}.crt'
    key_path = _STORE_DIR / f'{cid}.key'
    if not cert_path.exists() or not key_path.exists():
        return {'error': 'Cert/Key-Datei fehlt im Store'}, 404
    _audit('cert.store.apply', store_id=cid, cn=entry.get('common_name'))
    return _do_apply(cert_path.read_bytes(), _read_key_at_rest(key_path))


@certificates_bp.delete('/store/<cid>')
@require_permission('admin:config')
def store_delete(cid: str):
    entry = _store_entry(cid)
    if not entry:
        return {'error': 'Zertifikat nicht gefunden'}, 404
    if _active_fingerprint() and entry.get('sha256_fingerprint') == _active_fingerprint():
        return {'error': 'Das aktive Zertifikat kann nicht gelöscht werden'}, 409
    for ext in ('crt', 'key', 'json'):
        (_STORE_DIR / f'{cid}.{ext}').unlink(missing_ok=True)
    _audit('cert.store.delete', store_id=cid)
    return jsonify({'deleted': True}), 200


@certificates_bp.post('/store/import')
@require_permission('admin:config')
def store_import():
    """Beliebiges Zertifikat + privaten Schlüssel in den Store importieren."""
    data = request.get_json(silent=True) or {}
    cert_pem = (data.get('cert_pem') or '').encode()
    key_pem = (data.get('key_pem') or '').encode()
    if not ct.is_valid_cert_pem(cert_pem):
        return {'error': 'Kein gültiges Zertifikat (PEM)'}, 400
    if not key_pem or not ct.cert_matches_key(cert_pem, key_pem):
        return {'error': 'Privater Schlüssel fehlt oder passt nicht zum Zertifikat'}, 400
    cid = _store_save(cert_pem, key_pem, source='imported',
                      label=(data.get('label') or '').strip())
    _audit('cert.store.import', store_id=cid)
    return jsonify({'store_id': cid}), 201


# ─────────────────────────────────────────────────────────────────────────────
# CSR (für PKI)
# ─────────────────────────────────────────────────────────────────────────────

@certificates_bp.post('/csr/generate')
@require_permission('admin:config')
def csr_generate():
    data = request.get_json(silent=True) or {}
    sans = data.get('sans') or []
    dns, ips = ct.classify_san(sans)
    try:
        out = ct.generate_csr(
            common_name=(data.get('common_name') or '').strip(),
            dns_names=dns, ip_addresses=ips,
            key_size=int(data.get('key_size', 3072)),  # #742: secure default
            organization=data.get('organization', ''),
            organizational_unit=data.get('organizational_unit', ''),
            country=data.get('country', ''),
            state=data.get('state', ''),
            locality=data.get('locality', ''),
            email=data.get('email', ''),
        )
    except ValueError as e:
        return {'error': str(e)}, 400

    # Privaten Schlüssel serverseitig vorhalten, damit das signierte Cert später
    # zugeordnet/angewendet werden kann.
    csr_id = uuid.uuid4().hex[:12]
    try:
        _harden_key_dir(_PENDING_DIR)  # #742: 0700
        kp = _PENDING_DIR / f'{csr_id}.key'
        _write_key_at_rest(kp, out['key_pem'])  # #742: at-rest verschlüsselt
        meta = {
            'id': csr_id,
            'common_name': (data.get('common_name') or '').strip(),
            'created_at': int(time.time()),
        }
        (_PENDING_DIR / f'{csr_id}.json').write_text(json.dumps(meta), encoding='utf-8')
    except Exception as e:
        current_app.logger.warning('CSR-Key-Persistenz fehlgeschlagen: %s', e)

    _audit('cert.csr.generated', id=csr_id, cn=data.get('common_name'))
    return jsonify({
        'csr_id': csr_id,
        'csr_pem': out['csr_pem'].decode(),
        'key_pem': out['key_pem'].decode(),
        'info': ct.parse_csr_info(out['csr_pem']),
    }), 201


@certificates_bp.get('/csr/pending')
@require_permission('admin:config')
def csr_pending():
    items = []
    if _PENDING_DIR.exists():
        for meta in sorted(_PENDING_DIR.glob('*.json')):
            try:
                items.append(json.loads(meta.read_text(encoding='utf-8')))
            except Exception:
                pass
    return jsonify({'pending': sorted(items, key=lambda x: x.get('created_at', 0), reverse=True)}), 200


@certificates_bp.post('/csr/import-signed')
@require_permission('admin:config')
def csr_import_signed():
    """Von PKI signiertes Cert hochladen. Schlüssel: entweder mitgeliefert (key_pem)
    oder per csr_id aus dem serverseitig vorgehaltenen Pending-Key.

    Returns Match-Status + cert-info; das eigentliche Anwenden erfolgt über /apply.
    """
    data = request.get_json(silent=True) or {}
    cert_pem = (data.get('cert_pem') or '').encode()
    if not ct.is_valid_cert_pem(cert_pem):
        return {'error': 'Kein gültiges Zertifikat (PEM erwartet)'}, 400

    key_pem = (data.get('key_pem') or '').encode()
    csr_id = (data.get('csr_id') or '').strip()
    pending_kp: Path | None = None
    if not key_pem and csr_id:
        kp = _PENDING_DIR / f'{csr_id}.key'
        if kp.exists():
            key_pem = _read_key_at_rest(kp)  # #742: entschlüsseln
            pending_kp = kp
    if not key_pem:
        return {'error': 'Privater Schlüssel fehlt (key_pem oder gültige csr_id)'}, 400

    if not ct.cert_matches_key(cert_pem, key_pem):
        return {'error': 'Das Zertifikat passt nicht zum privaten Schlüssel'}, 400

    info = ct.parse_cert_info(cert_pem)
    cid = _store_save(cert_pem, key_pem, source='csr-signed', label=info.get('common_name', ''))

    # #742: Pending-CSR-Key nach erfolgreichem Import löschen (kein verwaistes
    # privates Schlüsselmaterial). Der Key liegt jetzt at-rest verschlüsselt im Store.
    if pending_kp is not None:
        pending_kp.unlink(missing_ok=True)
        (_PENDING_DIR / f'{csr_id}.json').unlink(missing_ok=True)

    _audit('cert.csr.imported', cn=info.get('common_name'), csr_id=csr_id, store_id=cid)
    # #742: privaten Schlüssel NICHT in der API-Antwort zurückgeben.
    # Das Anwenden erfolgt serverseitig über /store/<id>/apply (Key bleibt im Store).
    return jsonify({'matches': True, 'info': info, 'store_id': cid,
                    'cert_pem': cert_pem.decode()}), 200
