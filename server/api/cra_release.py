"""CRA Art. 13(4) — Wesentliche Änderung + Release-Versionierung (#1208).

REST-Blueprint ``/api/cra-release``. Bindestrich-Prefix → cra-Authz (#1169).
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission
from server.api._common import require_projekt

from cra.db import load_projekt
from cra import release_db as rdb

cra_release_bp = Blueprint("cra_release", __name__)
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


@cra_release_bp.get("/projekte/<projekt_name>/release")
@jwt_required()
@require_permission(Permission.CRA_READ)
def get_release(projekt_name):
    try:
        rec = rdb.get_release(DB_PATH, projekt_name) or {}
        rec["snapshots"] = rdb.list_snapshots(DB_PATH, projekt_name)
        rec["reassess_items"] = list(rdb.REASSESS_ITEMS)
        return jsonify(rec)
    except Exception as e:
        return _log_500(e)


@cra_release_bp.put("/projekte/<projekt_name>/release")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def put_release(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(rdb.save_release(DB_PATH, projekt_name, body))
    except Exception as e:
        return _log_500(e)


@cra_release_bp.post("/projekte/<projekt_name>/substantial-modification")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def substantial_modification(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    neue_version = (body.get("neue_version") or "").strip()
    grund = (body.get("grund") or "").strip()
    if not neue_version:
        return jsonify({"error": "'neue_version' ist Pflicht"}), 400
    if len(grund) < 5:
        return jsonify({"error": "Begründung (≥5 Zeichen) erforderlich"}), 400
    try:
        res = rdb.substantial_modification(DB_PATH, projekt_name,
                                           neue_version=neue_version, grund=grund)
        _audit("cra.release.substantial_modification", projekt=projekt_name,
               eingefroren=res["eingefrorene_version"], neue_version=neue_version)
        return jsonify(res), 201
    except Exception as e:
        return _log_500(e)
