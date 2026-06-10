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
from shared.net_validation import validate_outbound_url, SSRFError


def _validate_external_url(url: str | None) -> str | None:
    """SSRF-sichere Validierung (#1233). Leere URL → None; ungültig → ValueError."""
    if url is None:
        return None
    url = str(url).strip()
    if not url:
        return None
    return validate_outbound_url(url)  # nur http/https, keine internen Adressen


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
                            "doc_id": ex["id"] if ex else None,
                            # #1233: Web-Verknüpfung im Register-Badge anzeigen
                            "doc_mode": ex["doc_mode"] if ex else "inapp",
                            "external_url": ex.get("external_url") if ex else None})
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
            doc_mode = body.get("doc_mode", "inapp")
            try:
                ext_url = _validate_external_url(body.get("external_url")) \
                    if doc_mode == "extern" else None
            except (SSRFError, ValueError) as e:
                return jsonify({"error": f"Ungültige Web-URL: {e}"}), 400
            did = ddb.create_document(
                db_path, modul, projekt=projekt, doc_type=doc_type, titel=titel,
                content_html=body.get("content_html", ""),
                source=body.get("source", "manuell"),
                assistant_key=body.get("assistant_key"),
                firmen_id=_resolve_firmen_id(db_path, modul, projekt),
                meta=body.get("meta") or {}, created_by=str(get_jwt_identity() or ""),
                doc_mode=doc_mode, external_url=ext_url,
                external_label=body.get("external_label"))
            _audit(modul, "created", projekt=projekt, doc_id=did, doc_type=doc_type,
                   doc_mode=doc_mode)
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
        # #1233: Ziel-Modus bestimmen (Body > Bestand) für die URL-Validierung.
        target_mode = body.get("doc_mode", d.get("doc_mode", "inapp"))
        try:
            ext_url_arg = body.get("external_url", None)
            if ext_url_arg is not None and target_mode == "extern":
                ext_url_arg = _validate_external_url(ext_url_arg)
        except (SSRFError, ValueError) as e:
            return jsonify({"error": f"Ungültige Web-URL: {e}"}), 400
        try:
            res = ddb.update_document(db_path, modul, doc_id,
                                      titel=body.get("titel"),
                                      content_html=body.get("content_html"),
                                      meta=body.get("meta"),
                                      doc_mode=body.get("doc_mode"),
                                      external_url=ext_url_arg,
                                      external_label=body.get("external_label"),
                                      updated_by=str(get_jwt_identity() or ""))
            _audit(modul, "updated", projekt=projekt, doc_id=doc_id,
                   doc_mode=res.get("doc_mode") if res else None)
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

    # ── Manueller Erreichbarkeits-Check (extern, #1233) ────────────────────
    @bp.post("/<projekt>/<int:doc_id>/check-link")
    @jwt_required()
    @require_permission(perm_write)
    def check_link(projekt, doc_id):
        d = ddb.get_document(db_path, modul, doc_id)
        if not d or d.get("projekt") != projekt:
            return jsonify({"error": "Dokument nicht gefunden"}), 404
        url = (d.get("external_url") or "").strip()
        if d.get("doc_mode") != "extern" or not url:
            return jsonify({"error": "Dokument hat keine externe URL"}), 400
        reachable = False
        try:
            from shared.net_validation import safe_get
            # Manuell ausgelöst (kein Auto-Polling) — SSRF-sicher inkl. Redirects.
            resp = safe_get(url, timeout=8)
            reachable = resp.status_code < 400
            resp.close()
        except SSRFError as e:
            return jsonify({"error": f"Ungültige Web-URL: {e}"}), 400
        except Exception as e:  # noqa: BLE001 — Netzfehler = nicht erreichbar
            current_app.logger.info("Link-Check fehlgeschlagen (%s): %s", url, e)
            reachable = False
        res = ddb.record_reachability(db_path, modul, doc_id, reachable=reachable,
                                      updated_by=str(get_jwt_identity() or ""))
        _audit(modul, "link_checked", projekt=projekt, doc_id=doc_id, reachable=reachable)
        return jsonify({"ok": True, "reachable": reachable, "dokument": _serialize(res)})

    # ── Konformitäts-Checkliste (#1234) ────────────────────────────────────
    @bp.get("/<projekt>/<int:doc_id>/checklist")
    @jwt_required()
    @require_permission(perm_read)
    def get_checklist(projekt, doc_id):
        d = ddb.get_document(db_path, modul, doc_id)
        if not d or d.get("projekt") != projekt:
            return jsonify({"error": "Dokument nicht gefunden"}), 404
        try:
            soll = dcat.get_checklist(modul, d.get("doc_type", ""))
            ist = ddb.get_checklist_status(db_path, modul, doc_id)
            items = []
            erfuellt_pflicht = pflicht_total = 0
            for it in soll:
                st = ist.get(it["id"], {})
                done = bool(st.get("erfuellt"))
                items.append({**it, "erfuellt": done,
                              "kommentar": st.get("kommentar", "")})
                if it.get("pflicht", True):
                    pflicht_total += 1
                    if done:
                        erfuellt_pflicht += 1
            erfuellt_total = sum(1 for i in items if i["erfuellt"])
            return jsonify({
                "doc_type": d.get("doc_type", ""),
                "items": items,
                # #1236: Querverweis-Bausteine (vorhandene Modul-Daten als Bestandteil).
                "bausteine": dcat.get_bausteine(modul, d.get("doc_type", "")),
                "fortschritt": {
                    "erfuellt": erfuellt_total, "gesamt": len(items),
                    "pflicht_erfuellt": erfuellt_pflicht, "pflicht_gesamt": pflicht_total,
                }})
        except Exception as e:
            return _log_500(e)

    @bp.put("/<projekt>/<int:doc_id>/checklist")
    @jwt_required()
    @require_permission(perm_write)
    def put_checklist(projekt, doc_id):
        d = ddb.get_document(db_path, modul, doc_id)
        if not d or d.get("projekt") != projekt:
            return jsonify({"error": "Dokument nicht gefunden"}), 404
        body = request.get_json(silent=True) or {}
        items = body.get("items")
        if not isinstance(items, dict):
            return jsonify({"error": "items muss ein Objekt {item_id: {erfuellt,kommentar}} sein"}), 400
        try:
            ist = ddb.set_checklist_status(db_path, modul, doc_id, items,
                                           updated_by=str(get_jwt_identity() or ""))
            _audit(modul, "checklist_updated", projekt=projekt, doc_id=doc_id,
                   anzahl=len(items))
            return jsonify({"ok": True, "status": ist})
        except Exception as e:
            return _log_500(e)

    @bp.get("/<projekt>/<int:doc_id>/checklist/prompt")
    @jwt_required()
    @require_permission(perm_read)
    def checklist_prompt(projekt, doc_id):
        """Copy/Paste-KI-Prompt zur Prüfung der Annex-Punkte (kein Auto-Setzen)."""
        d = ddb.get_document(db_path, modul, doc_id)
        if not d or d.get("projekt") != projekt:
            return jsonify({"error": "Dokument nicht gefunden"}), 404
        soll = dcat.get_checklist(modul, d.get("doc_type", ""))
        if not soll:
            return jsonify({"error": "Keine Checkliste für diesen Dokumenttyp"}), 404
        spec = dcat.get_doc_spec(modul, d.get("doc_type", "")) or {}
        punkte = "\n".join(f'- [{i["id"]}] {i["label"]} ({i.get("rechtsbezug","")})' for i in soll)
        if d.get("doc_mode") == "extern":
            inhalt = f"Externe Web-Doku: {d.get('external_url') or '(keine URL)'}\n" \
                     "(Inhalt der verlinkten Seite hier einfügen, falls verfügbar.)"
        else:
            inhalt = (d.get("content_html") or "(noch kein Inhalt)")
        prompt = (
            f"Du bist Compliance-Prüfer. Prüfe, ob das folgende Dokument "
            f"„{spec.get('titel') or d.get('doc_type')}\" die gesetzlich geforderten "
            f"Pflichtinhalte ({spec.get('rechtsgrundlage','')}) abdeckt.\n\n"
            f"PFLICHTINHALTE (jeweils mit ID):\n{punkte}\n\n"
            f"DOKUMENT-INHALT:\n{inhalt}\n\n"
            "Antworte ausschließlich als JSON: "
            '{\"items\": [{\"id\": \"<id>\", \"erfuellt\": true|false, '
            '\"begruendung\": \"...\"}]}. '
            "Setze erfuellt nur dann true, wenn der Punkt inhaltlich klar abgedeckt ist."
        )
        return jsonify({"prompt": prompt})

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
