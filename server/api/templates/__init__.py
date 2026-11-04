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
from shared.templates import pdf_converter, validate
from shared.audit import audit_event

templates_bp = Blueprint("templates", __name__)

TEMPLATES_DB = Path("data/db/templates.sqlite")

_READ_PERM = {
    "cra": Permission.CRA_READ, "nis2": Permission.NIS2_READ,
    "aiact": Permission.AIACT_READ, "dsgvo": Permission.DSGVO_READ,
    "risikobewertung": Permission.RB_READ,
    "wiba": Permission.WIBA_READ,
    "compliance_audit": Permission.COMPLIANCE_AUDIT_READ,
}
_EXPORT_PERM = {
    "cra": Permission.CRA_EXPORT, "nis2": Permission.NIS2_EXPORT,
    "aiact": Permission.AIACT_EXPORT, "dsgvo": Permission.DSGVO_EXPORT,
    "risikobewertung": Permission.RB_EXPORT,
    "wiba": Permission.WIBA_EXPORT,
    "compliance_audit": Permission.COMPLIANCE_AUDIT_EXPORT,
}
# Single Source: liegt in der Engine, weil auch die Berichts-Center-Brücke sie
# braucht (#1735). Siehe shared/templates/schema.py.
_MODULE_DB = schema.MODULE_DB


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


def _pruefung(rec: dict[str, Any]) -> dict[str, Any]:
    """Variablen-Prüfung aus der Registry-Zeile (#1741).

    Rechnet auf der beim Upload gespeicherten Variablenliste, nicht auf der Datei —
    dadurch trägt jede Antwort das Ergebnis, ohne das DOCX erneut zu öffnen, und
    auch dann, wenn die Datei inzwischen fehlt.
    """
    namen = json.loads(rec.get("variablen_json") or "[]")
    return validate.pruefe_namen(rec.get("modul") or "", namen).as_dict()


def _pruefung_genau(rec: dict[str, Any]) -> validate.Pruefergebnis:
    """Prüfung **mit der Datei** — für Upload-Antwort und „als Standard setzen".

    Die Pflichtprüfung aus #1753 braucht die Pfade hinter der Variablenwurzel
    (``nachweis.version``, nicht nur ``nachweis``). Aus der Registry lässt sich
    die Datei nur erraten, indem man die gespeicherte Variablenliste vergleicht
    — und sobald zwei Vorlagen dieselben Wurzeln benutzen (zwei Nachweis-
    Vorlagen tun das immer), meldet die Prüfung nur noch, was in **allen**
    Kandidaten fehlt. Ergebnis: Eine Vorlage ohne Release-Angabe galt als
    vollständig, weil eine andere Nachweis-Vorlage sie hatte.

    Hier liegt die Zeile vor, also auch der Dateipfad. Für die **Liste** bleibt
    es bei ``_pruefung`` — dort wären es so viele Dateizugriffe wie Vorlagen.
    """
    pfad = str(rec.get("datei_pfad") or "")
    modul = rec.get("modul") or ""
    if pfad and Path(pfad).is_file():
        return validate.pruefe_variablen(modul, pfad)
    return validate.pruefe_namen(modul, json.loads(rec.get("variablen_json") or "[]"))


def _firma_name(firmen_id: Any) -> str:
    """Firmenname zur ``firmen_id`` — leer für Haus-Vorlagen und bei Fehlern.

    Die Liste zeigt sonst eine Zahl, und „Vorlage gilt für Mandant 7" ist keine
    Angabe, mit der jemand arbeiten kann (#1778).
    """
    if not firmen_id:
        return ""
    try:
        from shared import db as _sdb
        with _sdb.connect(str(Path("data/db/firmen.sqlite"))) as con:
            row = con.execute("SELECT name FROM firmen WHERE id=?",
                              (int(firmen_id),)).fetchone()
        return str(row[0]) if row and row[0] else ""
    except Exception:  # noqa: BLE001
        return ""


