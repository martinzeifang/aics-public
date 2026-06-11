"""SOC-Modul — REST-Blueprint (``/api/soc``) + Push-Empfänger (``/api/ingest/soc``).

Triage/Doku NUR für Wazuh-Alarme (kein SIEM-Nachbau). JWT pflicht + granulare
``SOC_*``-Permissions. Der Push-Webhook ist bewusst ein eigener, nicht-modularer
Pfad mit Token-Auth (siehe ``soc_ingest_bp``).

Sprint #29 / Epic #1254.
"""
from __future__ import annotations

import hmac
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from server.models.permission import Permission, require_permission

from soc import db as sdb
from soc import ingest as singest
from soc import wazuh_client as wz
from soc import meldepflicht
from soc import prompts as sprompts
from soc.constants import (
    ALERT_KINDS, ALERT_STATES, CONNECTION_MODES, DEFAULT_INDEX_PATTERN, DEFAULT_MIN_LEVEL,
    INCIDENT_STATES, INCIDENT_TRANSITIONS, REGIMES, SEVERITIES, can_transition,
)

soc_bp = Blueprint("soc", __name__)
soc_ingest_bp = Blueprint("soc_ingest", __name__)  # nicht-modular, Token-Auth

DB_PATH = Path("data/db/soc.sqlite")


def _audit(action: str, outcome: str = "success", **details: Any) -> None:
    try:
        from shared.audit import audit_event
        audit_event(action, module="soc", outcome=outcome, details=details)
    except Exception:
        pass


def _actor() -> str:
    ident = get_jwt_identity()
    if isinstance(ident, dict):
        return ident.get("username") or ident.get("sub") or "?"
    return str(ident or "?")


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path, type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


# ── Konstanten ───────────────────────────────────────────────────────────────

@soc_bp.get("/health")
@jwt_required()
@require_permission(Permission.SOC_READ)
def health():
    return jsonify({"status": "ok", "module": "soc"})


@soc_bp.get("/constants")
@jwt_required()
@require_permission(Permission.SOC_READ)
def constants():
    return jsonify({
        "alert_states": ALERT_STATES,
        "alert_kinds": ALERT_KINDS,
        "incident_states": INCIDENT_STATES,
        "incident_transitions": INCIDENT_TRANSITIONS,
        "severities": SEVERITIES,
        "connection_modes": CONNECTION_MODES,
        "regimes": {k: {"label": v["label"], "legal": v["legal"], "trigger_flag": v["trigger_flag"]}
                    for k, v in REGIMES.items()},
        "defaults": {"index_pattern": DEFAULT_INDEX_PATTERN, "min_level": DEFAULT_MIN_LEVEL},
    })


# ── Verbindung / Einrichtungsassistent ──────────────────────────────────────

@soc_bp.get("/connection")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def list_connection():
    try:
        return jsonify({"connections": sdb.list_connections(DB_PATH)})
    except Exception as e:
        return _log_500(e)


@soc_bp.post("/connection")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def save_connection():
    d = request.get_json(silent=True) or {}
    if d.get("modus") not in CONNECTION_MODES:
        return jsonify({"error": "modus muss 'pull' oder 'push' sein"}), 400
    try:
        cid = sdb.save_connection(
            DB_PATH, name=d.get("name", "default"), modus=d["modus"], url=d.get("url", ""),
            username=d.get("username", ""), secret=d.get("secret"),
            verify_tls=bool(d.get("verify_tls", True)),
            index_pattern=d.get("index_pattern", DEFAULT_INDEX_PATTERN),
            min_level=int(d.get("min_level", DEFAULT_MIN_LEVEL)),
            push_token=d.get("push_token"),
            manager_url=d.get("manager_url"), manager_user=d.get("manager_user"),
            manager_secret=d.get("manager_secret"),
            enabled=bool(d.get("enabled", True)))
        _audit("soc.connection.save", name=d.get("name", "default"), modus=d["modus"])
        return jsonify({"id": cid, "ok": True}), 201
    except Exception as e:
        return _log_500(e)


@soc_bp.delete("/connection/<name>")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def delete_connection(name: str):
    try:
        sdb.delete_connection(DB_PATH, name)
        _audit("soc.connection.delete", name=name)
        return jsonify({"ok": True})
    except Exception as e:
        return _log_500(e)


