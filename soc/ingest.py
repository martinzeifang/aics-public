"""SOC-Ingest: Alarme normalisiert übernehmen, Suppressions anwenden, Asset/Firma
zuordnen, idempotent speichern. Gemeinsam für PULL (Sync) und PUSH (Webhook).
"""
from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from soc import db as sdb
from soc import wazuh_client as wz


def _matches_suppression(alert: dict[str, Any], rule: dict[str, Any]) -> bool:
    if rule.get("rule_id") and str(rule["rule_id"]) != str(alert.get("rule_id", "")):
        return False
    if rule.get("agent_glob") and not fnmatch.fnmatch(alert.get("agent_name", ""), rule["agent_glob"]):
        return False
    if rule.get("srcip") and rule["srcip"] != alert.get("srcip", ""):
        return False
    # mind. ein Kriterium muss gesetzt sein, sonst keine Pauschal-Unterdrückung
    return any(rule.get(k) for k in ("rule_id", "agent_glob", "srcip"))


def ingest_alerts(db_path: Path, alerts: list[dict[str, Any]]) -> dict[str, int]:
    """Übernimmt eine Liste normalisierter Alarme. Returns {new, suppressed, skipped}."""
    sdb.ensure_db(db_path)
    suppressions = sdb.list_suppressions(db_path, only_enabled=True)
    assets = {a["agent_name"]: a for a in sdb.list_assets(db_path) if a.get("agent_name")}
    from soc import threatintel  # #1322 Threat-Intel-Anreicherung
    iocs = threatintel.list_iocs(db_path, only_active=True)
    new = suppressed = skipped = 0
    for a in alerts:
        # Suppression?
        if any(_matches_suppression(a, s) for s in suppressions):
            a["status"] = "suppressed"
            suppressed += 1
        # Threat-Intel: IOC-Treffer markieren + ggf. Severity anheben
        if iocs:
            threatintel.enrich_alert(a, iocs)
        # Asset → asset_id + firmen_id (#1305)
        asset = assets.get(a.get("agent_name", ""))
        if asset:
            a["asset_id"] = asset.get("id")
            if asset.get("firmen_id"):
                a["firmen_id"] = asset["firmen_id"]
        if sdb.upsert_alert(db_path, a):
            new += 1
        else:
            skipped += 1
    return {"new": new, "suppressed": suppressed, "skipped": skipped, "received": len(alerts)}


def run_pull(db_path: Path, connection_name: str = "default") -> dict[str, Any]:
    """Führt einen PULL-Sync für eine Verbindung aus (Cursor-basiert, idempotent)."""
    conn = sdb.load_connection(db_path, connection_name, with_secret=True)
    if not conn:
        return {"ok": False, "error": "Keine Verbindung konfiguriert"}
    if conn.get("modus") != "pull":
        return {"ok": False, "error": "Verbindung ist nicht im PULL-Modus"}
    cur = sdb.get_cursor(db_path, conn["id"])
    try:
        res = wz.pull_alerts(conn, after_ts=cur.get("cursor_ts", ""), after_id=cur.get("cursor_id", ""))
    except wz.WazuhError as e:
        sdb.set_cursor(db_path, conn["id"], cursor_ts=cur.get("cursor_ts", ""),
                       cursor_id=cur.get("cursor_id", ""), status=f"error: {e}", count=0)
        return {"ok": False, "error": str(e)}
    counts = ingest_alerts(db_path, res["alerts"])
    sdb.set_cursor(db_path, conn["id"], cursor_ts=res["cursor_ts"], cursor_id=res["cursor_id"],
                   status="ok", count=counts["new"])
    return {"ok": True, **counts, "cursor_ts": res["cursor_ts"]}


# ── Schwachstellen-Sync (#1343) ─────────────────────────────────────────────

_VULN_SEV_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def run_vuln_sync(db_path: Path, connection_name: str = "default") -> dict[str, Any]:
    """Vollständiger Snapshot-Sync des Wazuh-States-Schwachstellen-Index (#1343).

    Zieht den kompletten Ist-Bestand, upsertet idempotent (Triage bleibt, Schwere
    nur anheben), verknüpft Assets/Firma automatisch und setzt verschwundene CVEs
    auf 'Solved' (Reconcile, kein Hard-Delete). Returns Lauf-Statistik.
    """
    conn = sdb.load_connection(db_path, connection_name, with_secret=True)
    if not conn:
        return {"ok": False, "error": "Keine Verbindung konfiguriert"}
    if conn.get("modus") != "pull":
        return {"ok": False, "error": "Verbindung ist nicht im PULL-Modus"}
    if not conn.get("url"):
        return {"ok": False, "error": "Keine Indexer-URL — Schwachstellen-Sync braucht den States-Index (Port 9200)"}
    try:
        res = wz.pull_vulnerabilities(conn)
    except wz.WazuhError as e:
        return {"ok": False, "error": str(e)}

    min_sev = (conn.get("vuln_min_severity") or "medium").lower()
    min_rank = _VULN_SEV_RANK.get(min_sev, 1)

    # Asset-Auto-Link: Map agent_name/agent_id → (asset_id, firmen_id) (#1305-Muster)
    assets = sdb.list_assets(db_path)
    by_name = {a["agent_name"]: a for a in assets if a.get("agent_name")}
    by_id = {a["agent_id"]: a for a in assets if a.get("agent_id")}

    inserted = updated = unchanged = skipped = 0
    seen_uids: list[str] = []
    for v in res["vulns"]:
        if not v.get("cve_id"):
            skipped += 1
            continue
        if _VULN_SEV_RANK.get((v.get("severity") or "low").lower(), 0) < min_rank:
            skipped += 1
            continue
        asset = by_name.get(v.get("agent_name", "")) or by_id.get(v.get("agent_id", ""))
        if asset:
            v["asset_id"] = asset.get("id")
            if asset.get("firmen_id"):
                v["firmen_id"] = asset["firmen_id"]
        seen_uids.append(v["vuln_uid"])
        r = sdb.upsert_vulnerability(db_path, v)
        if r["action"] == "inserted":
            inserted += 1
        elif r["action"] == "updated":
            updated += 1
        else:
            unchanged += 1
    solved = sdb.reconcile_vulnerabilities(db_path, seen_uids)
    return {"ok": True, "received": res["count"], "inserted": inserted, "updated": updated,
            "unchanged": unchanged, "skipped": skipped, "solved": solved,
            "active": len(seen_uids)}
