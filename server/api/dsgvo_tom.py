"""DSGVO DS3+DS4 (#1103/#1104) — TOM-Katalog REST-Blueprint.

Self-contained Area. Der Integrator registriert das Blueprint in ``server/app.py``
mit ``url_prefix='/api/dsgvo-tom'``.

Permission-Pattern wie ``server/api/dsgvo.py``: JWT pflicht; zusätzlich
modul-spezifische DSGVO-Permissions (read/write/export) via ``require_permission``.
"""
from flask import current_app, Blueprint, request

from flask_jwt_extended import jwt_required

from pathlib import Path

from server.models.permission import Permission, require_permission

from dsgvo import tom_katalog as tk

dsgvo_tom_bp = Blueprint('dsgvo_tom', __name__)

DB_PATH = Path('data/db/dsgvo.sqlite')


def _log_500(e: Exception):
    current_app.logger.exception(
        '%s %s — %s: %s', request.method, request.path, type(e).__name__, e
    )
    return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Konstanten / Ziel-Katalog
# ============================================================

@dsgvo_tom_bp.get('/ziele')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_ziele():
    """Die 7 SDM-Gewährleistungsziele + Seed-Übersicht."""
    try:
        seed_by_ziel: dict[str, list] = {z: [] for z in tk.ZIELE}
        for entry in tk.SEED_KATALOG:
            seed_by_ziel.setdefault(entry['ziel'], []).append({
                'massnahme_key': entry['massnahme_key'],
                'titel': entry['titel'],
                'beschreibung': entry['beschreibung'],
            })
        return {'ziele': tk.ZIELE, 'seed': seed_by_ziel}, 200
    except Exception as e:
        return _log_500(e)


# ============================================================
# Katalog je Projekt
# ============================================================

@dsgvo_tom_bp.get('/projekte/<projekt_name>/massnahmen')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_massnahmen(projekt_name: str):
    """Alle Katalog-Maßnahmen eines Projekts, gruppiert nach Ziel."""
    try:
        items = tk.list_massnahmen(DB_PATH, projekt_name)
        gruppen = []
        for ziel in tk.ZIELE:
            zg = [m for m in items if m['ziel'] == ziel]
            gruppen.append({'ziel': ziel, 'massnahmen': zg})
        bewertet = sum(1 for m in items if int(m['status']) > 0)
        return {
            'projekt': projekt_name,
            'items': items,
            'gruppen': gruppen,
            'gesamt': len(items),
            'bewertet': bewertet,
        }, 200
    except Exception as e:
        return _log_500(e)


@dsgvo_tom_bp.post('/projekte/<projekt_name>/seed')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def post_seed(projekt_name: str):
    """Standard-Maßnahmenkatalog einspielen (idempotent; ?force=1 aktualisiert Texte)."""
    try:
        data = request.json or {}
        force = bool(data.get('force')) or request.args.get('force') in ('1', 'true')
        inserted = tk.seed_projekt(DB_PATH, projekt_name, force=force)
        items = tk.list_massnahmen(DB_PATH, projekt_name)
        return {'inserted': inserted, 'gesamt': len(items), 'items': items}, 200
    except Exception as e:
        return _log_500(e)


@dsgvo_tom_bp.post('/projekte/<projekt_name>/massnahmen')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def upsert_massnahme(projekt_name: str):
    """Maßnahme anlegen oder aktualisieren (Upsert über massnahme_key)."""
    try:
        data = request.json or {}
        if not str(data.get('massnahme_key', '')).strip():
            return {'error': 'Feld "massnahme_key" ist Pflicht'}, 400
        try:
            saved = tk.upsert_massnahme(DB_PATH, projekt_name, data)
        except ValueError as ve:
            return {'error': str(ve)}, 400
        return saved, 200
    except Exception as e:
        return _log_500(e)


@dsgvo_tom_bp.get('/projekte/<projekt_name>/massnahmen/<massnahme_key>')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_one(projekt_name: str, massnahme_key: str):
    try:
        m = tk.get_massnahme(DB_PATH, projekt_name, massnahme_key)
        if not m:
            return {'error': 'Maßnahme nicht gefunden'}, 404
        return m, 200
    except Exception as e:
        return _log_500(e)


@dsgvo_tom_bp.delete('/projekte/<projekt_name>/massnahmen/<massnahme_key>')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def delete_one(projekt_name: str, massnahme_key: str):
    try:
        ok = tk.delete_massnahme(DB_PATH, projekt_name, massnahme_key)
        if not ok:
            return {'error': 'Maßnahme nicht gefunden'}, 404
        return {'deleted': massnahme_key}, 200
    except Exception as e:
        return _log_500(e)


# ============================================================
# Wirksamkeitsprüfung
# ============================================================

@dsgvo_tom_bp.post('/projekte/<projekt_name>/massnahmen/<massnahme_key>/wirksamkeit')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def post_wirksamkeit(projekt_name: str, massnahme_key: str):
    """Wirksamkeitsprüfung dokumentieren (Datum + Ergebnis, optional Status)."""
    try:
        if not tk.get_massnahme(DB_PATH, projekt_name, massnahme_key):
            return {'error': 'Maßnahme nicht gefunden'}, 404
        data = request.json or {}
        status = data.get('status')
        m = tk.set_wirksamkeit(
            DB_PATH,
            projekt_name,
            massnahme_key,
            datum=str(data.get('datum', '') or data.get('wirksamkeit_datum', '')),
            ergebnis=str(data.get('ergebnis', '') or data.get('wirksamkeit_ergebnis', '')),
            status=None if status is None else int(status),
        )
        return m or {'error': 'Maßnahme nicht gefunden'}, (200 if m else 404)
    except Exception as e:
        return _log_500(e)


# ============================================================
# KI-Vorschlag (Stub)
# ============================================================

@dsgvo_tom_bp.get('/projekte/<projekt_name>/ki-vorschlag')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_ki_vorschlag(projekt_name: str):
    """KI-Vorschlag-Stub: heuristische Empfehlungen je Ziel (#1104)."""
    try:
        return tk.ki_vorschlag(DB_PATH, projekt_name), 200
    except Exception as e:
        return _log_500(e)
