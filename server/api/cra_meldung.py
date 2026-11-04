"""CRA Art. 14 — Melde-Workflow (#1192) + Nutzer-Advisory/CSAF (#1209).

REST-Blueprint ``/api/cra-meldung``. Bindestrich-Prefix → cra-Authz-Guard (#1169).
Deadline-Ampeln via ``shared/deadlines``. IDOR-sicher (projekt-scoped Routen).
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission
from server.api._common import require_projekt

import cra.deadlines as dl
from cra.db import load_projekt
from cra import meldung_db as mdb

cra_meldung_bp = Blueprint("cra_meldung", __name__)
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


def _stage_set_for(typ: str) -> str:
    return "cra_art14_incident" if typ == "serious_incident" else "cra_art14"


def _with_deadlines(m: dict) -> dict:
    """Meldung um Deadline-Auswertung (Ampel/Countdown) + Nachweis anreichern.

    #1760: Die Abschlussfrist läuft ab Verfügbarkeit der Korrekturmaßnahme
    (Schwachstelle) bzw. ab Einreichung der 72-Stunden-Meldung (Vorfall), nicht
    ab Erkennung. ``cra.deadlines.art14_fristen`` setzt den Fristbeginn und
    führt die Stufe als ``unbestimmt``, solange er fehlt — vorher konnte die
    Ampel Wochen zu früh rot zeigen. Bereits gemeldete Stufen werden als
    erfüllt geführt statt weiter als überfällig.
    """
    try:
        m["deadlines"] = dl.art14_fristen(
            m["erkannt_am"], _stage_set_for(m.get("typ", "")),
            massnahme_verfuegbar_ab=m.get("massnahme_verfuegbar_ab"),
            notification_gemeldet_am=m.get("notification_gemeldet_am"),
            erfuellt={s: m.get(f"{s}_gemeldet_am") or ""
                      for s in mdb.STUFEN if m.get(f"{s}_gemeldet_am")},
        )
    except Exception:
        m["deadlines"] = None
    try:
        m["nachweis"] = mdb.nachweis_status(m)
    except Exception:
        m["nachweis"] = None
    return m


def _unvollstaendig(e: mdb.AngabenUnvollstaendig):
    """400 mit Feldliste — die Oberfläche soll sagen können, was fehlt."""
    return jsonify({"error": str(e), "fehlende_felder": e.fehlende,
                    "kontext": e.kontext}), 400


# ── Konstanten ──────────────────────────────────────────────────────────────────

@cra_meldung_bp.get("/constants")
@jwt_required()
@require_permission(Permission.CRA_READ)
def constants():
    return jsonify({
        "typen": list(mdb.TYPEN),
        "status": list(mdb.STATUS),
        # #1760: Stufen, Adressaten und Mitgliedstaaten kommen aus einer Quelle
        # (meldung_db) — das Formular soll die Pflichtfelder nicht selbst kennen.
        "stufen": list(mdb.STUFEN),
        "kanaele": list(mdb.KANAELE),
        "mitgliedstaaten": mdb.MITGLIEDSTAATEN,
        "empfaenger_pflichtfelder": {
            k: [f for f, _ in mdb.PFLICHT_FELDER[k]] for k in mdb.KANAELE},
        "advisory_pflichtfelder": [f for f, _ in mdb.ADVISORY_PFLICHT],
        "abschlussfrist_anker": dl.FINAL_REPORT_ANKER,
    })


# ── Meldungen ─────────────────────────────────────────────────────────────────

@cra_meldung_bp.get("/projekte/<projekt_name>/meldungen")
@jwt_required()
@require_permission(Permission.CRA_READ)
def list_meldungen(projekt_name):
    try:
        items = [_with_deadlines(m) for m in mdb.list_meldungen(DB_PATH, projekt_name)]
        return jsonify(items)
    except Exception as e:
        return _log_500(e)


@cra_meldung_bp.post("/projekte/<projekt_name>/meldungen")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def create_meldung(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        pk = mdb.create_meldung(DB_PATH, projekt_name, body)
        _audit("cra.meldung.erstellt", object_id=str(pk), projekt=projekt_name)
        return jsonify(_with_deadlines(mdb.get_meldung(DB_PATH, pk, projekt_name))), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@cra_meldung_bp.get("/projekte/<projekt_name>/meldungen/<int:pk>")
@jwt_required()
@require_permission(Permission.CRA_READ)
def get_meldung(projekt_name, pk):
    m = mdb.get_meldung(DB_PATH, pk, projekt_name)
    if not m:
        return jsonify({"error": "Meldung nicht gefunden"}), 404
    return jsonify(_with_deadlines(m))


@cra_meldung_bp.put("/projekte/<projekt_name>/meldungen/<int:pk>")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def update_meldung(projekt_name, pk):
    body = request.get_json(silent=True) or {}
    try:
        if not mdb.update_meldung(DB_PATH, pk, projekt_name, body):
            return jsonify({"error": "Meldung nicht gefunden"}), 404
        return jsonify(_with_deadlines(mdb.get_meldung(DB_PATH, pk, projekt_name)))
    except Exception as e:
        return _log_500(e)


@cra_meldung_bp.post("/projekte/<projekt_name>/meldungen/<int:pk>/stufe")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def set_stufe(projekt_name, pk):
    """Stufe als gemeldet verbuchen — nur mit belegtem Adressaten (#1760).

    ``empfaenger`` im Body: ``{"csirt": {...}, "enisa": {...}}``. Fehlen
    Mitgliedstaat oder Einreichungsreferenz, antwortet der Endpunkt 400 mit
    ``fehlende_felder`` und schreibt nichts.
    """
    body = request.get_json(silent=True) or {}
    neuer_status = body.get("status", "")
    try:
        m = mdb.set_stufe(DB_PATH, pk, projekt_name, neuer_status,
                          body.get("empfaenger"))
        stufe = mdb.stufe_fuer_status(neuer_status)
        adressaten = (m.get("empfaenger") or {}).get(stufe, {}) if stufe else {}
        _audit("cra.meldung.stufe_gewechselt", object_id=str(pk), projekt=projekt_name,
               status=neuer_status,
               gemeldet_am=str(m.get(f"{stufe}_gemeldet_am") or "") if stufe else "")
        # Der Audit-Trail hält fest, an WEN gemeldet wurde — ein Zeitstempel
        # allein belegt die Meldung nicht.
        _audit("cra.meldung.gemeldet", object_id=str(pk), projekt=projekt_name,
               stufe=neuer_status,
               csirt_mitgliedstaat=adressaten.get("csirt", {}).get("mitgliedstaat", ""),
               csirt_referenz=adressaten.get("csirt", {}).get("referenz", ""),
               enisa_referenz=adressaten.get("enisa", {}).get("referenz", ""))
        return jsonify(_with_deadlines(m))
    except mdb.AngabenUnvollstaendig as e:
        return _unvollstaendig(e)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@cra_meldung_bp.post("/projekte/<projekt_name>/meldungen/<int:pk>/empfaenger")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def set_empfaenger(projekt_name, pk):
    """Empfänger/Einreichungsreferenzen einer Stufe erfassen oder ergänzen.

    Body: ``{"stufe": "early_warning", "csirt": {...}, "enisa": {...}}``.
    Nachträgliche Eingangsbestätigungen laufen über denselben Weg. Für eine
    bereits gemeldete Stufe werden die Pflichtangaben erzwungen.
    """
    body = request.get_json(silent=True) or {}
    stufe = str(body.get("stufe") or "").strip()
    daten = {k: body.get(k) for k in mdb.KANAELE if isinstance(body.get(k), dict)}
    try:
        m = mdb.set_empfaenger(DB_PATH, pk, projekt_name, stufe, daten)
        if not m:
            return jsonify({"error": "Meldung nicht gefunden"}), 404
        _audit("cra.meldung.empfaenger_erfasst", object_id=str(pk),
               projekt=projekt_name, stufe=stufe,
               csirt_mitgliedstaat=daten.get("csirt", {}).get("mitgliedstaat", ""),
               csirt_referenz=daten.get("csirt", {}).get("referenz", ""),
               enisa_referenz=daten.get("enisa", {}).get("referenz", ""))
        return jsonify(_with_deadlines(m))
    except mdb.AngabenUnvollstaendig as e:
        return _unvollstaendig(e)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@cra_meldung_bp.get("/projekte/<projekt_name>/meldungen/<int:pk>/nachweis")
@jwt_required()
@require_permission(Permission.CRA_READ)
def nachweis(projekt_name, pk):
    """Was die Meldeakte belegt — und was nicht (#1760)."""
    m = mdb.get_meldung(DB_PATH, pk, projekt_name)
    if not m:
        return jsonify({"error": "Meldung nicht gefunden"}), 404
    angereichert = _with_deadlines(dict(m))
    status = mdb.nachweis_status(m)
    status["abschlussfrist"] = (angereichert.get("deadlines") or {}).get("abschlussfrist")
    return jsonify(status)


@cra_meldung_bp.delete("/projekte/<projekt_name>/meldungen/<int:pk>")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def delete_meldung(projekt_name, pk):
    try:
        if not mdb.delete_meldung(DB_PATH, pk, projekt_name):
            return jsonify({"error": "Meldung nicht gefunden"}), 404
        _audit("cra.meldung.geloescht", object_id=str(pk), projekt=projekt_name)
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)


# ── Nutzer-Advisory (#1209, Art. 14(8)) ─────────────────────────────────────────

@cra_meldung_bp.post("/projekte/<projekt_name>/meldungen/<int:pk>/nutzer-advisory")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def set_advisory(projekt_name, pk):
    """Nutzerunterrichtung speichern (Art. 14 Abs. 8).

    ``veroeffentlicht: true`` ist die Behauptung, die Nutzer seien unterrichtet
    worden — dafür sind Kanal, URL, Datum und Empfängerkreis Pflicht (#1760).
    Ohne das Kennzeichen wird ein Entwurf gespeichert, der im Nachweis als
    Lücke erscheint.
    """
    body = request.get_json(silent=True) or {}
    try:
        m = mdb.set_advisory(DB_PATH, pk, projekt_name, body)
        if not m:
            return jsonify({"error": "Meldung nicht gefunden"}), 404
        _audit("cra.meldung.advisory_gespeichert", object_id=str(pk), projekt=projekt_name,
               veroeffentlicht=bool(body.get("veroeffentlicht")))
        if body.get("veroeffentlicht"):
            _audit("cra.meldung.nutzerunterrichtung_veroeffentlicht",
                   object_id=str(pk), projekt=projekt_name,
                   url=str(body.get("url") or ""),
                   veroeffentlicht_am=str(body.get("veroeffentlicht_am") or ""),
                   empfaengerkreis=str(body.get("empfaengerkreis") or ""))
        return jsonify(_with_deadlines(m))
    except mdb.AngabenUnvollstaendig as e:
        return _unvollstaendig(e)
    except Exception as e:
        return _log_500(e)


@cra_meldung_bp.get("/projekte/<projekt_name>/meldungen/<int:pk>/nutzer-advisory/csaf")
@jwt_required()
@require_permission(Permission.CRA_EXPORT)
def advisory_csaf(projekt_name, pk):
    """CSAF-nahe (maschinenlesbare) Nutzer-Advisory-Ausgabe (Art. 14(8))."""
    m = mdb.get_meldung(DB_PATH, pk, projekt_name)
    if not m:
        return jsonify({"error": "Meldung nicht gefunden"}), 404
    adv = m.get("advisory") or {}
    csaf = {
        "document": {
            "category": "csaf_security_advisory",
            "csaf_version": "2.0",
            "title": adv.get("titel") or m.get("titel") or "Sicherheitshinweis",
            "publisher": {"category": "vendor", "name": projekt_name},
            "tracking": {"id": f"CRA-MELDUNG-{pk}", "status": "final"},
        },
        "product_tree": {"products": adv.get("betroffene_produkte", [])},
        "vulnerabilities": [{
            "title": m.get("titel"),
            "notes": [{"category": "description", "text": adv.get("empfohlene_massnahmen", "")}],
            "remediations": [{"category": "mitigation", "details": m.get("mitigation", "")}],
            "scores": [{"severity": adv.get("schweregrad", "")}],
        }],
        "publication_channel": adv.get("veroeffentlichungskanal", ""),
        "published_at": adv.get("veroeffentlicht_am", ""),
        # #1760: URL und Empfängerkreis gehören zum Beleg der Unterrichtung.
        "publication_url": adv.get("url", ""),
        "audience": adv.get("empfaengerkreis", ""),
        "published": bool(adv.get("veroeffentlicht")),
    }
    if not adv.get("veroeffentlicht"):
        # Ein Entwurf darf nicht wie ein veröffentlichtes Advisory aussehen.
        csaf["document"]["tracking"]["status"] = "draft"
    return jsonify(csaf)


# ── ENISA-SRP-Export ────────────────────────────────────────────────────────────

@cra_meldung_bp.get("/projekte/<projekt_name>/meldungen/<int:pk>/export")
@jwt_required()
@require_permission(Permission.CRA_EXPORT)
def export_meldung(projekt_name, pk):
    m = mdb.get_meldung(DB_PATH, pk, projekt_name)
    if not m:
        return jsonify({"error": "Meldung nicht gefunden"}), 404
    fmt = (request.args.get("format") or "json").lower()
    deadlines = _with_deadlines(dict(m)).get("deadlines")
    payload = mdb.build_srp_payload(m, deadlines)
    _audit("cra.meldung.exportiert", object_id=str(pk), projekt=projekt_name, format=fmt)
    if fmt == "json":
        return jsonify(payload)
    # PDF/Text-Fallback: einfacher strukturierter Text → application/pdf via Engine.
    txt = json.dumps(payload, ensure_ascii=False, indent=2)
    buf = io.BytesIO(txt.encode("utf-8"))
    return send_file(buf, as_attachment=True,
                     download_name=f"cra-meldung-{pk}.json", mimetype="application/json")