def _serialize(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": rec["id"], "modul": rec["modul"], "name": rec["name"],
        # #1777/#1778: Für welchen Bericht und für welchen Mandanten gilt sie?
        "bericht_typ": str(rec.get("bericht_typ") or ""),
        "firmen_id": rec.get("firmen_id"),
        "firma": _firma_name(rec.get("firmen_id")),
        "version": rec["version"], "variablen": json.loads(rec.get("variablen_json") or "[]"),
        # Damit das Admin-UI eine fremde Vorlage sofort als solche zeigt, statt
        # sie erst im kaputten Export des Moduls auffallen zu lassen (#1741).
        "pruefung": _pruefung(rec),
        "mapping": json.loads(rec.get("mapping_json") or "{}"),
        "ist_default": bool(rec["ist_default"]), "aktiv": bool(rec["aktiv"]),
        "sha256": rec["datei_sha256"], "hochgeladen_am": rec["hochgeladen_am"],
        "hochgeladen_von": rec.get("hochgeladen_von", ""), "notizen": rec.get("notizen", ""),
    }


@templates_bp.get("/health")
@jwt_required()
def health():
    return {"soffice_available": pdf_converter.is_soffice_available()}, 200


def _bericht_typ_ok(modul: str, typ: str) -> bool:
    """Gehört dieser Berichtstyp zum Modul? Leer = alle Berichte."""
    if not typ:
        return True
    return any(s.get("key") == typ for s in schema.berichte_typen(modul))


def _firma_erlaubt(firmen_id: int | None) -> bool:
    """Darf der Anfragende für diesen Mandanten arbeiten? (#1185/#1778)

    Fail-closed, anders als der Detail-Guard: Hier wird etwas **angelegt**, und
    eine Vorlage für einen fremden Mandanten ist kein Anzeigefehler, sondern
    eine Datei, die später dessen Dokumente erzeugt.
    """
    if not firmen_id:
        return True
    try:
        claims = get_jwt() or {}
    except Exception:  # noqa: BLE001
        return False
    erlaubt = claims.get("allowed_firmen")
    if not isinstance(erlaubt, list):   # None = alle Firmen (Admin)
        return True
    return int(firmen_id) in [int(x) for x in erlaubt if str(x).strip().isdigit()]


@templates_bp.post("")
@require_permission(Permission.TEMPLATE_MANAGE)
def upload():
    f = request.files.get("file")
    modul = (request.form.get("modul") or "").strip()
    name = (request.form.get("name") or "").strip()
    bericht_typ = (request.form.get("bericht_typ") or "").strip()
    firmen_id = tdb._firmen_id(request.form.get("firmen_id"))
    if not f or not modul or not name:
        return {"error": "file, modul und name sind Pflicht"}, 400
    if modul not in _READ_PERM:
        return {"error": f"Unbekanntes Modul: {modul}"}, 400
    if not _bericht_typ_ok(modul, bericht_typ):
        return {"error": f"Unbekannter Berichtstyp für {modul}: {bericht_typ}"}, 400
    if not _firma_erlaubt(firmen_id):
        return {"error": "Forbidden", "required": "Zugriff auf diese Firma"}, 403
    from server.api.workspace_tmp import workspace_tmpdir
    tmp = Path(workspace_tmpdir()) / "upload.docx"
    f.save(str(tmp))
    try:
        try:
            rec = storage.upload_template(
                tmp, modul=modul, name=name, db_path=TEMPLATES_DB,
                hochgeladen_von=str((get_jwt() or {}).get("sub") or ""),
                notizen=request.form.get("notizen", ""),
                bericht_typ=bericht_typ, firmen_id=firmen_id)
        except Exception as e:
            current_app.logger.warning("template upload abgelehnt: %s: %s", type(e).__name__, e)
            return {"error": "Ungültige Vorlagendatei (kein gültiges DOCX?)"}, 400
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    audit_event("templates.uploaded", module="templates",
                details={"id": rec["id"], "modul": modul, "name": name,
                         "bericht_typ": bericht_typ, "firmen_id": firmen_id})
    out = _serialize(rec)
    # Mit der Datei geprüft (siehe _pruefung_genau) — die Liste bleibt billig.
    out["pruefung"] = _pruefung_genau(rec).as_dict()
    return out, 201


