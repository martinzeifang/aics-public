"""SOC-Modul — REST-Blueprint (``/api/soc``) + Push-Empfänger (``/api/ingest/soc``).

Triage/Doku NUR für Wazuh-Alarme (kein SIEM-Nachbau). JWT pflicht + granulare
``SOC_*``-Permissions. Der Push-Webhook ist bewusst ein eigener, nicht-modularer
Pfad mit Token-Auth (siehe ``soc_ingest_bp``).

Sprint #29 / Epic #1254.
"""
from __future__ import annotations

import hmac
import json
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
    DETECTION_STATES, INCIDENT_STATES, INCIDENT_TRANSITIONS, PIR_ACTION_STATES, REGIMES,
    SEVERITIES, UEBUNG_ERGEBNIS, UEBUNG_INJECT_STATES, UEBUNG_LIFECYCLE, UEBUNG_MASS_STATES,
    UEBUNG_STATES, UEBUNG_TYPES, UEBUNG_ZIEL_BEWERTUNG, UEBUNG_ZIEL_TYPES, VULN_TRIAGE_STATES,
    can_transition,
)

soc_bp = Blueprint("soc", __name__)
soc_ingest_bp = Blueprint("soc_ingest", __name__)  # nicht-modular, Token-Auth

DB_PATH = Path("data/db/soc.sqlite")

# In-Memory-Lauf-Status des Schwachstellen-Syncs je Verbindung (#1343). Background-
# Thread (voller States-Snapshot kann dauern) → 202 + Status-Polling, analog CRA.
import threading

_vuln_sync_lock = threading.Lock()
_vuln_sync_state: dict[str, dict[str, Any]] = {}  # name → {running, last_*}


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
        "pir_action_states": PIR_ACTION_STATES,
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
        # Partielles Update (#1315-Hotfix): nur explizit gesendete Felder überschreiben —
        # sonst löscht das Manager-Formular die Indexer-Felder (und umgekehrt).
        cid = sdb.save_connection(
            DB_PATH, name=d.get("name", "default"), modus=d["modus"], url=d.get("url"),
            username=d.get("username"), secret=d.get("secret"),
            verify_tls=d.get("verify_tls"),
            index_pattern=d.get("index_pattern"),
            min_level=d.get("min_level"),
            push_token=d.get("push_token"),
            manager_url=d.get("manager_url"), manager_user=d.get("manager_user"),
            manager_secret=d.get("manager_secret"),
            enabled=d.get("enabled"),
            vuln_index_pattern=d.get("vuln_index_pattern"),
            vuln_sync_enabled=d.get("vuln_sync_enabled"),
            vuln_min_severity=d.get("vuln_min_severity"))
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


# ── Schwachstellen-Register (#1343) ─────────────────────────────────────────

@soc_bp.get("/vulnerabilities")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_vulnerabilities():
    a = request.args
    only_active = a.get("only_active", "1").lower() not in ("0", "false", "no")
    try:
        return jsonify({"vulnerabilities": sdb.list_vulnerabilities(
            DB_PATH, severity=a.get("severity"), wazuh_status=a.get("wazuh_status"),
            triage_status=a.get("triage_status"), agent=a.get("agent"),
            asset_id=int(a["asset_id"]) if a.get("asset_id") else None,
            firmen_id=int(a["firmen_id"]) if a.get("firmen_id") else None,
            only_active=only_active, limit=int(a.get("limit", 1000))),
            "kpi": sdb.count_open_vulnerabilities(DB_PATH),
            "triage_states": VULN_TRIAGE_STATES})
    except Exception as e:
        return _log_500(e)


def _run_vuln_sync_bg(app, name: str) -> None:
    from soc import ingest as _ing
    try:
        with app.app_context():
            res = _ing.run_vuln_sync(DB_PATH, name)
    except Exception as e:  # noqa: BLE001
        res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    from datetime import datetime, timezone
    with _vuln_sync_lock:
        st = _vuln_sync_state.setdefault(name, {})
        st["running"] = False
        st["last_finished_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        st["last_result"] = res


@soc_bp.post("/vulnerabilities/sync")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def sync_vulnerabilities():
    """Stößt den Schwachstellen-Snapshot-Sync im Hintergrund an (202). 409 wenn schon laufend."""
    name = (request.get_json(silent=True) or {}).get("name", "default")
    from datetime import datetime, timezone
    with _vuln_sync_lock:
        st = _vuln_sync_state.setdefault(name, {})
        if st.get("running"):
            return jsonify({"ok": False, "error": "Schwachstellen-Sync läuft bereits", "running": True}), 409
        st["running"] = True
        st["last_started_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        st["last_result"] = None
    app = current_app._get_current_object()
    threading.Thread(target=_run_vuln_sync_bg, args=(app, name), daemon=True).start()
    _audit("soc.vuln.synced", outcome="started", name=name, actor=_actor())
    return jsonify({"ok": True, "running": True, "accepted": True}), 202


@soc_bp.get("/vulnerabilities/sync/status")
@jwt_required()
@require_permission(Permission.SOC_READ)
def vuln_sync_status():
    name = request.args.get("name", "default")
    with _vuln_sync_lock:
        st = dict(_vuln_sync_state.get(name, {"running": False}))
    return jsonify(st)


@soc_bp.get("/vulnerabilities/<int:vuln_id>")
@jwt_required()
@require_permission(Permission.SOC_READ)
def get_vulnerability(vuln_id: int):
    v = sdb.get_vulnerability(DB_PATH, vuln_id)
    return (jsonify(v) if v else (jsonify({"error": "Schwachstelle nicht gefunden"}), 404))


@soc_bp.post("/vulnerabilities/<int:vuln_id>/triage")
@jwt_required()
@require_permission(Permission.SOC_TRIAGE)
def triage_vulnerability(vuln_id: int):
    d = request.get_json(silent=True) or {}
    target = d.get("triage_status", "")
    if target not in VULN_TRIAGE_STATES:
        return jsonify({"error": f"Ungültiger Triage-Status '{target}'"}), 400
    if target == "promoted":
        return jsonify({"error": "'promoted' wird nur über die Promotion gesetzt"}), 400
    if not sdb.get_vulnerability(DB_PATH, vuln_id):
        return jsonify({"error": "Schwachstelle nicht gefunden"}), 404
    sdb.set_vulnerability_triage(DB_PATH, vuln_id, triage_status=target,
                                 kommentar=d.get("kommentar"))
    _audit("soc.vuln.triaged", id=vuln_id, status=target, actor=_actor())
    return jsonify({"ok": True, "triage_status": target})


@soc_bp.post("/vulnerabilities/bulk-triage")
@jwt_required()
@require_permission(Permission.SOC_TRIAGE)
def bulk_triage_vulnerabilities():
    d = request.get_json(silent=True) or {}
    ids = d.get("ids") or []
    target = d.get("triage_status", "")
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "ids (Liste) nötig"}), 400
    if target not in VULN_TRIAGE_STATES or target == "promoted":
        return jsonify({"error": f"Ungültiger Triage-Status '{target}'"}), 400
    n = 0
    for vid in ids:
        try:
            if sdb.set_vulnerability_triage(DB_PATH, int(vid), triage_status=target,
                                            kommentar=d.get("kommentar")):
                n += 1
        except (TypeError, ValueError):
            continue
    _audit("soc.vuln.triaged", count=n, status=target, bulk=True, actor=_actor())
    return jsonify({"ok": True, "updated": n})


