"""Agentlose Syslog-Quellen read-only erkennen (#1347 · Sprint #33 A).

Viele Geräte (Firewalls, IoT, Appliances) liefern Logs nicht über einen Wazuh-
Agenten, sondern per **Syslog an den Wazuh-Manager** (Agent ``000``). Solche
Quellen tauchen in der Manager-Agentenliste nicht auf und fehlen daher im
Asset-Inventar.

Dieses Modul fragt den Wazuh-**Indexer** (PULL-Verbindung) read-only per
``size:0``-Aggregation ab und schlägt die erkannten Quellen als SOC-Asset
(``source='syslog'``) vor. **Kein Ingest, kein Sync, keine Schreibzugriffe auf
Wazuh.** Norm: BSI DER.1 · OPS.1.1.5 · SOC-CMM Services.

Annahmen zu den Indexer-Feldnamen (Wazuh ``wazuh-alerts-*``):
  - ``agent.id``            : ``"000"`` = Manager-/Syslog-Quellen (keine Agenten)
  - ``predecoder.hostname`` : vom Syslog-Decoder extrahierter Hostname der Quelle
  - ``location``            : Herkunft (bei Remote-Syslog häufig die Absender-IP)
  - ``data.srcip``          : alternative Absender-IP (regelabhängig)
Bewiesen an Realdaten: ``predecoder.hostname='homeassistant'``,
``location='192.168.40.180'`` (siehe Issue).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from soc import db as sdb


def _base(url: str) -> str:
    return url.rstrip("/")


def _existing_keys(db_path: Path) -> set[str]:
    """Schlüssel bereits angelegter Assets (agent_name / hostname / ip), klein­geschrieben."""
    keys: set[str] = set()
    for a in sdb.list_assets(db_path):
        for f in ("agent_name", "hostname", "ip"):
            v = (a.get(f) or "").strip().lower()
            if v:
                keys.add(v)
    return keys


# Aggregations-Query (read-only, size:0). agent.id 000 = Manager/Syslog-Quellen.
def _build_agg_body(hours: int) -> dict[str, Any]:
    return {
        "size": 0,
        "query": {"bool": {"filter": [
            {"term": {"agent.id": "000"}},
            {"range": {"timestamp": {"gte": f"now-{int(hours)}h", "lte": "now"}}},
        ]}},
        "aggs": {
            # Primär gruppiert nach Hostname; je Bucket Top-Absender-IP, Programm,
            # Trefferzahl + last_seen.
            "by_host": {
                "terms": {"field": "predecoder.hostname", "size": 500,
                          "missing": "(ohne Hostname)"},
                "aggs": {
                    "ip": {"terms": {"field": "location", "size": 1}},
                    "srcip": {"terms": {"field": "data.srcip", "size": 1}},
                    "program": {"terms": {"field": "predecoder.program_name", "size": 1}},
                    "last_seen": {"max": {"field": "timestamp"}},
                },
            },
            # Fallback: Quellen ganz ohne predecoder.hostname rein nach Absender-IP,
            # damit hostname-lose Geräte nicht verloren gehen.
            "by_ip": {
                "terms": {"field": "location", "size": 500},
                "aggs": {
                    "program": {"terms": {"field": "predecoder.program_name", "size": 1}},
                    "last_seen": {"max": {"field": "timestamp"}},
                },
            },
        },
    }


def _first_bucket_key(agg: dict[str, Any]) -> str:
    buckets = (agg or {}).get("buckets") or []
    return str(buckets[0]["key"]) if buckets else ""


def discover_syslog_sources(db_path: Path, *, hours: int = 2,
                            connection_name: str = "default") -> dict[str, Any]:
    """Read-only Syslog-Quellen-Discovery über die PULL-Indexer-Verbindung.

    Liefert ``{ok, sources:[{hostname, ip, program, count, last_seen}], hours,
    total}`` — bereits als Asset vorhandene Quellen sind herausgefiltert. **Kein
    Schreibzugriff.**
    """
    hours = max(1, min(int(hours or 2), 168))
    conn = sdb.load_connection(db_path, connection_name, with_secret=True)
    if not conn:
        return {"ok": False, "error": "Keine Wazuh-Verbindung konfiguriert.", "sources": []}
    if conn.get("modus") == "push":
        return {"ok": False, "sources": [],
                "error": "Discovery braucht eine PULL-Indexer-Verbindung (Push-Modus kann den "
                         "Indexer nicht abfragen)."}
    url = _base(conn.get("url", ""))
    if not url:
        return {"ok": False, "error": "Keine Indexer-URL konfiguriert.", "sources": []}
    index = conn.get("index_pattern", "wazuh-alerts-*")
    auth = (conn.get("username", ""), conn.get("secret", ""))
    verify = bool(conn.get("verify_tls", True))

    try:
        r = requests.post(f"{url}/{index}/_search", json=_build_agg_body(hours),
                          auth=auth, verify=verify, timeout=30)
        if r.status_code == 401:
            return {"ok": False, "sources": [],
                    "error": "Authentifizierung fehlgeschlagen (401) — Indexer-Benutzer prüfen."}
        if r.status_code == 404:
            return {"ok": False, "sources": [],
                    "error": f"Index-Muster '{index}' nicht gefunden (404)."}
        r.raise_for_status()
    except requests.exceptions.SSLError:
        return {"ok": False, "sources": [],
                "error": "TLS-Fehler (self-signed?) — TLS-Prüfung deaktivieren."}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "sources": [],
                "error": f"Indexer {url} nicht erreichbar (Netz/Port 9200/Firewall)."}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "sources": [], "error": f"Indexer-Abfrage fehlgeschlagen: {e}"}

    aggs = r.json().get("aggregations", {}) or {}
    existing = _existing_keys(db_path)
    by_key: dict[str, dict[str, Any]] = {}

    for b in (aggs.get("by_host", {}) or {}).get("buckets", []) or []:
        hostname = str(b.get("key", "") or "")
        if hostname == "(ohne Hostname)":
            hostname = ""
        ip = _first_bucket_key(b.get("ip", {})) or _first_bucket_key(b.get("srcip", {}))
        program = _first_bucket_key(b.get("program", {}))
        last_seen = str(((b.get("last_seen", {}) or {}).get("value_as_string", "")) or "")
        # Eindeutiger Schlüssel: Hostname bevorzugt, sonst IP (robust gegen fehlende Hostnames)
        key = (hostname or ip).strip().lower()
        if not key:
            continue
        by_key[key] = {
            "hostname": hostname, "ip": ip, "program": program,
            "count": int(b.get("doc_count", 0)), "last_seen": last_seen,
        }

    # IP-only-Quellen ergänzen (kein predecoder.hostname) — nicht überschreiben.
    for b in (aggs.get("by_ip", {}) or {}).get("buckets", []) or []:
        ip = str(b.get("key", "") or "")
        key = ip.strip().lower()
        if not key or key in by_key:
            continue
        by_key[key] = {
            "hostname": "", "ip": ip,
            "program": _first_bucket_key(b.get("program", {})),
            "count": int(b.get("doc_count", 0)),
            "last_seen": str(((b.get("last_seen", {}) or {}).get("value_as_string", "")) or ""),
        }

    # Bereits als Asset vorhandene Quellen herausfiltern (keine Doppelanlage).
    sources = []
    for key, s in by_key.items():
        host_k = (s["hostname"] or "").strip().lower()
        ip_k = (s["ip"] or "").strip().lower()
        if (host_k and host_k in existing) or (ip_k and ip_k in existing):
            continue
        sources.append(s)
    sources.sort(key=lambda s: s["count"], reverse=True)
    return {"ok": True, "hours": hours, "total": len(sources), "sources": sources}


def create_assets_from_syslog(db_path: Path, sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Bulk-Anlage selektierter Syslog-Quellen als Asset (``source='syslog'``).

    Idempotent: bereits vorhandene Quellen (per Hostname/IP) werden übersprungen.
    Returns ``{created, skipped, ids}``.
    """
    existing = _existing_keys(db_path)
    created, skipped = 0, 0
    ids: list[int] = []
    for s in (sources or []):
        hostname = str((s.get("hostname") or "")).strip()
        ip = str((s.get("ip") or "")).strip()
        if not hostname and not ip:
            skipped += 1
            continue
        if (hostname.lower() in existing) or (ip.lower() in existing):
            skipped += 1
            continue
        name = hostname or ip  # robust gegen fehlende Hostnames
        program = str((s.get("program") or "")).strip()
        aid = sdb.upsert_asset(db_path, {
            "agent_name": name,
            "hostname": hostname,
            "ip": ip,
            "source": "syslog",
            "meta": {"syslog_program": program} if program else {},
        })
        ids.append(aid)
        created += 1
        if hostname:
            existing.add(hostname.lower())
        if ip:
            existing.add(ip.lower())
    return {"created": created, "skipped": skipped, "ids": ids}
