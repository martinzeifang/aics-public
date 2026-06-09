"""CRA Art. 32 / Annex VIII — Konformitätsbewertung + DoC/CE (#1201).

REST-Blueprint ``/api/cra-konformitaet``. Bindestrich-Prefix → cra-Authz (#1169).
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission
from server.api._common import require_projekt

from cra.db import load_projekt
from cra import konformitaet_db as kdb

cra_konformitaet_bp = Blueprint("cra_konformitaet", __name__)
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


@cra_konformitaet_bp.get("/constants")
@jwt_required()
@require_permission(Permission.CRA_READ)
def constants():
    return jsonify({"wege": list(kdb.WEGE), "ce_status": list(kdb.CE_STATUS),
                    "checkliste": kdb.CHECKLISTE})


@cra_konformitaet_bp.get("/projekte/<projekt_name>/konformitaet")
@jwt_required()
@require_permission(Permission.CRA_READ)
def get_konformitaet(projekt_name):
    try:
        release = request.args.get("release", "")
        rec = kdb.get_konformitaet(DB_PATH, projekt_name, release)
        return jsonify(rec or {})
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/konformitaet/list")
@jwt_required()
@require_permission(Permission.CRA_READ)
def list_konformitaet(projekt_name):
    try:
        return jsonify(kdb.list_konformitaet(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.put("/projekte/<projekt_name>/konformitaet")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def put_konformitaet(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        rec = kdb.save_konformitaet(DB_PATH, projekt_name, body)
        _audit("cra.konformitaet.gespeichert", projekt=projekt_name,
               weg=rec.get("bewertungsweg"))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


# #1220-A: Governance-Sign-off (Freigabe + Lock) — separate CRA_APPROVE-Permission.
@cra_konformitaet_bp.post("/projekte/<projekt_name>/konformitaet/freigeben")
@jwt_required()
@require_permission(Permission.CRA_APPROVE)
def freigeben(projekt_name):
    body = request.get_json(silent=True) or {}
    release = body.get("release_version", "")
    try:
        rec = kdb.freigeben(DB_PATH, projekt_name, release,
                            von=str(get_jwt_identity() or ""))
        _audit("cra.konformitaet.freigegeben", projekt=projekt_name,
               release=release, freigegeben_von=rec.get("freigegeben_von"))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/konformitaet/reopen")
@jwt_required()
@require_permission(Permission.CRA_APPROVE)
def reopen(projekt_name):
    body = request.get_json(silent=True) or {}
    release = body.get("release_version", "")
    try:
        rec = kdb.reopen(DB_PATH, projekt_name, release)
        _audit("cra.konformitaet.reopened", projekt=projekt_name, release=release)
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/konformitaet/doc")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def issue_doc(projekt_name):
    body = request.get_json(silent=True) or {}
    release = body.get("release_version", "")
    doc = body.get("doc") or {}
    try:
        rec = kdb.issue_doc(DB_PATH, projekt_name, doc, release)
        _audit("cra.konformitaet.doc_ausgestellt", projekt=projekt_name,
               doc_version=rec.get("doc_version"))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)