@soc_bp.post("/connection/test")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def test_connection():
    """Verbindungstest ohne Speichern: nimmt Live-Werte aus dem Body."""
    d = request.get_json(silent=True) or {}
    conn = {
        "modus": d.get("modus", "pull"), "url": d.get("url", ""),
        "username": d.get("username", ""), "secret": d.get("secret", ""),
        "verify_tls": bool(d.get("verify_tls", True)),
        "index_pattern": d.get("index_pattern", DEFAULT_INDEX_PATTERN),
        "min_level": int(d.get("min_level", DEFAULT_MIN_LEVEL)),
    }
    # Falls kein Secret im Body: gespeichertes verwenden
    if conn["modus"] == "pull" and not conn["secret"] and d.get("name"):
        saved = sdb.load_connection(DB_PATH, d["name"], with_secret=True)
        if saved:
            conn["secret"] = saved.get("secret", "")
    try:
        return jsonify(wz.test_connection(conn))
    except Exception as e:
        return _log_500(e)


@soc_bp.post("/sync")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def sync():
    name = (request.get_json(silent=True) or {}).get("name", "default")
    try:
        res = singest.run_pull(DB_PATH, name)
        _audit("soc.sync", outcome="success" if res.get("ok") else "fail", **{k: res.get(k) for k in ("new", "received")})
        return jsonify(res), (200 if res.get("ok") else 502)
    except Exception as e:
        return _log_500(e)


@soc_bp.get("/integration-snippet")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def integration_snippet():
    """Generiert die Wazuh-Integrator-Artefakte (PUSH) für den Wizard (#1260)."""
    base = request.host_url.rstrip("/")
    token = request.args.get("token", "<TOKEN>")
    level = request.args.get("level", str(DEFAULT_MIN_LEVEL))
    hook = f"{base}/api/ingest/soc"
    ossec = (
        "<integration>\n"
        "  <name>custom-soc</name>\n"
        f"  <hook_url>{hook}</hook_url>\n"
        f"  <level>{level}</level>\n"
        "  <alert_format>json</alert_format>\n"
        f"  <api_key>{token}</api_key>\n"
        "</integration>"
    )
    script = (
        "#!/usr/bin/env python3\n"
        "import sys, json, requests\n"
        "alert = json.load(open(sys.argv[1]))\n"
        "api_key = sys.argv[2] if len(sys.argv) > 2 else ''\n"
        "hook_url = sys.argv[3] if len(sys.argv) > 3 else ''\n"
        "requests.post(hook_url, json=alert, headers={'X-SOC-Token': api_key}, "
        "verify=False, timeout=15)\n"
    )
    return jsonify({
        "hook_url": hook,
        "ossec_conf": ossec,
        "script_path": "/var/ossec/integrations/custom-soc",
        "script": script,
        "install": [
            "sudo tee /var/ossec/integrations/custom-soc < script",
            "sudo chown root:wazuh /var/ossec/integrations/custom-soc",
            "sudo chmod 750 /var/ossec/integrations/custom-soc",
            "# <integration>-Block in /var/ossec/etc/ossec.conf einfügen, dann:",
            "sudo systemctl restart wazuh-manager",
        ],
    })


# ── Alarme ──────────────────────────────────────────────────────────────────

@soc_bp.get("/alerts")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_alerts():
    a = request.args
    try:
        return jsonify({"alerts": sdb.list_alerts(
            DB_PATH, status=a.get("status"), severity=a.get("severity"),
            min_level=int(a["min_level"]) if a.get("min_level") else None,
            agent=a.get("agent"), kind=a.get("kind"), group_key=a.get("group_key"),
            asset_id=int(a["asset_id"]) if a.get("asset_id") else None,
            limit=int(a.get("limit", 200)))})
    except Exception as e:
        return _log_500(e)


@soc_bp.get("/groups")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_groups():
    try:
        return jsonify({"groups": sdb.list_groups(DB_PATH, status=request.args.get("status"))})
    except Exception as e:
        return _log_500(e)


@soc_bp.get("/alerts/<alert_uid>")
@jwt_required()
@require_permission(Permission.SOC_READ)
def get_alert(alert_uid: str):
    al = sdb.get_alert(DB_PATH, alert_uid)
    if not al:
        return jsonify({"error": "Alarm nicht gefunden"}), 404
    return jsonify(al)


@soc_bp.post("/alerts/<alert_uid>/triage")
@jwt_required()
@require_permission(Permission.SOC_TRIAGE)
def triage_alert(alert_uid: str):
    al = sdb.get_alert(DB_PATH, alert_uid)
    if not al:
        return jsonify({"error": "Alarm nicht gefunden"}), 404
    target = (request.get_json(silent=True) or {}).get("status", "")
    if target not in ALERT_STATES:
        return jsonify({"error": f"Ungültiger Status '{target}'"}), 400
    if not can_transition(al["status"], target):
        return jsonify({"error": f"Übergang {al['status']}→{target} nicht erlaubt"}), 409
    sdb.set_alert_status(DB_PATH, alert_uid, target)
    _audit("soc.alert.triage", alert=alert_uid, status=target, actor=_actor())
    return jsonify({"ok": True, "status": target})


