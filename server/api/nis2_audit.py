"""N-AUD (#1204) — REST-Blueprint NIS2 Art. 32 Audit-Register + CAPA-Findings.

Mountpunkt ``/api/nis2-audit`` (Bindestrich-Prefix → automatischer nis2-Authz-
Guard). CRUD für Audits (3-Jahres-Zyklus) + verknüpfte Findings/CAPA mit
Verknüpfung zu Anforderung/Risiko. Audit-Report-Export (Markdown). Projekt-scoped
(IDOR): alle Einzelrouten über ``<projekt_name>``.
"""
from __future__ import annotations

import io
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from server.models.permission import Permission, require_permission

from nis2 import audit_db as adb

nis2_audit_bp = Blueprint("nis2_audit", __name__)
DB_PATH = Path("data/db/nis2.sqlite")


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


def _audit_log(action: str, **fields):
    try:
        from shared.audit import audit_event
        fields.setdefault("actor", str(get_jwt_identity() or ""))
        audit_event(action, module="nis2", details=fields)
    except Exception:  # noqa: BLE001
        pass


def _zyklus_status(audit: dict) -> dict:
    """Ampel der 3-Jahres-Wiedervorlage (naechster_audit_soll)."""
    from shared import deadlines as dl
    base = audit.get("naechster_audit_soll") or ""
    base_dt = dl.parse_dt(base)
    if base_dt is None:
        return {"ampel": "grey", "status": "no_base", "due_at": base}
    days_left = (base_dt - dl.now_utc()).total_seconds() / 86400.0
    if days_left < 0:
        return {"ampel": "red", "status": "overdue", "due_at": base,
                "days_left": round(days_left, 1)}
    if days_left <= 90:
        return {"ampel": "amber", "status": "due_soon", "due_at": base,
                "days_left": round(days_left, 1)}
    return {"ampel": "green", "status": "on_track", "due_at": base,
            "days_left": round(days_left, 1)}


def _enrich(audit: dict) -> dict:
    audit = dict(audit)
    audit["zyklus"] = _zyklus_status(audit)
    return audit


@nis2_audit_bp.get("/constants")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def constants():
    return jsonify({
        "audit_typen": list(adb.AUDIT_TYPEN),
        "audit_ergebnis": list(adb.AUDIT_ERGEBNIS),
        "finding_schweregrade": list(adb.FINDING_SCHWEREGRADE),
        "finding_status": list(adb.FINDING_STATUS),
        "finding_objekt": list(adb.FINDING_OBJEKT),
        "zyklus_monate": adb.AUDIT_ZYKLUS_MONATE,
    })


# ── Audits ──────────────────────────────────────────────────────────────────

@nis2_audit_bp.get("/projekte/<projekt_name>/audits")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def list_audits(projekt_name):
    try:
        return jsonify([_enrich(a) for a in adb.list_audits(DB_PATH, projekt_name)])
    except Exception as e:
        return _log_500(e)


