"""DS11 (#1111) — Einwilligungs-Management API (Art. 7 DSGVO).

Self-contained Blueprint. Der Integrator registriert ihn in ``app.py`` mit
``url_prefix='/api/dsgvo-einwilligung'`` (siehe StructuredOutput).

Permissions analog zu ``server/api/dsgvo.py``: Lesen erfordert ``DSGVO_READ``,
schreibende Aktionen ``DSGVO_WRITE``, der CSV-Import ``DSGVO_EXPORT``-nahe Rechte
(hier ``DSGVO_WRITE``, da Daten geschrieben werden).
"""
from pathlib import Path

from flask import Blueprint, current_app, request
from flask_jwt_extended import jwt_required

from server.models.permission import Permission, require_permission

from dsgvo.db import load_projekt
from dsgvo.einwilligung_db import (
    list_einwilligungen,
    get_einwilligung,
    save_einwilligung,
    delete_einwilligung,
    widerruf_einwilligung,
    import_csv,
)

dsgvo_einwilligung_bp = Blueprint("dsgvo_einwilligung", __name__)

DB_PATH = Path("data/db/dsgvo.sqlite")


def _err(e: Exception):
    current_app.logger.exception(
        "%s %s — %s: %s", request.method, request.path, type(e).__name__, e
    )
    return {"error": "Interner Serverfehler"}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Liste + Anlage
# ============================================================

@dsgvo_einwilligung_bp.get("/projekte/<projekt_name>/einwilligungen")
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def list_route(projekt_name: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {"error": "Projekt nicht gefunden"}, 404
        return {"items": list_einwilligungen(DB_PATH, projekt_name)}, 200
    except Exception as e:
        return _err(e)


@dsgvo_einwilligung_bp.post("/projekte/<projekt_name>/einwilligungen")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def create_route(projekt_name: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {"error": "Projekt nicht gefunden"}, 404
        data = request.json or {}
        eid = (data.get("einwilligung_id") or "").strip()
        if not eid:
            return {"error": 'Feld "einwilligung_id" ist Pflicht'}, 400
        created = not get_einwilligung(DB_PATH, projekt_name, eid)
        item = save_einwilligung(
            DB_PATH,
            projekt_name=projekt_name,
            einwilligung_id=eid,
            zweck=data.get("zweck", ""),
            text_version=str(data.get("text_version", "1") or "1"),
            einwilligung_text=data.get("einwilligung_text", ""),
            zeitpunkt=data.get("zeitpunkt", ""),
            kanal=data.get("kanal", ""),
            betroffener_quelle=data.get("betroffener_quelle", ""),
            widerruf_zeitpunkt=data.get("widerruf_zeitpunkt", ""),
            status=data.get("status", "aktiv") or "aktiv",
        )
        return item, (201 if created else 200)
    except Exception as e:
        return _err(e)


# ============================================================
# Einzel-Datensatz
# ============================================================

@dsgvo_einwilligung_bp.get(
    "/projekte/<projekt_name>/einwilligungen/<einwilligung_id>"
)
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_route(projekt_name: str, einwilligung_id: str):
    try:
        item = get_einwilligung(DB_PATH, projekt_name, einwilligung_id)
        if not item:
            return {"error": "Einwilligung nicht gefunden"}, 404
        return item, 200
    except Exception as e:
        return _err(e)


@dsgvo_einwilligung_bp.put(
    "/projekte/<projekt_name>/einwilligungen/<einwilligung_id>"
)
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def update_route(projekt_name: str, einwilligung_id: str):
    try:
        existing = get_einwilligung(DB_PATH, projekt_name, einwilligung_id)
        if not existing:
            return {"error": "Einwilligung nicht gefunden"}, 404
        data = request.json or {}
        item = save_einwilligung(
            DB_PATH,
            projekt_name=projekt_name,
            einwilligung_id=einwilligung_id,
            zweck=data.get("zweck", existing.get("zweck", "")),
            text_version=str(
                data.get("text_version", existing.get("text_version", "1")) or "1"
            ),
            einwilligung_text=data.get(
                "einwilligung_text", existing.get("einwilligung_text", "")
            ),
            zeitpunkt=data.get("zeitpunkt", existing.get("zeitpunkt", "")),
            kanal=data.get("kanal", existing.get("kanal", "")),
            betroffener_quelle=data.get(
                "betroffener_quelle", existing.get("betroffener_quelle", "")
            ),
            widerruf_zeitpunkt=data.get(
                "widerruf_zeitpunkt", existing.get("widerruf_zeitpunkt", "")
            ),
            status=data.get("status", existing.get("status", "aktiv")) or "aktiv",
        )
        return item, 200
    except Exception as e:
        return _err(e)


@dsgvo_einwilligung_bp.delete(
    "/projekte/<projekt_name>/einwilligungen/<einwilligung_id>"
)
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def delete_route(projekt_name: str, einwilligung_id: str):
    try:
        ok = delete_einwilligung(DB_PATH, projekt_name, einwilligung_id)
        if not ok:
            return {"error": "Einwilligung nicht gefunden"}, 404
        return {"deleted": True}, 200
    except Exception as e:
        return _err(e)


# ============================================================
# Widerruf (Art. 7 Abs. 3)
# ============================================================

@dsgvo_einwilligung_bp.post(
    "/projekte/<projekt_name>/einwilligungen/<einwilligung_id>/widerruf"
)
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def widerruf_route(projekt_name: str, einwilligung_id: str):
    try:
        data = request.json or {}
        item = widerruf_einwilligung(
            DB_PATH,
            projekt_name,
            einwilligung_id,
            widerruf_zeitpunkt=data.get("widerruf_zeitpunkt", ""),
        )
        if not item:
            return {"error": "Einwilligung nicht gefunden"}, 404
        return item, 200
    except Exception as e:
        return _err(e)


# ============================================================
# CSV-Import (Stub)
# ============================================================

@dsgvo_einwilligung_bp.post("/projekte/<projekt_name>/einwilligungen/import")
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def import_route(projekt_name: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {"error": "Projekt nicht gefunden"}, 404
        data = request.json or {}
        csv_text = data.get("csv") or data.get("csv_text") or ""
        if not csv_text.strip():
            return {"error": 'Feld "csv" ist Pflicht'}, 400
        result = import_csv(DB_PATH, projekt_name, csv_text)
        return result, 200
    except Exception as e:
        return _err(e)
