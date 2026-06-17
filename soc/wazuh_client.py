"""Generischer Wazuh-Client — funktioniert mit JEDER Wazuh-4.x-Instanz.

Default-Anbindung **PULL** vom Wazuh-Indexer (OpenSearch-REST, `:9200`,
`wazuh-alerts-*`). Inkrementelles Polling via `search_after` auf
``[timestamp, _id]`` (Cursor persistiert). Manager-API (`:55000`) nur für
Kontext (Agentenliste fürs Asset-Inventar), NIE als Alarmquelle.

Nichts ist auf eine konkrete Instanz hartkodiert — alle Werte kommen aus der
Verbindungs-Config (#1261).
"""
from __future__ import annotations

import hashlib
from typing import Any

import requests
import urllib3

from soc.constants import classify_kind, severity_from_level

# self-signed Indexer ist der Normalfall — Warnungen unterdrücken, wenn verify aus
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class WazuhError(RuntimeError):
    pass


def _base(url: str) -> str:
    return url.rstrip("/")


def _group_key(rule_id: str, agent_id: str, srcip: str, ts: str) -> str:
    """Dedup-Schlüssel: rule + Entität + 5-Minuten-Bucket (#1265)."""
    bucket = ts
    try:
        # ts z.B. '2026-06-11T08:43:08.835+0000' → '...T08:40'
        minute = int(ts[14:16])
        bucket = ts[:14] + f"{minute - (minute % 5):02d}"
    except Exception:
        pass
    raw = f"{rule_id}|{agent_id}|{srcip}|{bucket}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def normalize_alert(doc: dict[str, Any]) -> dict[str, Any]:
    """OpenSearch-Hit (`{_id, _source}`) → SOC-Alarm-Dict (siehe soc.db.upsert_alert)."""
    src = doc.get("_source", {}) or {}
    rule = src.get("rule", {}) or {}
    agent = src.get("agent", {}) or {}
    data = src.get("data", {}) or {}
    mitre = rule.get("mitre", {}) or {}
    level = rule.get("level", 0)
    rule_id = str(rule.get("id", ""))
    agent_id = str(agent.get("id", ""))
    srcip = data.get("srcip", "") or src.get("srcip", "") or ""
    ts = src.get("timestamp", "") or ""
    groups = rule.get("groups", []) or []
    return {
        "alert_uid": doc.get("_id", "") or f"{rule_id}:{ts}",
        "rule_id": rule_id,
        "rule_level": int(level) if str(level).isdigit() else 0,
        "severity": severity_from_level(level),
        "description": rule.get("description", ""),
        "groups": groups,
        "kind": classify_kind(groups),
        "mitre": {
            "id": mitre.get("id", []) or [],
            "technique": mitre.get("technique", []) or [],
            "tactic": mitre.get("tactic", []) or [],
        },
        "agent_id": agent_id,
        "agent_name": agent.get("name", ""),
        "srcip": srcip,
        "location": src.get("location", ""),
        "full_log": src.get("full_log", ""),
        "event_ts": ts,
        "raw_json": src,
        "group_key": _group_key(rule_id, agent_id, srcip, ts),
    }


