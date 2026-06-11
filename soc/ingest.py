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
    new = suppressed = skipped = 0
    for a in alerts:
        # Suppression?
        if any(_matches_suppression(a, s) for s in suppressions):
            a["status"] = "suppressed"
            suppressed += 1
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