@templates_bp.get("")
@jwt_required()
def list_for_module():
    modul = (request.args.get("modul") or "").strip()
    firmen_id = tdb._firmen_id(request.args.get("firmen_id"))
    if modul and modul not in _READ_PERM:
        return {"error": f"Unbekanntes Modul: {modul}"}, 400
    if modul and not _user_has(_READ_PERM[modul]):
        return {"error": "Forbidden", "required": str(_READ_PERM[modul])}, 403
    if firmen_id and not _firma_erlaubt(firmen_id):
        return {"error": "Forbidden", "required": "Zugriff auf diese Firma"}, 403
    # #1778: Mit Firmen-Angabe die Vorlagen dieses Mandanten **und** die
    # Haus-Vorlagen (das ist die Auswahl, die beim Export gilt); ohne Angabe
    # alles, was der Nutzer sehen darf.
    recs = storage.list_templates(TEMPLATES_DB, modul or None,
                                  firmen_id=firmen_id)
    # ohne modul: nur Module, für die der User Read hat
    if not modul:
        recs = [r for r in recs if _user_has(_READ_PERM.get(r["modul"]))]
    # Firmen-ACL auch ohne Firmen-Filter: Eine Vorlagenliste nennt sonst die
    # Mandanten, die der Nutzer gar nicht sehen darf (#1185). Fail-closed.
    recs = [r for r in recs if _firma_erlaubt(tdb._firmen_id(r.get("firmen_id")))]
    return [_serialize(r) for r in recs], 200


@templates_bp.get("/berichte/<modul>")
@jwt_required()
def berichte_fuer_modul(modul: str):
    """Berichtstypen des Moduls — womit das Admin-UI „für welchen Bericht?" füllt."""
    if modul not in _READ_PERM:
        return {"error": f"Unbekanntes Modul: {modul}"}, 404
    if not _user_has(_READ_PERM[modul]):
        return {"error": "Forbidden", "required": str(_READ_PERM[modul])}, 403
    return {"modul": modul, "berichte": schema.berichte_typen(modul)}, 200


@templates_bp.get("/<int:template_id>")
@jwt_required()
def get_one(template_id: int):
    rec = tdb.get_template(TEMPLATES_DB, template_id)
    if not rec:
        return {"error": "Vorlage nicht gefunden"}, 404
    if not _user_has(_READ_PERM.get(rec["modul"])):
        return {"error": "Forbidden"}, 403
    if not _firma_erlaubt(tdb._firmen_id(rec.get("firmen_id"))):
        return {"error": "Forbidden", "required": "Zugriff auf diese Firma"}, 403
    out = _serialize(rec)
    out["schema"] = schema.get_variables(rec["modul"])
    out["berichte"] = schema.berichte_typen(rec["modul"])
    return out, 200


