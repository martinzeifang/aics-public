"""DS12 (#1112) — REST-Blueprint für die DSB-Verwaltung (Art. 37-39 DSGVO).

Neuer, additiver Bereich. Das Blueprint-Objekt wird hier nur erzeugt; die
Registrierung in ``server/app.py`` übernimmt der Integrator (mit url_prefix
``/api/dsgvo-dsb``).

Permission-Muster wie in ``server/api/dsgvo.py``: Lesen erfordert DSGVO_READ,
Schreiben DSGVO_WRITE.

Pro Projekt existiert i. d. R. genau ein DSB-Datensatz (Upsert).
"""
from flask import Blueprint, current_app, request
from flask_jwt_extended import jwt_required

from server.models.permission import Permission, require_permission

from dsgvo.dsb_db import (
    DB_PATH,
    TYPEN,
    get_dsb,
    upsert_dsb,
    delete_dsb,
)

dsgvo_dsb_bp = Blueprint('dsgvo_dsb', __name__)


def _log_error(e: Exception) -> None:
    current_app.logger.exception(
        '%s %s — %s: %s', request.method, request.path, type(e).__name__, e,
    )


@dsgvo_dsb_bp.get('/constants')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_constants():
    return {'typen': list(TYPEN)}, 200


@dsgvo_dsb_bp.get('/projekte/<projekt_name>/dsb')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_projekt_dsb(projekt_name: str):
    """Liefert den DSB-Datensatz eines Projekts (oder ``null``)."""
    try:
        return {'dsb': get_dsb(DB_PATH, projekt_name)}, 200
    except Exception as e:
        _log_error(e)
        return {'error': 'Interner Serverfehler'}, 500


@dsgvo_dsb_bp.put('/projekte/<projekt_name>/dsb')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def put_projekt_dsb(projekt_name: str):
    """Legt den DSB-Datensatz an oder aktualisiert ihn (Upsert)."""
    try:
        data = request.json or {}
        typ = data.get('typ')
        if typ is not None and typ not in TYPEN:
            return {'error': f'Ungültiger Typ. Erlaubt: {", ".join(TYPEN)}'}, 400
        dsb = upsert_dsb(
            DB_PATH, projekt_name,
            typ=data.get('typ'),
            name=data.get('name'),
            bestelldatum=data.get('bestelldatum'),
            kontakt_email=data.get('kontakt_email'),
            kontakt_veroeffentlicht=data.get('kontakt_veroeffentlicht'),
            gemeldet_aufsicht=data.get('gemeldet_aufsicht'),
            aufgaben_nachweis=data.get('aufgaben_nachweis'),
            taetigkeitsbericht=data.get('taetigkeitsbericht'),
            notizen=data.get('notizen'),
        )
        return {'dsb': dsb}, 200
    except ValueError as ve:
        return {'error': str(ve)}, 400
    except Exception as e:
        _log_error(e)
        return {'error': 'Interner Serverfehler'}, 500


@dsgvo_dsb_bp.delete('/projekte/<projekt_name>/dsb')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def del_projekt_dsb(projekt_name: str):
    try:
        if not delete_dsb(DB_PATH, projekt_name):
            return {'error': 'Kein DSB-Datensatz vorhanden'}, 404
        return {'deleted': True}, 200
    except Exception as e:
        _log_error(e)
        return {'error': 'Interner Serverfehler'}, 500
