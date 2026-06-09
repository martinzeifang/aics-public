"""CRA Art. 13(19)-(22) — Korrekturmaßnahmen-/Rückruf-Workflow (#1202).

REST-Blueprint ``/api/cra-korrektur``. Bindestrich-Prefix → cra-Authz-Guard (#1169).
IDOR-sicher (projekt-scoped Routen). Behörden-Informations-Record + Audit-Trail.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission
from server.api._common import require_projekt

from cra.db import load_projekt
from cra import korrektur_db as kdb

cra_korrektur_bp = Blueprint("cra_korrektur", __name__)
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


@cra_korrektur_bp.get("/constants")
@jwt_required()
@require_permission(Permission.CRA_READ)
def constants():
    return jsonify({"typen": list(kdb.TYPEN), "status": list(kdb.STATUS)})


@cra_korrektur_bp.get("/projekte/<projekt_name>/korrekturmassnahmen")
@jwt_required()
@require_permission(Permission.CRA_READ)
def list_korrektur(projekt_name):
    try:
        return jsonify(kdb.list_korrektur(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@cra_korrektur_bp.post("/projekte/<projekt_name>/korrekturmassnahmen")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def create_korrektur(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        pk = kdb.create_korrektur(DB_PATH, projekt_name, body)
        _audit("cra.korrektur.erstellt", object_id=str(pk), projekt=projekt_name,
               typ=body.get("massnahmentyp"))
        return jsonify(kdb.get_korrektur(DB_PATH, pk, projekt_name)), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@cra_korrektur_bp.get("/projekte/<projekt_name>/korrekturmassnahmen/<int:pk>")
@jwt_required()
@require_permission(Permission.CRA_READ)
def get_korrektur(projekt_name, pk):
    k = kdb.get_korrektur(DB_PATH, pk, projekt_name)
    if not k:
        return jsonify({"error": "Korrekturmaßnahme nicht gefunden"}), 404
    return jsonify(k)


@cra_korrektur_bp.put("/projekte/<projekt_name>/korrekturmassnahmen/<int:pk>")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def update_korrektur(projekt_name, pk):
    body = request.get_json(silent=True) or {}
    try:
        k = kdb.update_korrektur(DB_PATH, pk, projekt_name, body)
        if not k:
            return jsonify({"error": "Korrekturmaßnahme nicht gefunden"}), 404
        _audit("cra.korrektur.aktualisiert", object_id=str(pk), projekt=projekt_name)
        return jsonify(k)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@cra_korrektur_bp.post("/projekte/<projekt_name>/korrekturmassnahmen/<int:pk>/behoerde")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def inform_behoerde(projekt_name, pk):
    body = request.get_json(silent=True) or {}
    try:
        k = kdb.inform_behoerde(DB_PATH, pk, projekt_name,
                                body.get("behoerde_name", ""), body.get("datum", ""))
        if not k:
            return jsonify({"error": "Korrekturmaßnahme nicht gefunden"}), 404
        _audit("cra.korrektur.behoerde_informiert", object_id=str(pk),
               projekt=projekt_name)
        return jsonify(k)
    except Exception as e:
        return _log_500(e)


@cra_korrektur_bp.post("/projekte/<projekt_name>/korrekturmassnahmen/<int:pk>/status")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def set_status(projekt_name, pk):
    body = request.get_json(silent=True) or {}
    try:
        k = kdb.set_status(DB_PATH, pk, projekt_name, body.get("status", ""))
        _audit("cra.korrektur.status_gewechselt", object_id=str(pk),
               projekt=projekt_name, status=body.get("status"))
        return jsonify(k)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@cra_korrektur_bp.delete("/projekte/<projekt_name>/korrekturmassnahmen/<int:pk>")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def delete_korrektur(projekt_name, pk):
    try:
        if not kdb.delete_korrektur(DB_PATH, pk, projekt_name):
            return jsonify({"error": "Korrekturmaßnahme nicht gefunden"}), 404
        _audit("cra.korrektur.geloescht", object_id=str(pk), projekt=projekt_name)
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)
