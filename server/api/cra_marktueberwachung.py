"""CRA Art. 52-56 — Register der Marktüberwachungsvorgänge (#1762).

REST-Blueprint ``/api/cra-marktueberwachung``. Der Bindestrich-Prefix führt den
zentralen Guard auf Modul ``cra`` (#1169); der Projektparameter heißt
``projekt_name``, weil die Firmen-ACL danach greift.

Fachliches siehe ``cra/marktueberwachung_db.py``: Hier liegt der Fall, in dem
**die Behörde** aktiv wird — ``cra/korrektur_db.py`` deckt den umgekehrten ab.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from server.api._common import require_projekt
from server.models.permission import Permission, require_permission

from cra import marktueberwachung_db as mdb
from cra.db import load_projekt

cra_marktueberwachung_bp = Blueprint("cra_marktueberwachung", __name__)
DB_PATH = Path("data/db/cra.sqlite")


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


def _audit(action: str, **fields):
    try:
        from shared.audit import audit_event
        fields.setdefault("actor", str(get_jwt_identity() or ""))
        audit_event(action, module="cra", details=fields)
    except Exception:  # noqa: BLE001
        pass


@cra_marktueberwachung_bp.get("/constants")
@jwt_required()
@require_permission(Permission.CRA_READ)
def constants():
    """Vorgangsarten und Stände — Single Source of Truth bleibt die DB-Schicht."""
    return jsonify({"vorgangsarten": list(mdb.VORGANGSARTEN),
                    "status": list(mdb.STATUS),
                    "ergebnis_min_zeichen": mdb.ERGEBNIS_MIN_ZEICHEN})


@cra_marktueberwachung_bp.get("/projekte/<projekt_name>/vorgaenge")
@jwt_required()
@require_permission(Permission.CRA_READ)
def list_vorgaenge(projekt_name):
    try:
        return jsonify(mdb.list_vorgaenge(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@cra_marktueberwachung_bp.get("/projekte/<projekt_name>/uebersicht")
@jwt_required()
@require_permission(Permission.CRA_READ)
def uebersicht(projekt_name):
    """Kennzahlen: laufend, versäumt, nächste Frist — für Panel und Ampel."""
    try:
        return jsonify(mdb.uebersicht(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@cra_marktueberwachung_bp.post("/projekte/<projekt_name>/vorgaenge")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def create_vorgang(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        pk = mdb.create_vorgang(DB_PATH, projekt_name, body)
        _audit("cra.marktaufsicht.erstellt", object_id=str(pk), projekt=projekt_name,
               vorgangsart=body.get("vorgangsart"),
               behoerde=body.get("behoerde_name"))
        return jsonify(mdb.get_vorgang(DB_PATH, pk, projekt_name)), 201
    except ValueError as e:
        # Pflichtangaben werden serverseitig erzwungen; der Text nennt, was
        # fehlt und warum, und geht unverändert ans Formular.
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@cra_marktueberwachung_bp.get("/projekte/<projekt_name>/vorgaenge/<int:pk>")
@jwt_required()
@require_permission(Permission.CRA_READ)
def get_vorgang(projekt_name, pk):
    v = mdb.get_vorgang(DB_PATH, pk, projekt_name)
    if not v:
        return jsonify({"error": "Vorgang nicht gefunden"}), 404
    return jsonify(v)


@cra_marktueberwachung_bp.put("/projekte/<projekt_name>/vorgaenge/<int:pk>")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def update_vorgang(projekt_name, pk):
    body = request.get_json(silent=True) or {}
    try:
        v = mdb.update_vorgang(DB_PATH, pk, projekt_name, body)
        if not v:
            return jsonify({"error": "Vorgang nicht gefunden"}), 404
        _audit("cra.marktaufsicht.aktualisiert", object_id=str(pk),
               projekt=projekt_name)
        return jsonify(v)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@cra_marktueberwachung_bp.post("/projekte/<projekt_name>/vorgaenge/<int:pk>/status")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def set_status(projekt_name, pk):
    body = request.get_json(silent=True) or {}
    try:
        v = mdb.set_status(DB_PATH, pk, projekt_name, body.get("status", ""))
        if not v:
            return jsonify({"error": "Vorgang nicht gefunden"}), 404
        _audit("cra.marktaufsicht.status_gewechselt", object_id=str(pk),
               projekt=projekt_name, status=body.get("status"))
        return jsonify(v)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@cra_marktueberwachung_bp.post("/projekte/<projekt_name>/vorgaenge/<int:pk>/unterlagen")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def add_unterlage(projekt_name, pk):
    """Eine der Behörde bereitgestellte Unterlage festhalten."""
    body = request.get_json(silent=True) or {}
    try:
        v = mdb.add_unterlage(DB_PATH, pk, projekt_name, body.get("titel", ""),
                              ref=body.get("ref", ""),
                              uebergeben_am=body.get("uebergeben_am", ""))
        if not v:
            return jsonify({"error": "Vorgang nicht gefunden"}), 404
        _audit("cra.marktaufsicht.unterlage", object_id=str(pk),
               projekt=projekt_name, titel=body.get("titel"))
        return jsonify(v)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@cra_marktueberwachung_bp.delete("/projekte/<projekt_name>/vorgaenge/<int:pk>")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def delete_vorgang(projekt_name, pk):
    try:
        if not mdb.delete_vorgang(DB_PATH, pk, projekt_name):
            return jsonify({"error": "Vorgang nicht gefunden"}), 404
        _audit("cra.marktaufsicht.geloescht", object_id=str(pk), projekt=projekt_name)
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)