@soc_bp.get("/alerts/<alert_uid>/analyze/prompt")
@jwt_required()
@require_permission(Permission.SOC_READ)
def alert_prompt(alert_uid: str):
    al = sdb.get_alert(DB_PATH, alert_uid)
    if not al:
        return jsonify({"error": "Alarm nicht gefunden"}), 404
    return jsonify({"prompt": sprompts.build_alert_prompt(al)})


@soc_bp.post("/alerts/<alert_uid>/analyze")
@jwt_required()
@require_permission(Permission.SOC_WRITE)
def analyze_alert(alert_uid: str):
    """KI-Analyse via lokalem Ollama (Default) ODER geparste Copy/Paste-Antwort."""
    al = sdb.get_alert(DB_PATH, alert_uid)
    if not al:
        return jsonify({"error": "Alarm nicht gefunden"}), 404
    body = request.get_json(silent=True) or {}
    pasted = body.get("response")
    try:
        if pasted:
            analysis = sprompts.parse_analysis(pasted)
        else:
            analysis = sprompts.analyze_with_ollama(al)
        sdb.store_analysis(DB_PATH, alert_uid, analysis)
        _audit("soc.alert.analyze", alert=alert_uid, mode="paste" if pasted else "ollama")
        return jsonify({"analysis": analysis})
    except Exception as e:
        from compliance_db.local_llm import OllamaError
        if isinstance(e, OllamaError):
            return jsonify({"error": str(e), "hinweis": "Ollama nicht verfügbar — Copy/Paste-Pfad nutzen."}), 503
        return _log_500(e)


# ── Suppressions / Tuning ───────────────────────────────────────────────────

@soc_bp.get("/suppressions")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_suppressions():
    return jsonify({"suppressions": sdb.list_suppressions(DB_PATH)})


@soc_bp.post("/suppressions")
@jwt_required()
@require_permission(Permission.SOC_TRIAGE)
def add_suppression():
    d = request.get_json(silent=True) or {}
    if not any(d.get(k) for k in ("rule_id", "agent_glob", "srcip")):
        return jsonify({"error": "Mindestens ein Kriterium (rule_id/agent_glob/srcip) nötig"}), 400
    sid = sdb.add_suppression(DB_PATH, rule_id=d.get("rule_id", ""), agent_glob=d.get("agent_glob", ""),
                              srcip=d.get("srcip", ""), reason=d.get("reason", ""),
                              created_by=_actor(), expires_at=d.get("expires_at"))
    _audit("soc.suppression.add", id=sid, actor=_actor())
    return jsonify({"id": sid, "ok": True}), 201


@soc_bp.delete("/suppressions/<int:sid>")
@jwt_required()
@require_permission(Permission.SOC_TRIAGE)
def delete_suppression(sid: int):
    sdb.delete_suppression(DB_PATH, sid)
    return jsonify({"ok": True})


@soc_bp.post("/suppressions/dry-run")
@jwt_required()
@require_permission(Permission.SOC_READ)
def suppression_dry_run():
    """Wie viele der letzten Alarme würde diese Regel matchen? (#1268)"""
    d = request.get_json(silent=True) or {}
    rule = {"rule_id": d.get("rule_id", ""), "agent_glob": d.get("agent_glob", ""), "srcip": d.get("srcip", "")}
    alerts = sdb.list_alerts(DB_PATH, limit=2000)
    n = sum(1 for a in alerts if singest._matches_suppression(a, rule))
    return jsonify({"matched": n, "of": len(alerts)})


# ── Assets ──────────────────────────────────────────────────────────────────

@soc_bp.get("/assets")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_assets():
    return jsonify({"assets": sdb.list_assets(DB_PATH)})


@soc_bp.post("/assets")
@jwt_required()
@require_permission(Permission.SOC_WRITE)
def save_asset():
    d = request.get_json(silent=True) or {}
    if not (d.get("agent_name") or d.get("agent_id")):
        return jsonify({"error": "agent_name oder agent_id nötig"}), 400
    aid = sdb.upsert_asset(DB_PATH, d)
    _audit("soc.asset.save", id=aid)
    return jsonify({"id": aid, "ok": True}), 201


@soc_bp.get("/assets/<int:asset_id>")
@jwt_required()
@require_permission(Permission.SOC_READ)
def get_asset(asset_id: int):
    a = sdb.get_asset(DB_PATH, asset_id)
    return (jsonify(a) if a else (jsonify({"error": "Asset nicht gefunden"}), 404))


@soc_bp.get("/assets/<int:asset_id>/detail")
@jwt_required()
@require_permission(Permission.SOC_READ)
def asset_detail(asset_id: int):
    """Asset-zentrische Detailsicht: Alarme, Incidents, Meldetracks, Risiko (#1308)."""
    d = sdb.asset_detail(DB_PATH, asset_id)
    return (jsonify(d) if d else (jsonify({"error": "Asset nicht gefunden"}), 404))


