"""DS-K (#1129–#1131) — REST-Blueprint Jährlicher Kontrollplan (``/api/dsgvo-kontrollen``).

- Kontrollen CRUD (DSGVO_WRITE), Stammdaten nach Freigabe gesperrt.
- Freigabe (DSGVO_APPROVE, GF/DSB) — auditiert.
- Durchführungs-Dokumentation + Datei-Anhänge (SHA-256, Magic-Bytes-Validierung).
"""
from __future__ import annotations

import io
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission

from dsgvo import kontrollen_db as kdb

dsgvo_kontrollen_bp = Blueprint("dsgvo_kontrollen", __name__)
DB_PATH = Path("data/db/dsgvo.sqlite")

_ALLOWED_EXT = {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".txt", ".md", ".csv"}
_MAX_BYTES = 25 * 1024 * 1024


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


def _audit(action: str, **fields):
    try:
        from shared.audit import audit_event
        fields.setdefault("actor", str(get_jwt_identity() or ""))
        audit_event(action, module="dsgvo", details=fields)
    except Exception:  # noqa: BLE001
        pass


# ── Konstanten ────────────────────────────────────────────────────────────────

@dsgvo_kontrollen_bp.get("/constants")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def constants():
    return jsonify({"status": list(kdb.STATUS), "bereiche": list(kdb.BEREICHE),
                    "frequenz": list(kdb.FREQUENZ)})


# ── Kontrollen ────────────────────────────────────────────────────────────────

@dsgvo_kontrollen_bp.get("/projekte/<projekt_name>/kontrollen")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def list_kontrollen(projekt_name):
    try:
        jahr = request.args.get("jahr", type=int)
        return jsonify(kdb.list_kontrollen(DB_PATH, projekt_name, jahr=jahr))
    except Exception as e:
        return _log_500(e)


