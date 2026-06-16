"""AI-Act Art. 5 — Verbots-Screening REST-Blueprint (``/api/aiact-art5``, #1206).

Dokumentierte Negativprüfung gegen die 8 verbotenen Praktiken (Art. 5(1) a–h).
Ein Treffer (``betroffen='ja'``) ist das Compliance-Gate, das die Risiko-Klasse
des Projekts automatisch auf ``prohibited`` setzt.

Bindestrich-Prefix ``aiact-art5`` mappt automatisch auf den ``aiact``-Authz-/
Lizenz-Guard (app.py #1169) — keine authz.py-Änderung nötig.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission

from ai_act import art5_screening as a5
from ai_act.db import load_projekt, update_projekt_meta

aiact_art5_bp = Blueprint("aiact_art5", __name__)
DB_PATH = Path("data/db/ai_act.sqlite")


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


def _enforce_prohibited_gate(projekt_name: str) -> dict:
    """Setzt bei einem Treffer das Risk-Tier des Projekts auf 'prohibited'.

    Schreibt ins ``meta_json`` (risk_tier) — additiv, ohne Bestehendes zu zerstören.
    Gibt das aktuelle Summary zurück.
    """
    summ = a5.summary(DB_PATH, projekt_name)
    if summ["has_prohibited"]:
        p = load_projekt(DB_PATH, projekt_name)
        if p:
            meta = p.get("meta") if isinstance(p.get("meta"), dict) else {}
            if meta.get("risk_tier") != "prohibited":
                meta = dict(meta)
                meta["risk_tier"] = "prohibited"
                meta["risk_tier_quelle"] = "art5_screening"
                update_projekt_meta(DB_PATH, projekt_name, meta)
                _audit("aiact.art5.gate_prohibited", projekt=projekt_name,
                       treffer=summ["treffer"])
    return summ


# ── Katalog ─────────────────────────────────────────────────────────────────

@aiact_art5_bp.get("/catalog")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def catalog():
    return jsonify({"tatbestaende": a5.catalog(), "betroffen": list(a5.BETROFFEN)})


# ── Screening ─────────────────────────────────────────────────────────────────

@aiact_art5_bp.get("/projekte/<projekt_name>/screening")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def get_screening(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify({
            "items": a5.load_screening(DB_PATH, projekt_name),
            "summary": a5.summary(DB_PATH, projekt_name),
        })
    except Exception as e:
        return _log_500(e)


@aiact_art5_bp.post("/projekte/<projekt_name>/screening/<tatbestand>")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def save_befund(projekt_name, tatbestand):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        geprueft_am = body.get("geprueft_am") or datetime.now(timezone.utc).date().isoformat()
        a5.save_befund(
            DB_PATH, projekt_name, tatbestand,
            betroffen=str(body.get("betroffen", "offen")),
            begruendung=str(body.get("begruendung", "") or ""),
            geprueft_von=str(body.get("geprueft_von", "") or str(get_jwt_identity() or "")),
            geprueft_am=geprueft_am,
        )
        summ = _enforce_prohibited_gate(projekt_name)
        _audit("aiact.art5.befund_saved", projekt=projekt_name, tatbestand=tatbestand,
               betroffen=body.get("betroffen"))
        return jsonify({"ok": True, "summary": summ})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


# ── Gate-Check (für Risk-Tier-Bestätigung) ────────────────────────────────────

@aiact_art5_bp.get("/projekte/<projekt_name>/gate")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def gate(projekt_name):
    """Liefert den Gate-Status: Darf das Risk-Tier bestätigt werden?

    ``allow_confirm`` ist False, solange noch Tatbestände offen sind — die
    Negativprüfung muss vollständig sein, bevor das Tier bestätigt werden darf.
    """
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        summ = a5.summary(DB_PATH, projekt_name)
        return jsonify({
            **summ,
            "allow_confirm": summ["complete"],
            "forced_tier": "prohibited" if summ["has_prohibited"] else None,
        })
    except Exception as e:
        return _log_500(e)


# ── KI-Wizard ─────────────────────────────────────────────────────────────────

@aiact_art5_bp.get("/projekte/<projekt_name>/wizard/prompt")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def wizard_prompt(projekt_name):
    try:
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify({"prompt": a5.build_art5_prompt(p)})
    except Exception as e:
        return _log_500(e)


@aiact_art5_bp.post("/projekte/<projekt_name>/wizard/parse")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def wizard_parse(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        raw = body.get("response") or body.get("raw") or ""
        if not raw:
            return jsonify({"error": 'Feld "response" ist Pflicht'}), 400
        items = a5.parse_art5_response(raw)
        if not items:
            return jsonify({"error": "Kein gültiges JSON mit Art.-5-Befunden erkannt"}), 400
        apply = bool(body.get("apply", True))
        actor = str(get_jwt_identity() or "")
        am = datetime.now(timezone.utc).date().isoformat()
        if apply:
            for it in items:
                a5.save_befund(DB_PATH, projekt_name, it["code"],
                               betroffen=it["betroffen"], begruendung=it["begruendung"],
                               geprueft_von=f"KI-Wizard ({actor})", geprueft_am=am)
        summ = _enforce_prohibited_gate(projekt_name)
        return jsonify({"items": items, "saved": apply, "summary": summ})
    except Exception as e:
        return _log_500(e)


# ── Export der Negativprüfung (Nachweis) ──────────────────────────────────────

@aiact_art5_bp.get("/projekte/<projekt_name>/export")
@jwt_required()
@require_permission(Permission.AIACT_EXPORT)
def export(projekt_name):
    try:
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        items = a5.load_screening(DB_PATH, projekt_name)
        summ = a5.summary(DB_PATH, projekt_name)
        lines = [
            f"# Art.-5-Verbots-Screening — Negativprüfung",
            f"Projekt: {projekt_name}",
            f"Stand: {datetime.now(timezone.utc).date().isoformat()}",
            "",
            f"Ergebnis: {'VERBOTENE PRAKTIK ERKANNT (prohibited)' if summ['has_prohibited'] else 'Keine verbotene Praktik festgestellt'}",
            "",
        ]
        for it in items:
            lines.append(f"## {it['code']}) {it['kurz']} ({it['ref']})")
            lines.append(f"- Betroffen: {it['betroffen']}")
            lines.append(f"- Begründung: {it['begruendung'] or '—'}")
            lines.append(f"- Geprüft von/am: {it['geprueft_von'] or '—'} / {it['geprueft_am'] or '—'}")
            lines.append("")
        buf = io.BytesIO("\n".join(lines).encode("utf-8"))
        _audit("aiact.art5.exported", projekt=projekt_name)
        return send_file(buf, mimetype="text/markdown", as_attachment=True,
                         download_name=f"art5_screening_{projekt_name}.md")
    except Exception as e:
        return _log_500(e)
