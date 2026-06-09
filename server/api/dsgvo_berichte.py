"""DS-B (#1135–#1138) — Einzelberichte/Berichts-Center (``/api/dsgvo-berichte``)."""
from __future__ import annotations

import io
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import jwt_required

from server.models.permission import Permission, require_permission

dsgvo_berichte_bp = Blueprint("dsgvo_berichte", __name__)
DB_PATH = Path("data/db/dsgvo.sqlite")


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


@dsgvo_berichte_bp.get("/berichte")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def list_berichte():
    from dsgvo.einzelberichte import available_reports
    return jsonify(available_reports())


@dsgvo_berichte_bp.get("/projekte/<projekt_name>/berichte/<area>/export")
@jwt_required()
@require_permission(Permission.DSGVO_EXPORT)
def export_bericht(projekt_name, area):
    fmt = (request.args.get("format") or "pdf").lower()
    if fmt not in {"pdf", "docx"}:
        return jsonify({"error": "Format muss pdf|docx sein"}), 400
    try:
        from dsgvo import einzelberichte as eb
        if area not in eb.AREA_REPORTS:
            return jsonify({"error": f"Unbekannter Bericht: {area}"}), 404
        titel = eb.AREA_REPORTS[area]["titel"].replace(" ", "_")
        name = f"{titel}_{projekt_name}".replace("/", "-")
        if fmt == "docx":
            data = eb.build_docx(DB_PATH, projekt_name, area)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            fn = f"{name}.docx"
        else:
            try:
                data = eb.build_pdf(DB_PATH, projekt_name, area)
            except Exception as e:  # noqa: BLE001
                current_app.logger.warning("Einzelbericht-PDF fehlgeschlagen: %s", e)
                return jsonify({"error": "PDF-Konverter nicht verfügbar — DOCX nutzen."}), 503
            mime = "application/pdf"
            fn = f"{name}.pdf"
        return send_file(io.BytesIO(data), mimetype=mime, as_attachment=True, download_name=fn)
    except Exception as e:
        return _log_500(e)
