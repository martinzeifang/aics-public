"""REST-Layer der Cross-Module Word-Vorlagen-Engine (#991).

Endpoints unter /api/templates. Verwaltung (Upload/Mapping/Default/Delete) braucht
TEMPLATE_MANAGE (Admin); Listing/Render nutzen die modul-spezifischen
READ-/EXPORT-Permissions. /api/templates ist KEIN Modul-Prefix im authz-Guard —
die Endpoints prüfen daher selbst (jwt_required + Permission).
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required, verify_jwt_in_request, get_jwt

from server.models.permission import Permission, require_permission, has_permission
from shared.templates import storage, engine, schema, db as tdb
from shared.templates import pdf_converter
from shared.audit import audit_event

templates_bp = Blueprint("templates", __name__)

TEMPLATES_DB = Path("data/db/templates.sqlite")

_READ_PERM = {
    "cra": Permission.CRA_READ, "nis2": Permission.NIS2_READ,
    "aiact": Permission.AIACT_READ, "dsgvo": Permission.DSGVO_READ,
    "risikobewertung": Permission.RB_READ,
}
_EXPORT_PERM = {
    "cra": Permission.CRA_EXPORT, "nis2": Permission.NIS2_EXPORT,
    "aiact": Permission.AIACT_EXPORT, "dsgvo": Permission.DSGVO_EXPORT,
    "risikobewertung": Permission.RB_EXPORT,
}
_MODULE_DB = {
    "cra": Path("data/db/cra.sqlite"), "nis2": Path("data/db/nis2.sqlite"),
    "aiact": Path("data/db/ai_act.sqlite"), "dsgvo": Path("data/db/dsgvo.sqlite"),
    "risikobewertung": Path("data/db/risikobewertung.sqlite"),
}


def _user_has(permission) -> bool:
    try:
        verify_jwt_in_request()
        claims = get_jwt()
    except Exception:
        return False
    roles = claims.get("roles", []) or []
    extra = claims.get("extra_permissions", []) or []
    if not roles and isinstance(claims.get("sub"), dict):
        roles = claims["sub"].get("roles", [])
        extra = claims["sub"].get("extra_permissions", extra)
    return has_permission(roles, permission, extra)


def _serialize(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": rec["id"], "modul": rec["modul"], "name": rec["name"],
        "version": rec["version"], "variablen": json.loads(rec.get("variablen_json") or "[]"),
        "mapping": json.loads(rec.get("mapping_json") or "{}"),
        "ist_default": bool(rec["ist_default"]), "aktiv": bool(rec["aktiv"]),
        "sha256": rec["datei_sha256"], "hochgeladen_am": rec["hochgeladen_am"],
        "hochgeladen_von": rec.get("hochgeladen_von", ""), "notizen": rec.get("notizen", ""),
    }


@templates_bp.get("/health")
@jwt_required()
def health():
    return {"soffice_available": pdf_converter.is_soffice_available()}, 200


@templates_bp.post("")
@require_permission(Permission.TEMPLATE_MANAGE)
def upload():
    f = request.files.get("file")
    modul = (request.form.get("modul") or "").strip()
    name = (request.form.get("name") or "").strip()
    if not f or not modul or not name:
        return {"error": "file, modul und name sind Pflicht"}, 400
    if modul not in _READ_PERM:
        return {"error": f"Unbekanntes Modul: {modul}"}, 400
    from server.api.workspace_tmp import workspace_tmpdir
    tmp = Path(workspace_tmpdir()) / "upload.docx"
    f.save(str(tmp))
    try:
        try:
            rec = storage.upload_template(
                tmp, modul=modul, name=name, db_path=TEMPLATES_DB,
                hochgeladen_von=str((get_jwt() or {}).get("sub") or ""),
                notizen=request.form.get("notizen", ""))
        except Exception as e:
            current_app.logger.warning("template upload abgelehnt: %s: %s", type(e).__name__, e)
            return {"error": "Ungültige Vorlagendatei (kein gültiges DOCX?)"}, 400
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    audit_event("templates.uploaded", module="templates",
                details={"id": rec["id"], "modul": modul, "name": name})
    return _serialize(rec), 201


@templates_bp.get("")
@jwt_required()
def list_for_module():
    modul = (request.args.get("modul") or "").strip()
    if modul and modul not in _READ_PERM:
        return {"error": f"Unbekanntes Modul: {modul}"}, 400
    if modul and not _user_has(_READ_PERM[modul]):
        return {"error": "Forbidden", "required": str(_READ_PERM[modul])}, 403
    recs = storage.list_templates(TEMPLATES_DB, modul or None)
    # ohne modul: nur Module, für die der User Read hat
    if not modul:
        recs = [r for r in recs if _user_has(_READ_PERM.get(r["modul"]))]
    return [_serialize(r) for r in recs], 200


@templates_bp.get("/<int:template_id>")
@jwt_required()
def get_one(template_id: int):
    rec = tdb.get_template(TEMPLATES_DB, template_id)
    if not rec:
        return {"error": "Vorlage nicht gefunden"}, 404
    if not _user_has(_READ_PERM.get(rec["modul"])):
        return {"error": "Forbidden"}, 403
    out = _serialize(rec)
    out["schema"] = schema.get_variables(rec["modul"])
    return out, 200


@templates_bp.put("/<int:template_id>/mapping")
@require_permission(Permission.TEMPLATE_MANAGE)
def put_mapping(template_id: int):
    rec = tdb.get_template(TEMPLATES_DB, template_id)
    if not rec:
        return {"error": "Vorlage nicht gefunden"}, 404
    data = request.json or {}
    storage.set_mapping(TEMPLATES_DB, template_id, data.get("mapping") or {})
    return {"updated": True}, 200


@templates_bp.put("/<int:template_id>/default")
@require_permission(Permission.TEMPLATE_MANAGE)
def put_default(template_id: int):
    rec = tdb.get_template(TEMPLATES_DB, template_id)
    if not rec:
        return {"error": "Vorlage nicht gefunden"}, 404
    storage.set_default(TEMPLATES_DB, template_id)
    return {"ist_default": True}, 200


@templates_bp.delete("/<int:template_id>")
@require_permission(Permission.TEMPLATE_MANAGE)
def delete_one(template_id: int):
    rec = tdb.get_template(TEMPLATES_DB, template_id)
    if not rec:
        return {"error": "Vorlage nicht gefunden"}, 404
    data = request.json or {}
    storage.soft_delete(TEMPLATES_DB, template_id,
                        by=str((get_jwt() or {}).get("sub") or ""),
                        reason=data.get("reason", ""))
    audit_event("templates.deleted", module="templates",
                details={"id": template_id, "modul": rec["modul"]})
    return {"deleted": True}, 200


@templates_bp.post("/<int:template_id>/render")
@jwt_required()
def render(template_id: int):
    rec = tdb.get_template(TEMPLATES_DB, template_id)
    if not rec or not rec.get("aktiv", 1):
        return {"error": "Vorlage nicht gefunden"}, 404
    modul = rec["modul"]
    if not _user_has(_EXPORT_PERM.get(modul)):
        return {"error": "Forbidden", "required": str(_EXPORT_PERM.get(modul))}, 403

    data = request.json or {}
    projekt = (data.get("projekt") or "").strip()
    fmt = (data.get("format") or "docx").lower()
    if not projekt:
        return {"error": "projekt ist Pflicht"}, 400
    if fmt not in ("docx", "pdf"):
        return {"error": "format muss docx oder pdf sein"}, 400

    builder = schema.get_context_builder(modul)
    if builder is None:
        return {"error": f"Für Modul '{modul}' ist noch kein Adapter implementiert"}, 501

    try:
        context = builder(_MODULE_DB[modul], projekt)
    except Exception as e:
        current_app.logger.exception("Kontext-Build fehlgeschlagen: %s", e)
        return {"error": "Projekt nicht gefunden oder Kontextfehler"}, 404

    docx_bytes = engine.render_docx(TEMPLATES_DB, template_id, context)

    ext = "docx"
    out_bytes = docx_bytes
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if fmt == "pdf":
        try:
            out_bytes = pdf_converter.convert_docx_to_pdf(docx_bytes)
            ext = "pdf"
            mime = "application/pdf"
        except pdf_converter.PDFConversionUnavailable:
            return {"error": "PDF-Konversion nicht konfiguriert",
                    "hint": "LibreOffice fehlt im Container"}, 503
        except pdf_converter.PDFConversionTimeout:
            return {"error": "PDF-Konversion überschritt das Zeitlimit"}, 504
        except pdf_converter.PDFConversionFailed as e:
            current_app.logger.warning("PDF-Konversion fehlgeschlagen: %s", e)
            return {"error": "PDF-Konversion fehlgeschlagen"}, 500

    audit_event("templates.rendered", module="templates",
                details={"id": template_id, "modul": modul, "projekt": projekt, "format": ext})
    safe_projekt = "".join(c for c in projekt if c.isalnum() or c in "._-") or "export"
    safe_name = "".join(c for c in rec["name"] if c.isalnum() or c in "._-") or "vorlage"
    return send_file(
        io.BytesIO(out_bytes), mimetype=mime, as_attachment=True,
        download_name=f"{safe_projekt}_{safe_name}.{ext}")
