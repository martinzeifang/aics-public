"""AI-Act Art. 51-55 — GPAI-Modul REST-Blueprint (``/api/aiact-gpai``, #1195).

Klassifizierung (FLOP-Schwellenwert), systemic-risk-Flag + Kommissions-
Notifikation (2-Wochen-Fristenuhr), Pflicht-Register (Annex XI/XII, Copyright/TDM,
Trainingsdaten-Summary, Red-Teaming/Systemic-Risk/Cybersecurity/Code-of-Practice)
und AI-Office-Incident-Tracking. Bindestrich-Prefix mappt auf den ``aiact``-Guard.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission

from ai_act import gpai
from ai_act.db import load_projekt

aiact_gpai_bp = Blueprint("aiact_gpai", __name__)
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


@aiact_gpai_bp.get("/requirements")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def requirements():
    return jsonify({"requirements": gpai.requirements(),
                    "flop_threshold": gpai.SYSTEMIC_FLOP_THRESHOLD,
                    "incident_status": list(gpai.INCIDENT_STATUS)})


# ── Klassifizierung ─────────────────────────────────────────────────────────

@aiact_gpai_bp.get("/projekte/<projekt_name>/gpai")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def get_gpai(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify({
            "klassifizierung": gpai.get_klassifizierung(DB_PATH, projekt_name),
            "checks": gpai.load_checks(DB_PATH, projekt_name),
            "incidents": gpai.list_incidents(DB_PATH, projekt_name),
            "summary": gpai.summary(DB_PATH, projekt_name),
        })
    except Exception as e:
        return _log_500(e)


@aiact_gpai_bp.put("/projekte/<projekt_name>/klassifizierung")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def save_klassifizierung(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        klass = gpai.save_klassifizierung(DB_PATH, projekt_name, body)
        _audit("aiact.gpai.klassifiziert", projekt=projekt_name,
               systemisch=klass["systemisch"], training_flop=klass["training_flop"])
        return jsonify({"klassifizierung": klass,
                        "checks": gpai.load_checks(DB_PATH, projekt_name),
                        "summary": gpai.summary(DB_PATH, projekt_name)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


# ── Pflicht-Register / Checks ───────────────────────────────────────────────

@aiact_gpai_bp.post("/projekte/<projekt_name>/checks/<req_id>")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def save_check(projekt_name, req_id):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        gpai.save_check(DB_PATH, projekt_name, req_id,
                        status=int(body.get("status", 0) or 0),
                        kommentar=str(body.get("kommentar", "") or ""),
                        nachweis_ref=str(body.get("nachweis_ref", "") or ""))
        _audit("aiact.gpai.check_saved", projekt=projekt_name, req_id=req_id)
        return jsonify({"checks": gpai.load_checks(DB_PATH, projekt_name),
                        "summary": gpai.summary(DB_PATH, projekt_name)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


# ── AI-Office-Incident-Tracking (nur systemisch) ─────────────────────────────

@aiact_gpai_bp.post("/projekte/<projekt_name>/incidents")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def create_incident(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        if not gpai.get_klassifizierung(DB_PATH, projekt_name)["systemisch"]:
            return jsonify({"error": "AI-Office-Incident-Tracking nur für GPAI "
                                     "mit systemischem Risiko (Art. 55(1)c)"}), 409
        new_id = gpai.create_incident(DB_PATH, projekt_name, body)
        _audit("aiact.gpai.incident_created", projekt=projekt_name, id=new_id)
        return jsonify({"id": new_id,
                        "incidents": gpai.list_incidents(DB_PATH, projekt_name)}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@aiact_gpai_bp.delete("/projekte/<projekt_name>/incidents/<int:incident_id>")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def delete_incident(projekt_name, incident_id):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        if not gpai.delete_incident(DB_PATH, projekt_name, incident_id):
            return jsonify({"error": "Incident nicht gefunden"}), 404
        return jsonify({"ok": True,
                        "incidents": gpai.list_incidents(DB_PATH, projekt_name)})
    except Exception as e:
        return _log_500(e)


# ── KI-Wizard ─────────────────────────────────────────────────────────────────

@aiact_gpai_bp.get("/projekte/<projekt_name>/wizard/prompt")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def wizard_prompt(projekt_name):
    try:
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify({"prompt": gpai.build_gpai_prompt(p)})
    except Exception as e:
        return _log_500(e)


# #1244: Dokument-Assistenten (Copyright-Policy / Trainingsdaten-Summary).
# Liefern reine Copy/Paste-Prompts; das Ergebnis (Markdown) wird über die generische
# „Als Dokument speichern"-Funktion (#1235) als managed_doc abgelegt.

@aiact_gpai_bp.get("/projekte/<projekt_name>/wizard/copyright-policy/prompt")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def copyright_policy_prompt(projekt_name):
    try:
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify({"prompt": gpai.build_copyright_policy_prompt(p)})
    except Exception as e:
        return _log_500(e)


@aiact_gpai_bp.get("/projekte/<projekt_name>/wizard/training-summary/prompt")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def training_summary_prompt(projekt_name):
    try:
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify({"prompt": gpai.build_training_summary_prompt(p)})
    except Exception as e:
        return _log_500(e)


@aiact_gpai_bp.post("/projekte/<projekt_name>/wizard/parse")
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
        parsed = gpai.parse_gpai_response(raw)
        if not parsed:
            return jsonify({"error": "Kein gültiges GPAI-JSON erkannt"}), 400
        if bool(body.get("apply", True)):
            klass = gpai.get_klassifizierung(DB_PATH, projekt_name)
            klass_update = {
                "ist_gpai": parsed.get("ist_gpai", klass["ist_gpai"]),
                "training_flop": parsed.get("training_flop", klass["training_flop"]),
                "systemisch_override": klass.get("systemisch_override", ""),
                "copyright_tdm_policy": klass.get("copyright_tdm_policy", ""),
                "trainingsdaten_summary": klass.get("trainingsdaten_summary", ""),
                "notifikation_kommission_am": klass.get("notifikation_kommission_am", ""),
                "schwellwert_erreicht_am": klass.get("schwellwert_erreicht_am", ""),
                "kommentar": klass.get("kommentar", ""),
            }
            gpai.save_klassifizierung(DB_PATH, projekt_name, klass_update)
            for c in parsed.get("checks", []):
                gpai.save_check(DB_PATH, projekt_name, c["id"],
                                status=c["status"], kommentar=c.get("kommentar", ""))
        return jsonify({"parsed": parsed,
                        "klassifizierung": gpai.get_klassifizierung(DB_PATH, projekt_name),
                        "checks": gpai.load_checks(DB_PATH, projekt_name),
                        "summary": gpai.summary(DB_PATH, projekt_name)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)