@templates_bp.get("/schema/<modul>")
@jwt_required()
def schema_for_modul(modul: str):
    """B1 (#1092): Variablen-Schema eines Moduls OHNE Template-ID — damit der
    Anwender die ``{{ tokens }}`` kennt, bevor er eine Vorlage hochlädt."""
    if modul not in _READ_PERM:
        return {"error": f"Unbekanntes Modul: {modul}"}, 404
    if not _user_has(_READ_PERM[modul]):
        return {"error": "Forbidden", "required": str(_READ_PERM[modul])}, 403
    return {"modul": modul, "schema": schema.get_variables(modul)}, 200


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
    if not _firma_erlaubt(tdb._firmen_id(rec.get("firmen_id"))):
        return {"error": "Forbidden", "required": "Zugriff auf diese Firma"}, 403
    # Ein Standard wirkt auf **jeden** Export des Moduls. Genau so ist #1741
    # entstanden: eine Compliance-Audit-Vorlage als CRA-Standard hat sämtliche
    # CRA-Berichte lahmgelegt, bis jemand den Standard entfernte. Hochladen bleibt
    # erlaubt (eine Vorlage darf in Arbeit sein) — zum Standard wird sie nicht.
    erg = _pruefung_genau(rec)
    if not erg.ok:
        return {"error": erg.meldung, "pruefung": erg.as_dict()}, 409
    storage.set_default(TEMPLATES_DB, template_id)
    audit_event("templates.default_set", module="templates",
                details={"id": template_id, "modul": rec["modul"],
                         "bericht_typ": str(rec.get("bericht_typ") or ""),
                         "firmen_id": rec.get("firmen_id")})
    return {"ist_default": True}, 200


@templates_bp.delete("/<int:template_id>")
@require_permission(Permission.TEMPLATE_MANAGE)
def delete_one(template_id: int):
    rec = tdb.get_template(TEMPLATES_DB, template_id)
    if not rec:
        return {"error": "Vorlage nicht gefunden"}, 404
    if not _firma_erlaubt(tdb._firmen_id(rec.get("firmen_id"))):
        return {"error": "Forbidden", "required": "Zugriff auf diese Firma"}, 403
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
    if not _firma_erlaubt(tdb._firmen_id(rec.get("firmen_id"))):
        return {"error": "Forbidden", "required": "Zugriff auf diese Firma"}, 403

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
        # Über die Brücke, damit der Test-Export denselben Kontext sieht wie das
        # Berichts-Center — inklusive der typ-abhängigen Angaben (#1777). Vorher
        # konnte eine Nachweis-Vorlage im Admin-UI leer durchlaufen und im Modul
        # korrekt rendern, was die Prüfung wertlos macht.
        from shared.reports.vorlagen import kontext as _kontext
        context = _kontext(modul, projekt, typ=str(rec.get("bericht_typ") or ""),
                           version=str(data.get("version") or ""))
    except Exception as e:
        current_app.logger.exception("Kontext-Build fehlgeschlagen: %s", e)
        return {"error": "Projekt nicht gefunden oder Kontextfehler"}, 404

    try:
        docx_bytes = engine.render_docx(TEMPLATES_DB, template_id, context)
    except engine.RenderFehler as e:
        # Fehler der Vorlage, nicht des Servers (#1741).
        current_app.logger.warning("Vorlage %s passt nicht zu %s: %s",
                                   template_id, modul, e)
        return e.as_dict(), 422

    ext = "docx"
    out_bytes = docx_bytes
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if fmt == "pdf":
        try:
            out_bytes = pdf_converter.convert_docx_to_pdf(docx_bytes)
            ext = "pdf"
            mime = "application/pdf"
        except pdf_converter.PDFConversionError as e:
            # #1903: Diese Stelle war das Modell für die Aufteilung — sie hatte
            # sie als einzige. Zwei Korrekturen: `PDFConversionFailed` ist ein
            # Fehler des Konverters (502), nicht unserer (500), und sein **Grund**
            # gehört in die Antwort; bisher stand er nur im Log.
            from shared.pdf_fehler import pdf_fehler_antwort
            current_app.logger.warning("PDF-Konversion fehlgeschlagen: %s", e)
            return pdf_fehler_antwort(e)

    audit_event("templates.rendered", module="templates",
                details={"id": template_id, "modul": modul, "projekt": projekt, "format": ext})
    safe_projekt = "".join(c for c in projekt if c.isalnum() or c in "._-") or "export"
    safe_name = "".join(c for c in rec["name"] if c.isalnum() or c in "._-") or "vorlage"
    return send_file(
        io.BytesIO(out_bytes), mimetype=mime, as_attachment=True,
        download_name=f"{safe_projekt}_{safe_name}.{ext}")
