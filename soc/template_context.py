"""SOC-Adapter für die zentrale Word-Vorlagen-Engine (#1277).

Stellt ``build_soc_context`` + ``SOC_VARIABLES`` bereit, die ``shared.templates.schema``
über *guarded imports* einbindet. SOC ist nicht projekt-gebunden — der ``projekt``-
Parameter dient optional als Firmen-/Label-Filter; ausgegeben wird eine Lage-Übersicht
(KPIs + offene Incidents).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

SOC_VARIABLES: list[dict[str, Any]] = [
    {"token": "[soc.alerts_total]", "name": "soc.alerts_total", "beschreibung": "Alarme gesamt"},
    {"token": "[soc.alerts_new]", "name": "soc.alerts_new", "beschreibung": "Neue (untriagierte) Alarme"},
    {"token": "[soc.alerts_vulnerability]", "name": "soc.alerts_vulnerability", "beschreibung": "Schwachstellen-Alarme"},
    {"token": "[soc.fp_rate]", "name": "soc.fp_rate", "beschreibung": "False-Positive-Rate (0–1)"},
    {"token": "[soc.incidents_open]", "name": "soc.incidents_open", "beschreibung": "Offene Incidents"},
    {"token": "[soc.incidents]", "name": "soc.incidents", "beschreibung": "Liste der Incidents (id, titel, status, severity)"},
    {"token": "[soc.mtta_hours]", "name": "soc.mtta_hours", "beschreibung": "Mittlere Reaktionszeit (h) (#1325)"},
    {"token": "[soc.mttr_hours]", "name": "soc.mttr_hours", "beschreibung": "Mittlere Behebungszeit (h) (#1325)"},
    {"token": "[soc.sla_compliance]", "name": "soc.sla_compliance", "beschreibung": "SLA-Einhaltung 0–1 (#1325)"},
]


def build_soc_context(db_path: Path | str, projekt: str | None = None) -> dict[str, Any]:
    from soc import db as sdb
    p = Path(db_path) if db_path else Path("data/db/soc.sqlite")
    try:
        k = sdb.kpis(p)
    except Exception:
        k = {}
    incidents = []
    try:
        for i in sdb.list_incidents(p, include_closed=True, limit=200):
            incidents.append({"id": i.get("id"), "titel": i.get("titel", ""),
                              "status": i.get("status", ""), "severity": i.get("severity", "")})
    except Exception:
        pass
    try:
        sla = sdb.sla_kpis(p)
    except Exception:
        sla = {}
    return {
        "soc": {
            "alerts_total": k.get("alerts_total", 0),
            "alerts_new": k.get("alerts_new", 0),
            "alerts_vulnerability": k.get("alerts_vulnerability", 0),
            "fp_rate": k.get("fp_rate", 0.0),
            "incidents_open": k.get("incidents_open", 0),
            "incidents": incidents,
            "mtta_hours": sla.get("mtta_hours"),
            "mttr_hours": sla.get("mttr_hours"),
            "sla_compliance": sla.get("sla_compliance"),
        },
        "projekt": projekt or "",
    }