@soc_bp.delete("/assets/<int:asset_id>")
@jwt_required()
@require_permission(Permission.SOC_WRITE)
def delete_asset(asset_id: int):
    """Manuelles Asset löschen (#1311)."""
    con = sdb._connect(DB_PATH)
    try:
        con.execute("DELETE FROM soc_assets WHERE id=?", (asset_id,))
        con.commit()
    finally:
        con.close()
    _audit("soc.asset.delete", id=asset_id)
    return jsonify({"ok": True})


@soc_bp.post("/alerts/<alert_uid>/assign")
@jwt_required()
@require_permission(Permission.SOC_WRITE)
def assign_alert(alert_uid: str):
    """Alarm einem Asset zuordnen/umhängen (#1305)."""
    if not sdb.get_alert(DB_PATH, alert_uid):
        return jsonify({"error": "Alarm nicht gefunden"}), 404
    aid = (request.get_json(silent=True) or {}).get("asset_id")
    sdb.assign_alert_asset(DB_PATH, alert_uid, int(aid) if aid else None)
    return jsonify({"ok": True})


@soc_bp.post("/incidents/<int:incident_id>/assign")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def assign_incident(incident_id: int):
    """Incident einem Asset zuordnen/umhängen (#1306)."""
    if not sdb.get_incident(DB_PATH, incident_id):
        return jsonify({"error": "Incident nicht gefunden"}), 404
    aid = (request.get_json(silent=True) or {}).get("asset_id")
    sdb.assign_incident_asset(DB_PATH, incident_id, int(aid) if aid else None, actor=_actor())
    return jsonify({"ok": True})


@soc_bp.post("/assets/refresh")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def refresh_assets():
    """Asset-Inventar aus der Wazuh-Manager-Agentenliste auffüllen (#1280)."""
    d = request.get_json(silent=True) or {}
    # Akzeptiere manager_url ODER url; falls leer, gespeicherte Manager-Creds nutzen (#1300)
    manager_url = d.get("manager_url") or d.get("url") or ""
    username = d.get("username", "")
    password = d.get("password", "")
    verify_tls = bool(d.get("verify_tls", True))
    if not manager_url or not password:
        saved = sdb.load_connection(DB_PATH, d.get("name", "default"), with_secret=True)
        if saved:
            manager_url = manager_url or saved.get("manager_url", "")
            username = username or saved.get("manager_user", "")
            password = password or saved.get("manager_secret", "")
    if not manager_url:
        return jsonify({"error": "Manager-URL (z. B. https://host:55000) nötig"}), 400
    try:
        agents = wz.fetch_agents(manager_url, username, password, verify_tls=verify_tls)
        n = 0
        for ag in agents:
            sdb.upsert_asset(DB_PATH, ag)
            n += 1
        try:
            from shared.firmen_link import backfill_firmen_ids
            backfill_firmen_ids(DB_PATH, "soc_assets", "organisation")
        except Exception:
            pass
        _audit("soc.assets.refresh", count=n)
        return jsonify({"ok": True, "imported": n})
    except wz.WazuhError as e:
        return jsonify({"ok": False, "error": str(e)}), 502
    except Exception as e:
        return _log_500(e)


# ── Incidents ───────────────────────────────────────────────────────────────

@soc_bp.get("/incidents")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_incidents():
    a = request.args
    include_closed = a.get("include_closed", "").lower() in ("1", "true", "yes")
    return jsonify({"incidents": sdb.list_incidents(
        DB_PATH, status=a.get("status"), include_closed=include_closed)})


@soc_bp.post("/incidents/<int:incident_id>/close")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def close_incident(incident_id: int):
    """Schließt einen Incident mit Pflicht-Begründung (#1296)."""
    reason = (request.get_json(silent=True) or {}).get("reason", "")
    res = sdb.close_incident(DB_PATH, incident_id, reason=reason, actor=_actor())
    if not res.get("ok"):
        return jsonify(res), 400
    _audit("soc.incident.closed", id=incident_id, actor=_actor())
    return jsonify({"ok": True})


