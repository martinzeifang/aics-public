"""CRA Art. 13(1) / Annex VII — Traceability + Vollständigkeitsmatrix (#1217).

REST-Blueprint ``/api/cra-traceability``. Bindestrich-Prefix → cra-Authz (#1169).
Per-Requirement Nachweis↔Anforderung-Verknüpfung + granulare Annex-VII-Matrix.
IDOR-sicher (projekt-scoped Routen).
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission
from server.api._common import require_projekt

from cra.db import load_projekt
from cra import traceability_db as tdb

cra_traceability_bp = Blueprint("cra_traceability", __name__)
DB_PATH = Path("data/db/cra.sqlite")


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


def _audit(action: str, **fields):
    try:
        from shared.audit import audit_event
        fields.setdefault("actor", str(get_jwt_identity() or ""))
        audit_event(action, module="cra", details=fields)
    except Exception:  # noqa: BLE001
        pass


@cra_traceability_bp.get("/constants")
@jwt_required()
@require_permission(Permission.CRA_READ)
def constants():
    return jsonify({"annex_vii_bausteine": tdb.ANNEX_VII_BAUSTEINE})


@cra_traceability_bp.get("/projekte/<projekt_name>/dokumente")
@jwt_required()
@require_permission(Permission.CRA_READ)
def list_dokumente(projekt_name):
    try:
        return jsonify(tdb.list_dokumente(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@cra_traceability_bp.post("/projekte/<projekt_name>/dokumente")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def create_dokument(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        pk = tdb.create_dokument(
            DB_PATH, projekt_name, body.get("doc_name", ""),
            doc_path=body.get("doc_path", ""), doc_type=body.get("doc_type", "resource"),
            anforderung_id=body.get("anforderung_id", ""),
            owasp_id=body.get("owasp_id", ""),
            annex_baustein=body.get("annex_baustein", ""))
        _audit("cra.traceability.dokument_erstellt", object_id=str(pk),
               projekt=projekt_name)
        return jsonify(tdb.get_dokument(DB_PATH, pk, projekt_name)), 201
    except Exception as e:
        return _log_500(e)


@cra_traceability_bp.put("/projekte/<projekt_name>/dokumente/<int:pk>/link")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def link_dokument(projekt_name, pk):
    body = request.get_json(silent=True) or {}
    try:
        d = tdb.link_dokument(
            DB_PATH, pk, projekt_name,
            anforderung_id=body.get("anforderung_id"),
            owasp_id=body.get("owasp_id"),
            annex_baustein=body.get("annex_baustein"),
            doc_type=body.get("doc_type"))
        if not d:
            return jsonify({"error": "Dokument nicht gefunden"}), 404
        _audit("cra.traceability.verknuepft", object_id=str(pk), projekt=projekt_name)
        return jsonify(d)
    except Exception as e:
        return _log_500(e)


@cra_traceability_bp.get("/projekte/<projekt_name>/requirement-traceability")
@jwt_required()
@require_permission(Permission.CRA_READ)
def requirement_traceability(projekt_name):
    try:
        return jsonify(tdb.requirement_traceability(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@cra_traceability_bp.get("/projekte/<projekt_name>/annex-vii-status")
@jwt_required()
@require_permission(Permission.CRA_READ)
def annex_vii_status(projekt_name):
    try:
        return jsonify(tdb.annex_vii_status(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@cra_traceability_bp.get("/projekte/<projekt_name>/dokumente/<int:pk>/download")
@jwt_required()
@require_permission(Permission.CRA_READ)
def download_dokument(projekt_name, pk):
    """#1603: Hinterlegten Nachweis öffnen/herunterladen.

    Für ``doc_path=evidence:<id>`` wird die Datei aus dem Evidence-Store ausgeliefert;
    http(s)-Links werden als Redirect zurückgegeben. IDOR-sicher (projekt-scoped)."""
    try:
        from flask import redirect, send_file
        doc = next((d for d in tdb.list_dokumente(DB_PATH, projekt_name) if int(d["id"]) == int(pk)), None)
        if not doc:
            return jsonify({"error": "Nachweis nicht gefunden"}), 404
        path = str(doc.get("doc_path") or "")
        if path.startswith(("http://", "https://")):
            return redirect(path)
        if path.startswith("evidence:"):
            import io
            from pathlib import Path as _P
            from evidence.db import get_document
            doc_id = path.split(":", 1)[1]
            ev = get_document(_P("data/db/evidence.sqlite"), doc_id)
            stored = getattr(ev, "stored_path", "") if ev else ""
            if not stored or not _P(stored).is_file():
                return jsonify({"error": "Belegdatei nicht gefunden"}), 404
            name = str(doc.get("doc_name") or getattr(ev, "filename", None) or "nachweis")
            _audit("cra.dokument.downloaded", projekt=projekt_name, dokument_id=int(pk))
            if stored.lower().endswith(".enc"):
                # Opt-in at-rest-verschlüsselter Beleg → entschlüsselt ausliefern.
                from shared.crypto_at_rest import decrypt_bytes
                from ai_compliance_suite.config import load_config as _lc
                _at = ((_lc() or {}).get("security", {}) or {}).get("at_rest_encryption", {}) or {}
                data_bytes = decrypt_bytes(_P(stored).read_bytes(),
                                           key_env=str(_at.get("key_env", "AICS_AT_REST_KEY")))
                return send_file(io.BytesIO(data_bytes), as_attachment=False,
                                 download_name=name.removesuffix(".enc"))
            return send_file(_P(stored).resolve(), as_attachment=False, download_name=name)
        return jsonify({"error": "Kein öffenbarer Nachweis (interner Verweis)"}), 400
    except Exception as e:
        return _log_500(e)