@soc_bp.post("/vulnerabilities/<int:vuln_id>/promote")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def promote_vulnerability(vuln_id: int):
    """Nimmt eine Schwachstelle bewusst als Alarm bzw. Incident in den Workflow auf (#1343).

    target='alert'   → regulärer soc_alerts-Eintrag (kind='vulnerability'), durchläuft
                       den normalen Triage-/Incident-Workflow.
    target='incident'→ Incident erzeugen + verknüpfen.
    Doppelte Promotion wird verhindert (promoted_alert_uid/promoted_incident_id).
    """
    v = sdb.get_vulnerability(DB_PATH, vuln_id)
    if not v:
        return jsonify({"error": "Schwachstelle nicht gefunden"}), 404
    target = (request.get_json(silent=True) or {}).get("target", "alert")
    if target not in ("alert", "incident"):
        return jsonify({"error": "target muss 'alert' oder 'incident' sein"}), 400

    cve = v.get("cve_id", "")
    pkg = v.get("package_name", "")
    desc = f"Schwachstelle {cve} in {pkg}".strip() if cve else "Schwachstelle"

    if target == "alert":
        if v.get("promoted_alert_uid"):
            return jsonify({"error": "Bereits als Alarm aufgenommen", "alert_uid": v["promoted_alert_uid"]}), 409
        alert_uid = f"socvuln:{v['vuln_uid']}"
        _vraw = v.get("raw_json") or {}
        if isinstance(_vraw, str):
            try:
                _vraw = json.loads(_vraw)
            except (ValueError, TypeError):
                _vraw = {}
        if not isinstance(_vraw, dict):
            _vraw = {}
        alert = {
            "alert_uid": alert_uid, "rule_id": "", "rule_level": 0,
            "severity": v.get("severity", "low"), "kind": "vulnerability",
            "description": desc, "groups": ["vulnerability-detector"], "mitre": {},
            "agent_id": v.get("agent_id", ""), "agent_name": v.get("agent_name", ""),
            "srcip": "", "location": "wazuh-states-vulnerabilities",
            "full_log": v.get("advisory_url", ""), "event_ts": v.get("detection_time", ""),
            "raw_json": {"soc_vulnerability_id": vuln_id, **_vraw},
            "group_key": "", "status": "new",
            "asset_id": v.get("asset_id"), "firmen_id": v.get("firmen_id"),
        }
        created = sdb.upsert_alert(DB_PATH, alert)
        sdb.set_vulnerability_promotion(DB_PATH, vuln_id, alert_uid=alert_uid)
        _audit("soc.vuln.promoted", id=vuln_id, target="alert", alert_uid=alert_uid, actor=_actor())
        return jsonify({"ok": True, "target": "alert", "alert_uid": alert_uid, "created": created}), 201

    # target == incident
    if v.get("promoted_incident_id"):
        return jsonify({"error": "Bereits als Incident aufgenommen", "incident_id": v["promoted_incident_id"]}), 409
    iid = sdb.create_incident(
        DB_PATH, titel=desc, severity=v.get("severity", "medium"),
        klassifikation="vulnerability", asset_id=v.get("asset_id"),
        agent_name=v.get("agent_name", ""), owner=_actor(),
        beschreibung=f"Aus SOC-Schwachstellen-Register: {cve} — Paket {pkg} "
                     f"(Version {v.get('package_version', '')}), Fix: {v.get('fixed_version', '') or '—'}.\n"
                     f"Advisory: {v.get('advisory_url', '') or '—'}",
        firmen_id=v.get("firmen_id"), actor=_actor())
    sdb.set_vulnerability_promotion(DB_PATH, vuln_id, incident_id=iid)
    _audit("soc.vuln.promoted", id=vuln_id, target="incident", incident_id=iid, actor=_actor())
    return jsonify({"ok": True, "target": "incident", "incident_id": iid}), 201


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


@soc_bp.get("/assets/discover-syslog")
@jwt_required()
@require_permission(Permission.SOC_READ)
def discover_syslog():
    """Read-only Syslog-Quellen der letzten N h erkennen (#1347). KEIN Sync.

    Aggregiert agentlose Quellen (Wazuh-Manager, agent.id 000) über den Indexer
    und schlägt noch nicht inventarisierte Quellen vor.
    """
    try:
        from soc import asset_discovery as sad
        hours = request.args.get("hours", default=2, type=int) or 2
        res = sad.discover_syslog_sources(DB_PATH, hours=hours)
        if not res.get("ok"):
            return jsonify(res), 502 if res.get("error") else 200
        _audit("soc.asset.discovered", count=res.get("total", 0), hours=res.get("hours"))
        return jsonify(res)
    except Exception as e:
        return _log_500(e)


@soc_bp.post("/assets/from-syslog")
@jwt_required()
@require_permission(Permission.SOC_WRITE)
def assets_from_syslog():
    """Selektierte Syslog-Quellen als Asset anlegen (source='syslog', #1347).

    Body: ``{"sources": [{hostname, ip, program, ...}, …]}``. Idempotent — bereits
    vorhandene Quellen (Hostname/IP) werden nicht doppelt angelegt.
    """
    try:
        from soc import asset_discovery as sad
        d = request.get_json(silent=True) or {}
        sources = d.get("sources") or []
        if not isinstance(sources, list) or not sources:
            return jsonify({"error": "Liste 'sources' nötig"}), 400
        res = sad.create_assets_from_syslog(DB_PATH, sources)
        try:
            from shared.firmen_link import backfill_firmen_ids
            backfill_firmen_ids(DB_PATH, "soc_assets", "organisation")
        except Exception:
            pass
        _audit("soc.asset.from_syslog", created=res.get("created", 0), skipped=res.get("skipped", 0))
        return jsonify({"ok": True, **res}), 201
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


# ── Berichts-Center (#1350) ─────────────────────────────────────────────────

@soc_bp.get("/berichte")
@jwt_required()
@require_permission(Permission.SOC_READ)
def berichte_catalog():
    """Katalog der Berichtstypen + Liste automatisch erzeugter Berichte (Historie)."""
    from soc import berichte
    try:
        runs = berichte.list_runs(DB_PATH, limit=100)
    except Exception:  # noqa: BLE001
        runs = []
    return jsonify({"typen": berichte.available_reports(), "runs": runs})