@dsgvo_kontrollen_bp.post("/projekte/<projekt_name>/kontrollen")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def save_kontrolle(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        # Stammdaten nach Freigabe/Abschluss gesperrt (#1130).
        existing = kdb.get_kontrolle_by_cid(DB_PATH, projekt_name, body.get("kontroll_id", ""))
        if existing and existing.get("status") in ("freigegeben", "abgeschlossen"):
            return jsonify({"error": "Freigegebene/abgeschlossene Kontrolle ist gesperrt"}), 409
        pk = kdb.save_kontrolle(DB_PATH, projekt_name, body)
        return jsonify({"id": pk, "ok": True}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@dsgvo_kontrollen_bp.post("/projekte/<projekt_name>/kontrollen/seed")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def seed_kontrollen(projekt_name):
    body = request.get_json(silent=True) or {}
    jahr = int(body.get("jahr") or 0)
    if not jahr:
        return jsonify({"error": "'jahr' ist Pflicht"}), 400
    try:
        n = kdb.seed_standard(DB_PATH, projekt_name, jahr)
        return jsonify({"ok": True, "angelegt": n})
    except Exception as e:
        return _log_500(e)


@dsgvo_kontrollen_bp.get("/kontrollen/<int:pk>")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_kontrolle(pk):
    k = kdb.get_kontrolle(DB_PATH, pk)
    if not k:
        return jsonify({"error": "Kontrolle nicht gefunden"}), 404
    return jsonify(k)


@dsgvo_kontrollen_bp.post("/kontrollen/<int:pk>/freigeben")
@jwt_required()
@require_permission(Permission.DSGVO_APPROVE)
def freigeben(pk):
    k = kdb.get_kontrolle(DB_PATH, pk)
    if not k:
        return jsonify({"error": "Kontrolle nicht gefunden"}), 404
    if k.get("status") != "geplant":
        return jsonify({"error": "Nur geplante Kontrollen können freigegeben werden"}), 409
    try:
        who = str(get_jwt_identity() or "")
        kdb.set_status(DB_PATH, pk, "freigegeben", freigabe_von=who)
        _audit("dsgvo.kontrolle.freigegeben", object_id=str(pk),
               projekt=k.get("projekt_name", ""))
        return jsonify({"ok": True, "kontrolle": kdb.get_kontrolle(DB_PATH, pk)})
    except Exception as e:
        return _log_500(e)


@dsgvo_kontrollen_bp.post("/kontrollen/<int:pk>/dokumentieren")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def dokumentieren(pk):
    k = kdb.get_kontrolle(DB_PATH, pk)
    if not k:
        return jsonify({"error": "Kontrolle nicht gefunden"}), 404
    body = request.get_json(silent=True) or {}
    try:
        kdb.dokumentieren(
            DB_PATH, pk,
            durchgefuehrt_am=body.get("durchgefuehrt_am", ""),
            durchgefuehrt_von=body.get("durchgefuehrt_von", "") or str(get_jwt_identity() or ""),
            ergebnis=body.get("ergebnis", ""),
            abschliessen=bool(body.get("abschliessen")))
        return jsonify({"ok": True, "kontrolle": kdb.get_kontrolle(DB_PATH, pk)})
    except Exception as e:
        return _log_500(e)


@dsgvo_kontrollen_bp.delete("/kontrollen/<int:pk>")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def delete_kontrolle(pk):
    try:
        kdb.delete_kontrolle(DB_PATH, pk)
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)


# ── Anhänge ───────────────────────────────────────────────────────────────────

@dsgvo_kontrollen_bp.get("/kontrollen/<int:pk>/anhaenge")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def list_anhaenge(pk):
    return jsonify(kdb.list_anhaenge(DB_PATH, pk))


@dsgvo_kontrollen_bp.post("/kontrollen/<int:pk>/anhaenge")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def upload_anhang(pk):
    if not kdb.get_kontrolle(DB_PATH, pk):
        return jsonify({"error": "Kontrolle nicht gefunden"}), 404
    up = request.files.get("file")
    if not up or not up.filename:
        return jsonify({"error": "Keine Datei"}), 400
    ext = Path(up.filename).suffix.lower()
    if ext not in _ALLOWED_EXT:
        return jsonify({"error": f"Dateityp nicht erlaubt: {ext}"}), 400
    data = up.read()
    if len(data) > _MAX_BYTES:
        return jsonify({"error": "Datei zu groß (max. 25 MB)"}), 400
    # Magic-Bytes-Validierung (für bekannte Typen).
    try:
        from shared.upload_validation import validate_magic_bytes, UploadValidationError
        try:
            validate_magic_bytes(data, suffix=ext)
        except UploadValidationError as e:
            return jsonify({"error": f"Dateiinhalt passt nicht zur Endung: {e}"}), 400
    except ImportError:
        pass
    try:
        rec = kdb.add_anhang(DB_PATH, pk, filename=up.filename, data=data,
                             mime=up.mimetype or "", uploaded_by=str(get_jwt_identity() or ""))
        _audit("dsgvo.kontroll_anhang.uploaded", object_id=str(pk), filename=up.filename)
        return jsonify({"ok": True, "anhang": rec}), 201
    except Exception as e:
        return _log_500(e)


@dsgvo_kontrollen_bp.get("/anhaenge/<int:anhang_id>/download")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def download_anhang(anhang_id):
    a = kdb.get_anhang(DB_PATH, anhang_id)
    if not a:
        return jsonify({"error": "Anhang nicht gefunden"}), 404
    p = Path(a["stored_path"])
    if not p.exists():
        return jsonify({"error": "Datei fehlt"}), 410
    return send_file(str(p), as_attachment=True, download_name=a["filename"])


@dsgvo_kontrollen_bp.delete("/anhaenge/<int:anhang_id>")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def delete_anhang(anhang_id):
    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip()
    if len(reason) < 5:
        return jsonify({"error": "Begründung (≥5 Zeichen) erforderlich"}), 400
    ok = kdb.soft_delete_anhang(DB_PATH, anhang_id, by=str(get_jwt_identity() or ""), reason=reason)
    if not ok:
        return jsonify({"error": "Anhang nicht gefunden"}), 404
    _audit("dsgvo.kontroll_anhang.deleted", object_id=str(anhang_id), reason=reason)
    return jsonify({"ok": True})
