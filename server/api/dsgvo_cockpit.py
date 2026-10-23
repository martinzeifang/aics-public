"""DS2 (#1102) — REST-Blueprint für das Accountability-/DSMS-Cockpit (Art. 5 Abs. 2).

Neuer, additiver Bereich. Das Blueprint-Objekt wird hier nur erzeugt; die
Registrierung in ``server/app.py`` übernimmt der Integrator (mit url_prefix
``/api/dsgvo-cockpit``).

Reine Lese-/Aggregations-Schicht: Permission DSGVO_READ (Muster wie
``server/api/dsgvo.py``).
"""
from flask import Blueprint, current_app, request
from flask_jwt_extended import jwt_required

from server.models.permission import Permission, require_permission

from dsgvo.dsms_cockpit import DB_PATH, build_cockpit

dsgvo_cockpit_bp = Blueprint('dsgvo_cockpit', __name__)


def _log_error(e: Exception) -> None:
    current_app.logger.exception(
        '%s %s — %s: %s', request.method, request.path, type(e).__name__, e,
    )


@dsgvo_cockpit_bp.get('/projekte/<projekt_name>/dsms-cockpit')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_dsms_cockpit(projekt_name: str):
    """Bereichsübergreifende DSMS-Übersicht (Reifegrade + offene Aufgaben/Fristen)."""
    try:
        return build_cockpit(DB_PATH, projekt_name), 200
    except Exception as e:
        _log_error(e)
        return {'error': 'Interner Serverfehler'}, 500
