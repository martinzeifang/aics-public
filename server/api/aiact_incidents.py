"""AI-Act Art. 73 — Serious-Incident-Register REST-Blueprint (``/api/aiact-incidents``, #1197).

Schwerwiegende Vorfälle mit Schweregrad-Klasse, abgeleiteter Meldefrist (2/10/15
Tage), Status-Lifecycle und Behörden-Einreichungsnachweis. Die Fristenuhr
(Ampel/Countdown/Überfälligkeit) kommt aus der kanonischen
:mod:`shared.deadlines`-Engine (Stage-Set ``aiact_art73``).

Bindestrich-Prefix ``aiact-incidents`` mappt automatisch auf den ``aiact``-Authz-/
Lizenz-Guard (app.py #1169) — keine authz.py-Änderung nötig.
"""
from __future__ import annotations

import re
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission

from ai_act import incidents as inc
from ai_act.db import load_projekt

aiact_incidents_bp = Blueprint("aiact_incidents", __name__)
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


# ── Katalog ─────────────────────────────────────────────────────────────────

@aiact_incidents_bp.get("/constants")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def constants():
    return jsonify({"schweregrade": inc.schweregrade(), "status": list(inc.STATUS)})


# ── Register CRUD (alle Routen projekt-scoped → IDOR-sicher) ─────────────────

@aiact_incidents_bp.get("/projekte/<projekt_name>/incidents")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def list_incidents(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify({
            "items": inc.list_incidents(DB_PATH, projekt_name),
            "summary": inc.summary(DB_PATH, projekt_name),
        })
    except Exception as e:
        return _log_500(e)


@aiact_incidents_bp.get("/projekte/<projekt_name>/incidents/<int:incident_id>")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def get_incident(projekt_name, incident_id):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        item = inc.get_incident(DB_PATH, projekt_name, incident_id)
        if not item:
            return jsonify({"error": "Vorfall nicht gefunden"}), 404
        return jsonify(item)
    except Exception as e:
        return _log_500(e)


@aiact_incidents_bp.post("/projekte/<projekt_name>/incidents")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def create_incident(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        new_id = inc.create_incident(DB_PATH, projekt_name, body)
        _audit("aiact.incident.created", projekt=projekt_name, id=new_id,
               schweregrad=body.get("schweregrad"))
        return jsonify(inc.get_incident(DB_PATH, projekt_name, new_id)), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@aiact_incidents_bp.put("/projekte/<projekt_name>/incidents/<int:incident_id>")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def update_incident(projekt_name, incident_id):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        if not inc.update_incident(DB_PATH, projekt_name, incident_id, body):
            return jsonify({"error": "Vorfall nicht gefunden"}), 404
        _audit("aiact.incident.updated", projekt=projekt_name, id=incident_id,
               status=body.get("status"))
        return jsonify(inc.get_incident(DB_PATH, projekt_name, incident_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@aiact_incidents_bp.delete("/projekte/<projekt_name>/incidents/<int:incident_id>")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def delete_incident(projekt_name, incident_id):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        if not inc.delete_incident(DB_PATH, projekt_name, incident_id):
            return jsonify({"error": "Vorfall nicht gefunden"}), 404
        _audit("aiact.incident.deleted", projekt=projekt_name, id=incident_id)
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)


# ── A23-Wizard-Reporttext an einen Incident binden (statt nur Notiz) ─────────

@aiact_incidents_bp.post("/projekte/<projekt_name>/incidents/<int:incident_id>/report")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def attach_report(projekt_name, incident_id):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        report = str(body.get("report_text") or body.get("report") or "")
        if not report:
            return jsonify({"error": 'Feld "report_text" ist Pflicht'}), 400
        if not inc.attach_report(DB_PATH, projekt_name, incident_id, report):
            return jsonify({"error": "Vorfall nicht gefunden"}), 404
        _audit("aiact.incident.report_attached", projekt=projekt_name, id=incident_id)
        return jsonify(inc.get_incident(DB_PATH, projekt_name, incident_id))
    except Exception as e:
        return _log_500(e)


# ── Optionaler Issue-Link (object_kind='aiact_incident', spiegelt #1087) ─────

@aiact_incidents_bp.get("/projekte/<projekt_name>/incidents/<int:incident_id>/issues")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def list_issues(projekt_name, incident_id):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        from shared.issue_links import list_links, ensure_tables
        ensure_tables(DB_PATH)
        links = list_links(DB_PATH, projekt_name=projekt_name,
                           object_kind="aiact_incident", object_id=str(incident_id))
        return jsonify({"links": [_serialize_link(l) for l in links]})
    except Exception as e:
        return _log_500(e)


@aiact_incidents_bp.post("/projekte/<projekt_name>/incidents/<int:incident_id>/issues/link")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def link_issue(projekt_name, incident_id):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        if not inc.get_incident(DB_PATH, projekt_name, incident_id):
            return jsonify({"error": "Vorfall nicht gefunden"}), 404
        url = str(body.get("url") or "")
        if not url:
            return jsonify({"error": 'Feld "url" ist Pflicht'}), 400
        provider = (body.get("provider") or "github").lower()
        repo = str(body.get("repo") or "")
        if not repo:
            gh = re.match(r"https?://github\.com/([^/]+/[^/]+)/issues/\d+", url)
            gl = re.match(r"https?://[^/]+/([^/]+/[^/]+)/-/issues/\d+", url)
            if gh:
                repo, provider = gh.group(1), "github"
            elif gl:
                repo, provider = gl.group(1), "gitlab"
        num_match = re.search(r"/(?:issues|merge_requests)/(\d+)", url)
        number = int(num_match.group(1)) if num_match else None
        from shared.issue_links import add_link
        add_link(
            DB_PATH, projekt_name=projekt_name,
            object_kind="aiact_incident", object_id=str(incident_id),
            provider=provider, repo=repo, url=url,
            issue_number=number if provider == "github" else None,
            issue_iid=number if provider == "gitlab" else None,
            title=body.get("title") or url,
        )
        _audit("aiact.incident_issue.linked", projekt=projekt_name, id=incident_id, url=url)
        return jsonify({"linked": True, "url": url, "number": number,
                        "provider": provider}), 201
    except Exception as e:
        return _log_500(e)


@aiact_incidents_bp.delete("/projekte/<projekt_name>/incidents/issues/<link_id>")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def unlink_issue(projekt_name, link_id):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        from shared.issue_links import delete_link
        delete_link(DB_PATH, link_id)
        return jsonify({"deleted": True, "link_id": link_id})
    except Exception as e:
        return _log_500(e)


def _serialize_link(l) -> dict:
    return {
        "id": getattr(l, "id", None),
        "provider": getattr(l, "provider", ""),
        "repo": getattr(l, "repo", ""),
        "url": getattr(l, "url", ""),
        "issue_number": getattr(l, "issue_number", None),
        "issue_iid": getattr(l, "issue_iid", None),
        "title": getattr(l, "title", ""),
        "state": getattr(l, "state", ""),
    }
