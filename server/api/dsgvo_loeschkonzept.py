"""DS10 (#1110) — DSGVO-Löschkonzept-API (Art. 17 + DIN 66398).

Eigenständiges Blueprint; wird vom Integrator in ``server/app.py`` mit dem
url_prefix ``/api/dsgvo-loeschkonzept`` registriert (hier NICHT registriert).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required

from server.models.permission import Permission, require_permission

from dsgvo.loeschkonzept_db import (
    DB_PATH,
    RECHTSGRUNDLAGE_FRIST,
    delete_regel,
    get_regel,
    list_faellig,
    list_regeln,
    save_regel,
    update_status,
)

dsgvo_loeschkonzept_bp = Blueprint("dsgvo_loeschkonzept", __name__)


def _payload() -> Dict[str, Any]:
    return request.json or {}


# ── Regeln ──────────────────────────────────────────────────────────────────

@dsgvo_loeschkonzept_bp.get("/projekte/<projekt_name>/regeln")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_regeln(projekt_name: str):
    try:
        return jsonify(list_regeln(DB_PATH, projekt_name)), 200
    except Exception as e:
        current_app.logger.exception(
            "%s %s — %s: %s", request.method, request.path, type(e).__name__, e
        )
        return {"error": "Interner Serverfehler"}, 500


@dsgvo_loeschkonzept_bp.get("/projekte/<projekt_name>/faellig")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_faellig(projekt_name: str):
    """Fällige Löschungen (status-basiert, mit gesetztem Trigger)."""
    try:
        return jsonify(list_faellig(DB_PATH, projekt_name)), 200
    except Exception as e:
        current_app.logger.exception(
            "%s %s — %s: %s", request.method, request.path, type(e).__name__, e
        )
        return {"error": "Interner Serverfehler"}, 500


@dsgvo_loeschkonzept_bp.post("/projekte/<projekt_name>/regeln")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def create_regel(projekt_name: str):
    try:
        data = _payload()
        regel_id = (data.get("regel_id") or "").strip()
        if not regel_id:
            return {"error": 'Feld "regel_id" ist Pflicht'}, 400
        rg = (data.get("rechtsgrundlage_frist") or "gesetzlich").strip()
        if rg not in RECHTSGRUNDLAGE_FRIST:
            return {
                "error": f'rechtsgrundlage_frist muss eines von {RECHTSGRUNDLAGE_FRIST} sein'
            }, 400
        pk = save_regel(
            DB_PATH,
            projekt_name,
            regel_id,
            datenkategorie=(data.get("datenkategorie") or "").strip(),
            aufbewahrungsfrist=(data.get("aufbewahrungsfrist") or "").strip(),
            rechtsgrundlage_frist=rg,
            loeschklasse=(data.get("loeschklasse") or "").strip(),
            loesch_trigger=(data.get("loesch_trigger") or "").strip(),
            verantwortlich=(data.get("verantwortlich") or "").strip(),
            status=(data.get("status") or "offen").strip(),
            vvt_ref=(data.get("vvt_ref") or "").strip(),
        )
        regel = get_regel(DB_PATH, pk)
        return jsonify(regel), 201
    except Exception as e:
        current_app.logger.exception(
            "%s %s — %s: %s", request.method, request.path, type(e).__name__, e
        )
        return {"error": "Interner Serverfehler"}, 500


@dsgvo_loeschkonzept_bp.put("/regeln/<int:regel_pk>")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def put_regel(regel_pk: int):
    try:
        existing = get_regel(DB_PATH, regel_pk)
        if not existing:
            return {"error": "Regel nicht gefunden"}, 404
        data = _payload()
        rg = (data.get("rechtsgrundlage_frist") or existing["rechtsgrundlage_frist"]).strip()
        if rg not in RECHTSGRUNDLAGE_FRIST:
            return {
                "error": f'rechtsgrundlage_frist muss eines von {RECHTSGRUNDLAGE_FRIST} sein'
            }, 400
        save_regel(
            DB_PATH,
            existing["projekt_name"],
            existing["regel_id"],
            datenkategorie=(data.get("datenkategorie", existing["datenkategorie"]) or "").strip(),
            aufbewahrungsfrist=(data.get("aufbewahrungsfrist", existing["aufbewahrungsfrist"]) or "").strip(),
            rechtsgrundlage_frist=rg,
            loeschklasse=(data.get("loeschklasse", existing["loeschklasse"]) or "").strip(),
            loesch_trigger=(data.get("loesch_trigger", existing["loesch_trigger"]) or "").strip(),
            verantwortlich=(data.get("verantwortlich", existing["verantwortlich"]) or "").strip(),
            status=(data.get("status", existing["status"]) or "offen").strip(),
            vvt_ref=(data.get("vvt_ref", existing["vvt_ref"]) or "").strip(),
        )
        return jsonify(get_regel(DB_PATH, regel_pk)), 200
    except Exception as e:
        current_app.logger.exception(
            "%s %s — %s: %s", request.method, request.path, type(e).__name__, e
        )
        return {"error": "Interner Serverfehler"}, 500


@dsgvo_loeschkonzept_bp.put("/regeln/<int:regel_pk>/status")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def put_status(regel_pk: int):
    try:
        data = _payload()
        status = (data.get("status") or "").strip()
        if not status:
            return {"error": 'Feld "status" ist Pflicht'}, 400
        if not update_status(DB_PATH, regel_pk, status):
            return {"error": "Regel nicht gefunden"}, 404
        return jsonify(get_regel(DB_PATH, regel_pk)), 200
    except Exception as e:
        current_app.logger.exception(
            "%s %s — %s: %s", request.method, request.path, type(e).__name__, e
        )
        return {"error": "Interner Serverfehler"}, 500


@dsgvo_loeschkonzept_bp.delete("/regeln/<int:regel_pk>")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def remove_regel(regel_pk: int):
    try:
        if not delete_regel(DB_PATH, regel_pk):
            return {"error": "Regel nicht gefunden"}, 404
        return {"ok": True}, 200
    except Exception as e:
        current_app.logger.exception(
            "%s %s — %s: %s", request.method, request.path, type(e).__name__, e
        )
        return {"error": "Interner Serverfehler"}, 500
