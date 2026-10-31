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
from server.api._common import pdf_fehler
from shared.templates.pdf_converter import PDFConversionError

from dsgvo import datenpannen_frist as pf
from dsgvo import meldepflicht as mp

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
    """Datenpannen mit berechneter Art.-33-Frist **und** Meldepflicht.

    #1891: Die beiden Pflicht-Häkchen kamen bis v8.2.3 aus dem Browser — keine
    Stelle leitete sie ab, obwohl Art. 33 Abs. 1 und Art. 34 Abs. 1 die
    Bedingung nennen und ``risikoeinschaetzung`` daneben steht. Der gerechnete
    Stand kommt jetzt mit; **überschrieben wird nichts** (das Häkchen bleibt
    die Entscheidung des Verantwortlichen).
    """
    try:
        pannen = pf.list_pannen_mit_frist(DB_PATH, projekt_name)
        return jsonify([mp.enrich_panne(p) for p in pannen])
    except Exception as e:
        return _log_500(e)


@dsgvo_datenpannen_bp.get("/projekte/<projekt_name>/datenpannen/meldepflicht")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def meldepflicht_uebersicht(projekt_name):
    """Die offenen Widersprüche zur Meldepflicht über alle Pannen (#1891).

    Nur **offene** Vorgänge: Eine Liste, die bei jeder Panne anschlägt, wird
    abgeschaltet (#1774/#1877).
    """
    try:
        pannen = [mp.enrich_panne(p)
                  for p in pf.list_pannen_mit_frist(DB_PATH, projekt_name)]
        return jsonify({"widersprueche": mp.offene_widersprueche(pannen),
                        "gesamt": len(pannen)})
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
    except PDFConversionError as e:
        # #1903: Hier stand `except RuntimeError` — der Konverter wirft aber
        # direkt von Exception ab. Der Zweig griff also **nie**, und jeder
        # PDF-Fehler wurde unten zu einem 500 „Interner Serverfehler". Jetzt
        # unterschieden: 503 nicht erreichbar · 504 Zeitlimit · 502 mit Grund.
        return pdf_fehler(e, "Art-33-Meldeformular")
    except Exception as e:
        return _log_500(e)
    name = f"Art33-Meldeformular_{projekt_name}_{panne_pk}.{ 'pdf' if fmt == 'pdf' else 'docx' }"
    return send_file(io.BytesIO(data), mimetype=mime, as_attachment=True, download_name=name)
