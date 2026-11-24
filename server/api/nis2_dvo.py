"""N-DVO (#1220 Teil B) — REST-Blueprint NIS2 DVO (EU) 2024/2690.

Mountpunkt ``/api/nis2-dvo`` (Bindestrich-Prefix → automatischer nis2-Authz-
Guard). Sektor-aktiviertes DVO-2690-Anforderungsset (13 Abschnitte als Controls
über ``nis2_anforderungen_custom``) + Erheblichkeits-Schwellenwert-Katalog je
Diensttyp als Triage-Entscheidungshilfe.
"""
from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from server.models.permission import Permission, require_permission

from nis2 import dvo2690 as dvo

nis2_dvo_bp = Blueprint("nis2_dvo", __name__)
DB_PATH = Path("data/db/nis2.sqlite")


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


def _audit(action: str, **fields):
    try:
        from shared.audit import audit_event
        fields.setdefault("actor", str(get_jwt_identity() or ""))
        audit_event(action, module="nis2", details=fields)
    except Exception:  # noqa: BLE001
        pass


def _projekt_sektor(projekt_name: str) -> str:
    """Sektor aus dem N6-Klassifikator des Projekts (für DVO-Relevanz)."""
    try:
        from nis2.db import load_projekt
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return ""
        meta = json.loads(p.get("meta_json") or "{}")
        return (meta.get("nis2") or {}).get("klassifikator", {}).get("sektor", "") or ""
    except Exception:  # noqa: BLE001
        return ""


@nis2_dvo_bp.get("/schwellenwerte")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def schwellenwerte():
    """Erheblichkeits-Schwellenwert-Katalog je Diensttyp (Triage-Hilfe)."""
    return jsonify({"schwellenwerte": dvo.SCHWELLENWERTE,
                    "sections": dvo.DVO_SECTIONS})


@nis2_dvo_bp.get("/projekte/<projekt_name>/status")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def status(projekt_name):
    try:
        sektor = _projekt_sektor(projekt_name)
        active = dvo.list_active(DB_PATH)
        return jsonify({
            "sektor": sektor,
            "relevant": dvo.is_dvo_relevant(sektor),
            "aktiv": bool(active),
            "anzahl_controls": len(active),
            "controls": active,
        })
    except Exception as e:
        return _log_500(e)


@nis2_dvo_bp.post("/projekte/<projekt_name>/activate")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def activate(projekt_name):
    try:
        n = dvo.activate(DB_PATH)
        _audit("nis2.dvo2690.activated", projekt=projekt_name, controls=n)
        return jsonify({"ok": True, "anzahl_controls": n,
                        "controls": dvo.list_active(DB_PATH)}), 201
    except Exception as e:
        return _log_500(e)


@nis2_dvo_bp.post("/projekte/<projekt_name>/deactivate")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def deactivate(projekt_name):
    try:
        n = dvo.deactivate(DB_PATH)
        _audit("nis2.dvo2690.deactivated", projekt=projekt_name, removed=n)
        return jsonify({"ok": True, "entfernt": n})
    except Exception as e:
        return _log_500(e)