@nis2_audit_bp.post("/projekte/<projekt_name>/audits")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def save_audit(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        pk = adb.save_audit(DB_PATH, projekt_name, body)
        _audit_log("nis2.audit.saved", projekt=projekt_name, object_id=str(pk))
        return jsonify({"ok": True, "id": pk,
                        "audit": _enrich(adb.get_audit(DB_PATH, projekt_name, pk))}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@nis2_audit_bp.get("/projekte/<projekt_name>/audits/<int:pk>")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def get_audit(projekt_name, pk):
    a = adb.get_audit(DB_PATH, projekt_name, pk)
    if not a:
        return jsonify({"error": "Audit nicht gefunden"}), 404
    return jsonify(_enrich(a))


@nis2_audit_bp.delete("/projekte/<projekt_name>/audits/<int:pk>")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def delete_audit(projekt_name, pk):
    try:
        if not adb.delete_audit(DB_PATH, projekt_name, pk):
            return jsonify({"error": "Audit nicht gefunden"}), 404
        _audit_log("nis2.audit.deleted", projekt=projekt_name, object_id=str(pk))
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)


# ── Findings (CAPA) ──────────────────────────────────────────────────────────

@nis2_audit_bp.post("/projekte/<projekt_name>/audits/<int:pk>/findings")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def save_finding(projekt_name, pk):
    if not adb.get_audit(DB_PATH, projekt_name, pk):
        return jsonify({"error": "Audit nicht gefunden"}), 404
    body = request.get_json(silent=True) or {}
    try:
        fid = adb.save_finding(DB_PATH, projekt_name, pk, body)
        _audit_log("nis2.audit_finding.saved", projekt=projekt_name,
                   object_id=str(pk), finding_id=str(fid))
        return jsonify({"ok": True, "id": fid,
                        "audit": _enrich(adb.get_audit(DB_PATH, projekt_name, pk))}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@nis2_audit_bp.delete(
    "/projekte/<projekt_name>/audits/<int:pk>/findings/<int:finding_id>")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def delete_finding(projekt_name, pk, finding_id):
    try:
        if not adb.delete_finding(DB_PATH, projekt_name, pk, finding_id):
            return jsonify({"error": "Finding nicht gefunden"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)


# ── Audit-Report-Export ──────────────────────────────────────────────────────

def _build_report_markdown(projekt_name: str, audit: dict) -> str:
    lines = [
        f"# NIS2-Audit-Report (Art. 32) — {projekt_name}",
        "",
        f"- **Titel:** {audit.get('titel', '') or '—'}",
        f"- **Typ:** {audit.get('audit_typ', '')}",
        f"- **Scope:** {audit.get('scope', '') or '—'}",
        f"- **Prüfer:** {audit.get('pruefer', '') or '—'}",
        f"- **Durchgeführt am:** {audit.get('durchgefuehrt_am', '') or '—'}",
        f"- **Nächster Audit (3-Jahres-Zyklus):** "
        f"{audit.get('naechster_audit_soll', '') or '—'}",
        f"- **Zertifikat:** {audit.get('zertifikat_url', '') or '—'} "
        f"(Ablauf: {audit.get('zertifikat_ablauf', '') or '—'})",
        f"- **Ergebnis:** {audit.get('ergebnis', '')}",
        "",
        "## Findings / CAPA (Art. 21 Abs. 4)",
    ]
    findings = audit.get("findings", [])
    if not findings:
        lines.append("_Keine Findings erfasst._")
    for i, f in enumerate(findings, 1):
        link = ""
        if f.get("objekt_typ"):
            link = f" · verknüpft: {f['objekt_typ']} {f.get('objekt_ref', '')}"
        lines += [
            "",
            f"### Finding {i} — {f.get('schweregrad', '')} ({f.get('status', '')}){link}",
            f.get("beschreibung", "") or "(keine Beschreibung)",
            f"- **Maßnahme:** {f.get('massnahme', '') or '—'}",
            f"- **Verantwortlich:** {f.get('verantwortlich', '') or '—'}",
            f"- **Frist:** {f.get('frist', '') or '—'}",
        ]
    if audit.get("notizen"):
        lines += ["", "## Notizen", "", audit["notizen"]]
    return "\n".join(lines)


@nis2_audit_bp.get("/projekte/<projekt_name>/audits/<int:pk>/export")
@jwt_required()
@require_permission(Permission.NIS2_EXPORT)
def export_audit(projekt_name, pk):
    a = adb.get_audit(DB_PATH, projekt_name, pk)
    if not a:
        return jsonify({"error": "Audit nicht gefunden"}), 404
    try:
        md = _build_report_markdown(projekt_name, a)
        buf = io.BytesIO(md.encode("utf-8"))
        _audit_log("nis2.audit.exported", projekt=projekt_name, object_id=str(pk))
        return send_file(buf, as_attachment=True,
                         download_name=f"NIS2-Audit_{projekt_name}_{pk}.md",
                         mimetype="text/markdown")
    except Exception as e:
        return _log_500(e)