@soc_bp.post("/incidents/report")
@jwt_required()
@require_permission(Permission.SOC_EXPORT)
def incidents_report():
    """Einzelne/mehrere Incidents als PDF (Fallback DOCX) (#1299)."""
    from soc import report_export
    d = request.get_json(silent=True) or {}
    ids = d.get("ids") or []
    fmt = (d.get("format") or "pdf").lower()
    if not ids:
        return jsonify({"error": "Keine Incidents ausgewählt"}), 400
    items = []
    for iid in ids:
        inc = sdb.get_incident(DB_PATH, int(iid))
        if not inc:
            continue
        items.append({"incident": inc, "alerts": sdb.get_incident_alerts(DB_PATH, int(iid)),
                      "meldetracks": sdb.list_meldetracks(DB_PATH, int(iid)),
                      "timeline": sdb.list_timeline(DB_PATH, int(iid))})
    if not items:
        return jsonify({"error": "Incidents nicht gefunden"}), 404
    from flask import Response
    try:
        if fmt == "docx":
            data = report_export.render_incidents_docx(items)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = "docx"
        else:
            data = report_export.render_incidents_pdf(items)
            mime, ext = "application/pdf", "pdf"
    except Exception as e:
        from shared.templates.pdf_converter import PDFConversionUnavailable
        if isinstance(e, PDFConversionUnavailable):
            return jsonify({"error": "PDF-Konverter nicht verfügbar (Gotenberg/soffice). DOCX nutzen."}), 503
        return _log_500(e)
    _audit("soc.incidents.report", count=len(items), format=ext)
    return Response(data, mimetype=mime, headers={
        "Content-Disposition": f'attachment; filename="soc-incidents.{ext}"'})


@soc_bp.post("/incidents")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def create_incident():
    d = request.get_json(silent=True) or {}
    if not d.get("titel"):
        return jsonify({"error": "titel ist Pflicht"}), 400
    iid = sdb.create_incident(
        DB_PATH, titel=d["titel"], severity=d.get("severity", "medium"),
        klassifikation=d.get("klassifikation", ""), asset_id=d.get("asset_id"),
        agent_name=d.get("agent_name", ""), owner=d.get("owner", "") or _actor(),
        beschreibung=d.get("beschreibung", ""), mitre=d.get("mitre"),
        firmen_id=d.get("firmen_id"), alert_uids=d.get("alert_uids") or [], actor=_actor())
    _audit("soc.incident.create", id=iid, actor=_actor())
    return jsonify({"id": iid, "ok": True}), 201


@soc_bp.get("/incidents/<int:incident_id>")
@jwt_required()
@require_permission(Permission.SOC_READ)
def get_incident(incident_id: int):
    inc = sdb.get_incident(DB_PATH, incident_id)
    if not inc:
        return jsonify({"error": "Incident nicht gefunden"}), 404
    inc["timeline"] = sdb.list_timeline(DB_PATH, incident_id)
    inc["meldetracks"] = sdb.list_meldetracks(DB_PATH, incident_id)
    return jsonify(inc)


