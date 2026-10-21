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

# #1562: keine System-Controls in einer Organisation mit KI-Systemen (409).
from ai_act.scope import make_org_write_guard as _org_guard  # noqa: E402
aiact_conformity_bp.before_request(_org_guard(DB_PATH))

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
    """Auswahlliste verknüpfbarer CRA-Projekte (read-only, optional).

    #1560: ALLE CRA-Projekte (vorher nur solche mit ``cra_konformitaet``-Zeile und
    hinter einem toten ``Path.exists()``-Guard → unter Postgres immer leer).
    Optional ``?projekt=<AI-Act-Projekt>``: Projekte derselben Firma zuerst, ein
    Produkt-Treffer (``<Firma> – <Produkt>``, #1541) als ``vorschlag``.
    """
    try:
        from cra.db import list_projekte as cra_list, load_projekt as cra_load
        from cra.konformitaet_db import DB_PATH as CRA_DB
        firma = produkt = ""
        p = load_projekt(DB_PATH, request.args.get("projekt", "")) if request.args.get("projekt") else None
        if p:
            firma = (p.get("organisation") or "").strip().casefold()
            produkt = (p.get("produkt") or "").strip().casefold()
        items = []
        for name in cra_list(Path(CRA_DB)):
            cp = cra_load(Path(CRA_DB), name) or {}
            same_firma = bool(firma) and (cp.get("unternehmen") or "").strip().casefold() == firma
            same_produkt = same_firma and bool(produkt) and (cp.get("produkt") or "").strip().casefold() == produkt
            items.append({"name": name, "unternehmen": cp.get("unternehmen") or "",
                          "produkt": cp.get("produkt") or "",
                          "firma_match": same_firma, "produkt_match": same_produkt})
        items.sort(key=lambda i: (not i["produkt_match"], not i["firma_match"], i["name"].casefold()))
        vorschlag = next((i["name"] for i in items if i["produkt_match"]), "")
        # "projekte" bleibt eine Namensliste (Abwärtskompatibilität des Stores).
        return jsonify({"projekte": [i["name"] for i in items], "items": items,
                        "vorschlag": vorschlag})
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
