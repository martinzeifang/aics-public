"""N-INC (#1194) — REST-Blueprint NIS2 Art. 23 Vorfall-/Meldungs-Register.

Mountpunkt ``/api/nis2-incidents`` (Bindestrich-Prefix → automatischer
nis2-Authz-Guard). CRUD für Vorfälle + verknüpfte Melde-Stufen (24h/72h/
Zwischen/1M) mit Fristen-Lifecycle (``shared.deadlines`` STAGE_SET ``nis2_art23``),
Ampel/Countdown je Vorfall, projekt-scoped IDOR-Schutz, BSI-konformer
Einzelmeldungs-Export (Markdown/TXT).
"""
from __future__ import annotations

import io
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from server.models.permission import Permission, require_permission

from nis2 import incident_db as idb

nis2_incidents_bp = Blueprint("nis2_incidents", __name__)
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


def _enrich(incident: dict) -> dict:
    """Vorfall mit Fristen-Auswertung + abgeleiteten Stufen-Status anreichern."""
    incident = dict(incident)
    incident["deadlines"] = idb.evaluate_incident_deadlines(incident)
    incident["meldung_status"] = idb.derive_meldung_status(incident)
    return incident


# ── Konstanten ────────────────────────────────────────────────────────────────

@nis2_incidents_bp.get("/constants")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def constants():
    return jsonify({
        "incident_status": list(idb.INCIDENT_STATUS),
        "meldung_status": list(idb.MELDUNG_STATUS),
        "meldung_typen": list(idb.MELDUNG_TYPEN),
        "schweregrade": list(idb.SCHWEREGRADE),
    })


# ── Vorfälle ────────────────────────────────────────────────────────────────

@nis2_incidents_bp.get("/projekte/<projekt_name>/incidents")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def list_incidents(projekt_name):
    try:
        items = [_enrich(i) for i in idb.list_incidents(DB_PATH, projekt_name)]
        return jsonify(items)
    except Exception as e:
        return _log_500(e)


