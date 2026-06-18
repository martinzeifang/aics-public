"""CRA PSIRT-SLA-Tracking gegen offene CVEs (#1207, Annex I Teil II).

Berechnet pro offenem ``cra_vuln`` aus ``discovered_at`` + schwere-passender
PSIRT-Fix-SLA ein Soll-Fix-Datum + Status on_track/faellig/ueberfaellig. Nutzt
die zentrale ``shared/deadlines``-Engine (Duration-Parser + SLA-Status).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import cra.deadlines as dl
from cra.db import list_vuln, load_psirt

# Schwere → PSIRT-SLA-Feld.
_SEVERITY_SLA_FIELD = {
    "critical": "fix_sla_critical",
    "high": "fix_sla_high",
    "medium": "fix_sla_medium",
}
# Offene (= noch zu fixende) Status.
_OPEN_STATUS = {"open", "triaging"}


def compute_sla_status(db_path: Path, projekt_name: str,
                       *, now=None) -> dict[str, Any]:
    """SLA-Status pro offenem CVE aggregieren.

    Returns ``{"psirt_set":bool,"items":[…],"violations":int,"due_soon":int}``.
    Jedes Item: CVE-Felder + ``sla_text``/``due_at``/``hours_left``/``status``.
    """
    psirt = load_psirt(db_path, projekt_name) or {}
    psirt_set = bool(psirt)
    vulns = list_vuln(db_path, projekt_name)
    items: list[dict[str, Any]] = []
    violations = 0
    due_soon = 0
    for v in vulns:
        if v.get("status") not in _OPEN_STATUS:
            continue
        sev = (v.get("schwere") or "unknown").lower()
        sla_field = _SEVERITY_SLA_FIELD.get(sev)
        sla_text = psirt.get(sla_field, "") if sla_field else ""
        base = v.get("discovered_at") or v.get("created_at") or ""
        if sla_text and base:
            res = dl.sla_status(base, sla_text, now=now)
        else:
            res = {"due_at": None, "hours_left": None, "status": "unbekannt",
                   "sla_hours": None}
        if res["status"] == "ueberfaellig":
            violations += 1
        elif res["status"] == "faellig":
            due_soon += 1
        items.append({
            "id": v.get("id"),
            "cve_id": v.get("cve_id"),
            "titel": v.get("titel"),
            "schwere": sev,
            "discovered_at": base,
            "sla_text": sla_text,
            "due_at": res["due_at"],
            "hours_left": res["hours_left"],
            "status": res["status"],
        })
    # Verletzungen + bald-fällige zuerst.
    _rank = {"ueberfaellig": 0, "faellig": 1, "on_track": 2, "unbekannt": 3}
    items.sort(key=lambda i: (_rank.get(i["status"], 9),
                              i["hours_left"] if i["hours_left"] is not None else 1e9))
    return {
        "psirt_set": psirt_set,
        "items": items,
        "violations": violations,
        "due_soon": due_soon,
        "total_open": len(items),
    }
