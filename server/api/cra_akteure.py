"""CRA Art. 19-22 — Wirtschaftsakteure-Register (#1200).

REST-Blueprint ``/api/cra-akteure``. Bindestrich-Prefix → cra-Authz-Guard (#1169).
IDOR-sicher (projekt-scoped Routen). Rollen-spezifische Pflicht-Checklisten für
Importeur/Händler/Bevollmächtigter.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission
from server.api._common import require_projekt

from cra.db import load_projekt
from cra import akteure_db as adb

cra_akteure_bp = Blueprint("cra_akteure", __name__)
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


@cra_akteure_bp.get("/constants")
@jwt_required()
@require_permission(Permission.CRA_READ)
def constants():
    return jsonify({"rollen": list(adb.ROLLEN), "status": list(adb.STATUS),
                    "checkliste": adb.CHECKLISTE})


@cra_akteure_bp.get("/projekte/<projekt_name>/akteure")
@jwt_required()
@require_permission(Permission.CRA_READ)
def list_akteure(projekt_name):
    try:
        return jsonify(adb.list_akteure(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@cra_akteure_bp.post("/projekte/<projekt_name>/akteure")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def create_akteur(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        pk = adb.create_akteur(DB_PATH, projekt_name, body)
        _audit("cra.akteur.erstellt", object_id=str(pk), projekt=projekt_name,
               rolle=body.get("rolle"))
        return jsonify(adb.get_akteur(DB_PATH, pk, projekt_name)), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@cra_akteure_bp.get("/projekte/<projekt_name>/akteure/<int:pk>")
@jwt_required()
@require_permission(Permission.CRA_READ)
def get_akteur(projekt_name, pk):
    a = adb.get_akteur(DB_PATH, pk, projekt_name)
    if not a:
        return jsonify({"error": "Akteur nicht gefunden"}), 404
    return jsonify(a)


@cra_akteure_bp.put("/projekte/<projekt_name>/akteure/<int:pk>")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def update_akteur(projekt_name, pk):
    body = request.get_json(silent=True) or {}
    try:
        a = adb.update_akteur(DB_PATH, pk, projekt_name, body)
        if not a:
            return jsonify({"error": "Akteur nicht gefunden"}), 404
        _audit("cra.akteur.aktualisiert", object_id=str(pk), projekt=projekt_name)
        return jsonify(a)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@cra_akteure_bp.delete("/projekte/<projekt_name>/akteure/<int:pk>")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def delete_akteur(projekt_name, pk):
    try:
        if not adb.delete_akteur(DB_PATH, pk, projekt_name):
            return jsonify({"error": "Akteur nicht gefunden"}), 404
        _audit("cra.akteur.geloescht", object_id=str(pk), projekt=projekt_name)
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)
