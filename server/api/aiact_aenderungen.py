"""AI-Act Änderungsverwaltung je KI-System — REST-Blueprint (#1756).

``/api/aiact-aenderungen``. Der Bindestrich-Prefix ist kein Stilmittel: Die
Authz-Normalisierung (#1169) und das Lizenz-Gate leiten daraus das Basis-Modul
``aiact`` ab — ein eigener Name würde beide umgehen.

Die Pfade ``/freigeben`` und ``/zurueckweisen`` heißen so, weil der Modul-Guard
genau diese Endungen als Sign-off-Pfade kennt (#1754) und dort zusätzlich
``aiact:approve`` akzeptiert. Eine Freigabe ist ein POST, und die Freigabe-Rolle
hat bewusst kein Schreibrecht; mit einem eigenen Pfadnamen (``/approve``) würde
der Guard sie vor dem Endpunkt abweisen.

Rollentrennung:

* ``AIACT_WRITE`` — anlegen, Stammdaten, Checkliste, Kernfrage, einreichen, umsetzen
* ``AIACT_APPROVE`` — freigeben, zurückweisen (Rolle ``aiact_approver``, ohne Schreibrecht)
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.api._common import require_projekt
from server.models.permission import Permission, require_permission

from ai_act import aenderung_checkliste as ac
from ai_act import aenderung_gate as gate
from ai_act import aenderungen_db as adb
from ai_act.db import load_projekt

aiact_aenderungen_bp = Blueprint("aiact_aenderungen", __name__)
DB_PATH = Path("data/db/ai_act.sqlite")

# #1562: Eine Organisation, zu deren Firma KI-Systeme angelegt sind, führt keine
# System-Controls. Der Änderungsvorgang ist einer — er hängt am KI-System. Die
# Antwort ist dieselbe wie bei allen übrigen Registern (409
# ``org_controls_locked``), nicht ein eigenes Fehlerbild: Wer die Oberfläche
# bedient, soll nicht pro Register eine neue Erklärung lesen müssen.
from ai_act.scope import make_org_write_guard as _org_guard  # noqa: E402

aiact_aenderungen_bp.before_request(_org_guard(DB_PATH))


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


def _wer() -> str:
    return str(get_jwt_identity() or "")


def _gate_fuer(rec: dict) -> dict:
    """Rechenstand zu einem Vorgang.

    ``seit`` ist die Anlage des Vorgangs: Ab da zählt eine Fortschreibung der
    Dokumentation als „nachgezogen". Der Zeitpunkt der Änderung selbst wäre
    verlockend (``wirksam_ab``), ist aber optional und oft in der Zukunft — er
    würde eine bereits erledigte Nachführung als offen melden.
    """
    return gate.evaluate(rec.get("projekt_name") or "",
                         wesentlich=rec.get("wesentlich") or "",
                         grund_art=rec.get("grund_art") or "",
                         seit=str(rec.get("created_at") or ""),
                         db_path=DB_PATH)


# ── Katalog + Konstanten ────────────────────────────────────────────────────

@aiact_aenderungen_bp.get("/constants")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def constants():
    return jsonify({
        "grund_arten": adb.grund_arten(),
        "wesentlich_werte": adb.wesentlich_werte(),
        "status_werte": list(adb.STATUS),
        "gesperrte_status": list(adb.GESPERRTE_STATUS),
        "checkliste_status": list(ac.STATUS),
        "min_grund": adb.MIN_GRUND,
    })


@aiact_aenderungen_bp.get("/projekte/<projekt_name>/aenderungen/katalog")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def katalog(projekt_name):
    """Der Rechts-Kanon (Soll), unabhängig von einem Vorgang.

    Optional ``?wesentlich=`` und ``?grund_art=``: dann enthält jeder Punkt die
    abgeleitete Relevanz samt Grund. Nicht relevante Punkte werden **nicht**
    entfernt — im Nachweis soll stehen, dass eine Pflicht geprüft und warum sie
    nicht einschlägig war.
    """
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    wesentlich = str(request.args.get("wesentlich") or "")
    grund_art = str(request.args.get("grund_art") or "")
    if wesentlich or grund_art:
        items = ac.relevanter_katalog(wesentlich, grund_art)
    else:
        items = ac.katalog()
    return jsonify({"katalog": items,
                    "begruendung_pflicht": sorted(ac.BEGRUENDUNG_PFLICHT),
                    "gerechnet": sorted(ac.gerechnete_ids()),
                    "kernfrage_id": ac.KERNFRAGE_ID,
                    "status_werte": list(ac.STATUS)})


# ── Liste + Detail ──────────────────────────────────────────────────────────

@aiact_aenderungen_bp.get("/projekte/<projekt_name>/aenderungen")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def liste(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    try:
        from ai_act.scope import SCOPE_SYSTEM, scope_of
        p = load_projekt(DB_PATH, projekt_name) or {}
        return jsonify({
            "aenderungen": adb.list_aenderungen(DB_PATH, projekt_name),
            # Die Oberfläche zeigt den Reiter nur bei KI-Systemen; der Server
            # sagt hier, womit er es zu tun hat, damit sie das nicht raten muss.
            "scope": scope_of(p),
            "ist_ki_system": scope_of(p) == SCOPE_SYSTEM,
        })
    except Exception as e:
        return _log_500(e)


@aiact_aenderungen_bp.get("/projekte/<projekt_name>/aenderungen/<stand>")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def detail(projekt_name, stand):
    """Ein Vorgang mit Rechenstand. **Legt nichts an** (#1747-Lehre).

    Ein Deep-Link mit Tippfehler im Stand würde sonst einen leeren Entwurf
    hinterlassen, und jeder Vorab-Abruf des Browsers schriebe in die Datenbank.
    """
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    try:
        rec = adb.get_aenderung(DB_PATH, projekt_name, stand)
        if not rec:
            # Die Ampel steht trotzdem zur Verfügung: Man will wissen, wie der
            # Stand wäre, bevor man einen Vorgang eröffnet.
            leer = gate.evaluate(projekt_name, db_path=DB_PATH)
            return jsonify({"vorgang": None, "existiert": False, "gate": leer,
                            "gate_bei_einreichung": {},
                            "katalog": ac.relevanter_katalog(),
                            "stand": ac.leerer_stand()})
        return jsonify({
            "vorgang": rec, "existiert": True,
            # Live gerechnet vs. bei der Einreichung eingefroren — getrennt,
            # sonst ist nach der Freigabe nicht unterscheidbar, was geprüft
            # wurde und was sich seither geändert hat.
            "gate": _gate_fuer(rec),
            "gate_bei_einreichung": rec.get("gate") or {},
            "katalog": ac.relevanter_katalog(rec.get("wesentlich") or "",
                                             rec.get("grund_art") or ""),
            "stand": rec.get("checkliste") or ac.leerer_stand(),
        })
    except Exception as e:
        return _log_500(e)


# ── Anlegen + Stammdaten ────────────────────────────────────────────────────

@aiact_aenderungen_bp.post("/projekte/<projekt_name>/aenderungen")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def anlegen(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        rec = adb.create_aenderung(DB_PATH, projekt_name, body, von=_wer())
        _audit("aiact.aenderung.angelegt", projekt=projekt_name,
               stand=rec.get("stand"), grund_art=rec.get("grund_art"))
        return jsonify(rec), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@aiact_aenderungen_bp.put("/projekte/<projekt_name>/aenderungen/<stand>")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def stammdaten(projekt_name, stand):
    body = request.get_json(silent=True) or {}
    try:
        rec = adb.update_stammdaten(DB_PATH, projekt_name, stand, body)
        return jsonify(rec)
    except LookupError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@aiact_aenderungen_bp.delete("/projekte/<projekt_name>/aenderungen/<stand>")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def verwerfen(projekt_name, stand):
    try:
        if not adb.delete_aenderung(DB_PATH, projekt_name, stand):
            return jsonify({"error": "Änderungsvorgang nicht gefunden"}), 404
        _audit("aiact.aenderung.verworfen", projekt=projekt_name, stand=stand)
        return jsonify({"ok": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


# ── Kernfrage + Checkliste ──────────────────────────────────────────────────

@aiact_aenderungen_bp.put("/projekte/<projekt_name>/aenderungen/<stand>/wesentliche-aenderung")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def wesentliche_aenderung(projekt_name, stand):
    """Die Kernfrage beantworten — ja / nein / vorab_bewertet (Art. 43 Abs. 4)."""
    body = request.get_json(silent=True) or {}
    try:
        rec = adb.set_wesentlich(
            DB_PATH, projekt_name, stand,
            wert=str(body.get("wert") or ""), grund=str(body.get("grund") or ""),
            von=_wer(), vorab_referenz=str(body.get("vorab_referenz") or ""))
        _audit("aiact.aenderung.wesentlich", projekt=projekt_name, stand=stand,
               wert=rec.get("wesentlich"),
               neubewertung=rec.get("neubewertung_erforderlich"))
        return jsonify({"vorgang": rec, "gate": _gate_fuer(rec),
                        "katalog": ac.relevanter_katalog(rec.get("wesentlich") or "",
                                                         rec.get("grund_art") or "")})
    except LookupError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@aiact_aenderungen_bp.put("/projekte/<projekt_name>/aenderungen/<stand>/checkliste/<item_id>")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def checkliste_setzen(projekt_name, stand, item_id):
    body = request.get_json(silent=True) or {}
    try:
        rec = adb.set_checkliste(
            DB_PATH, projekt_name, stand, item_id,
            status=str(body.get("status") or "offen"),
            begruendung=str(body.get("begruendung") or ""), von=_wer())
        return jsonify(rec)
    except LookupError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


# ── Statusmaschine ──────────────────────────────────────────────────────────

@aiact_aenderungen_bp.post("/projekte/<projekt_name>/aenderungen/<stand>/einreichen")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def einreichen(projekt_name, stand):
    try:
        rec = adb.get_aenderung(DB_PATH, projekt_name, stand)
        if not rec:
            return jsonify({"error": "Änderungsvorgang nicht gefunden"}), 404
        ergebnis = adb.einreichen(DB_PATH, projekt_name, stand, von=_wer(),
                                  gate=_gate_fuer(rec))
        _audit("aiact.aenderung.eingereicht", projekt=projekt_name, stand=stand,
               ampel=(ergebnis.get("gate") or {}).get("ampel"))
        return jsonify(ergebnis)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@aiact_aenderungen_bp.post("/projekte/<projekt_name>/aenderungen/<stand>/zurueckweisen")
@jwt_required()
@require_permission(Permission.AIACT_APPROVE)
def zurueckweisen(projekt_name, stand):
    body = request.get_json(silent=True) or {}
    try:
        rec = adb.zurueckweisen(DB_PATH, projekt_name, stand, von=_wer(),
                                grund=str(body.get("grund") or ""))
        _audit("aiact.aenderung.zurueckgewiesen", projekt=projekt_name, stand=stand)
        return jsonify(rec)
    except LookupError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@aiact_aenderungen_bp.post("/projekte/<projekt_name>/aenderungen/<stand>/freigeben")
@jwt_required()
@require_permission(Permission.AIACT_APPROVE)
def freigeben(projekt_name, stand):
    try:
        rec = adb.freigeben(DB_PATH, projekt_name, stand, von=_wer())
        _audit("aiact.aenderung.freigegeben", projekt=projekt_name, stand=stand,
               wesentlich=rec.get("wesentlich"))
        return jsonify(rec)
    except LookupError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@aiact_aenderungen_bp.post("/projekte/<projekt_name>/aenderungen/<stand>/umsetzen")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def umsetzen(projekt_name, stand):
    try:
        rec = adb.umsetzen(DB_PATH, projekt_name, stand)
        _audit("aiact.aenderung.umgesetzt", projekt=projekt_name, stand=stand)
        return jsonify(rec)
    except LookupError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)
