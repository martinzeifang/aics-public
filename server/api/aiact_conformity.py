"""AI-Act Art. 43/48 — Konformitätsbewertung + CE REST-Blueprint (``/api/aiact-conformity``, #1198).

Strukturiertes Konformitätsbewertungsverfahren (Annex VI intern / Annex VII NB),
Annex-VI-Checkliste, NB-Zertifikats-Upload, CE-Register, Re-Assessment-Trigger und
DoC-Gate. Bindestrich-Prefix mappt automatisch auf den ``aiact``-Guard.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission

from ai_act import conformity as conf
from ai_act.db import load_projekt

aiact_conformity_bp = Blueprint("aiact_conformity", __name__)
DB_PATH = Path("data/db/ai_act.sqlite")

_MAX_CERT_BYTES = 25 * 1024 * 1024


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


def _audit(action: str, **fields):
    try:
        from shared.audit import audit_event
        fields.setdefault("actor", str(get_jwt_identity() or ""))
        audit_event(action, module="aiact", details=fields)
    except Exception:  # noqa: BLE001
        pass


@aiact_conformity_bp.get("/constants")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def constants():
    return jsonify({"verfahren": conf.verfahren_katalog(),
                    "checkliste": conf.checkliste_katalog(),
                    "ergebnis": list(conf.ERGEBNIS)})


@aiact_conformity_bp.get("/projekte/<projekt_name>/conformity")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def get_conformity(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify({
            "record": conf.get_or_empty(DB_PATH, projekt_name),
            "doc_gate": conf.doc_gate(DB_PATH, projekt_name),
        })
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.put("/projekte/<projekt_name>/conformity")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def save_conformity(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        rec = conf.save(DB_PATH, projekt_name, body)
        _audit("aiact.conformity.saved", projekt=projekt_name,
               verfahren=rec.get("verfahren"), ergebnis=rec.get("ergebnis"))
        return jsonify({"record": rec, "doc_gate": conf.doc_gate(DB_PATH, projekt_name)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.post("/projekte/<projekt_name>/certificate")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def upload_certificate(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify({"error": 'Datei-Feld "file" fehlt'}), 400
        if not f.filename.lower().endswith(".pdf"):
            return jsonify({"error": "Nur PDF-Zertifikate werden unterstützt"}), 400
        content = f.read()
        if not content:
            return jsonify({"error": "Leere Datei"}), 400
        if len(content) > _MAX_CERT_BYTES:
            return jsonify({"error": "Zertifikat zu groß (max. 25 MB)"}), 400
        # Magic-Byte-Prüfung (PDF).
        try:
            from shared.upload_validation import validate_magic_bytes
            validate_magic_bytes(content, suffix=".pdf")
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        rec = conf.store_certificate(DB_PATH, projekt_name, f.filename, content)
        _audit("aiact.conformity.certificate_uploaded", projekt=projekt_name,
               sha256=rec.get("nb_zertifikat_sha256"))
        return jsonify({"record": rec, "doc_gate": conf.doc_gate(DB_PATH, projekt_name)}), 201
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.get("/projekte/<projekt_name>/doc-gate")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def doc_gate(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify(conf.doc_gate(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


# ── Optionale CRA-Verknüpfung (#1243) ───────────────────────────────────────────
# Grundfall: keine Verknüpfung (manuell). Optional kann ein CRA-Projekt verknüpft
# werden → dessen CE/Konformitätsdaten werden read-only referenziert. „Manuell
# überstimmen" (sticky) verhindert jede Automatik-Übernahme. Jederzeit lösbar.

@aiact_conformity_bp.get("/cra-projekte")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def cra_projekte():
    """Auswahlliste verknüpfbarer CRA-Projekte (read-only, optional)."""
    try:
        from cra.konformitaet_db import DB_PATH as CRA_DB
        from shared import db as _sdb
        from pathlib import Path as _P
        path = _P(CRA_DB)
        if not path.exists():
            return jsonify({"projekte": []})
        con = _sdb.connect(str(path))
        try:
            try:
                rows = con.execute(
                    "SELECT DISTINCT projekt_name FROM cra_konformitaet "
                    "ORDER BY projekt_name").fetchall()
            except Exception:
                rows = []
        finally:
            con.close()
        return jsonify({"projekte": [r[0] for r in rows]})
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.get("/projekte/<projekt_name>/cra-link")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def get_cra_link(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify(conf.get_cra_link(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.put("/projekte/<projekt_name>/cra-link")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def put_cra_link(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        link = conf.set_cra_link(
            DB_PATH, projekt_name,
            linked_cra_projekt=body.get("linked_cra_projekt"),
            manual_override=body.get("manual_override"))
        _audit("aiact.conformity.cra_link_set", projekt=projekt_name,
               linked=link.get("linked_cra_projekt"),
               manual_override=link.get("manual_override"))
        return jsonify(link)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)
