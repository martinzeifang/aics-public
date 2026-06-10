"""DSGVO DS9 (#1109) – Drittlandtransfer + TIA REST-API (Art. 44–49).

Eigenständiger Blueprint (additiv). Wird vom Integrator in ``app.py`` mit dem
url_prefix ``/api/dsgvo-transfer`` registriert. Permissions exakt wie die
DSGVO-API: Lesen → ``DSGVO_READ``, Schreiben → ``DSGVO_WRITE``,
Export/TIA-Erstellung bleibt Schreib-Operation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required

from server.models.permission import Permission, require_permission

from dsgvo.transfer_db import (
    GRUNDLAGEN,
    TIA_STATUS,
    delete_transfer,
    get_transfer,
    list_transfers,
    save_tia,
    upsert_transfer,
)

dsgvo_transfer_bp = Blueprint("dsgvo_transfer", __name__)

DB_PATH = Path("data/db/dsgvo.sqlite")


def _log_500(e: Exception):
    current_app.logger.exception(
        "%s %s — %s: %s", request.method, request.path, type(e).__name__, e
    )
    return {"error": "Interner Serverfehler"}, 500  # Detail nur im Server-Log (#737)


@dsgvo_transfer_bp.get("/constants")
@jwt_required()
def get_constants():
    """Erlaubte Grundlagen + TIA-Status für das Frontend."""
    return jsonify({"grundlagen": list(GRUNDLAGEN), "tia_status": list(TIA_STATUS)})


@dsgvo_transfer_bp.get("/projekte/<projekt_name>/transfers")
@require_permission(Permission.DSGVO_READ)
def get_transfers(projekt_name: str):
    try:
        return jsonify({"transfers": list_transfers(DB_PATH, projekt_name)})
    except Exception as e:  # noqa: BLE001
        return _log_500(e)


@dsgvo_transfer_bp.get("/projekte/<projekt_name>/transfers/<transfer_id>")
@require_permission(Permission.DSGVO_READ)
def get_one_transfer(projekt_name: str, transfer_id: str):
    try:
        t = get_transfer(DB_PATH, projekt_name, transfer_id)
        if t is None:
            return {"error": "Transfer nicht gefunden"}, 404
        return jsonify(t)
    except Exception as e:  # noqa: BLE001
        return _log_500(e)


@dsgvo_transfer_bp.post("/projekte/<projekt_name>/transfers")
@require_permission(Permission.DSGVO_WRITE)
def create_transfer(projekt_name: str):
    try:
        data: dict[str, Any] = request.json or {}
        transfer_id = (data.get("transfer_id") or "").strip()
        if not transfer_id:
            return {"error": 'Feld "transfer_id" ist Pflicht'}, 400
        grundlage = (data.get("grundlage") or "").strip()
        if grundlage and grundlage not in GRUNDLAGEN:
            return {"error": f"Ungültige Grundlage: {grundlage}"}, 400
        if get_transfer(DB_PATH, projekt_name, transfer_id):
            return {"error": "Transfer existiert bereits"}, 409
        t = upsert_transfer(
            DB_PATH,
            projekt_name,
            transfer_id,
            empfaenger=data.get("empfaenger", ""),
            drittland=data.get("drittland", ""),
            grundlage=grundlage,
            garantie_detail=data.get("garantie_detail", ""),
            tia_status=data.get("tia_status", "offen"),
            tia=data.get("tia_json") or data.get("tia"),
            vvt_ref=data.get("vvt_ref", ""),
            avv_ref=data.get("avv_ref", ""),
        )
        return jsonify(t), 201
    except Exception as e:  # noqa: BLE001
        return _log_500(e)


@dsgvo_transfer_bp.put("/projekte/<projekt_name>/transfers/<transfer_id>")
@require_permission(Permission.DSGVO_WRITE)
def update_transfer(projekt_name: str, transfer_id: str):
    try:
        existing = get_transfer(DB_PATH, projekt_name, transfer_id)
        if existing is None:
            return {"error": "Transfer nicht gefunden"}, 404
        data: dict[str, Any] = request.json or {}
        grundlage = (data.get("grundlage", existing.get("grundlage", "")) or "").strip()
        if grundlage and grundlage not in GRUNDLAGEN:
            return {"error": f"Ungültige Grundlage: {grundlage}"}, 400
        t = upsert_transfer(
            DB_PATH,
            projekt_name,
            transfer_id,
            empfaenger=data.get("empfaenger", existing.get("empfaenger", "")),
            drittland=data.get("drittland", existing.get("drittland", "")),
            grundlage=grundlage,
            garantie_detail=data.get("garantie_detail", existing.get("garantie_detail", "")),
            tia_status=data.get("tia_status", existing.get("tia_status", "offen")),
            tia=data.get("tia_json") if ("tia_json" in data or "tia" in data) else existing.get("tia_json"),
            vvt_ref=data.get("vvt_ref", existing.get("vvt_ref", "")),
            avv_ref=data.get("avv_ref", existing.get("avv_ref", "")),
        )
        return jsonify(t)
    except Exception as e:  # noqa: BLE001
        return _log_500(e)


@dsgvo_transfer_bp.put("/projekte/<projekt_name>/transfers/<transfer_id>/tia")
@require_permission(Permission.DSGVO_WRITE)
def update_tia(projekt_name: str, transfer_id: str):
    """Geführte TIA (EDSA 01/2020) speichern."""
    try:
        data: dict[str, Any] = request.json or {}
        tia = data.get("tia") if data.get("tia") is not None else data.get("tia_json", data)
        status = data.get("tia_status")
        if status is not None and status not in TIA_STATUS:
            return {"error": f"Ungültiger TIA-Status: {status}"}, 400
        t = save_tia(DB_PATH, projekt_name, transfer_id, tia=tia, tia_status=status)
        if t is None:
            return {"error": "Transfer nicht gefunden"}, 404
        return jsonify(t)
    except Exception as e:  # noqa: BLE001
        return _log_500(e)


@dsgvo_transfer_bp.delete("/projekte/<projekt_name>/transfers/<transfer_id>")
@require_permission(Permission.DSGVO_WRITE)
def remove_transfer(projekt_name: str, transfer_id: str):
    try:
        if not delete_transfer(DB_PATH, projekt_name, transfer_id):
            return {"error": "Transfer nicht gefunden"}, 404
        return {"status": "deleted"}, 200
    except Exception as e:  # noqa: BLE001
        return _log_500(e)
