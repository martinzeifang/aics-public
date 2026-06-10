"""N-REG (#1203) — REST-Blueprint NIS2 Art. 27 BSI-Registrierungs-Stammdatensatz.

Mountpunkt ``/api/nis2-registrierung`` (Bindestrich-Prefix → automatischer
nis2-Authz-Guard). 1:1-Registrierung je Projekt mit den 6 Pflichtangaben,
Vollständigkeits-Validierung, Vorbefüllung aus Projekt-/Scoping-/Klassifikator-
Stammdaten, Export (JSON/Markdown) für die BSI-Portal-Eingabe und Wiedervorlage
der jährlichen Bestätigung (3-Monats-Frist-Hinweis).
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from server.models.permission import Permission, require_permission

from nis2 import registrierung_db as rdb

nis2_registrierung_bp = Blueprint("nis2_registrierung", __name__)
DB_PATH = Path("data/db/nis2.sqlite")


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


def _audit(action: str, **fields):
    try:
        from shared.audit import audit_event
        fields.setdefault("actor", str(get_jwt_identity() or ""))
        audit_event(action, module="nis2", details=fields)
    except Exception:  # noqa: BLE001
        pass


# ── Wiedervorlage (jährliche Bestätigung) ───────────────────────────────────

def _confirm_status(reg: dict) -> dict:
    """Ampel/Status der jährlichen Bestätigungs-Wiedervorlage.

    Nutzt die kanonische ``shared.deadlines``-Engine: Frist = nächste Jahres-
    Bestätigung, Warnung (amber) ab 3 Monaten vor Fälligkeit.
    """
    from shared import deadlines as dl
    base = reg.get("naechste_jahres_bestaetigung") or ""
    if not base:
        return {"ampel": "grey", "status": "no_base", "due_at": "",
                "hinweis": "Keine jährliche Bestätigung terminiert."}
    # 3-Monats-Vorwarnung: Stufe mit offset 0 ab dem Fälligkeitsdatum, warn 90d.
    base_dt = dl.parse_dt(base)
    if base_dt is None:
        return {"ampel": "grey", "status": "no_base", "due_at": base, "hinweis": ""}
    now = dl.now_utc()
    days_left = (base_dt - now).total_seconds() / 86400.0
    if days_left < 0:
        ampel, status = "red", "overdue"
        hinweis = "Jährliche Bestätigung überfällig."
    elif days_left <= 90:
        ampel, status = "amber", "due_soon"
        hinweis = f"Jährliche Bestätigung in {int(days_left)} Tagen fällig (3-Monats-Frist)."
    else:
        ampel, status = "green", "on_track"
        hinweis = f"Nächste Bestätigung in {int(days_left)} Tagen."
    return {"ampel": ampel, "status": status, "due_at": base,
            "days_left": round(days_left, 1), "hinweis": hinweis}


def _enrich(reg: dict | None) -> dict | None:
    if not reg:
        return reg
    reg = dict(reg)
    reg["bestaetigung"] = _confirm_status(reg)
    return reg


@nis2_registrierung_bp.get("/constants")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def constants():
    return jsonify({
        "status": list(rdb.REG_STATUS),
        "pflichtfelder": list(rdb.PFLICHTFELDER),
    })


@nis2_registrierung_bp.get("/projekte/<projekt_name>/registrierung")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def get_registrierung(projekt_name):
    try:
        return jsonify(_enrich(rdb.get_registrierung(DB_PATH, projekt_name)) or {})
    except Exception as e:
        return _log_500(e)


@nis2_registrierung_bp.post("/projekte/<projekt_name>/registrierung")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def save_registrierung(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        reg = rdb.save_registrierung(DB_PATH, projekt_name, body)
        _audit("nis2.registrierung.saved", projekt=projekt_name,
               status=reg.get("status", ""))
        return jsonify({"ok": True, "registrierung": _enrich(reg)}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


# ── Vorbefüllung aus Stammdaten/Scoping/Klassifikator ───────────────────────

@nis2_registrierung_bp.get("/projekte/<projekt_name>/registrierung/prefill")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def prefill(projekt_name):
    """Liefert Vorschlagswerte aus Projekt-Stammdaten + Scoping + Klassifikator."""
    try:
        from nis2.db import load_projekt
        suggest: dict = {}
        p = load_projekt(DB_PATH, projekt_name)
        if p:
            suggest["name"] = p.get("unternehmen", "") or projekt_name
            meta = json.loads(p.get("meta_json") or "{}")
            klass = (meta.get("nis2") or {}).get("klassifikator") or {}
            if klass.get("sektor"):
                suggest["sektor"] = klass["sektor"]
            if klass.get("subsektor"):
                suggest["subsektor"] = klass["subsektor"]
        # Scoping ergänzt Sektor/Anhang/Hauptniederlassung, falls vorhanden.
        try:
            from nis2 import scoping_db as sdb
            sc = sdb.get_scoping(DB_PATH, projekt_name)
            if sc:
                suggest.setdefault("sektor", sc.get("sektor", ""))
                suggest.setdefault("subsektor", sc.get("subsektor", ""))
                if sc.get("hauptniederlassung"):
                    suggest["anschrift"] = sc["hauptniederlassung"]
                if sc.get("eu_vertreter"):
                    suggest["eu_niederlassungen"] = sc["eu_vertreter"]
                if sc.get("anhang") in ("I", "II"):
                    suggest.setdefault(
                        "einrichtungsart", f"Anhang {sc['anhang']}")
        except Exception:  # noqa: BLE001
            pass
        return jsonify(suggest)
    except Exception as e:
        return _log_500(e)


# ── Export (BSI-Portal-Eingabe) ─────────────────────────────────────────────

def _build_markdown(projekt_name: str, reg: dict) -> str:
    lines = [
        f"# NIS2-Registrierung beim BSI (Art. 27) — {projekt_name}",
        f"_Status: {reg.get('status', '')}_",
        "",
        "## Pflichtangaben (Art. 27 Abs. 2)",
        f"1. **Name:** {reg.get('name', '') or '—'}",
        f"2. **Sektor/Subsektor/Einrichtungsart:** "
        f"{reg.get('sektor', '') or '—'} / {reg.get('subsektor', '') or '—'} / "
        f"{reg.get('einrichtungsart', '') or '—'}",
        f"3. **Anschrift Hauptniederlassung:** {reg.get('anschrift', '') or '—'}",
        f"   - Sonstige EU-Niederlassungen/Vertreter: "
        f"{reg.get('eu_niederlassungen', '') or '—'}",
        f"4. **Kontakt:** {reg.get('kontakt_email', '') or '—'} / "
        f"{reg.get('kontakt_telefon', '') or '—'}",
        f"5. **Mitgliedstaaten der Diensteerbringung:** "
        f"{reg.get('mitgliedstaaten', '') or '—'}",
        f"6. **IP-Adressbereiche:** {reg.get('ip_bereiche', '') or '—'}",
        "",
        "## Übermittlung",
        f"- **Registrierungsdatum:** {reg.get('registrierungs_datum', '') or '—'}",
        f"- **Bestätigungsreferenz:** {reg.get('bestaetigungs_referenz', '') or '—'}",
        f"- **Nächste Jahres-Bestätigung:** "
        f"{reg.get('naechste_jahres_bestaetigung', '') or '—'}",
    ]
    miss = rdb.missing_fields(reg)
    if miss:
        lines += ["", f"> ⚠️ Unvollständig — fehlende Pflichtangaben: {', '.join(miss)}"]
    return "\n".join(lines)


@nis2_registrierung_bp.get("/projekte/<projekt_name>/registrierung/export")
@jwt_required()
@require_permission(Permission.NIS2_EXPORT)
def export_registrierung(projekt_name):
    reg = rdb.get_registrierung(DB_PATH, projekt_name)
    if not reg:
        return jsonify({"error": "Keine Registrierung vorhanden"}), 404
    fmt = (request.args.get("format") or "md").lower()
    try:
        if fmt == "json":
            buf = io.BytesIO(json.dumps(reg, ensure_ascii=False, indent=2).encode("utf-8"))
            mimetype, ext = "application/json", "json"
        else:
            buf = io.BytesIO(_build_markdown(projekt_name, reg).encode("utf-8"))
            mimetype, ext = "text/markdown", "md"
        _audit("nis2.registrierung.exported", projekt=projekt_name, format=fmt)
        return send_file(buf, as_attachment=True,
                         download_name=f"NIS2-Registrierung_{projekt_name}.{ext}",
                         mimetype=mimetype)
    except Exception as e:
        return _log_500(e)
