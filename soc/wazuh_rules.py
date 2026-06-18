"""Wazuh-Manager-API — read-only Abruf des installierten Regelwerks (#1348).

Liest das **komplette installierte Regelwerk** über die Manager-API
(``GET /rules``, paginiert über ``limit``/``offset``) und mappt jede Regel auf
ein schlankes Dict ``{id, level, description, groups[], mitre[], filename,
status}``. Reiner Lese-Zugriff (kein Schreibpfad).

**Authentifizierung** identisch zu :func:`soc.wazuh_client.fetch_agents`:
``POST /security/user/authenticate?raw=true`` (Basic-Auth) liefert ein JWT als
Plaintext; alle folgenden Aufrufe nutzen ``Authorization: Bearer <token>``.

**Voraussetzung (RBAC):** Der Manager-API-Benutzer braucht die Berechtigung
``rules:read`` (z. B. eine ``soc-reader``-Rolle, die ``rules:read`` + ``agent:read``
gewährt). Fehlt sie, antwortet die API mit HTTP 403 — der Fehlertext weist
darauf hin.

Die Manager-API (Port **55000**) ist hier — anders als der Indexer (9200) — die
korrekte Quelle: nur sie kennt das geladene Regelwerk. Port-Fallback auf 55000
wie beim Agenten-Abruf (häufiger Tippfehler in der URL).
"""
from __future__ import annotations

from typing import Any

import requests
import urllib3

from soc.wazuh_client import WazuhError, _base, _with_port

# self-signed Manager-API ist der Normalfall — Warnungen unterdrücken, wenn verify aus
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def normalize_rule(item: dict[str, Any]) -> dict[str, Any]:
    """Manager-API-``/rules``-Eintrag → schlankes Regel-Dict.

    Robust gegen fehlende/variierende Felder über Wazuh-4.x-Versionen.
    ATT&CK steht je nach Version unter ``mitre`` (Liste/Objekt) oder
    ``details.mitre`` — beide Formen werden auf eine flache Technik-ID-Liste
    reduziert.
    """
    rid = item.get("id")
    try:
        rid = int(rid)
    except (TypeError, ValueError):
        rid = 0
    level = item.get("level", 0)
    try:
        level = int(level)
    except (TypeError, ValueError):
        level = 0

    groups = item.get("groups") or []
    if isinstance(groups, str):
        groups = [groups]
    groups = [str(g) for g in groups if g]

    mitre = _extract_mitre(item)

    filename = str(item.get("filename") or item.get("file") or "")
    status = str(item.get("status") or "")
    description = str(item.get("description") or "")
    return {
        "id": rid,
        "level": level,
        "description": description,
        "groups": groups,
        "mitre": mitre,
        "filename": filename,
        "status": status,
    }


def _extract_mitre(item: dict[str, Any]) -> list[str]:
    """Flache Liste von ATT&CK-Technik-IDs aus den variierenden Wazuh-Formen."""
    raw = item.get("mitre")
    if raw is None:
        details = item.get("details") or {}
        raw = details.get("mitre")
    out: list[str] = []
    if isinstance(raw, dict):
        # {"id": ["T1059"], "technique": [...], "tactic": [...]}
        ids = raw.get("id") or []
        if isinstance(ids, str):
            ids = [ids]
        out = [str(x) for x in ids if x]
    elif isinstance(raw, list):
        for el in raw:
            if isinstance(el, str):
                out.append(el)
            elif isinstance(el, dict):
                val = el.get("id") or el.get("technique") or ""
                if val:
                    out.append(str(val))
    elif isinstance(raw, str) and raw:
        out = [raw]
    # Duplikate entfernen, Reihenfolge erhalten
    seen: set[str] = set()
    uniq: list[str] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def _authenticate(base: str, username: str, password: str, *, verify_tls: bool,
                  timeout: int) -> str:
    # ?raw=true liefert den Token als Plaintext und umgeht die schwere RBAC-Berechnung
    # des JSON-Pfades, die beim ersten (kalten) Aufruf in einen Timeout/500 läuft.
    auth = requests.post(f"{base}/security/user/authenticate", params={"raw": "true"},
                         auth=(username, password), verify=verify_tls, timeout=timeout)
    auth.raise_for_status()
    return auth.text.strip()


def _fetch_rules_once(base: str, username: str, password: str, *, verify_tls: bool,
                      timeout: int, page_size: int) -> list[dict[str, Any]]:
    """Holt ALLE Regeln über ``/rules`` mit ``limit``/``offset``-Paginierung."""
    token = _authenticate(base, username, password, verify_tls=verify_tls, timeout=timeout)
    headers = {"Authorization": f"Bearer {token}"}
    rules: list[dict[str, Any]] = []
    offset = 0
    # Harte Obergrenze gegen Endlosschleife (Wazuh liefert ~5–10k Default-Regeln)
    for _ in range(2000):
        r = requests.get(f"{base}/rules", headers=headers,
                         params={"limit": page_size, "offset": offset},
                         verify=verify_tls, timeout=timeout)
        if r.status_code == 403:
            raise WazuhError(
                "Manager-API-Benutzer fehlt die Berechtigung 'rules:read' (HTTP 403). "
                "Bitte dem API-Benutzer eine Rolle mit 'rules:read' zuweisen "
                "(z. B. soc-reader).")
        r.raise_for_status()
        data = r.json().get("data", {}) or {}
        items = data.get("affected_items", []) or []
        for it in items:
            rules.append(normalize_rule(it))
        total = data.get("total_affected_items")
        offset += len(items)
        if not items:
            break
        if isinstance(total, int) and offset >= total:
            break
        if len(items) < page_size:
            break
    return rules


def fetch_rules(manager_url: str, username: str, password: str, *, verify_tls: bool = True,
                timeout: int = 30, page_size: int = 500) -> list[dict[str, Any]]:
    """Komplettes installiertes Regelwerk über die Manager-API (read-only).

    Probiert den angegebenen Port und — bei Verbindungsfehler — automatisch den
    Standard-Port **55000**. 401 → klarer Auth-Fehler, 403 → fehlende
    ``rules:read``-Berechtigung.
    """
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
            return _fetch_rules_once(b, username, password, verify_tls=verify_tls,
                                     timeout=timeout, page_size=page_size)
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