def test_connection(conn: dict[str, Any]) -> dict[str, Any]:
    """Verbindungstest (PULL): Trefferzahl ab min_level der letzten 24 h."""
    if conn.get("modus") == "push":
        return {"ok": True, "modus": "push",
                "hinweis": "Push-Modus: Empfang über /api/soc/ingest — kein aktiver Test nötig."}
    url = _base(conn.get("url", ""))
    if not url:
        return {"ok": False, "error": "Keine Indexer-URL konfiguriert"}
    body = {
        "size": 0,
        "query": {"bool": {"filter": [
            {"range": {"rule.level": {"gte": int(conn.get("min_level", 7))}}},
            {"range": {"timestamp": {"gte": "now-24h", "lte": "now"}}},
        ]}},
    }
    try:
        r = requests.post(
            f"{url}/{conn.get('index_pattern', 'wazuh-alerts-*')}/_search",
            json=body, auth=(conn.get("username", ""), conn.get("secret", "")),
            verify=bool(conn.get("verify_tls", True)), timeout=15)
        if r.status_code == 401:
            return {"ok": False, "error": "Authentifizierung fehlgeschlagen (401) — Benutzer/Passwort prüfen"}
        if r.status_code == 404:
            return {"ok": False, "error": f"Index-Muster '{conn.get('index_pattern')}' nicht gefunden (404)"}
        r.raise_for_status()
        total = (r.json().get("hits", {}).get("total", {}) or {}).get("value", 0)
        return {"ok": True, "modus": "pull", "count_24h": total,
                "hinweis": f"{total} Alarme ab Level {conn.get('min_level', 7)} in den letzten 24 h."}
    except requests.exceptions.SSLError:
        return {"ok": False, "error": "TLS-Fehler (self-signed?) — „TLS prüfen“ deaktivieren."}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": f"Indexer {url} nicht erreichbar (Netz/Port 9200/Firewall)."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def pull_alerts(conn: dict[str, Any], *, after_ts: str = "", after_id: str = "",
                batch: int = 500, max_batches: int = 20) -> dict[str, Any]:
    """Ziehe neue Alarme via search_after-Cursor. Returns {alerts, cursor_ts, cursor_id, count}."""
    url = _base(conn.get("url", ""))
    if not url:
        raise WazuhError("Keine Indexer-URL konfiguriert")
    index = conn.get("index_pattern", "wazuh-alerts-*")
    auth = (conn.get("username", ""), conn.get("secret", ""))
    verify = bool(conn.get("verify_tls", True))
    min_level = int(conn.get("min_level", 7))

    alerts: list[dict[str, Any]] = []
    cursor_ts, cursor_id = after_ts, after_id
    for _ in range(max_batches):
        body: dict[str, Any] = {
            "size": batch,
            "query": {"bool": {"filter": [{"range": {"rule.level": {"gte": min_level}}}]}},
            "sort": [{"timestamp": {"order": "asc"}}, {"_id": {"order": "asc"}}],
        }
        if cursor_ts:
            body["search_after"] = [cursor_ts, cursor_id or ""]
        try:
            r = requests.post(f"{url}/{index}/_search", json=body, auth=auth,
                              verify=verify, timeout=30)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise WazuhError(f"Indexer-Abfrage fehlgeschlagen: {e}") from e
        hits = r.json().get("hits", {}).get("hits", []) or []
        if not hits:
            break
        for h in hits:
            alerts.append(normalize_alert(h))
        last = hits[-1]
        sort_vals = last.get("sort") or []
        cursor_ts = str(sort_vals[0]) if sort_vals else last.get("_source", {}).get("timestamp", cursor_ts)
        cursor_id = str(sort_vals[1]) if len(sort_vals) > 1 else last.get("_id", cursor_id)
        if len(hits) < batch:
            break
    return {"alerts": alerts, "cursor_ts": cursor_ts, "cursor_id": cursor_id, "count": len(alerts)}


