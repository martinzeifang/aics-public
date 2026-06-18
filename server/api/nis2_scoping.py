"""N-SCOPE (#1210/#1211) — REST-Blueprint NIS2 Art. 2/3 + Art. 26 Scoping.

Mountpunkt ``/api/nis2-scoping`` (Bindestrich-Prefix → automatischer
nis2-Authz-Guard). 1:1-Scoping-Bewertung je Projekt:
- Größenschwellen-Nachweis (Art. 2/3), deterministische Klassen-Auswertung,
- Hauptniederlassung/EU-Vertreter (Art. 26) mit bedingter Pflichtvalidierung,
- Scoping-Dokument-Export (JSON/Markdown).

Projekt-scoped (IDOR): alle Routen über ``<projekt_name>``.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from server.models.permission import Permission, require_permission

from nis2 import scoping_db as sdb

nis2_scoping_bp = Blueprint("nis2_scoping", __name__)
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


@nis2_scoping_bp.get("/constants")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def constants():
    return jsonify({
        "anhang": list(sdb.ANHANG),
        "size_class": list(sdb.SIZE_CLASS),
    })


@nis2_scoping_bp.get("/projekte/<projekt_name>/scoping")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def get_scoping(projekt_name):
    try:
        return jsonify(sdb.get_scoping(DB_PATH, projekt_name) or {})
    except Exception as e:
        return _log_500(e)


@nis2_scoping_bp.post("/projekte/<projekt_name>/scoping")
@jwt_required()
@require_permission(Permission.NIS2_WRITE)
def save_scoping(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        sc = sdb.save_scoping(DB_PATH, projekt_name, body)
        _audit("nis2.scoping.saved", projekt=projekt_name,
               size_class=sc.get("size_class", ""), version=sc.get("version"))
        return jsonify({"ok": True, "scoping": sc}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


# ── Vorschau der deterministischen Größenschwellen-Auswertung ───────────────

@nis2_scoping_bp.post("/preview-size-class")
@jwt_required()
@require_permission(Permission.NIS2_READ)
def preview_size_class():
    """Berechnet die Klasse ohne zu speichern (Live-Vorschau im Formular)."""
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(sdb.evaluate_size_class(
            int(body.get("mitarbeiterzahl", 0) or 0),
            float(body.get("jahresumsatz", 0) or 0),
            float(body.get("bilanzsumme", 0) or 0),
            body.get("anhang", "keiner")))
    except (ValueError, TypeError):
        return jsonify({"error": "Ungültige Zahlenwerte"}), 400


# ── Scoping-Dokument-Export ──────────────────────────────────────────────────

def _build_scoping_markdown(projekt_name: str, sc: dict) -> str:
    lines = [
        f"# NIS2-Betroffenheitsanalyse / Scoping-Dokument — {projekt_name}",
        f"_Version {sc.get('version', 1)} · Stand {sc.get('scoping_datum', '') or '—'}_",
        "",
        "## Größenschwellen (Art. 2/3 NIS2)",
        f"- **Mitarbeiterzahl:** {sc.get('mitarbeiterzahl', 0)}",
        f"- **Jahresumsatz:** {sc.get('jahresumsatz', 0)} Mio. EUR",
        f"- **Bilanzsumme:** {sc.get('bilanzsumme', 0)} Mio. EUR",
        f"- **Sektor:** {sc.get('sektor', '') or '—'} / {sc.get('subsektor', '') or '—'}",
        f"- **Anhang:** {sc.get('anhang', 'keiner')}",
        f"- **Konzernverbund:** {sc.get('konzernverbund', '') or '—'}",
        "",
        f"### Einstufung: **{sc.get('size_class', '')}**",
        sc.get("size_begruendung", "") or "(keine Begründung)",
        "",
        "## Jurisdiktion / Territorialität (Art. 26 NIS2)",
        f"- **Hauptniederlassung:** {sc.get('hauptniederlassung', '') or '—'}",
        f"- **Zuständige Behörde:** {sc.get('zustaendige_behoerde', '') or '—'}",
        f"- **In der EU niedergelassen:** {'ja' if sc.get('eu_niedergelassen') else 'nein'}",
        f"- **EU-Vertreter:** {sc.get('eu_vertreter', '') or '—'}",
    ]
    if sc.get("notizen"):
        lines += ["", "## Notizen", "", sc["notizen"]]
    return "\n".join(lines)


@nis2_scoping_bp.get("/projekte/<projekt_name>/scoping/export")
@jwt_required()
@require_permission(Permission.NIS2_EXPORT)
def export_scoping(projekt_name):
    sc = sdb.get_scoping(DB_PATH, projekt_name)
    if not sc:
        return jsonify({"error": "Kein Scoping-Datensatz vorhanden"}), 404
    fmt = (request.args.get("format") or "md").lower()
    try:
        if fmt == "json":
            buf = io.BytesIO(json.dumps(sc, ensure_ascii=False, indent=2).encode("utf-8"))
            mimetype, ext = "application/json", "json"
        else:
            buf = io.BytesIO(_build_scoping_markdown(projekt_name, sc).encode("utf-8"))
            mimetype, ext = "text/markdown", "md"
        _audit("nis2.scoping.exported", projekt=projekt_name, format=fmt)
        return send_file(buf, as_attachment=True,
                         download_name=f"NIS2-Scoping_{projekt_name}.{ext}",
                         mimetype=mimetype)
    except Exception as e:
        return _log_500(e)
