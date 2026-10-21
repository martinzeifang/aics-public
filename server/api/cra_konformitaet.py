"""CRA Art. 32 / Annex VIII — Konformitätsbewertung + DoC/CE (#1201).

REST-Blueprint ``/api/cra-konformitaet``. Bindestrich-Prefix → cra-Authz (#1169).
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission
from server.api._common import require_projekt

from cra.db import load_projekt
from cra import konformitaet_db as kdb

cra_konformitaet_bp = Blueprint("cra_konformitaet", __name__)
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


@cra_konformitaet_bp.get("/constants")
@jwt_required()
@require_permission(Permission.CRA_READ)
def constants():
    return jsonify({"wege": list(kdb.WEGE), "ce_status": list(kdb.CE_STATUS),
                    "checkliste": kdb.CHECKLISTE})


@cra_konformitaet_bp.get("/projekte/<projekt_name>/konformitaet")
@jwt_required()
@require_permission(Permission.CRA_READ)
def get_konformitaet(projekt_name):
    try:
        release = request.args.get("release", "")
        rec = kdb.get_konformitaet(DB_PATH, projekt_name, release)
        return jsonify(rec or {})
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/konformitaet/list")
@jwt_required()
@require_permission(Permission.CRA_READ)
def list_konformitaet(projekt_name):
    try:
        return jsonify(kdb.list_konformitaet(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.put("/projekte/<projekt_name>/konformitaet")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def put_konformitaet(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        rec = kdb.save_konformitaet(DB_PATH, projekt_name, body)
        _audit("cra.konformitaet.gespeichert", projekt=projekt_name,
               weg=rec.get("bewertungsweg"))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


# #1220-A: Governance-Sign-off (Freigabe + Lock) — separate CRA_APPROVE-Permission.
@cra_konformitaet_bp.post("/projekte/<projekt_name>/konformitaet/freigeben")
@jwt_required()
@require_permission(Permission.CRA_APPROVE)
def freigeben(projekt_name):
    body = request.get_json(silent=True) or {}
    release = body.get("release_version", "")
    try:
        rec = kdb.freigeben(DB_PATH, projekt_name, release,
                            von=str(get_jwt_identity() or ""))
        _audit("cra.konformitaet.freigegeben", projekt=projekt_name,
               release=release, freigegeben_von=rec.get("freigegeben_von"))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/konformitaet/reopen")
@jwt_required()
@require_permission(Permission.CRA_APPROVE)
def reopen(projekt_name):
    body = request.get_json(silent=True) or {}
    release = body.get("release_version", "")
    try:
        rec = kdb.reopen(DB_PATH, projekt_name, release)
        _audit("cra.konformitaet.reopened", projekt=projekt_name, release=release)
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/konformitaet/doc")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def issue_doc(projekt_name):
    body = request.get_json(silent=True) or {}
    release = body.get("release_version", "")
    doc = body.get("doc") or {}
    try:
        rec = kdb.issue_doc(DB_PATH, projekt_name, doc, release)
        _audit("cra.konformitaet.doc_ausgestellt", projekt=projekt_name,
               doc_version=rec.get("doc_version"))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


# ── Sprint #49: Release-Check (Gate) + Konformitätsnachweis + Sign-off-Archiv ────

@cra_konformitaet_bp.get("/projekte/<projekt_name>/release-check")
@jwt_required()
@require_permission(Permission.CRA_READ)
def release_check(projekt_name):
    """#1612/#1615: Konformitäts-Gate/Release-Readiness mit offenen Punkten + Deep-Links."""
    try:
        from cra.konformitaet_gate import evaluate
        version = request.args.get("version") or None
        return jsonify(evaluate(projekt_name, version=version))
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/nachweis")
@jwt_required()
@require_permission(Permission.CRA_EXPORT)
def konformitaet_nachweis(projekt_name):
    """#1610: Kundenfähiger CRA-Konformitätsnachweis je Version (docx|pdf)."""
    try:
        from cra.konformitaet_report import build_docx, build_pdf
        version = request.args.get("version") or None
        fmt = (request.args.get("format") or "pdf").lower()
        from flask import send_file
        from io import BytesIO
        if fmt == "docx":
            data = build_docx(projekt_name, version=version)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = "docx"
        else:
            data = build_pdf(projekt_name, version=version)
            mime = "application/pdf"; ext = "pdf"
        _audit("cra.konformitaet.nachweis_erzeugt", projekt=projekt_name, version=version, format=ext)
        name = f"CRA-Konformitaetsnachweis_{projekt_name}_{version or 'aktuell'}.{ext}"
        return send_file(BytesIO(data), mimetype=mime, as_attachment=True, download_name=name)
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/nachweis/freigeben")
@jwt_required()
@require_permission(Permission.CRA_EXPORT)
def konformitaet_nachweis_freigeben(projekt_name):
    """#1611: Nachweis je Version freigeben → PDF unveränderlich mit SHA-256 archivieren."""
    try:
        from cra.konformitaet_report import build_pdf
        from cra.konformitaet_gate import evaluate
        from cra import konformitaet_final_db as fdb
        body = request.get_json(silent=True) or {}
        version = str(body.get("version") or "").strip()
        if not version:
            return jsonify({"error": "Feld 'version' ist Pflicht"}), 400
        gate = evaluate(projekt_name, version=version)
        if gate["ampel"] == "rot" and not body.get("confirm_rot"):
            return jsonify({"error": "release_rot", "ampel": "rot",
                            "hinweis": "Release ist nicht konform (offene Punkte). Freigabe nur mit "
                                       "confirm_rot=true (als bewusste bedingte Freigabe).",
                            "offene_punkte": gate["offene_punkte"]}), 428
        pdf = build_pdf(projekt_name, version=version)
        rec = fdb.add_final(DB_PATH, projekt_name, version=version, pdf_bytes=pdf,
                            ampel=gate["ampel"], freigegeben_von=str(get_jwt_identity() or ""))
        _audit("cra.konformitaet.nachweis_freigegeben", projekt=projekt_name, version=version,
               sha256=rec["sha256"], ampel=gate["ampel"])
        return jsonify(rec)
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/nachweis/archiv")
@jwt_required()
@require_permission(Permission.CRA_READ)
def konformitaet_nachweis_archiv(projekt_name):
    try:
        from cra import konformitaet_final_db as fdb
        return jsonify({"eintraege": fdb.list_final(DB_PATH, projekt_name)})
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/nachweis/archiv/<int:final_id>/download")
@jwt_required()
@require_permission(Permission.CRA_READ)
def konformitaet_nachweis_archiv_download(projekt_name, final_id):
    try:
        from cra import konformitaet_final_db as fdb
        from flask import send_file
        rec = fdb.get_final(DB_PATH, projekt_name, final_id)
        if not rec or not Path(rec["pdf_path"]).is_file():
            return jsonify({"error": "Nachweis nicht gefunden"}), 404
        _audit("cra.konformitaet.nachweis_heruntergeladen", projekt=projekt_name, final_id=final_id)
        return send_file(Path(rec["pdf_path"]).resolve(), mimetype="application/pdf",
                         as_attachment=True,
                         download_name=f"CRA-Konformitaetsnachweis_{projekt_name}_{rec.get('version') or ''}.pdf")
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/versions")
@jwt_required()
@require_permission(Permission.CRA_READ)
def release_versions(projekt_name):
    """#1662: Versions-/Tag-Historie des verknüpften Repos (GitHub/GitLab)."""
    try:
        from shared.vcs_repo_config import resolve_repo
        from shared.vcs_versions import list_versions
        projekt = load_projekt(DB_PATH, projekt_name) or {}
        meta = projekt.get("meta") if isinstance(projekt.get("meta"), dict) else {}
        vcs = meta.get("vcs_publish") if isinstance(meta.get("vcs_publish"), dict) else {}
        repo = resolve_repo(vcs, None)
        provider = str(vcs.get("provider") or "github").strip().lower()
        versions = list_versions(provider, repo, vcs) if repo else []
        return jsonify({"repo": repo, "provider": provider if repo else None, "versions": versions})
    except Exception as e:
        return _log_500(e)
