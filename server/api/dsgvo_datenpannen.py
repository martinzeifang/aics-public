"""DS-P (#1193) — REST-Blueprint Datenpannen-Fristen + Art.-33-Meldeformular
(``/api/dsgvo-datenpannen``).

ERWEITERT die bestehende Datenpannen-Logik (CRUD bleibt unter ``/api/dsgvo``):
liefert die 72-h-Frist-/Overdue-Felder (Art. 33(1)) und exportiert das
strukturierte Art.-33(3)-Behörden-Meldeformular (a–d) als DOCX/PDF.
"""
from __future__ import annotations

import io
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import jwt_required

from server.models.permission import Permission, require_permission

from dsgvo import datenpannen_frist as pf

dsgvo_datenpannen_bp = Blueprint("dsgvo_datenpannen", __name__)
DB_PATH = Path("data/db/dsgvo.sqlite")


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


@dsgvo_datenpannen_bp.get("/projekte/<projekt_name>/datenpannen")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def list_pannen(projekt_name):
    """Datenpannen mit berechneten Art.-33-Frist-Feldern."""
    try:
        return jsonify(pf.list_pannen_mit_frist(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@dsgvo_datenpannen_bp.get("/projekte/<projekt_name>/datenpannen/fristen")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def fristen_summary(projekt_name):
    """Aggregierte Frist-/Overdue-Übersicht für Cockpit/Pflicht-Doku."""
    try:
        return jsonify(pf.offene_fristen(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@dsgvo_datenpannen_bp.get("/projekte/<projekt_name>/datenpannen/<int:panne_pk>")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_panne(projekt_name, panne_pk):
    """Projekt-scoped Einzel-Lookup (IDOR-sicher)."""
    p = pf.get_panne(DB_PATH, projekt_name, panne_pk)
    if not p:
        return jsonify({"error": "Datenpanne nicht gefunden"}), 404
    return jsonify(p)


@dsgvo_datenpannen_bp.get(
    "/projekte/<projekt_name>/datenpannen/<int:panne_pk>/meldeformular")
@jwt_required()
@require_permission(Permission.DSGVO_EXPORT)
def meldeformular(projekt_name, panne_pk):
    """Art.-33(3)-Behörden-Meldeformular (a–d) als DOCX/PDF."""
    if not pf.get_panne(DB_PATH, projekt_name, panne_pk):
        return jsonify({"error": "Datenpanne nicht gefunden"}), 404
    fmt = (request.args.get("format") or "docx").lower()
    try:
        if fmt == "pdf":
            data = pf.build_meldeformular_pdf(DB_PATH, projekt_name, panne_pk)
            mime = "application/pdf"
        else:
            data = pf.build_meldeformular_docx(DB_PATH, projekt_name, panne_pk)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except RuntimeError as e:
        # PDF-Konverter nicht verfügbar / Timeout.
        current_app.logger.error("meldeformular PDF: %s", e)
        return jsonify({"error": "PDF-Konverter nicht verfügbar"}), 503
    except Exception as e:
        return _log_500(e)
    name = f"Art33-Meldeformular_{projekt_name}_{panne_pk}.{ 'pdf' if fmt == 'pdf' else 'docx' }"
    return send_file(io.BytesIO(data), mimetype=mime, as_attachment=True, download_name=name)