@nis2_incidents_bp.post("/projekte/<projekt_name>/incidents")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def save_incident(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        pk = idb.save_incident(DB_PATH, projekt_name, body)
        _audit("nis2.incident.saved", projekt=projekt_name,
               incident_id=body.get("incident_id", ""), object_id=str(pk))
        return jsonify({"ok": True, "id": pk,
                        "incident": _enrich(idb.get_incident(DB_PATH, projekt_name, pk))}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@nis2_incidents_bp.get("/projekte/<projekt_name>/incidents/<int:pk>")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def get_incident(projekt_name, pk):
    inc = idb.get_incident(DB_PATH, projekt_name, pk)
    if not inc:
        return jsonify({"error": "Vorfall nicht gefunden"}), 404
    return jsonify(_enrich(inc))


@nis2_incidents_bp.delete("/projekte/<projekt_name>/incidents/<int:pk>")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def delete_incident(projekt_name, pk):
    try:
        ok = idb.delete_incident(DB_PATH, projekt_name, pk)
        if not ok:
            return jsonify({"error": "Vorfall nicht gefunden"}), 404
        _audit("nis2.incident.deleted", projekt=projekt_name, object_id=str(pk))
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)


# ── Meldungen (Stufen) ──────────────────────────────────────────────────────

@nis2_incidents_bp.post("/projekte/<projekt_name>/incidents/<int:pk>/meldungen")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def save_meldung(projekt_name, pk):
    # Projekt-scoped Containment (IDOR): Meldung nur zu eigenem Vorfall.
    inc = idb.get_incident(DB_PATH, projekt_name, pk)
    if not inc:
        return jsonify({"error": "Vorfall nicht gefunden"}), 404
    body = request.get_json(silent=True) or {}
    try:
        mid = idb.save_meldung(DB_PATH, pk, body)
        _audit("nis2.incident_meldung.saved", projekt=projekt_name,
               object_id=str(pk), typ=body.get("typ", ""), meldung_id=str(mid))
        return jsonify({"ok": True, "id": mid,
                        "incident": _enrich(idb.get_incident(DB_PATH, projekt_name, pk))}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@nis2_incidents_bp.delete(
    "/projekte/<projekt_name>/incidents/<int:pk>/meldungen/<int:meldung_id>")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def delete_meldung(projekt_name, pk, meldung_id):
    inc = idb.get_incident(DB_PATH, projekt_name, pk)
    if not inc:
        return jsonify({"error": "Vorfall nicht gefunden"}), 404
    m = idb.get_meldung(DB_PATH, meldung_id)
    if not m or int(m["incident_pk"]) != int(pk):
        return jsonify({"error": "Meldung nicht gefunden"}), 404
    try:
        idb.delete_meldung(DB_PATH, meldung_id)
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)


# ── BSI-konformer Einzelmeldungs-Export ─────────────────────────────────────

_TYP_LABEL = {
    "24h": "Frühwarnung (24h) — Art. 23 Abs. 4 lit. a NIS2",
    "72h": "Vorfallmeldung (72h) — Art. 23 Abs. 4 lit. b NIS2",
    "zwischen": "Zwischenbericht (auf Ersuchen) — Art. 23 Abs. 4 NIS2",
    "1M": "Abschlussbericht (1 Monat) — Art. 23 Abs. 4 lit. c NIS2",
}


def _build_meldung_markdown(projekt_name: str, inc: dict, m: dict) -> str:
    lines = [
        f"# NIS2-Meldung an BSI/CSIRT — {_TYP_LABEL.get(m['typ'], m['typ'])}",
        "",
        f"- **Projekt:** {projekt_name}",
        f"- **Vorfall-ID:** {inc.get('incident_id', '')}",
        f"- **Titel:** {inc.get('titel', '')}",
        f"- **Kenntniserlangung:** {inc.get('kenntnis_zeitpunkt', '')}",
        f"- **Schweregrad:** {inc.get('schweregrad', '')}",
        f"- **Grenzüberschreitend:** {'ja' if inc.get('grenzueberschreitend') else 'nein'}",
        f"- **Betroffene Assets:** {inc.get('betroffene_assets', '')}",
        f"- **Meldestatus:** {m.get('status', '')}",
        f"- **Übermittelt am:** {m.get('ist_zeitpunkt', '') or '—'}",
        f"- **BSI-Referenz:** {m.get('bsi_referenz', '') or '—'}",
        "",
        "## Meldetext",
        "",
        m.get("text", "") or "(kein Text erfasst)",
    ]
    if m["typ"] == "1M" and inc.get("root_cause"):
        lines += ["", "## Grundursache (Root Cause)", "", inc["root_cause"]]
    return "\n".join(lines)


@nis2_incidents_bp.get(
    "/projekte/<projekt_name>/incidents/<int:pk>/meldungen/<int:meldung_id>/export")
@jwt_required()
@require_permission(Permission.NIS2_EXPORT)
def export_meldung(projekt_name, pk, meldung_id):
    inc = idb.get_incident(DB_PATH, projekt_name, pk)
    if not inc:
        return jsonify({"error": "Vorfall nicht gefunden"}), 404
    m = idb.get_meldung(DB_PATH, meldung_id)
    if not m or int(m["incident_pk"]) != int(pk):
        return jsonify({"error": "Meldung nicht gefunden"}), 404
    try:
        md = _build_meldung_markdown(projekt_name, inc, m)
        buf = io.BytesIO(md.encode("utf-8"))
        fname = f"NIS2-Meldung_{inc.get('incident_id', pk)}_{m['typ']}.md"
        _audit("nis2.incident_meldung.exported", projekt=projekt_name,
               object_id=str(pk), meldung_id=str(meldung_id))
        return send_file(buf, as_attachment=True, download_name=fname,
                         mimetype="text/markdown")
    except Exception as e:
        return _log_500(e)