def _vuln_uid(agent_id: str, cve_id: str, package_name: str) -> str:
    """Stabiler Dedup-Key: dieselbe CVE kann mehrere Pakete auf demselben Host treffen."""
    raw = f"{agent_id}|{cve_id}|{package_name}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def normalize_vulnerability(doc: dict[str, Any]) -> dict[str, Any]:
    """States-Index-Hit (`{_id, _source}`) → SOC-Vuln-Dict (siehe soc.db.upsert_vulnerability).

    Mappt das ECS-artige Schema des ``wazuh-states-vulnerabilities-*``-Index:
    ``vulnerability.*`` (CVE/Severity/CVSS/Status), ``package.*`` (Paket/Version/
    Fix-Bedingung) und ``agent.*`` (Host). Felder werden defensiv gelesen — Wazuh
    4.8/4.9 variieren leicht in der Verschachtelung (siehe Annahmen im PR).
    """
    from soc.constants import severity_from_vuln, VULN_WAZUH_ACTIVE

    src = doc.get("_source", {}) or {}
    vuln = src.get("vulnerability", {}) or {}
    pkg = src.get("package", {}) or {}
    agent = src.get("agent", {}) or {}

    cve_id = str(vuln.get("id", "") or vuln.get("cve", "") or "")
    # CVSS: bevorzugt v3, sonst v2 — Score/Version/Vector aus dem score-Objekt
    score_obj = vuln.get("score", {}) or {}
    cvss_score = score_obj.get("base")
    cvss_version = str(score_obj.get("version", "") or "")
    if cvss_score is None:
        # Alternative Verschachtelung vulnerability.cvss.cvss3.base_score
        cvss = vuln.get("cvss", {}) or {}
        for ver_key, ver_lbl in (("cvss3", "3"), ("cvss2", "2")):
            block = cvss.get(ver_key, {}) or {}
            if block.get("base_score") is not None:
                cvss_score = block.get("base_score")
                cvss_version = cvss_version or ver_lbl
                break
    try:
        cvss_score = float(cvss_score) if cvss_score is not None else 0.0
    except (TypeError, ValueError):
        cvss_score = 0.0

    severity = severity_from_vuln(vuln.get("severity"), cvss_score)
    agent_id = str(agent.get("id", "") or "")
    agent_name = str(agent.get("name", "") or "")
    package_name = str(pkg.get("name", "") or "")

    # Wazuh-Status: 'under_evaluation' (bool) oder vulnerability.state/category
    status = str(vuln.get("state", "") or "").strip() or VULN_WAZUH_ACTIVE
    # Fix-Information: condition beschreibt z. B. "Package less than X"
    refs = vuln.get("reference") or vuln.get("references") or []
    if isinstance(refs, str):
        refs = [refs]

    return {
        "vuln_uid": _vuln_uid(agent_id, cve_id, package_name),
        "cve_id": cve_id,
        "severity": severity,
        "cvss_score": cvss_score,
        "cvss_version": cvss_version,
        "cvss_vector": str(score_obj.get("vector", "") or ""),
        "package_name": package_name,
        "package_version": str(pkg.get("version", "") or ""),
        "fixed_version": str(pkg.get("fixed_version", "") or vuln.get("fixed_version", "") or ""),
        "condition": str(pkg.get("condition", "") or vuln.get("condition", "") or ""),
        "wazuh_status": status,
        "detection_time": str(vuln.get("detected_at", "") or vuln.get("detection_time", "")
                              or src.get("@timestamp", "") or ""),
        "published_at": str(vuln.get("published_at", "") or vuln.get("published", "") or ""),
        "advisory_url": str((refs[0] if refs else "") or ""),
        "external_refs": list(refs) if isinstance(refs, list) else [],
        "agent_id": agent_id,
        "agent_name": agent_name,
        "source": "wazuh-states",
        "raw_json": src,
    }


def pull_vulnerabilities(conn: dict[str, Any], *, batch: int = 1000,
                         max_batches: int = 50) -> dict[str, Any]:
    """Ziehe den vollständigen Schwachstellen-Ist-Bestand aus dem States-Index (#1343).

    Der States-Index ist ein Snapshot (kein Event-Strom) → wir paginieren mit
    ``search_after`` über ``_id`` durch ALLE Treffer (kein Cursor-/Min-Level-Filter).
    Returns {vulns, count}.
    """
    url = _base(conn.get("url", ""))
    if not url:
        raise WazuhError("Keine Indexer-URL konfiguriert")
    index = conn.get("vuln_index_pattern") or "wazuh-states-vulnerabilities-*"
    auth = (conn.get("username", ""), conn.get("secret", ""))
    verify = bool(conn.get("verify_tls", True))

    vulns: list[dict[str, Any]] = []
    after_id = ""
    for _ in range(max_batches):
        body: dict[str, Any] = {
            "size": batch,
            "query": {"match_all": {}},
            "sort": [{"_id": {"order": "asc"}}],
        }
        if after_id:
            body["search_after"] = [after_id]
        try:
            r = requests.post(f"{url}/{index}/_search", json=body, auth=auth,
                              verify=verify, timeout=60)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise WazuhError(f"States-Index-Abfrage fehlgeschlagen: {e}") from e
        hits = r.json().get("hits", {}).get("hits", []) or []
        if not hits:
            break
        for h in hits:
            vulns.append(normalize_vulnerability(h))
        last = hits[-1]
        sort_vals = last.get("sort") or []
        after_id = str(sort_vals[0]) if sort_vals else last.get("_id", after_id)
        if len(hits) < batch:
            break
    return {"vulns": vulns, "count": len(vulns)}


