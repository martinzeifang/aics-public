"""DS8 (#1108) — REST-Blueprint für das Betroffenenrechte-Register (Art. 15-22).

Neuer, additiver Bereich. Das Blueprint-Objekt wird hier nur erzeugt; die
Registrierung in ``server/app.py`` übernimmt der Integrator (mit url_prefix
``/api/dsgvo-betroffenenrechte``).

Permission-Muster wie in ``server/api/dsgvo.py``: Lesen erfordert DSGVO_READ,
Schreiben DSGVO_WRITE.
"""
from pathlib import Path

from flask import Blueprint, current_app, request
from flask_jwt_extended import jwt_required

from server.models.permission import Permission, require_permission

from dsgvo.betroffenenrechte_db import (
    DB_PATH,
    TYPEN,
    STATUS,
    list_antraege,
    get_antrag,
    create_antrag,
    update_antrag,
    delete_antrag,
)

dsgvo_betroffenenrechte_bp = Blueprint('dsgvo_betroffenenrechte', __name__)


def _log_error(e: Exception) -> None:
    current_app.logger.exception(
        '%s %s — %s: %s', request.method, request.path, type(e).__name__, e,
    )


@dsgvo_betroffenenrechte_bp.get('/constants')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_constants():
    return {'typen': list(TYPEN), 'status': list(STATUS)}, 200


@dsgvo_betroffenenrechte_bp.get('/projekte/<projekt_name>/antraege')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_antraege(projekt_name: str):
    try:
        return list_antraege(DB_PATH, projekt_name), 200
    except Exception as e:
        _log_error(e)
        return {'error': 'Interner Serverfehler'}, 500


@dsgvo_betroffenenrechte_bp.post('/projekte/<projekt_name>/antraege')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def post_antrag(projekt_name: str):
    try:
        data = request.json or {}
        typ = (data.get('typ') or '').strip()
        eingang = (data.get('eingang_datum') or '').strip()
        if typ not in TYPEN:
            return {'error': f'Ungültiger Typ. Erlaubt: {", ".join(TYPEN)}'}, 400
        if not eingang:
            return {'error': 'Feld "eingang_datum" ist Pflicht'}, 400
        antrag = create_antrag(
            DB_PATH, projekt_name,
            typ=typ,
            eingang_datum=eingang,
            antrag_id=(data.get('antrag_id') or '').strip(),
            verlaengert=data.get('verlaengert', 0),
            identitaet_geprueft=data.get('identitaet_geprueft', 0),
            status=(data.get('status') or 'eingegangen'),
            bearbeiter=(data.get('bearbeiter') or ''),
            ergebnis=(data.get('ergebnis') or ''),
            notizen=(data.get('notizen') or ''),
        )
        return antrag, 201
    except ValueError as ve:
        return {'error': str(ve)}, 400
    except Exception as e:
        _log_error(e)
        return {'error': 'Interner Serverfehler'}, 500


@dsgvo_betroffenenrechte_bp.get('/antraege/<int:antrag_id>')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_one(antrag_id: int):
    try:
        antrag = get_antrag(DB_PATH, antrag_id)
        if antrag is None:
            return {'error': 'Antrag nicht gefunden'}, 404
        return antrag, 200
    except Exception as e:
        _log_error(e)
        return {'error': 'Interner Serverfehler'}, 500


@dsgvo_betroffenenrechte_bp.put('/antraege/<int:antrag_id>')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def put_antrag(antrag_id: int):
    try:
        data = request.json or {}
        antrag = update_antrag(DB_PATH, antrag_id, **data)
        if antrag is None:
            return {'error': 'Antrag nicht gefunden'}, 404
        return antrag, 200
    except ValueError as ve:
        return {'error': str(ve)}, 400
    except Exception as e:
        _log_error(e)
        return {'error': 'Interner Serverfehler'}, 500


@dsgvo_betroffenenrechte_bp.delete('/antraege/<int:antrag_id>')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def del_antrag(antrag_id: int):
    try:
        if not delete_antrag(DB_PATH, antrag_id):
            return {'error': 'Antrag nicht gefunden'}, 404
        return {'deleted': True}, 200
    except Exception as e:
        _log_error(e)
        return {'error': 'Interner Serverfehler'}, 500
