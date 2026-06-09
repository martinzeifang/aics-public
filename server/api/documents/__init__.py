"""S4 (#1153) — Generisches Dokumenten-REST-Blueprint (Factory, 5× registriert).

Ein Blueprint, modul-parametrisiert. Mount je Modul unter ``/api/<urlmod>-dokumente``
(Area-Prefix-Muster wie dsgvo-tom/dsgvo-kontrollen). Explizite Permissions + Audit.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Callable

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission

from shared.documents import db as ddb
from shared.documents import catalog as dcat


def _audit(modul: str, action: str, **details):
    try:
        from shared.audit import audit_event
        details.setdefault("actor", str(get_jwt_identity() or ""))
        audit_event(f"{modul}.dokument.{action}", module=modul, details=details)
    except Exception:  # noqa: BLE001
        pass


def _resolve_firmen_id(db_path: Path, modul: str, projekt: str):
    try:
        import sqlite3
        from shared.firmen_link import MODULE_PROJECT_TABLES
        entry = MODULE_PROJECT_TABLES.get(f"{modul}.sqlite")
        if not entry:
            return None
        table = entry[0]
        con = sqlite3.connect(str(db_path))
        try:
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
            if "firmen_id" not in cols:
                return None
            row = con.execute(f"SELECT firmen_id FROM {table} WHERE name=?", (projekt,)).fetchone()
            return row[0] if row else None
        finally:
            con.close()
    except Exception:  # noqa: BLE001
        return None


def make_documents_blueprint(modul: str, url_prefix: str, db_path: Path,
                             *, perm_read: Permission, perm_write: Permission,
                             perm_export: Permission) -> Blueprint:
    bp = Blueprint(f"{modul}_documents", __name__)

    def _log_500(e: Exception):
        current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                     type(e).__name__, e)
        return jsonify({"error": "Interner Serverfehler"}), 500

    def _serialize(doc: dict) -> dict:
        spec = dcat.get_doc_spec(modul, doc.get("doc_type", "")) or {}
        return {**doc, "rechtsgrundlage": spec.get("rechtsgrundlage", ""),
                "katalog_titel": spec.get("titel", "")}

    # ── Liste ──────────────────────────────────────────────────────────────
    @bp.get("/<projekt>")
    @jwt_required()
    @require_permission(perm_read)
    def list_docs(projekt):
        try:
            docs = ddb.list_documents(db_path, modul, projekt)
            return jsonify([_serialize(d) for d in docs])
        except Exception as e:
            return _log_500(e)

    # ── Katalog (Soll-Ist) ─────────────────────────────────────────────────
    @bp.get("/<projekt>/catalog")
    @jwt_required()
    @require_permission(perm_read)
    def catalog(projekt):
        try:
            docs = ddb.list_documents(db_path, modul, projekt)
            by_type: dict[str, dict] = {}
            for d in docs:
                # bester Status je doc_type (freigegeben > final > entwurf)
                rank = {"entwurf": 1, "final": 2, "freigegeben": 3}
                cur = by_type.get(d["doc_type"])
                if not cur or rank.get(d["status"], 0) > rank.get(cur["status"], 0):
                    by_type[d["doc_type"]] = d
            out = []
            for spec in dcat.get_catalog(modul):
                ex = by_type.get(spec["doc_type"])
                out.append({**spec,
                            "vorhanden": bool(ex),
                            "status": ex["status"] if ex else "fehlt",
                            "doc_id": ex["id"] if ex else None})
            return jsonify({"katalog": out,
                            "weitere": [_serialize(d) for d in docs
                                        if not dcat.get_doc_spec(modul, d.get("doc_type", ""))]})
        except Exception as e:
            return _log_500(e)

    # ── Anlegen ────────────────────────────────────────────────────────────
    @bp.post("/<projekt>")
    @jwt_required()
    @require_permission(perm_write)
    def create_doc(projekt):
        body = request.get_json(silent=True) or {}
        try:
            doc_type = body.get("doc_type", "")
            spec = dcat.get_doc_spec(modul, doc_type)
            titel = body.get("titel") or (spec["titel"] if spec else "Neues Dokument")
            did = ddb.create_document(
                db_path, modul, projekt=projekt, doc_type=doc_type, titel=titel,
                content_html=body.get("content_html", ""),
                source=body.get("source", "manuell"),
                assistant_key=body.get("assistant_key"),
                firmen_id=_resolve_firmen_id(db_path, modul, projekt),
                meta=body.get("meta") or {}, created_by=str(get_jwt_identity() or ""))
            _audit(modul, "created", projekt=projekt, doc_id=did, doc_type=doc_type)
            return jsonify({"ok": True, "id": did}), 201
        except Exception as e:
            return _log_500(e)

    # ── Einzeln lesen/ändern/löschen ───────────────────────────────────────
    @bp.get("/<projekt>/<int:doc_id>")
    @jwt_required()
    @require_permission(perm_read)
    def get_doc(projekt, doc_id):
        d = ddb.get_document(db_path, modul, doc_id)
        if not d or d.get("projekt") != projekt:
            return jsonify({"error": "Dokument nicht gefunden"}), 404
        return jsonify(_serialize(d))

    @bp.put("/<projekt>/<int:doc_id>")
    @jwt_required()
    @require_permission(perm_write)
    def update_doc(projekt, doc_id):
        d = ddb.get_document(db_path, modul, doc_id)
        if not d or d.get("projekt") != projekt:
            return jsonify({"error": "Dokument nicht gefunden"}), 404
        if d.get("status") == "freigegeben" and not request.args.get("force"):
            # Freigegebenes Dokument: Bearbeitung erzeugt neue Version (erlaubt),
            # aber Status muss vorher zurückgesetzt werden — hier nur Warnung.
            pass
        body = request.get_json(silent=True) or {}
        try:
            res = ddb.update_document(db_path, modul, doc_id,
                                      titel=body.get("titel"),
                                      content_html=body.get("content_html"),
                                      meta=body.get("meta"),
                                      updated_by=str(get_jwt_identity() or ""))
            _audit(modul, "updated", projekt=projekt, doc_id=doc_id)
            return jsonify({"ok": True, "dokument": _serialize(res)})
        except Exception as e:
            return _log_500(e)

    @bp.delete("/<projekt>/<int:doc_id>")
    @jwt_required()
    @require_permission(perm_write)
    def delete_doc(projekt, doc_id):
        ok = ddb.soft_delete_document(db_path, modul, doc_id, deleted_by=str(get_jwt_identity() or ""))
        if not ok:
            return jsonify({"error": "Dokument nicht gefunden"}), 404
        _audit(modul, "deleted", projekt=projekt, doc_id=doc_id)
        return jsonify({"ok": True})

    @bp.post("/<projekt>/<int:doc_id>/status")
    @jwt_required()
    @require_permission(perm_write)
    def status_doc(projekt, doc_id):
        body = request.get_json(silent=True) or {}
        status = body.get("status", "")
        try:
            res = ddb.set_status(db_path, modul, doc_id, status,
                                 updated_by=str(get_jwt_identity() or ""))
            if not res:
                return jsonify({"error": "Dokument nicht gefunden"}), 404
            _audit(modul, "status_changed", projekt=projekt, doc_id=doc_id, status=status)
            return jsonify({"ok": True, "dokument": _serialize(res)})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return _log_500(e)

    # ── Export DOCX/PDF ────────────────────────────────────────────────────
    @bp.post("/<projekt>/<int:doc_id>/export")
    @jwt_required()
    @require_permission(perm_export)
    def export_doc(projekt, doc_id):
        fmt = (request.args.get("format") or "pdf").lower()
        if fmt not in {"pdf", "docx"}:
            return jsonify({"error": "Format muss pdf|docx sein"}), 400
        d = ddb.get_document(db_path, modul, doc_id)
        if not d or d.get("projekt") != projekt:
            return jsonify({"error": "Dokument nicht gefunden"}), 404
        doc = _serialize(d)
        doc.setdefault("meta", {})["projekt"] = projekt
        name = (doc.get("titel") or "Dokument").replace(" ", "_").replace("/", "-")
        try:
            from shared.documents import export as dx
            if fmt == "docx":
                data = dx.render_document_docx(doc)
                mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                fn = f"{name}.docx"
            else:
                try:
                    data = dx.render_document_pdf(doc)
                except Exception as e:  # noqa: BLE001
                    current_app.logger.warning("Dokument-PDF fehlgeschlagen: %s", e)
                    return jsonify({"error": "PDF-Konverter nicht verfügbar — DOCX nutzen."}), 503
                mime = "application/pdf"
                fn = f"{name}.pdf"
            _audit(modul, "exported", projekt=projekt, doc_id=doc_id, format=fmt)
            return send_file(io.BytesIO(data), mimetype=mime, as_attachment=True, download_name=fn)
        except Exception as e:
            return _log_500(e)

    return bp


# Modul-Konfiguration für die Registrierung in server/app.py
DOCUMENT_MODULES = [
    # (db_modul, url_mod, db_file, READ, WRITE, EXPORT)
    ("ai_act", "aiact", "ai_act.sqlite", Permission.AIACT_READ, Permission.AIACT_WRITE, Permission.AIACT_EXPORT),
    ("cra", "cra", "cra.sqlite", Permission.CRA_READ, Permission.CRA_WRITE, Permission.CRA_EXPORT),
    ("nis2", "nis2", "nis2.sqlite", Permission.NIS2_READ, Permission.NIS2_WRITE, Permission.NIS2_EXPORT),
    ("dsgvo", "dsgvo", "dsgvo.sqlite", Permission.DSGVO_READ, Permission.DSGVO_WRITE, Permission.DSGVO_EXPORT),
    ("wiba", "wiba", "wiba.sqlite", Permission.WIBA_READ, Permission.WIBA_WRITE, Permission.WIBA_EXPORT),
]


def register_document_blueprints(app, data_dir: Path) -> None:
    for modul, urlmod, dbfile, pr, pw, pe in DOCUMENT_MODULES:
        bp = make_documents_blueprint(
            modul, f"/api/{urlmod}-dokumente", Path(data_dir) / dbfile,
            perm_read=pr, perm_write=pw, perm_export=pe)
        app.register_blueprint(bp, url_prefix=f"/api/{urlmod}-dokumente")
