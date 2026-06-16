"""CRA Art. 13(1) / Annex VII — Traceability + Vollständigkeitsmatrix (#1217).

REST-Blueprint ``/api/cra-traceability``. Bindestrich-Prefix → cra-Authz (#1169).
Per-Requirement Nachweis↔Anforderung-Verknüpfung + granulare Annex-VII-Matrix.
IDOR-sicher (projekt-scoped Routen).
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission
from server.api._common import require_projekt

from cra.db import load_projekt
from cra import traceability_db as tdb

cra_traceability_bp = Blueprint("cra_traceability", __name__)
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


@cra_traceability_bp.get("/constants")
@jwt_required()
@require_permission(Permission.CRA_READ)
def constants():
    return jsonify({"annex_vii_bausteine": tdb.ANNEX_VII_BAUSTEINE})


@cra_traceability_bp.get("/projekte/<projekt_name>/dokumente")
@jwt_required()
@require_permission(Permission.CRA_READ)
def list_dokumente(projekt_name):
    try:
        return jsonify(tdb.list_dokumente(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@cra_traceability_bp.post("/projekte/<projekt_name>/dokumente")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def create_dokument(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        pk = tdb.create_dokument(
            DB_PATH, projekt_name, body.get("doc_name", ""),
            doc_path=body.get("doc_path", ""), doc_type=body.get("doc_type", "resource"),
            anforderung_id=body.get("anforderung_id", ""),
            owasp_id=body.get("owasp_id", ""),
            annex_baustein=body.get("annex_baustein", ""))
        _audit("cra.traceability.dokument_erstellt", object_id=str(pk),
               projekt=projekt_name)
        return jsonify(tdb.get_dokument(DB_PATH, pk, projekt_name)), 201
    except Exception as e:
        return _log_500(e)


@cra_traceability_bp.put("/projekte/<projekt_name>/dokumente/<int:pk>/link")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def link_dokument(projekt_name, pk):
    body = request.get_json(silent=True) or {}
    try:
        d = tdb.link_dokument(
            DB_PATH, pk, projekt_name,
            anforderung_id=body.get("anforderung_id"),
            owasp_id=body.get("owasp_id"),
            annex_baustein=body.get("annex_baustein"),
            doc_type=body.get("doc_type"))
        if not d:
            return jsonify({"error": "Dokument nicht gefunden"}), 404
        _audit("cra.traceability.verknuepft", object_id=str(pk), projekt=projekt_name)
        return jsonify(d)
    except Exception as e:
        return _log_500(e)


@cra_traceability_bp.get("/projekte/<projekt_name>/requirement-traceability")
@jwt_required()
@require_permission(Permission.CRA_READ)
def requirement_traceability(projekt_name):
    try:
        return jsonify(tdb.requirement_traceability(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@cra_traceability_bp.get("/projekte/<projekt_name>/annex-vii-status")
@jwt_required()
@require_permission(Permission.CRA_READ)
def annex_vii_status(projekt_name):
    try:
        return jsonify(tdb.annex_vii_status(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)