@soc_bp.put("/incidents/<int:incident_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def update_incident(incident_id: int):
    d = request.get_json(silent=True) or {}
    inc = sdb.update_incident(DB_PATH, incident_id, d, actor=_actor())
    if not inc:
        return jsonify({"error": "Incident nicht gefunden"}), 404
    return jsonify(inc)


@soc_bp.post("/incidents/<int:incident_id>/status")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def incident_status(incident_id: int):
    inc = sdb.get_incident(DB_PATH, incident_id)
    if not inc:
        return jsonify({"error": "Incident nicht gefunden"}), 404
    target = (request.get_json(silent=True) or {}).get("status", "")
    if target not in INCIDENT_STATES:
        return jsonify({"error": f"Ungültiger Status '{target}'"}), 400
    if not can_transition(inc["status"], target, incident=True):
        return jsonify({"error": f"Übergang {inc['status']}→{target} nicht erlaubt"}), 409
    sdb.set_incident_status(DB_PATH, incident_id, target, actor=_actor())
    _audit("soc.incident.status", id=incident_id, status=target, actor=_actor())
    return jsonify({"ok": True, "status": target})


@soc_bp.get("/incidents/<int:incident_id>/alerts")
@jwt_required()
@require_permission(Permission.SOC_READ)
def incident_alerts(incident_id: int):
    """Vollständige Wazuh-Alarm-Datensätze des Incidents (#1291)."""
    return jsonify({"alerts": sdb.get_incident_alerts(DB_PATH, incident_id)})


@soc_bp.get("/incidents/<int:incident_id>/analyze/prompt")
@jwt_required()
@require_permission(Permission.SOC_READ)
def incident_prompt(incident_id: int):
    inc = sdb.get_incident(DB_PATH, incident_id)
    if not inc:
        return jsonify({"error": "Incident nicht gefunden"}), 404
    alerts = sdb.get_incident_alerts(DB_PATH, incident_id)
    return jsonify({"prompt": sprompts.build_incident_prompt(inc, alerts)})


@soc_bp.post("/incidents/<int:incident_id>/analyze")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def analyze_incident(incident_id: int):
    """KI-Analyse des Incidents (Ollama-Default oder geparste Copy/Paste-Antwort) (#1290)."""
    inc = sdb.get_incident(DB_PATH, incident_id)
    if not inc:
        return jsonify({"error": "Incident nicht gefunden"}), 404
    body = request.get_json(silent=True) or {}
    pasted = body.get("response")
    try:
        if pasted:
            analysis = sprompts.parse_analysis(pasted)
        else:
            alerts = sdb.get_incident_alerts(DB_PATH, incident_id)
            analysis = sprompts.analyze_incident_with_ollama(inc, alerts)
        sdb.store_incident_analysis(DB_PATH, incident_id, analysis)
        _audit("soc.incident.analyze", id=incident_id, mode="paste" if pasted else "ollama")
        return jsonify({"analysis": analysis})
    except Exception as e:
        from compliance_db.local_llm import OllamaError
        if isinstance(e, OllamaError):
            return jsonify({"error": str(e), "hinweis": "Ollama nicht verfügbar — Copy/Paste-Pfad nutzen."}), 503
        return _log_500(e)


@soc_bp.post("/incidents/<int:incident_id>/timeline")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def add_note(incident_id: int):
    detail = (request.get_json(silent=True) or {}).get("detail", "")
    if not detail:
        return jsonify({"error": "detail nötig"}), 400
    sdb.add_timeline_note(DB_PATH, incident_id, actor=_actor(), detail=detail)
    return jsonify({"ok": True})


# ── Meldepflicht-Router (#1281) ─────────────────────────────────────────────

@soc_bp.put("/incidents/<int:incident_id>/regimes")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def set_regimes(incident_id: int):
    """Am Incident gewählte Melde-Regelwerke setzen (steuern den Router, #1301)."""
    if not sdb.get_incident(DB_PATH, incident_id):
        return jsonify({"error": "Incident nicht gefunden"}), 404
    flags = request.get_json(silent=True) or {}
    sdb.set_incident_regimes(DB_PATH, incident_id, flags, actor=_actor())
    return jsonify({"ok": True})


@soc_bp.post("/incidents/<int:incident_id>/evaluate")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def evaluate_incident(incident_id: int):
    res = meldepflicht.evaluate_incident(DB_PATH, incident_id, actor=_actor())
    if not res.get("ok"):
        return jsonify(res), 404
    _audit("soc.meldepflicht.evaluate", id=incident_id, regimes=res.get("regimes"))
    return jsonify(res)


@soc_bp.get("/incidents/<int:incident_id>/meldetracks")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_meldetracks(incident_id: int):
    return jsonify({"meldetracks": sdb.list_meldetracks(DB_PATH, incident_id)})


@soc_bp.put("/meldetracks/<int:track_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def update_meldetrack(track_id: int):
    d = request.get_json(silent=True) or {}
    sdb.update_meldetrack(DB_PATH, track_id, status=d.get("status"), target_ref=d.get("target_ref"),
                          notiz=d.get("notiz"), deadlines=d.get("deadlines"))
    return jsonify({"ok": True})


# ── Modul-Brücken: Incident → echter Melde-Record (#1272/#1282) ─────────────

@soc_bp.post("/incidents/<int:incident_id>/bridge/dsgvo")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def bridge_dsgvo(incident_id: int):
    """Erzeugt aus dem Incident eine DSGVO-Datenpanne (Art. 33/34) im Zielprojekt."""
    from soc import bridges
    projekt = (request.get_json(silent=True) or {}).get("projekt_name", "")
    if not projekt:
        return jsonify({"error": "projekt_name (DSGVO-Projekt) nötig"}), 400
    res = bridges.to_dsgvo_datenpanne(DB_PATH, incident_id, projekt, actor=_actor())
    if not res.get("ok"):
        return jsonify(res), 400
    _audit("soc.bridge.dsgvo", id=incident_id, panne=res.get("panne_id"))
    return jsonify(res), 201


@soc_bp.post("/incidents/<int:incident_id>/bridge/cra")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def bridge_cra(incident_id: int):
    """Übernimmt den Incident als aktiv ausgenutzte Schwachstelle in cra_vuln (Art. 14)."""
    from soc import bridges
    d = request.get_json(silent=True) or {}
    projekt = d.get("projekt_name", "")
    if not projekt:
        return jsonify({"error": "projekt_name (CRA-Projekt) nötig"}), 400
    res = bridges.to_cra_vuln(DB_PATH, incident_id, projekt, cve_id=d.get("cve_id", ""), actor=_actor())
    if not res.get("ok"):
        return jsonify(res), 400
    _audit("soc.bridge.cra", id=incident_id, cve=res.get("cve_id"))
    return jsonify(res), 201


@soc_bp.post("/incidents/<int:incident_id>/bridge/nis2")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def bridge_nis2(incident_id: int):
    """Erzeugt einen NIS2-Art.-23-Meldeentwurf als Dokument im NIS2-Modul."""
    from soc import bridges
    projekt = (request.get_json(silent=True) or {}).get("projekt_name", "")
    if not projekt:
        return jsonify({"error": "projekt_name (NIS2-Projekt) nötig"}), 400
    res = bridges.to_nis2_meldung(DB_PATH, incident_id, projekt, actor=_actor())
    if not res.get("ok"):
        return jsonify(res), 400
    _audit("soc.bridge.nis2", id=incident_id, doc=res.get("doc_id"))
    return jsonify(res), 201


@soc_bp.post("/incidents/<int:incident_id>/bridge/aiact")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def bridge_aiact(incident_id: int):
    """Erzeugt einen AI-Act-Art.-73-Meldeentwurf als Dokument im AI-Act-Modul."""
    from soc import bridges
    projekt = (request.get_json(silent=True) or {}).get("projekt_name", "")
    if not projekt:
        return jsonify({"error": "projekt_name (AI-Act-Projekt) nötig"}), 400
    res = bridges.to_aiact_meldung(DB_PATH, incident_id, projekt, actor=_actor())
    if not res.get("ok"):
        return jsonify(res), 400
    _audit("soc.bridge.aiact", id=incident_id, doc=res.get("doc_id"))
    return jsonify(res), 201


# ── Issue-Verknüpfung: Incident → GitHub/GitLab (#1274) ─────────────────────

_SOC_ISSUE_PROJEKT = "soc"  # synthetischer Bucket für shared.issue_links


def _incident_issue_defaults(inc: dict) -> tuple[str, str]:
    title = f"[SOC #{inc.get('id')}] {inc.get('titel', 'Security Incident')}"
    body = (f"**SOC-Incident #{inc.get('id')}**\n\n"
            f"- Status: {inc.get('status', '')}\n- Schwere: {inc.get('severity', '')}\n"
            f"- Klassifikation: {inc.get('klassifikation') or '—'}\n"
            f"- Asset: {inc.get('agent_name') or '—'}\n\n"
            f"{inc.get('beschreibung') or ''}\n\n"
            f"_Automatisch aus dem SOC-Modul erzeugt._")
    return title, body


@soc_bp.get("/incidents/<int:incident_id>/issues")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_incident_issues(incident_id: int):
    from dataclasses import asdict
    from shared.issue_links import list_links
    links = list_links(DB_PATH, projekt_name=_SOC_ISSUE_PROJEKT,
                       object_kind="soc_incident", object_id=str(incident_id))
    return jsonify({"issues": [asdict(li) for li in links]})


@soc_bp.post("/incidents/<int:incident_id>/issues")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def create_incident_issue(incident_id: int):
    """Erzeugt ein GitHub/GitLab-Issue für den Incident und verknüpft es."""
    inc = sdb.get_incident(DB_PATH, incident_id)
    if not inc:
        return jsonify({"error": "Incident nicht gefunden"}), 404
    d = request.get_json(silent=True) or {}
    provider = (d.get("provider") or "github").lower()
    repo = d.get("repo", "")
    if not repo:
        return jsonify({"error": "repo (owner/name bzw. group/project) nötig"}), 400
    def_title, def_body = _incident_issue_defaults(inc)
    title = d.get("title") or def_title
    body = d.get("body") or def_body
    issue_url, issue_number, issue_iid = "", None, None
    try:
        if provider == "github":
            from vcs.github_issues import create_issue as gh_create
            ci = gh_create(repo=repo, title=title, body=body)
            issue_url, issue_number = ci.url, ci.number
        elif provider == "gitlab":
            from vcs.gitlab_issues import create_issue as gl_create
            ci = gl_create(base_url=d.get("gitlab_base_url") or "https://gitlab.com",
                           token_env=d.get("gitlab_token_env") or "GITLAB_TOKEN",
                           project=repo, title=title, body=body)
            issue_url, issue_iid = ci.url, ci.iid
        else:
            return jsonify({"error": f"Unbekannter Provider: {provider}"}), 400
    except Exception as e:
        current_app.logger.exception("SOC issue create failed")
        return jsonify({"error": f"Issue-Erstellung fehlgeschlagen: {e}"}), 502
    from shared.issue_links import add_link
    add_link(DB_PATH, projekt_name=_SOC_ISSUE_PROJEKT, object_kind="soc_incident",
             object_id=str(incident_id), provider=provider, repo=repo, url=issue_url,
             issue_number=issue_number, issue_iid=issue_iid, title=title)
    sdb.add_timeline_note(DB_PATH, incident_id, actor=_actor(),
                          detail=f"{provider}-Issue erstellt: {issue_url}")
    _audit("soc.incident_issue.created", id=incident_id, provider=provider, repo=repo, url=issue_url)
    return jsonify({"created": True, "provider": provider, "url": issue_url,
                    "issue_number": issue_number, "issue_iid": issue_iid}), 201


@soc_bp.delete("/incidents/<int:incident_id>/issues/<link_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def delete_incident_issue(incident_id: int, link_id: str):
    from shared.issue_links import delete_link
    delete_link(DB_PATH, link_id)
    return jsonify({"ok": True})


# ── KPIs (Dashboard) ────────────────────────────────────────────────────────

@soc_bp.get("/kpis")
@jwt_required()
@require_permission(Permission.SOC_READ)
def kpis():
    return jsonify(sdb.kpis(DB_PATH))


@soc_bp.get("/control-evidence")
@jwt_required()
@require_permission(Permission.SOC_READ)
def control_evidence():
    """Kennzahlen-Nachweis „Incident-Handling" für NIS2 Art. 21 / AI-Act Art. 72 (#1285)."""
    return jsonify(sdb.control_evidence(DB_PATH))


@soc_bp.get("/likelihood")
@jwt_required()
@require_permission(Permission.SOC_READ)
def likelihood():
    """Empirischer Eintrittswahrscheinlichkeits-Vorschlag für die Risikobewertung (#1284)."""
    a = request.args
    return jsonify(sdb.incident_frequency(DB_PATH, agent=a.get("agent"), rule_id=a.get("rule_id")))


# ── Lagebericht-Assistent (#1270) ───────────────────────────────────────────

@soc_bp.get("/lagebericht/prompt")
@jwt_required()
@require_permission(Permission.SOC_READ)
def lagebericht_prompt():
    incs = sdb.list_incidents(DB_PATH)
    return jsonify({"prompt": sprompts.build_lagebericht_prompt(sdb.kpis(DB_PATH), incs)})


@soc_bp.post("/lagebericht")
@jwt_required()
@require_permission(Permission.SOC_READ)
def lagebericht():
    """SOC-Lagebericht (Prosa) via Ollama ODER eingefügte KI-Antwort."""
    pasted = (request.get_json(silent=True) or {}).get("response")
    if pasted:
        return jsonify({"report": pasted})
    try:
        text = sprompts.lagebericht_with_ollama(sdb.kpis(DB_PATH), sdb.list_incidents(DB_PATH))
        return jsonify({"report": text})
    except Exception as e:
        from compliance_db.local_llm import OllamaError
        if isinstance(e, OllamaError):
            return jsonify({"error": str(e), "hinweis": "Ollama nicht verfügbar — Copy/Paste-Pfad nutzen."}), 503
        return _log_500(e)


# ── OWASP-LLM-Erkennung (#1286, nice-to-have) ───────────────────────────────

@soc_bp.get("/owasp-llm")
@jwt_required()
@require_permission(Permission.SOC_READ)
def owasp_llm_detect():
    from soc import owasp_llm
    return jsonify({"detections": owasp_llm.detect_llm_alerts(DB_PATH)})


@soc_bp.post("/owasp-llm/push")
@jwt_required()
@require_permission(Permission.SOC_WRITE)
def owasp_llm_push():
    """Schreibt SOC-LLM-Treffer als Evidenz ins AI-Act-OWASP-LLM-Register."""
    from soc import owasp_llm
    projekt = (request.get_json(silent=True) or {}).get("projekt_name", "")
    if not projekt:
        return jsonify({"error": "projekt_name (AI-Act-Projekt) nötig"}), 400
    res = owasp_llm.push_to_aiact(DB_PATH, Path("data/db/ai_act.sqlite"), projekt)
    _audit("soc.owasp_llm.push", projekt=projekt, pushed=res.get("pushed"))
    return jsonify(res)


# ── PUSH-Empfänger (nicht-modular, Token-Auth) ──────────────────────────────

@soc_ingest_bp.post("/soc")
def push_ingest():
    """Wazuh-Integrator-Webhook. Token via Header X-SOC-Token (oder ?token=)."""
    token = request.headers.get("X-SOC-Token") or request.args.get("token", "")
    if not token:
        return jsonify({"error": "Token fehlt"}), 401
    # Token gegen alle aktiven Push-Verbindungen prüfen
    valid = False
    for c in sdb.list_connections(DB_PATH, with_secrets=True):
        if c.get("modus") == "push" and c.get("enabled") and c.get("push_token"):
            if hmac.compare_digest(str(c["push_token"]), str(token)):
                valid = True
                break
    if not valid:
        return jsonify({"error": "Ungültiges Token"}), 401
    doc = request.get_json(silent=True) or {}
    # Wazuh-Alert kommt als _source-artiges Objekt → in OpenSearch-Hit-Form bringen
    hit = doc if "_source" in doc else {"_id": doc.get("id") or doc.get("_id") or "", "_source": doc}
    if not hit.get("_id"):
        import hashlib as _h
        hit["_id"] = _h.sha1(str(doc).encode()).hexdigest()
    alert = wz.normalize_alert(hit)
    counts = singest.ingest_alerts(DB_PATH, [alert])
    return jsonify({"ok": True, **counts}), 202
