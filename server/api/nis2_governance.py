"""N-GOV (#1212) — REST-Blueprint NIS2 Art. 20 Governance-Nachweis-Register.

Mountpunkt ``/api/nis2-governance`` (Bindestrich-Prefix → automatischer
nis2-Authz-Guard). CRUD für Billigungsbeschluss/Management-Review/Schulung mit
Teilnehmerliste (Schulung) + N16-Quiz-Verknüpfung und naechster_review-
Wiedervorlage-Ampel. Aufnahme in den Readiness-Report erfolgt im /report-Endpoint
(siehe ``server/api/nis2.py``). Projekt-scoped (IDOR).
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from server.models.permission import Permission, require_permission

from nis2 import governance_db as gdb

nis2_governance_bp = Blueprint("nis2_governance", __name__)
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


def _review_status(nachweis: dict) -> dict:
    """Wiedervorlage-Ampel der naechster_review-Frist."""
    from shared import deadlines as dl
    base = nachweis.get("naechster_review") or ""
    base_dt = dl.parse_dt(base)
    if base_dt is None:
        return {"ampel": "grey", "status": "no_base", "due_at": base}
    days_left = (base_dt - dl.now_utc()).total_seconds() / 86400.0
    if days_left < 0:
        return {"ampel": "red", "status": "overdue", "due_at": base,
                "days_left": round(days_left, 1)}
    if days_left <= 30:
        return {"ampel": "amber", "status": "due_soon", "due_at": base,
                "days_left": round(days_left, 1)}
    return {"ampel": "green", "status": "on_track", "due_at": base,
            "days_left": round(days_left, 1)}


def _enrich(n: dict) -> dict:
    n = dict(n)
    n["review"] = _review_status(n)
    return n


@nis2_governance_bp.get("/constants")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def constants():
    return jsonify({
        "nachweis_typen": list(gdb.NACHWEIS_TYPEN),
        "teilnehmer_status": list(gdb.TEILNEHMER_STATUS),
    })


# ── Nachweise ─────────────────────────────────────────────────────────────────

@nis2_governance_bp.get("/projekte/<projekt_name>/nachweise")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def list_nachweise(projekt_name):
    try:
        return jsonify([_enrich(n) for n in gdb.list_nachweise(DB_PATH, projekt_name)])
    except Exception as e:
        return _log_500(e)


@nis2_governance_bp.post("/projekte/<projekt_name>/nachweise")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def save_nachweis(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        pk = gdb.save_nachweis(DB_PATH, projekt_name, body)
        _audit("nis2.governance.saved", projekt=projekt_name, object_id=str(pk),
               typ=body.get("typ", ""))
        return jsonify({"ok": True, "id": pk,
                        "nachweis": _enrich(gdb.get_nachweis(DB_PATH, projekt_name, pk))}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@nis2_governance_bp.get("/projekte/<projekt_name>/nachweise/<int:pk>")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def get_nachweis(projekt_name, pk):
    n = gdb.get_nachweis(DB_PATH, projekt_name, pk)
    if not n:
        return jsonify({"error": "Nachweis nicht gefunden"}), 404
    return jsonify(_enrich(n))


@nis2_governance_bp.delete("/projekte/<projekt_name>/nachweise/<int:pk>")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def delete_nachweis(projekt_name, pk):
    try:
        if not gdb.delete_nachweis(DB_PATH, projekt_name, pk):
            return jsonify({"error": "Nachweis nicht gefunden"}), 404
        _audit("nis2.governance.deleted", projekt=projekt_name, object_id=str(pk))
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)


# ── Teilnehmer (Schulung) ─────────────────────────────────────────────────────

@nis2_governance_bp.post("/projekte/<projekt_name>/nachweise/<int:pk>/teilnehmer")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def save_teilnehmer(projekt_name, pk):
    if not gdb.get_nachweis(DB_PATH, projekt_name, pk):
        return jsonify({"error": "Nachweis nicht gefunden"}), 404
    body = request.get_json(silent=True) or {}
    try:
        tid = gdb.save_teilnehmer(DB_PATH, pk, body)
        return jsonify({"ok": True, "id": tid,
                        "nachweis": _enrich(gdb.get_nachweis(DB_PATH, projekt_name, pk))}), 201
    except Exception as e:
        return _log_500(e)


@nis2_governance_bp.delete(
    "/projekte/<projekt_name>/nachweise/<int:pk>/teilnehmer/<int:teilnehmer_id>")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def delete_teilnehmer(projekt_name, pk, teilnehmer_id):
    if not gdb.get_nachweis(DB_PATH, projekt_name, pk):
        return jsonify({"error": "Nachweis nicht gefunden"}), 404
    try:
        if not gdb.delete_teilnehmer(DB_PATH, pk, teilnehmer_id):
            return jsonify({"error": "Teilnehmer nicht gefunden"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)