@soc_bp.get("/berichte/runs/<int:run_id>/download")
@jwt_required()
@require_permission(Permission.SOC_EXPORT)
def berichte_run_download(run_id: int):
    """Lädt eine automatisch erzeugte Berichtsdatei aus ``data/soc/berichte/``."""
    from flask import Response
    from soc import berichte
    run = next((r for r in berichte.list_runs(DB_PATH, limit=1000) if r["id"] == run_id), None)
    if not run or not run.get("dateiname"):
        return jsonify({"error": "Bericht nicht gefunden"}), 404
    data = berichte.read_stored(run["dateiname"])
    if data is None:
        return jsonify({"error": "Berichtsdatei nicht mehr vorhanden"}), 404
    ext = run.get("format") or "docx"
    mime = ("application/pdf" if ext == "pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    _audit("soc.berichte.run_download", run_id=run_id, typ=run.get("typ"))
    return Response(data, mimetype=mime, headers={
        "Content-Disposition": f'attachment; filename="{run["dateiname"]}"'})


@soc_bp.get("/berichte/<typ>")
@jwt_required()
@require_permission(Permission.SOC_EXPORT)
def berichte_export(typ: str):
    """Erzeugt einen Bericht über den frei wählbaren Zeitraum (von/bis) als DOCX/PDF."""
    from flask import Response
    from soc import berichte
    if typ not in berichte.BERICHT_TYPEN:
        return jsonify({"error": "Unbekannter Berichtstyp"}), 404
    von = (request.args.get("von") or "").strip() or None
    bis = (request.args.get("bis") or "").strip() or None
    fmt = (request.args.get("format") or "docx").lower()
    try:
        if fmt == "pdf":
            data = berichte.render_pdf(DB_PATH, typ, von=von, bis=bis)
            mime, ext = "application/pdf", "pdf"
        else:
            data = berichte.render_docx(DB_PATH, typ, von=von, bis=bis)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = "docx"
    except Exception as e:  # noqa: BLE001
        from shared.templates.pdf_converter import PDFConversionUnavailable
        if isinstance(e, PDFConversionUnavailable):
            return jsonify({"error": "PDF-Konverter nicht verfügbar (Gotenberg/soffice). DOCX nutzen."}), 503
        return _log_500(e)
    _audit("soc.berichte.export", typ=typ, format=ext, von=von, bis=bis)
    return Response(data, mimetype=mime, headers={
        "Content-Disposition": f'attachment; filename="soc-bericht-{typ}.{ext}"'})


@soc_bp.post("/berichte/<typ>/generate")
@jwt_required()
@require_permission(Permission.SOC_EXPORT)
def berichte_generate(typ: str):
    """Erzeugt einen Bericht serverseitig + legt ihn in der Historie ab (manuelle Auslösung)."""
    from soc import berichte
    if typ not in berichte.BERICHT_TYPEN:
        return jsonify({"error": "Unbekannter Berichtstyp"}), 404
    d = request.get_json(silent=True) or {}
    res = berichte.generate_and_store(
        DB_PATH, typ, von=d.get("von"), bis=d.get("bis"),
        fmt=(d.get("format") or "docx").lower(),
        periode=d.get("periode") or "manuell", erzeugt_von=_actor())
    _audit("soc.berichte.generate", typ=typ, outcome="success" if res.get("ok") else "failure")
    return (jsonify(res), 201) if res.get("ok") else (jsonify(res), 500)


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
    inc["sla"] = sdb.incident_sla(DB_PATH, inc)  # #1315
    inc["pir"] = sdb.get_pir(DB_PATH, incident_id)  # #1316
    inc["pir_actions"] = sdb.list_pir_actions(DB_PATH, incident_id=incident_id)
    from soc import betrieb  # #1318 Eskalationspfad für die Severity
    betrieb.seed_defaults(DB_PATH)
    inc["escalation_path"] = betrieb.list_escalation(DB_PATH, severity=inc.get("severity") or "high")
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
    # Pflicht-Playbook-Schritte vor „resolved" abhaken (#1314)
    if target == "resolved":
        open_mand = sdb.incident_mandatory_open(DB_PATH, incident_id)
        if open_mand:
            return jsonify({"error": f"{open_mand} offene Pflicht-Schritt(e) im Playbook — "
                                     "vor dem Abschluss (Behoben) erledigen."}), 409
    sdb.set_incident_status(DB_PATH, incident_id, target, actor=_actor())
    _audit("soc.incident.status", id=incident_id, status=target, actor=_actor())
    return jsonify({"ok": True, "status": target})


@soc_bp.get("/incidents/<int:incident_id>/alerts")
@jwt_required()
@require_permission(Permission.SOC_READ)
def incident_alerts(incident_id: int):
    """Vollständige Wazuh-Alarm-Datensätze des Incidents (#1291)."""
    return jsonify({"alerts": sdb.get_incident_alerts(DB_PATH, incident_id)})


@soc_bp.post("/incidents/<int:incident_id>/alerts")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def link_incident_alerts(incident_id: int):
    """Mehrere existierende Alarme einem Incident zuordnen (#1328)."""
    uids = (request.get_json(silent=True) or {}).get("alert_uids") or []
    if not isinstance(uids, list) or not uids:
        return jsonify({"error": "alert_uids (Liste) nötig"}), 400
    res = sdb.add_alerts_to_incident(DB_PATH, incident_id, [str(u) for u in uids], actor=_actor())
    if not res.get("ok"):
        return jsonify(res), 404
    _audit("soc.incident.alerts_linked", id=incident_id, added=res.get("added"))
    return jsonify(res)


@soc_bp.delete("/incidents/<int:incident_id>/alerts/<path:alert_uid>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def unlink_incident_alert(incident_id: int, alert_uid: str):
    """Einen Alarm von einem Incident lösen (#1328)."""
    res = sdb.remove_alert_from_incident(DB_PATH, incident_id, alert_uid, actor=_actor())
    _audit("soc.incident.alert_unlinked", id=incident_id, uid=alert_uid)
    return jsonify(res)


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


# ── Response-Playbooks / Runbooks (#1314) ───────────────────────────────────

@soc_bp.get("/playbooks")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_playbooks():
    from soc.playbooks import seed_default_playbooks
    seed_default_playbooks(DB_PATH)  # idempotent: Standard-Katalog beim ersten Zugriff
    return jsonify({"playbooks": sdb.list_playbooks(DB_PATH)})


@soc_bp.post("/playbooks")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def save_playbook():
    d = request.get_json(silent=True) or {}
    if not d.get("name"):
        return jsonify({"error": "name ist Pflicht"}), 400
    pid = sdb.save_playbook(DB_PATH, id=d.get("id"), name=d["name"], kategorie=d.get("kategorie", ""),
                            beschreibung=d.get("beschreibung", ""), steps=d.get("steps") or [],
                            enabled=bool(d.get("enabled", True)))
    _audit("soc.playbook.save", id=pid)
    return jsonify({"id": pid, "ok": True}), 201


@soc_bp.delete("/playbooks/<int:playbook_id>")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def delete_playbook(playbook_id: int):
    sdb.delete_playbook(DB_PATH, playbook_id)
    return jsonify({"ok": True})


@soc_bp.get("/incidents/<int:incident_id>/playbooks")
@jwt_required()
@require_permission(Permission.SOC_READ)
def incident_playbooks(incident_id: int):
    return jsonify({"playbooks": sdb.list_incident_playbooks(DB_PATH, incident_id),
                    "mandatory_open": sdb.incident_mandatory_open(DB_PATH, incident_id)})


@soc_bp.post("/incidents/<int:incident_id>/playbooks")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def assign_playbook(incident_id: int):
    if not sdb.get_incident(DB_PATH, incident_id):
        return jsonify({"error": "Incident nicht gefunden"}), 404
    pid = (request.get_json(silent=True) or {}).get("playbook_id")
    if not pid:
        return jsonify({"error": "playbook_id nötig"}), 400
    try:
        iid = sdb.assign_playbook_to_incident(DB_PATH, incident_id, int(pid), actor=_actor())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    _audit("soc.playbook.assign", incident=incident_id, playbook=pid)
    return jsonify({"id": iid, "ok": True}), 201


@soc_bp.post("/incidents/<int:incident_id>/playbooks/<int:instance_id>/step")
@jwt_required()
@require_permission(Permission.SOC_TRIAGE)
def toggle_playbook_step(incident_id: int, instance_id: int):
    d = request.get_json(silent=True) or {}
    res = sdb.toggle_playbook_step(DB_PATH, instance_id, int(d.get("step_id", 0)),
                                   bool(d.get("done")), actor=_actor())
    if not res:
        return jsonify({"error": "Playbook-Instanz nicht gefunden"}), 404
    return jsonify({"ok": True})


# ── SLA-/KPI-Management (#1315) ─────────────────────────────────────────────

@soc_bp.get("/sla")
@jwt_required()
@require_permission(Permission.SOC_READ)
def get_sla():
    return jsonify({"sla": sdb.list_sla(DB_PATH)})


@soc_bp.post("/sla")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def save_sla():
    d = request.get_json(silent=True) or {}
    sev = d.get("severity")
    if sev not in ("critical", "high", "medium", "low"):
        return jsonify({"error": "Ungültige Severity"}), 400
    sdb.save_sla(DB_PATH, sev, int(d.get("ack_minutes", 60)), int(d.get("resolve_minutes", 1440)))
    _audit("soc.sla.save", severity=sev)
    return jsonify({"ok": True, "sla": sdb.list_sla(DB_PATH)})


@soc_bp.get("/sla-kpis")
@jwt_required()
@require_permission(Permission.SOC_READ)
def get_sla_kpis():
    return jsonify(sdb.sla_kpis(DB_PATH))


# ── Post-Incident-Review (PIR) + Maßnahmen (#1316) ──────────────────────────

@soc_bp.put("/incidents/<int:incident_id>/pir")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def save_pir(incident_id: int):
    if not sdb.get_incident(DB_PATH, incident_id):
        return jsonify({"error": "Incident nicht gefunden"}), 404
    d = request.get_json(silent=True) or {}
    sdb.save_pir(DB_PATH, incident_id, root_cause=d.get("root_cause", ""),
                 what_went_well=d.get("what_went_well", ""),
                 what_went_wrong=d.get("what_went_wrong", ""),
                 lessons=d.get("lessons", ""), actor=_actor())
    _audit("soc.pir.save", incident=incident_id)
    return jsonify({"ok": True, "pir": sdb.get_pir(DB_PATH, incident_id)})


@soc_bp.post("/incidents/<int:incident_id>/pir/actions")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def create_pir_action(incident_id: int):
    if not sdb.get_incident(DB_PATH, incident_id):
        return jsonify({"error": "Incident nicht gefunden"}), 404
    d = request.get_json(silent=True) or {}
    if not (d.get("beschreibung") or "").strip():
        return jsonify({"error": "Beschreibung ist Pflicht"}), 400
    aid = sdb.save_pir_action(DB_PATH, incident_id=incident_id, beschreibung=d["beschreibung"],
                              owner=d.get("owner", ""), frist=d.get("frist", ""),
                              status=d.get("status", "offen"), actor=_actor())
    _audit("soc.pir.action.create", incident=incident_id, action=aid)
    return jsonify({"id": aid, "ok": True}), 201


@soc_bp.put("/pir/actions/<int:action_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def update_pir_action(action_id: int):
    d = request.get_json(silent=True) or {}
    if d.get("status") not in PIR_ACTION_STATES:
        return jsonify({"error": f"Status muss eines von {PIR_ACTION_STATES} sein"}), 400
    # Reine Status-Änderung vs. Vollbearbeitung
    if set(d.keys()) <= {"status"}:
        res = sdb.set_pir_action_status(DB_PATH, action_id, d["status"], actor=_actor())
        if not res.get("ok"):
            return jsonify(res), 404
    else:
        if "incident_id" not in d:
            return jsonify({"error": "incident_id nötig"}), 400
        sdb.save_pir_action(DB_PATH, id=action_id, incident_id=int(d["incident_id"]),
                            beschreibung=d.get("beschreibung", ""), owner=d.get("owner", ""),
                            frist=d.get("frist", ""), status=d["status"], actor=_actor())
    _audit("soc.pir.action.update", action=action_id, status=d["status"])
    return jsonify({"ok": True})


@soc_bp.delete("/pir/actions/<int:action_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def delete_pir_action(action_id: int):
    sdb.delete_pir_action(DB_PATH, action_id)
    _audit("soc.pir.action.delete", action=action_id)
    return jsonify({"ok": True})


@soc_bp.get("/pir/actions")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_pir_actions():
    only_open = request.args.get("only_open", "").lower() in ("1", "true", "yes")
    return jsonify({"actions": sdb.list_pir_actions(DB_PATH, only_open=only_open)})


@soc_bp.get("/pir/actions/export")
@jwt_required()
@require_permission(Permission.SOC_EXPORT)
def export_pir_actions():
    """Offene Maßnahmen-Übersicht als CSV."""
    import csv
    import io
    from flask import Response
    rows = sdb.list_pir_actions(DB_PATH, only_open=request.args.get("only_open", "1") != "0")
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Incident", "Titel", "Maßnahme", "Owner", "Frist", "Status", "Angelegt"])
    for a in rows:
        w.writerow([a["incident_id"], a.get("incident_titel", ""), a["beschreibung"],
                    a["owner"], a["frist"], a["status"], (a.get("created_at") or "")[:10]])
    _audit("soc.pir.actions.export", count=len(rows))
    return Response("﻿" + buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="soc-massnahmen.csv"'})


# ── Beweissicherung / Asservaten + Chain of Custody (#1317) ─────────────────

@soc_bp.get("/incidents/<int:incident_id>/evidence")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_evidence(incident_id: int):
    from soc import evidence as sev
    return jsonify({"evidence": sev.list_evidence(DB_PATH, incident_id)})


@soc_bp.post("/incidents/<int:incident_id>/evidence")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def add_evidence(incident_id: int):
    from soc import evidence as sev
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Datei (file) nötig"}), 400
    try:
        rd = int(request.form.get("retention_days", 365))
        res = sev.add_evidence(DB_PATH, incident_id, filename=f.filename, data=f.read(),
                               content_type=f.mimetype or "", retention_days=rd,
                               beschreibung=request.form.get("beschreibung", ""), actor=_actor())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not res.get("ok"):
        return jsonify(res), 404
    _audit("soc.evidence.added", incident=incident_id, evidence=res.get("id"))
    return jsonify(res), 201


@soc_bp.post("/incidents/<int:incident_id>/evidence/snapshot")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def freeze_snapshot(incident_id: int):
    from soc import evidence as sev
    rd = int((request.get_json(silent=True) or {}).get("retention_days", 365))
    res = sev.freeze_log_snapshot(DB_PATH, incident_id, retention_days=rd, actor=_actor())
    if not res.get("ok"):
        return jsonify(res), 404
    _audit("soc.evidence.snapshot", incident=incident_id, evidence=res.get("id"))
    return jsonify(res), 201


@soc_bp.get("/evidence/<int:evidence_id>/custody")
@jwt_required()
@require_permission(Permission.SOC_READ)
def evidence_custody(evidence_id: int):
    from soc import evidence as sev
    ev = sev.get_evidence(DB_PATH, evidence_id)
    if not ev:
        return jsonify({"error": "Asservat nicht gefunden"}), 404
    return jsonify({"evidence": ev, "custody": sev.list_custody(DB_PATH, evidence_id)})


@soc_bp.get("/evidence/<int:evidence_id>/download")
@jwt_required()
@require_permission(Permission.SOC_EXPORT)
def download_evidence(evidence_id: int):
    from flask import Response
    from soc import evidence as sev
    out = sev.read_evidence_file(DB_PATH, evidence_id, action="exported", actor=_actor())
    if not out:
        return jsonify({"error": "Asservat nicht verfügbar (gelöscht/fehlend)"}), 404
    data, ev = out
    _audit("soc.evidence.downloaded", evidence=evidence_id)
    return Response(data, mimetype=ev.get("content_type") or "application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{ev["filename"]}"'})


@soc_bp.delete("/evidence/<int:evidence_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def delete_evidence(evidence_id: int):
    from soc import evidence as sev
    reason = (request.get_json(silent=True) or {}).get("reason", "")
    res = sev.delete_evidence(DB_PATH, evidence_id, reason=reason, actor=_actor())
    if not res.get("ok"):
        return jsonify(res), 400
    _audit("soc.evidence.deleted", evidence=evidence_id)
    return jsonify(res)


# ── Schicht-/On-Call-Betrieb + Eskalationsmatrix + RACI (#1318) ─────────────

@soc_bp.get("/handover")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_handover():
    from soc import betrieb
    return jsonify({"handovers": betrieb.list_handovers(DB_PATH)})


@soc_bp.post("/handover")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def save_handover():
    from soc import betrieb
    d = request.get_json(silent=True) or {}
    hid = betrieb.save_handover(DB_PATH, schicht=d.get("schicht", ""), datum=d.get("datum", ""),
                                von_user=d.get("von_user", "") or _actor(), an_user=d.get("an_user", ""),
                                offene_punkte=d.get("offene_punkte", ""), notizen=d.get("notizen", ""),
                                actor=_actor())
    _audit("soc.handover.save", id=hid)
    return jsonify({"id": hid, "ok": True}), 201


@soc_bp.delete("/handover/<int:handover_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def delete_handover(handover_id: int):
    from soc import betrieb
    betrieb.delete_handover(DB_PATH, handover_id)
    return jsonify({"ok": True})


@soc_bp.get("/escalation")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_escalation():
    from soc import betrieb
    betrieb.seed_defaults(DB_PATH)  # Standard-Matrix beim ersten Zugriff
    return jsonify({"escalation": betrieb.list_escalation(DB_PATH)})


@soc_bp.post("/escalation")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def save_escalation():
    from soc import betrieb
    d = request.get_json(silent=True) or {}
    if d.get("severity") not in SEVERITIES:
        return jsonify({"error": "Ungültige Severity"}), 400
    eid = betrieb.save_escalation(DB_PATH, id=d.get("id"), severity=d["severity"],
                                  stufe=int(d.get("stufe", 1)), rolle=d.get("rolle", ""),
                                  person=d.get("person", ""), kontakt=d.get("kontakt", ""),
                                  frist_minuten=int(d.get("frist_minuten", 30)))
    _audit("soc.escalation.save", id=eid)
    return jsonify({"id": eid, "ok": True}), 201


@soc_bp.delete("/escalation/<int:escalation_id>")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def delete_escalation(escalation_id: int):
    from soc import betrieb
    betrieb.delete_escalation(DB_PATH, escalation_id)
    return jsonify({"ok": True})


@soc_bp.get("/raci")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_raci():
    from soc import betrieb
    return jsonify({"raci": betrieb.list_raci(DB_PATH)})


@soc_bp.post("/raci")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def save_raci():
    from soc import betrieb
    d = request.get_json(silent=True) or {}
    if not d.get("vorfallstyp") or not d.get("rolle"):
        return jsonify({"error": "vorfallstyp + rolle nötig"}), 400
    if d.get("raci") not in ("R", "A", "C", "I"):
        return jsonify({"error": "raci muss R/A/C/I sein"}), 400
    rid = betrieb.save_raci(DB_PATH, id=d.get("id"), vorfallstyp=d["vorfallstyp"],
                            rolle=d["rolle"], raci=d["raci"])
    return jsonify({"id": rid, "ok": True}), 201


@soc_bp.delete("/raci/<int:raci_id>")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def delete_raci(raci_id: int):
    from soc import betrieb
    betrieb.delete_raci(DB_PATH, raci_id)
    return jsonify({"ok": True})


@soc_bp.post("/incidents/<int:incident_id>/escalate")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def escalate_incident(incident_id: int):
    from soc import betrieb
    stufe = int((request.get_json(silent=True) or {}).get("stufe", 1))
    res = betrieb.escalate_incident(DB_PATH, incident_id, stufe, actor=_actor())
    if not res.get("ok"):
        return jsonify(res), 404
    _audit("soc.incident.escalated", id=incident_id, stufe=stufe)
    return jsonify(res)


# ── SOC-Übungen / Tests (#1319) ─────────────────────────────────────────────

@soc_bp.get("/uebungen")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_uebungen():
    from soc import uebungen
    return jsonify({"uebungen": uebungen.list_uebungen(DB_PATH),
                    "types": UEBUNG_TYPES, "states": UEBUNG_STATES, "ergebnis": UEBUNG_ERGEBNIS,
                    "lifecycle": UEBUNG_LIFECYCLE, "ziel_types": UEBUNG_ZIEL_TYPES,
                    "ziel_bewertung": UEBUNG_ZIEL_BEWERTUNG, "inject_states": UEBUNG_INJECT_STATES,
                    "mass_states": UEBUNG_MASS_STATES})


@soc_bp.get("/uebungen/<int:uebung_id>")
@jwt_required()
@require_permission(Permission.SOC_READ)
def get_uebung_detail(uebung_id: int):
    """Übung inkl. ISO-22398-Details (Ziele, MSEL-Injects, Improvement Plan)."""
    from soc import uebungen
    u = uebungen.get_uebung(DB_PATH, uebung_id, with_details=True)
    if not u:
        return jsonify({"error": "Übung nicht gefunden"}), 404
    return jsonify({"uebung": u})


@soc_bp.post("/uebungen")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def save_uebung():
    from soc import uebungen
    d = request.get_json(silent=True) or {}
    if not d.get("id") and not (d.get("titel") or "").strip():
        return jsonify({"error": "Titel ist Pflicht"}), 400
    if d.get("typ") and d["typ"] not in UEBUNG_TYPES:
        return jsonify({"error": "Ungültiger Typ"}), 400
    if d.get("lifecycle") and d["lifecycle"] not in UEBUNG_LIFECYCLE:
        return jsonify({"error": "Ungültige Lebenszyklus-Phase"}), 400
    uid = uebungen.save_uebung(DB_PATH, actor=_actor(),
                               **{k: v for k, v in d.items() if k != "id"}, id=d.get("id"))
    _audit("soc.uebung.save", id=uid)
    return jsonify({"id": uid, "ok": True}), 201


@soc_bp.delete("/uebungen/<int:uebung_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def delete_uebung(uebung_id: int):
    from soc import uebungen
    uebungen.delete_uebung(DB_PATH, uebung_id)
    _audit("soc.uebung.delete", id=uebung_id)
    return jsonify({"ok": True})


# ── ISO-22398: Übungsziele (#1351) ──────────────────────────────────────────

@soc_bp.post("/uebungen/<int:uebung_id>/ziele")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def save_uebung_ziel(uebung_id: int):
    from soc import uebungen
    d = request.get_json(silent=True) or {}
    if d.get("typ") and d["typ"] not in UEBUNG_ZIEL_TYPES:
        return jsonify({"error": "Ungültiger Zieltyp"}), 400
    if d.get("bewertung") and d["bewertung"] not in UEBUNG_ZIEL_BEWERTUNG:
        return jsonify({"error": "Ungültige Bewertung"}), 400
    zid = uebungen.save_ziel(DB_PATH, uebung_id=uebung_id,
                             **{k: v for k, v in d.items() if k != "id"}, id=d.get("id"))
    _audit("soc.uebung.ziel.save", uebung_id=uebung_id, id=zid)
    return jsonify({"id": zid, "ok": True}), 201


@soc_bp.delete("/uebungen/ziele/<int:ziel_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def delete_uebung_ziel(ziel_id: int):
    from soc import uebungen
    uebungen.delete_ziel(DB_PATH, ziel_id)
    _audit("soc.uebung.ziel.delete", id=ziel_id)
    return jsonify({"ok": True})


# ── ISO-22398: MSEL-Injects (#1351) ─────────────────────────────────────────

@soc_bp.post("/uebungen/<int:uebung_id>/injects")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def save_uebung_inject(uebung_id: int):
    from soc import uebungen
    d = request.get_json(silent=True) or {}
    if d.get("status") and d["status"] not in UEBUNG_INJECT_STATES:
        return jsonify({"error": "Ungültiger Inject-Status"}), 400
    iid = uebungen.save_inject(DB_PATH, uebung_id=uebung_id,
                               **{k: v for k, v in d.items() if k != "id"}, id=d.get("id"))
    _audit("soc.uebung.inject.save", uebung_id=uebung_id, id=iid)
    return jsonify({"id": iid, "ok": True}), 201


@soc_bp.delete("/uebungen/injects/<int:inject_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def delete_uebung_inject(inject_id: int):
    from soc import uebungen
    uebungen.delete_inject(DB_PATH, inject_id)
    _audit("soc.uebung.inject.delete", id=inject_id)
    return jsonify({"ok": True})


# ── ISO-22398: Improvement Plan / Korrekturmaßnahmen (#1351) ────────────────

@soc_bp.post("/uebungen/<int:uebung_id>/massnahmen")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def save_uebung_massnahme(uebung_id: int):
    from soc import uebungen
    d = request.get_json(silent=True) or {}
    if d.get("status") and d["status"] not in UEBUNG_MASS_STATES:
        return jsonify({"error": "Ungültiger Status"}), 400
    if not d.get("id") and not (d.get("beschreibung") or "").strip():
        return jsonify({"error": "Beschreibung ist Pflicht"}), 400
    mid = uebungen.save_massnahme(DB_PATH, uebung_id=uebung_id, actor=_actor(),
                                  id=d.get("id"), beschreibung=d.get("beschreibung", ""),
                                  owner=d.get("owner", ""), frist=d.get("frist", ""),
                                  status=d.get("status", "offen"))
    _audit("soc.uebung.massnahme.save", uebung_id=uebung_id, id=mid)
    return jsonify({"id": mid, "ok": True}), 201


@soc_bp.post("/uebungen/massnahmen/<int:massnahme_id>/status")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def set_uebung_massnahme_status(massnahme_id: int):
    from soc import uebungen
    d = request.get_json(silent=True) or {}
    status = (d.get("status") or "").strip()
    if status not in UEBUNG_MASS_STATES:
        return jsonify({"error": "Ungültiger Status"}), 400
    res = uebungen.set_massnahme_status(DB_PATH, massnahme_id, status, actor=_actor())
    if not res.get("ok"):
        return jsonify(res), 404
    _audit("soc.uebung.massnahme.status", id=massnahme_id, status=status)
    return jsonify(res)


@soc_bp.delete("/uebungen/massnahmen/<int:massnahme_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def delete_uebung_massnahme(massnahme_id: int):
    from soc import uebungen
    uebungen.delete_massnahme(DB_PATH, massnahme_id)
    _audit("soc.uebung.massnahme.delete", id=massnahme_id)
    return jsonify({"ok": True})


# ── After-Action-Report-Export (ISO 22398, #1351) ──────────────────────────

@soc_bp.get("/uebungen/<int:uebung_id>/aar")
@jwt_required()
@require_permission(Permission.SOC_EXPORT)
def export_uebung_aar(uebung_id: int):
    """After-Action-Report einer Übung als DOCX/PDF (ISO-22398-Layout)."""
    from flask import Response
    from soc import berichte, uebungen
    u = uebungen.get_uebung(DB_PATH, uebung_id)
    if not u:
        return jsonify({"error": "Übung nicht gefunden"}), 404
    fmt = (request.args.get("format") or "docx").lower()
    try:
        if fmt == "pdf":
            data = berichte.render_aar_pdf(DB_PATH, uebung_id)
            mime, ext = "application/pdf", "pdf"
        else:
            data = berichte.render_aar_docx(DB_PATH, uebung_id)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = "docx"
    except Exception as e:  # noqa: BLE001
        from shared.templates.pdf_converter import PDFConversionUnavailable
        if isinstance(e, PDFConversionUnavailable):
            return jsonify({"error": "PDF-Konverter nicht verfügbar (Gotenberg/soffice). DOCX nutzen."}), 503
        return _log_500(e)
    _audit("soc.uebung.aar.export", uebung_id=uebung_id, format=ext)
    return Response(data, mimetype=mime, headers={
        "Content-Disposition": f'attachment; filename="soc-aar-{uebung_id}.{ext}"'})


@soc_bp.get("/uebungen/export")
@jwt_required()
@require_permission(Permission.SOC_EXPORT)
def export_uebungen():
    import csv
    import io
    from flask import Response
    from soc import uebungen
    rows = uebungen.list_uebungen(DB_PATH)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Datum", "Typ", "Titel", "Status", "Ergebnis", "Teilnehmer",
                "Erwartet", "Tatsächlich", "Auswertung", "Maßnahmen"])
    for u in rows:
        w.writerow([u["datum"], u["typ"], u["titel"], u["status"], u["ergebnis"], u["teilnehmer"],
                    u["erwartete_erkennung"], u["tatsaechliche_erkennung"], u["auswertung"], u["massnahmen"]])
    _audit("soc.uebungen.export", count=len(rows))
    return Response("﻿" + buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="soc-uebungen.csv"'})


# ── Detection-Use-Cases + ATT&CK-Coverage (#1321) ───────────────────────────

@soc_bp.get("/detection/usecases")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_detection_usecases():
    from soc import detection
    return jsonify({"usecases": detection.list_usecases(DB_PATH), "states": DETECTION_STATES})


@soc_bp.post("/detection/usecases")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def save_detection_usecase():
    from soc import detection
    d = request.get_json(silent=True) or {}
    if not d.get("id") and not (d.get("name") or "").strip():
        return jsonify({"error": "Name ist Pflicht"}), 400
    if d.get("status") and d["status"] not in DETECTION_STATES:
        return jsonify({"error": "Ungültiger Status"}), 400
    uid = detection.save_usecase(DB_PATH, id=d.get("id"), name=d.get("name", ""),
                                 bedrohung=d.get("bedrohung", ""),
                                 attack_techniques=d.get("attack_techniques") or [],
                                 wazuh_rules=d.get("wazuh_rules", ""),
                                 status=d.get("status", "geplant"),
                                 datenquelle=d.get("datenquelle", ""), notizen=d.get("notizen", ""))
    _audit("soc.detection.usecase.save", id=uid)
    return jsonify({"id": uid, "ok": True}), 201


@soc_bp.delete("/detection/usecases/<int:usecase_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def delete_detection_usecase(usecase_id: int):
    from soc import detection
    detection.delete_usecase(DB_PATH, usecase_id)
    return jsonify({"ok": True})


@soc_bp.get("/detection/coverage")
@jwt_required()
@require_permission(Permission.SOC_READ)
def detection_coverage():
    """ATT&CK-Coverage-Heatmap. ``?source=alarme|regelwerk|beides`` (#1349).

    Liefert zusätzlich Regelwerk-basierte Use-Case-Kandidaten (``rule_candidates``)
    zur 1-Klick-Bestätigung.
    """
    from soc import detection
    source = request.args.get("source") or "beides"
    return jsonify({"coverage": detection.attack_coverage(DB_PATH, source=source),
                    "gaps": detection.coverage_gaps(DB_PATH, source=source),
                    "suggestions": detection.suggestions_from_alerts(DB_PATH),
                    "rule_candidates": detection.usecase_candidates_from_rules(DB_PATH)})


@soc_bp.get("/detection/rule-coverage")
@jwt_required()
@require_permission(Permission.SOC_READ)
def detection_rule_coverage():
    """Reine Regelwerk-Abdeckung: Technik → abdeckende Rule-IDs + Kandidaten (#1349).

    Capability-Sicht aus dem installierten Regelwerk (``soc_rules``), unabhängig von
    gefeuerten Alarmen.
    """
    from soc import detection
    rule_map = detection.techniques_from_ruleset(DB_PATH)
    techniques = []
    for tid, rids in sorted(rule_map.items()):
        meta = detection.TECHNIQUES.get(tid)
        techniques.append({
            "technique": tid, "name": meta[0] if meta else tid,
            "tactic": meta[1] if meta else "—",
            "rule_ids": rids, "rule_count": len(rids),
            "known": meta is not None})
    return jsonify({
        "techniques": techniques,
        "technique_count": len(techniques),
        "candidates": detection.usecase_candidates_from_rules(DB_PATH),
        "sync": sdb.rules_sync_state(DB_PATH)})


@soc_bp.post("/detection/use-cases/confirm")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def confirm_detection_usecase():
    """Bestätigt einen Regelwerk-Kandidaten per Knopfdruck → Use-Case ``aktiv`` (#1349)."""
    from soc import detection
    d = request.get_json(silent=True) or {}
    technique = (d.get("technique") or "").strip()
    if not technique:
        return jsonify({"error": "Technik-ID ist Pflicht"}), 400
    rule_ids_raw = d.get("rule_ids") or []
    rule_ids = []
    for r in rule_ids_raw:
        try:
            rule_ids.append(int(r))
        except (TypeError, ValueError):
            continue
    try:
        uid = detection.confirm_usecase(
            DB_PATH, technique=technique, rule_ids=rule_ids,
            existing_usecase_id=d.get("existing_usecase_id"),
            name=d.get("name", ""), bedrohung=d.get("bedrohung", ""))
    except Exception as e:
        return _log_500(e)
    _audit("soc.detection.usecase.confirmed", id=uid, technique=technique,
           rule_count=len(rule_ids))
    return jsonify({"id": uid, "ok": True}), 201


# ── Regelwerk-Explorer (#1348) ──────────────────────────────────────────────
# Read-only Abruf + durchsuchbarer Cache des installierten Wazuh-Regelwerks.
# Quelle ist die Manager-API (GET /rules); der Manager-API-Benutzer braucht die
# RBAC-Berechtigung 'rules:read' (z. B. eine soc-reader-Rolle).

@soc_bp.post("/rules/sync")
@jwt_required()
@require_permission(Permission.SOC_CONFIG)
def sync_rules():
    """Zieht das komplette installierte Regelwerk read-only in den Cache (#1348).

    Manager-Creds wie bei /assets/refresh: explizit gesendet ODER aus der
    gespeicherten Verbindung. Der API-Benutzer braucht 'rules:read'.
    """
    from soc import wazuh_rules as wzr
    d = request.get_json(silent=True) or {}
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
            if "verify_tls" not in d:
                verify_tls = bool(saved.get("verify_tls", True))
    if not manager_url:
        return jsonify({"error": "Manager-URL (z. B. https://host:55000) nötig"}), 400
    try:
        rules = wzr.fetch_rules(manager_url, username, password, verify_tls=verify_tls)
        n = sdb.replace_rules(DB_PATH, rules)
        _audit("soc.rules.synced", count=n)
        return jsonify({"ok": True, "count": n, "sync": sdb.rules_sync_state(DB_PATH)})
    except wz.WazuhError as e:
        sdb.record_rules_sync_error(DB_PATH, str(e))
        _audit("soc.rules.synced", outcome="failure", error=str(e))
        return jsonify({"ok": False, "error": str(e)}), 502
    except Exception as e:
        sdb.record_rules_sync_error(DB_PATH, f"{type(e).__name__}: {e}")
        return _log_500(e)


@soc_bp.get("/rules")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_rules():
    """Read-only Such-/Filtersicht auf den Regelwerk-Cache (#1348)."""
    try:
        return jsonify(sdb.list_rules(
            DB_PATH,
            group=request.args.get("group") or None,
            mitre=request.args.get("mitre") or None,
            min_level=request.args.get("min_level", type=int),
            status=request.args.get("status") or None,
            q=request.args.get("q") or None,
            limit=request.args.get("limit", default=2000, type=int)))
    except Exception as e:
        return _log_500(e)


# ── Threat-Intelligence / IOC-Feeds (#1322) ─────────────────────────────────

@soc_bp.get("/iocs")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_iocs():
    from soc import threatintel
    return jsonify({"iocs": threatintel.list_iocs(DB_PATH), "types": threatintel.IOC_TYPES,
                    "alerts_with_iocs": threatintel.alerts_with_iocs(DB_PATH)})


@soc_bp.post("/iocs")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def save_ioc():
    from soc import threatintel
    d = request.get_json(silent=True) or {}
    if not d.get("id") and not (d.get("wert") or "").strip():
        return jsonify({"error": "Wert ist Pflicht"}), 400
    if d.get("typ") and d["typ"] not in threatintel.IOC_TYPES:
        return jsonify({"error": "Ungültiger IOC-Typ"}), 400
    iid = threatintel.save_ioc(DB_PATH, id=d.get("id"), typ=d.get("typ", "ip"),
                               wert=d.get("wert", ""), quelle=d.get("quelle", ""),
                               confidence=int(d.get("confidence", 50)),
                               beschreibung=d.get("beschreibung", ""),
                               gueltig_bis=d.get("gueltig_bis", ""),
                               enabled=bool(d.get("enabled", True)), actor=_actor())
    _audit("soc.ioc.save", id=iid)
    return jsonify({"id": iid, "ok": True}), 201


@soc_bp.post("/iocs/import")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def import_iocs():
    from soc import threatintel
    d = request.get_json(silent=True) or {}
    n = threatintel.import_iocs(DB_PATH, d.get("text", ""), quelle=d.get("quelle", "import"),
                                actor=_actor())
    rescanned = threatintel.rescan_alerts(DB_PATH)
    _audit("soc.ioc.import", count=n)
    return jsonify({"ok": True, "imported": n, "alerts_matched": rescanned})


@soc_bp.delete("/iocs/<int:ioc_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def delete_ioc(ioc_id: int):
    from soc import threatintel
    threatintel.delete_ioc(DB_PATH, ioc_id)
    return jsonify({"ok": True})


@soc_bp.post("/iocs/rescan")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def rescan_iocs():
    from soc import threatintel
    n = threatintel.rescan_alerts(DB_PATH)
    _audit("soc.ioc.rescan", matched=n)
    return jsonify({"ok": True, "alerts_matched": n})


# ── Threat-Hunting (#1323) ──────────────────────────────────────────────────

@soc_bp.get("/hunts")
@jwt_required()
@require_permission(Permission.SOC_READ)
def list_hunts():
    from soc import hunting
    return jsonify({"hunts": hunting.list_hunts(DB_PATH)})


@soc_bp.post("/hunts")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def save_hunt():
    from soc import hunting
    d = request.get_json(silent=True) or {}
    if not d.get("id") and not (d.get("hypothese") or "").strip():
        return jsonify({"error": "Hypothese ist Pflicht"}), 400
    hid = hunting.save_hunt(DB_PATH, actor=_actor(),
                            **{k: v for k, v in d.items() if k != "id"}, id=d.get("id"))
    _audit("soc.hunt.save", id=hid)
    return jsonify({"id": hid, "ok": True}), 201


@soc_bp.delete("/hunts/<int:hunt_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def delete_hunt(hunt_id: int):
    from soc import hunting
    hunting.delete_hunt(DB_PATH, hunt_id)
    return jsonify({"ok": True})


@soc_bp.post("/hunts/query")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def run_hunt_query():
    from soc import hunting
    d = request.get_json(silent=True) or {}
    res = hunting.run_query(DB_PATH, d.get("query", ""), limit=int(d.get("limit", 50)))
    _audit("soc.hunt.query", outcome="success" if res.get("ok") else "fail")
    return jsonify(res), (200 if res.get("ok") else 502)


@soc_bp.post("/hunts/<int:hunt_id>/escalate")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def escalate_hunt(hunt_id: int):
    from soc import hunting
    d = request.get_json(silent=True) or {}
    res = hunting.escalate_to_incident(DB_PATH, hunt_id, titel=d.get("titel", ""),
                                       severity=d.get("severity", "medium"), actor=_actor())
    if not res.get("ok"):
        return jsonify(res), 404
    _audit("soc.hunt.escalated", id=hunt_id, incident=res.get("incident_id"))
    return jsonify(res), 201


# ── Log-Source-/Coverage-Management + Health (#1324) ────────────────────────

@soc_bp.get("/log-sources")
@jwt_required()
@require_permission(Permission.SOC_READ)
def log_sources_health():
    from soc import logsources
    silent = int(request.args.get("silent_days", 7))
    return jsonify({**logsources.health(DB_PATH, silent_days=silent),
                    "register": logsources.list_sources(DB_PATH)})


@soc_bp.post("/log-sources")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def save_log_source():
    from soc import logsources
    d = request.get_json(silent=True) or {}
    if not (d.get("name") or "").strip():
        return jsonify({"error": "Name ist Pflicht"}), 400
    sid = logsources.save_source(DB_PATH, id=d.get("id"), name=d["name"], typ=d.get("typ", ""),
                                 erwartet=bool(d.get("erwartet", True)), notizen=d.get("notizen", ""))
    _audit("soc.logsource.save", id=sid)
    return jsonify({"id": sid, "ok": True}), 201


@soc_bp.delete("/log-sources/<int:source_id>")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def delete_log_source(source_id: int):
    from soc import logsources
    logsources.delete_source(DB_PATH, source_id)
    return jsonify({"ok": True})


# ── Periodisches Management-Reporting (#1325) ───────────────────────────────

@soc_bp.get("/mgmt-report")
@jwt_required()
@require_permission(Permission.SOC_READ)
def mgmt_report_data():
    from soc import mgmt_report
    period = request.args.get("period", "monat")
    return jsonify(mgmt_report.build_report_data(DB_PATH, period=period))


@soc_bp.get("/mgmt-report/export")
@jwt_required()
@require_permission(Permission.SOC_EXPORT)
def mgmt_report_export():
    from flask import Response
    from soc import mgmt_report
    period = request.args.get("period", "monat")
    fmt = (request.args.get("format") or "pdf").lower()
    data = mgmt_report.build_report_data(DB_PATH, period=period)
    try:
        if fmt == "docx":
            blob = mgmt_report.render_docx(data)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = "docx"
        else:
            blob = mgmt_report.render_pdf(data)
            mime, ext = "application/pdf", "pdf"
    except Exception as e:
        from shared.templates.pdf_converter import PDFConversionUnavailable
        if isinstance(e, PDFConversionUnavailable):
            return jsonify({"error": "PDF-Konverter nicht verfügbar (Gotenberg/soffice). DOCX nutzen."}), 503
        return _log_500(e)
    _audit("soc.mgmt_report.export", period=period, format=ext)
    return Response(blob, mimetype=mime, headers={
        "Content-Disposition": f'attachment; filename="soc-management-report-{period}.{ext}"'})


# ── SOC-Reifegrad-Self-Assessment (SOC-CMM) (#1326) ─────────────────────────

@soc_bp.get("/assessment/catalog")
@jwt_required()
@require_permission(Permission.SOC_READ)
def assessment_catalog():
    from soc import soccmm
    return jsonify({"catalog": soccmm.CATALOG, "max_level": soccmm.MAX_LEVEL,
                    "suggestions": soccmm.auto_suggestions(DB_PATH),
                    "latest": soccmm.latest_scores(DB_PATH),
                    "history": soccmm.list_assessments(DB_PATH)})


@soc_bp.post("/assessment")
@jwt_required()
@require_permission(Permission.SOC_INCIDENT)
def save_assessment():
    from soc import soccmm
    d = request.get_json(silent=True) or {}
    res = soccmm.create_assessment(DB_PATH, datum=d.get("datum", ""),
                                   durchgefuehrt_von=d.get("durchgefuehrt_von", ""),
                                   notizen=d.get("notizen", ""), scores=d.get("scores") or {},
                                   actor=_actor())
    _audit("soc.assessment.save", id=res.get("id"), reifegrad=res.get("gesamt_reifegrad"))
    return jsonify(res), 201


@soc_bp.get("/assessment/<int:assessment_id>")
@jwt_required()
@require_permission(Permission.SOC_READ)
def get_assessment(assessment_id: int):
    from soc import soccmm
    a = soccmm.get_assessment(DB_PATH, assessment_id)
    if not a:
        return jsonify({"error": "Assessment nicht gefunden"}), 404
    return jsonify(a)


@soc_bp.get("/assessment/export")
@jwt_required()
@require_permission(Permission.SOC_EXPORT)
def export_assessment():
    from flask import Response
    from soc import soccmm
    fmt = (request.args.get("format") or "pdf").lower()
    aid = request.args.get("id", type=int)
    try:
        if fmt == "docx":
            blob = soccmm.render_docx(DB_PATH, aid)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = "docx"
        else:
            blob = soccmm.render_pdf(DB_PATH, aid)
            mime, ext = "application/pdf", "pdf"
    except Exception as e:
        from shared.templates.pdf_converter import PDFConversionUnavailable
        if isinstance(e, PDFConversionUnavailable):
            return jsonify({"error": "PDF-Konverter nicht verfügbar (Gotenberg/soffice). DOCX nutzen."}), 503
        return _log_500(e)
    _audit("soc.assessment.export", format=ext)
    return Response(blob, mimetype=mime, headers={
        "Content-Disposition": f'attachment; filename="soc-reifegrad.{ext}"'})


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
