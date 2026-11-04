"""DS-EUV (#1219) — REST-Blueprint EU-Vertreter-Benennung (``/api/dsgvo-eu-vertreter``).

Art. 27 DSGVO: Anwendbarkeitsprüfung (Art. 3(2)) + Benennungs-Mini-Register.
EIN Datensatz pro Projekt (Upsert). Permissions DSGVO_READ/WRITE. Routen
projekt-scoped (IDOR).
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission

from dsgvo import eu_vertreter_db as euv_db

dsgvo_eu_vertreter_bp = Blueprint("dsgvo_eu_vertreter", __name__)
DB_PATH = Path("data/db/dsgvo.sqlite")


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


def _audit(action: str, **fields):
    try:
        from shared.audit import audit_event
        fields.setdefault("actor", str(get_jwt_identity() or ""))
        audit_event(action, module="dsgvo", details=fields)
    except Exception:  # noqa: BLE001
        pass


@dsgvo_eu_vertreter_bp.get("/projekte/<projekt_name>/eu-vertreter")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_vertreter(projekt_name):
    try:
        rec = euv_db.get_vertreter(DB_PATH, projekt_name)
        return jsonify(rec or {})
    except Exception as e:
        return _log_500(e)


@dsgvo_eu_vertreter_bp.put("/projekte/<projekt_name>/eu-vertreter")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def put_vertreter(projekt_name):
    body = request.get_json(silent=True) or {}
    body.pop("projekt_name", None)  # Scope kommt aus dem Pfad
    try:
        rec = euv_db.upsert_vertreter(DB_PATH, projekt_name, body)
        _audit("dsgvo.eu_vertreter.saved", projekt=projekt_name,
               einschlaegig=bool(rec.get("einschlaegig")))
        return jsonify(rec)
    except Exception as e:
        return _log_500(e)


@dsgvo_eu_vertreter_bp.delete("/projekte/<projekt_name>/eu-vertreter")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def delete_vertreter(projekt_name):
    if not euv_db.delete_vertreter(DB_PATH, projekt_name):
        return jsonify({"error": "Kein Eintrag vorhanden"}), 404
    _audit("dsgvo.eu_vertreter.deleted", projekt=projekt_name)
    return jsonify({"ok": True})
