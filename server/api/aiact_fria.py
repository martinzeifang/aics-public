"""AI-Act Art. 27 — FRIA-Workflow REST-Blueprint (``/api/aiact-fria``, #1196).

Grundrechte-Folgenabschätzung durch Betreiber: Register, Pflichtfeld-Erfassung im
geführten Stepper, Pflicht-Trigger (high-risk + Betreiber-Typ), Behörden-
Mitteilung. Bindestrich-Prefix mappt automatisch auf den ``aiact``-Guard.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission

from ai_act import fria as f
from ai_act.db import load_projekt

aiact_fria_bp = Blueprint("aiact_fria", __name__)
DB_PATH = Path("data/db/ai_act.sqlite")


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


def _audit(action: str, **fields):
    try:
        from shared.audit import audit_event
        fields.setdefault("actor", str(get_jwt_identity() or ""))
        audit_event(action, module="aiact", details=fields)
    except Exception:  # noqa: BLE001
        pass


@aiact_fria_bp.get("/constants")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def constants():
    return jsonify({"betreiber_typen": f.betreiber_typen(),
                    "stages": list(f.STAGES), "status": list(f.STATUS)})


@aiact_fria_bp.get("/projekte/<projekt_name>/fria")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def get_fria(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify({
            "record": f.get_or_empty(DB_PATH, projekt_name),
            "trigger": f.trigger(DB_PATH, projekt_name),
        })
    except Exception as e:
        return _log_500(e)


@aiact_fria_bp.get("/projekte/<projekt_name>/trigger")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def get_trigger(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        bt = request.args.get("betreiber_typ")
        return jsonify(f.trigger(DB_PATH, projekt_name, betreiber_typ=bt))
    except Exception as e:
        return _log_500(e)


@aiact_fria_bp.put("/projekte/<projekt_name>/fria")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def save_fria(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        rec = f.save(DB_PATH, projekt_name, body)
        _audit("aiact.fria.saved", projekt=projekt_name, stage=rec.get("stage"))
        return jsonify({"record": rec, "trigger": f.trigger(DB_PATH, projekt_name)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@aiact_fria_bp.post("/projekte/<projekt_name>/mitteilung")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def report_to_authority(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        rec = f.mark_reported(DB_PATH, projekt_name,
                              behoerde=str(body.get("behoerde", "") or ""),
                              am=str(body.get("am", "") or ""))
        _audit("aiact.fria.reported", projekt=projekt_name)
        return jsonify({"record": rec})
    except Exception as e:
        return _log_500(e)


@aiact_fria_bp.get("/projekte/<projekt_name>/mitteilung/export")
@jwt_required()
@require_permission(Permission.AIACT_EXPORT)
def export_mitteilung(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        text = f.build_mitteilung(DB_PATH, projekt_name)
        buf = io.BytesIO(text.encode("utf-8"))
        _audit("aiact.fria.exported", projekt=projekt_name)
        return send_file(buf, mimetype="text/markdown", as_attachment=True,
                         download_name=f"fria_mitteilung_{projekt_name}.md")
    except Exception as e:
        return _log_500(e)


# ── KI-Wizard ─────────────────────────────────────────────────────────────────

@aiact_fria_bp.get("/projekte/<projekt_name>/wizard/prompt")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def wizard_prompt(projekt_name):
    try:
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify({"prompt": f.build_fria_prompt(p)})
    except Exception as e:
        return _log_500(e)


@aiact_fria_bp.post("/projekte/<projekt_name>/wizard/parse")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def wizard_parse(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        raw = body.get("response") or body.get("raw") or ""
        if not raw:
            return jsonify({"error": 'Feld "response" ist Pflicht'}), 400
        parsed = f.parse_fria_response(raw)
        if not parsed:
            return jsonify({"error": "Kein gültiges FRIA-JSON erkannt"}), 400
        rec = None
        if bool(body.get("apply", True)):
            existing = f.get_or_empty(DB_PATH, projekt_name)
            existing.update(parsed)
            rec = f.save(DB_PATH, projekt_name, existing)
        return jsonify({"parsed": parsed, "saved": rec is not None,
                        "record": rec or f.get_or_empty(DB_PATH, projekt_name)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)