def run_query(conn: dict[str, Any], query: str, *, limit: int = 50) -> dict[str, Any]:
    """Read-only Ad-hoc-Indexer-Query (Threat-Hunting, #1323).

    ``query`` ist ein Lucene-/query_string-Ausdruck (z. B. ``data.srcip:1.2.3.4 AND
    rule.level:>=10``). Returns {total, hits:[normalisierte Alarme]}.
    """
    url = _base(conn.get("url", ""))
    if not url:
        raise WazuhError("Keine Indexer-URL konfiguriert")
    index = conn.get("index_pattern", "wazuh-alerts-*")
    auth = (conn.get("username", ""), conn.get("secret", ""))
    verify = bool(conn.get("verify_tls", True))
    q = (query or "").strip() or "*"
    body = {
        "size": max(1, min(int(limit), 200)),
        "query": {"query_string": {"query": q}},
        "sort": [{"timestamp": {"order": "desc"}}],
        "track_total_hits": True,
    }
    try:
        r = requests.post(f"{url}/{index}/_search", json=body, auth=auth, verify=verify, timeout=30)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise WazuhError(f"Hunt-Query fehlgeschlagen: {e}") from e
    data = r.json().get("hits", {})
    total = data.get("total", {})
    total_n = total.get("value", 0) if isinstance(total, dict) else int(total or 0)
    hits = [normalize_alert(h) for h in (data.get("hits") or [])]
    return {"total": total_n, "hits": hits}


def _with_port(base: str, port: int) -> str:
    """Ersetzt/ergänzt den Port in einer Basis-URL."""
    import re
    m = re.match(r"^(https?://[^/:]+)(?::\d+)?(.*)$", base)
    if not m:
        return base
    return f"{m.group(1)}:{port}{m.group(2)}"


def _fetch_agents_once(base: str, username: str, password: str, *, verify_tls: bool,
                       timeout: int) -> list[dict[str, Any]]:
    # ?raw=true liefert den Token als Plaintext und umgeht die schwere RBAC-Berechnung
    # des JSON-Pfades, die beim ersten (kalten) Aufruf in einen Timeout/500 läuft.
    auth = requests.post(f"{base}/security/user/authenticate", params={"raw": "true"},
                         auth=(username, password), verify=verify_tls, timeout=timeout)
    auth.raise_for_status()
    token = auth.text.strip()
    r = requests.get(f"{base}/agents", headers={"Authorization": f"Bearer {token}"},
                     params={"limit": 500}, verify=verify_tls, timeout=timeout)
    r.raise_for_status()
    items = r.json().get("data", {}).get("affected_items", []) or []
    out = []
    for a in items:
        osd = a.get("os", {}) or {}
        os_str = " ".join(x for x in (osd.get("name", ""), str(osd.get("version", ""))) if x).strip()
        out.append({
            "agent_id": a.get("id", ""), "agent_name": a.get("name", ""),
            "ip": a.get("ip", ""), "hostname": osd.get("hostname", ""),
            "agent_status": a.get("status", ""), "last_keepalive": a.get("lastKeepAlive", ""),
            "os": os_str, "agent_version": a.get("version", ""), "source": "agent",
        })
    return out


def fetch_agents(manager_url: str, username: str, password: str, *, verify_tls: bool = True,
                 timeout: int = 15) -> list[dict[str, Any]]:
    """Agentenliste über die Manager-API. Probiert den angegebenen Port und — bei
    Verbindungsfehler — automatisch den Standard-Port **55000** (häufiger Tippfehler).
    Ein 401 wird klar als Authentifizierungsfehler gemeldet (nicht als „nicht erreichbar")."""
    if not password:
        raise WazuhError("Kein API-Passwort angegeben — bitte im Formular erneut eingeben "
                         "(das Feld wird beim Öffnen aus Sicherheitsgründen geleert).")
    base = _base(manager_url)
    attempts = [base]
    fb = _with_port(base, 55000)
    if fb != base:
        attempts.append(fb)
    last_conn_err: Exception | None = None
    for b in attempts:
        try:
            return _fetch_agents_once(b, username, password, verify_tls=verify_tls, timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            last_conn_err = e
            continue  # nächsten Port versuchen
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response is not None else None
            if code == 401:
                raise WazuhError("Authentifizierung fehlgeschlagen (401) — Benutzer/Passwort "
                                 "der Wazuh-Manager-API prüfen (Feld nach dem Öffnen erneut "
                                 "eingeben).") from e
            raise WazuhError(f"Manager-API-Fehler ({b}): HTTP {code}") from e
        except requests.exceptions.RequestException as e:
            raise WazuhError(f"Manager-API-Fehler ({b}): {e}") from e
    raise WazuhError(f"Manager-API nicht erreichbar ({base} bzw. Port 55000). "
                     f"Bitte Erreichbarkeit prüfen. Details: {last_conn_err}")
