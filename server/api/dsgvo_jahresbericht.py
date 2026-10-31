"""DS-J (#1132–#1134) — Jahresbericht REST-Blueprint (``/api/dsgvo-jahresbericht``).

Aggregation/Vorschau, Export (DOCX/PDF), Online-Freigabe (GF) + DSB-Signatur.
"""
from __future__ import annotations

import io
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission
from server.api._common import pdf_fehler
from shared.templates.pdf_converter import PDFConversionError

dsgvo_jahresbericht_bp = Blueprint("dsgvo_jahresbericht", __name__)
DB_PATH = Path("data/db/dsgvo.sqlite")


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


def _audit(action: str, **details):
    try:
        from shared.audit import audit_event
        details.setdefault("actor", str(get_jwt_identity() or ""))
        audit_event(action, module="dsgvo", details=details)
    except Exception:  # noqa: BLE001
        pass


@dsgvo_jahresbericht_bp.get("/projekte/<projekt_name>/jahresbericht/<int:jahr>")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_jahresbericht(projekt_name, jahr):
    try:
        from dsgvo.jahresbericht import build_jahresbericht_context
        from dsgvo import jahresbericht_db as jdb
        ctx = build_jahresbericht_context(DB_PATH, projekt_name, jahr)
        ctx["signoff"] = jdb.get(DB_PATH, projekt_name, jahr)
        return jsonify(ctx)
    except Exception as e:
        return _log_500(e)


@dsgvo_jahresbericht_bp.get("/projekte/<projekt_name>/jahresbericht/<int:jahr>/export")
@jwt_required()
@require_permission(Permission.DSGVO_EXPORT)
def export_jahresbericht(projekt_name, jahr):
    fmt = (request.args.get("format") or "pdf").lower()
    if fmt not in {"pdf", "docx"}:
        return jsonify({"error": "Format muss pdf|docx sein"}), 400
    try:
        from dsgvo import jahresbericht_db as jdb
        from dsgvo import jahresbericht_export as jx
        signoff = jdb.get(DB_PATH, projekt_name, jahr)
        name = f"Datenschutz-Jahresbericht_{projekt_name}_{jahr}".replace("/", "-")
        if fmt == "docx":
            data = jx.build_jahresbericht_docx(DB_PATH, projekt_name, jahr, signoff=signoff)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            fn = f"{name}.docx"
        else:
            try:
                data = jx.build_jahresbericht_pdf(DB_PATH, projekt_name, jahr, signoff=signoff)
            except PDFConversionError as e:
                # #1903: Vorher fing hier ein `except Exception` **jeden** Fehler
                # und nannte den Konverter als Ursache — auch wenn der Fehler im
                # Dokumentbau lag. Jetzt nur noch echte Konverter-Fehler, und die
                # unterschieden; alles andere fällt in _log_500 (500 ist dort richtig).
                return pdf_fehler(e, "Jahresbericht")
            mime = "application/pdf"
            fn = f"{name}.pdf"
        return send_file(io.BytesIO(data), mimetype=mime, as_attachment=True, download_name=fn)
    except Exception as e:
        return _log_500(e)


@dsgvo_jahresbericht_bp.post("/projekte/<projekt_name>/jahresbericht/<int:jahr>/freigeben")
@jwt_required()
@require_permission(Permission.DSGVO_APPROVE)
def freigeben(projekt_name, jahr):
    try:
        from dsgvo import jahresbericht_db as jdb
        cur = jdb.get(DB_PATH, projekt_name, jahr)
        if cur.get("status") != "entwurf":
            return jsonify({"error": f"Nur Entwürfe können freigegeben werden (Status: {cur.get('status')})"}), 409
        rec = jdb.freigeben(DB_PATH, projekt_name, jahr, von=str(get_jwt_identity() or ""))
        _audit("dsgvo.jahresbericht.freigegeben", projekt=projekt_name, jahr=jahr)
        return jsonify({"ok": True, "signoff": rec})
    except Exception as e:
        return _log_500(e)


@dsgvo_jahresbericht_bp.post("/projekte/<projekt_name>/jahresbericht/<int:jahr>/signieren")
@jwt_required()
@require_permission(Permission.DSGVO_SIGN)
def signieren(projekt_name, jahr):
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or str(get_jwt_identity() or "")).strip()
    try:
        from dsgvo import jahresbericht_db as jdb
        from dsgvo import jahresbericht_export as jx
        cur = jdb.get(DB_PATH, projekt_name, jahr)
        if cur.get("status") != "freigegeben":
            return jsonify({"error": "Bericht muss zuerst von der Geschäftsführung freigegeben werden"}), 409
        # Finalisierte PDF erzeugen + unveränderlich ablegen
        try:
            pdf = jx.build_jahresbericht_pdf(DB_PATH, projekt_name, jahr, signoff=cur)
        except PDFConversionError as e:
            # #1903: wie oben — der Grund des Konverters gehört in die Meldung.
            # Die Folge für den Vorgang bleibt und wird zusätzlich genannt: Ohne
            # finale PDF ist die Signatur nach #1132–#1134 nicht abzuschließen.
            from shared.pdf_fehler import pdf_fehler_antwort
            current_app.logger.warning("Signatur-PDF fehlgeschlagen: %s", e)
            nutzlast, status = pdf_fehler_antwort(e)
            nutzlast["error"] += (" Die Signatur kann erst abgeschlossen werden, "
                                  "wenn die finale PDF erzeugt werden konnte.")
            return jsonify(nutzlast), status
        rec = jdb.signieren(DB_PATH, projekt_name, jahr,
                            von=str(get_jwt_identity() or ""), name=name, pdf_bytes=pdf)
        _audit("dsgvo.jahresbericht.signiert", projekt=projekt_name, jahr=jahr, sha256=rec.get("sha256"))
        return jsonify({"ok": True, "signoff": rec})
    except ValueError as e:
        # #1780: Vier-Augen-Verstoß und fehlende Freigabe sind Fachfehler, keine
        # Serverfehler — als 500 wären sie im Frontend „Unbekannter Fehler".
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)
