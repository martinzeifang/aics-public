"""S8 (#1078): Zentrales Risiko-Cockpit — modulübergreifende REST-Aggregation.

``GET /api/risk-cockpit/<firmen_id>`` liefert alle **offenen** Risiken einer
Firma über die Module Risikobewertung (``rb_risiken``) und CRA (``cra_vuln``),
normalisiert auf ein gemeinsames Schema und um CRA→RB-Duplikate bereinigt.

Read-only: Die Aggregation liest ausschließlich (keine Mutation von
``rb_risiken``/``cra_vuln``). Logik in ``shared/risk_cockpit.py``.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, request
from flask_jwt_extended import jwt_required

from server.models.permission import Permission, require_permission

from shared.risk_cockpit import build_cockpit, DEFAULT_RB_DB, DEFAULT_CRA_DB

risk_cockpit_bp = Blueprint("risk_cockpit", __name__)

# Kurzer Modulname (wie im Frontend) → Modul-DB-Datei (für /by-projekt).
_MODULE_ALIASES = {
    "risikobewertung": "risikobewertung.sqlite",
    "nis2": "nis2.sqlite",
    "aiact": "ai_act.sqlite",
    "ai_act": "ai_act.sqlite",
    "dsgvo": "dsgvo.sqlite",
    "cra": "cra.sqlite",
    "wiba": "wiba.sqlite",
}


def _filtered_cockpit(firmen_id: int) -> dict:
    """Aggregation + optionale, additive Server-Filter (case-insensitive)."""
    rb_db = Path(current_app.config.get("RB_DB_PATH", DEFAULT_RB_DB))
    cra_db = Path(current_app.config.get("CRA_DB_PATH", DEFAULT_CRA_DB))
    data = build_cockpit(int(firmen_id), rb_db=rb_db, cra_db=cra_db)
    f_source = (request.args.get("source") or "").strip().lower()
    f_severity = (request.args.get("severity") or "").strip().lower()
    f_status = (request.args.get("status") or "").strip().lower()
    f_projekt = (request.args.get("projekt") or "").strip()
    items = data["items"]
    if f_source:
        items = [i for i in items if i.get("source", "").lower() == f_source]
    if f_severity:
        items = [i for i in items if i.get("severity", "").lower() == f_severity]
    if f_status:
        items = [i for i in items if str(i.get("status", "")).lower() == f_status]
    if f_projekt:
        items = [i for i in items if i.get("projekt", "") == f_projekt]
    data["items"] = items
    return data


@risk_cockpit_bp.get("/<int:firmen_id>")
@jwt_required()
@require_permission(Permission.RB_READ)
def get_risk_cockpit(firmen_id: int):
    """Alle offenen Risiken/Schwachstellen der Firma (read-only Aggregation).

    Optionale Query-Filter: ``source`` (rb|cra), ``severity``, ``status``, ``projekt``.
    """
    try:
        return _filtered_cockpit(int(firmen_id)), 200
    except Exception as e:  # pragma: no cover - defensive
        current_app.logger.exception(
            "%s %s — %s: %s", request.method, request.path, type(e).__name__, e
        )
        return {"error": "Interner Serverfehler"}, 500


@risk_cockpit_bp.get("/by-projekt/<module>/<path:projekt>")
@jwt_required()
@require_permission(Permission.RB_READ)
def get_risk_cockpit_by_projekt(module: str, projekt: str):
    """Cockpit über ein Modul-Projekt: löst firmen_id aus der Projekt-Tabelle auf
    (S1-FK) und aggregiert dann firmenweit. Erlaubt das Einbetten des Cockpits in
    jeden Modul-Tab ohne dass das Frontend die firmen_id kennen muss."""
    try:
        import sqlite3
        from shared.firmen_link import MODULE_PROJECT_TABLES
        dbfile = _MODULE_ALIASES.get(module, module if module.endswith(".sqlite") else "")
        entry = MODULE_PROJECT_TABLES.get(dbfile)
        if not entry:
            return {"error": f"unbekanntes Modul: {module}"}, 400
        table = entry[0]
        mod_db = Path(current_app.config.get("RB_DB_PATH", DEFAULT_RB_DB)).parent / dbfile
        firmen_id = None
        if mod_db.exists():
            con = sqlite3.connect(str(mod_db))
            try:
                cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
                if "firmen_id" in cols:
                    row = con.execute(
                        f"SELECT firmen_id FROM {table} WHERE name=?", (projekt,)
                    ).fetchone()
                    firmen_id = row[0] if row else None
            finally:
                con.close()
        if not firmen_id:
            return {"firmen_id": None, "unassigned": True, "items": [],
                    "summary": {}}, 200
        out = _filtered_cockpit(int(firmen_id))
        out["firmen_id"] = int(firmen_id)
        return out, 200
    except Exception as e:  # pragma: no cover - defensive
        current_app.logger.exception(
            "%s %s — %s: %s", request.method, request.path, type(e).__name__, e
        )
        return {"error": "Interner Serverfehler"}, 500
