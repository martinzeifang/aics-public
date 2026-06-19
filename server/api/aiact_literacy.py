"""AI-Act Art. 4 — AI-Literacy-Register REST-Blueprint (``/api/aiact-literacy``, #1199).

Kompetenzkonzept + Schulungsnachweise je Rolle/Person mit Gültigkeits-/
Auffrischungsfrist. Bindestrich-Prefix mappt automatisch auf den aiact-Guard.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission

from ai_act import ai_literacy as lit
from ai_act.db import load_projekt

aiact_literacy_bp = Blueprint("aiact_literacy", __name__)
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


@aiact_literacy_bp.get("/constants")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def constants():
    return jsonify({"kompetenzlevel": list(lit.KOMPETENZLEVEL)})


@aiact_literacy_bp.get("/projekte/<projekt_name>/literacy")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def get_register(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify({
            "konzept": lit.get_konzept(DB_PATH, projekt_name),
            "nachweise": lit.list_nachweise(DB_PATH, projekt_name),
            "summary": lit.summary(DB_PATH, projekt_name),
            "oversight_personen": lit.oversight_personen(DB_PATH, projekt_name),
        })
    except Exception as e:
        return _log_500(e)


@aiact_literacy_bp.put("/projekte/<projekt_name>/konzept")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def save_konzept(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        res = lit.save_konzept(DB_PATH, projekt_name, str(body.get("konzept", "")))
        _audit("aiact.literacy.konzept_saved", projekt=projekt_name)
        return jsonify({"ok": True, "konzept": res})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@aiact_literacy_bp.post("/projekte/<projekt_name>/nachweise")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def save_nachweis(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        pk = lit.save_nachweis(DB_PATH, projekt_name, body)
        _audit("aiact.literacy.nachweis_saved", projekt=projekt_name, id=pk)
        return jsonify({"ok": True, "id": pk}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@aiact_literacy_bp.delete("/projekte/<projekt_name>/nachweise/<int:pk>")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def delete_nachweis(projekt_name, pk):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        lit.delete_nachweis(DB_PATH, projekt_name, pk)
        _audit("aiact.literacy.nachweis_deleted", projekt=projekt_name, id=pk)
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)


# ── KI-Ausfüll-Assistent (Art. 4, #1242) ────────────────────────────────────────

@aiact_literacy_bp.get("/projekte/<projekt_name>/wizard/prompt")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def wizard_prompt(projekt_name):
    try:
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        meta = p.get("meta") if isinstance(p.get("meta"), dict) else {}
        stufe = str(meta.get("risiko_stufe") or meta.get("risikostufe")
                    or meta.get("klassifizierung") or "")
        konzept = lit.get_konzept(DB_PATH, projekt_name).get("konzept", "")
        return jsonify({"prompt": lit.build_literacy_prompt(
            p, risiko_stufe=stufe, konzept=konzept)})
    except Exception as e:
        return _log_500(e)


@aiact_literacy_bp.post("/projekte/<projekt_name>/wizard/parse")
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
        parsed = lit.parse_literacy_response(raw)
        if not parsed:
            return jsonify({"error": "Kein gültiges AI-Literacy-JSON erkannt"}), 400
        applied = None
        if bool(body.get("apply", False)):
            applied = lit.apply_literacy_suggestions(DB_PATH, projekt_name, parsed)
            _audit("aiact.literacy.wizard_applied", projekt=projekt_name,
                   created=applied.get("created"))
        return jsonify({
            "parsed": parsed,
            "applied": applied,
            # plan_markdown ist der speicher-/exportierbare AI-Literacy-Plan.
            "plan_markdown": parsed.get("plan_markdown", ""),
            "konzept": lit.get_konzept(DB_PATH, projekt_name),
            "nachweise": lit.list_nachweise(DB_PATH, projekt_name),
            "summary": lit.summary(DB_PATH, projekt_name),
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)
