"""N-FRIST (#1213) — REST-Blueprint NIS2 Kontrollzyklus-/Wiedervorlage-Dashboard.

Mountpunkt ``/api/nis2-fristen`` (Bindestrich-Prefix → automatischer nis2-Authz-
Guard). Reine Aggregation/Read-only über N2/N4/N5/Bewertungen (+ Audit/
Registrierung) mit faellig/ueberfaellig-Ampeln aus ``shared.deadlines``.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required

from server.models.permission import Permission, require_permission

from nis2 import fristen as nf

nis2_fristen_bp = Blueprint("nis2_fristen", __name__)
DB_PATH = Path("data/db/nis2.sqlite")


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


@nis2_fristen_bp.get("/projekte/<projekt_name>/fristen")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def list_fristen(projekt_name):
    try:
        return jsonify(nf.collect_fristen(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)
