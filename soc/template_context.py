"""SOC-Adapter für die zentrale Word-Vorlagen-Engine (#1277).

Stellt ``build_soc_context`` + ``SOC_VARIABLES`` bereit, die ``shared.templates.schema``
über *guarded imports* einbindet. SOC ist nicht projekt-gebunden — der ``projekt``-
Parameter dient optional als Firmen-/Label-Filter; ausgegeben wird eine Lage-Übersicht
(KPIs + offene Incidents).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# Aufbau wie bei allen anderen Adaptern: {"key", "typ", "beschreibung", "pflicht"}
# (#1731). Vorher standen hier "token"/"name" mit Klammer-Platzhaltern wie
# "[soc.alerts_total]" — das ist die Schreibweise der Gutachten-Vorlagen, nicht
# die dieser Engine (docxtpl/Jinja, also "{{ soc.alerts_total }}"). Das Admin-UI
# liest "key"/"typ" und zeigte für SOC daher leere Spalten.
SOC_VARIABLES: list[dict[str, Any]] = [
    {"key": "soc.alerts_total", "typ": "zahl",
     "beschreibung": "Alarme gesamt", "pflicht": False},
    {"key": "soc.alerts_new", "typ": "zahl",
     "beschreibung": "Neue (untriagierte) Alarme", "pflicht": False},
    {"key": "soc.alerts_vulnerability", "typ": "zahl",
     "beschreibung": "Schwachstellen-Alarme", "pflicht": False},
    {"key": "soc.fp_rate", "typ": "zahl",
     "beschreibung": "False-Positive-Rate (0–1)", "pflicht": False},
    {"key": "soc.incidents_open", "typ": "zahl",
     "beschreibung": "Offene Incidents", "pflicht": False},
    {"key": "soc.incidents", "typ": "liste",
     "beschreibung": "Liste der Incidents (id, titel, status, severity)",
     "pflicht": False},
    {"key": "soc.mtta_hours", "typ": "zahl",
     "beschreibung": "Mittlere Reaktionszeit in Stunden (#1325)", "pflicht": False},
    {"key": "soc.mttr_hours", "typ": "zahl",
     "beschreibung": "Mittlere Behebungszeit in Stunden (#1325)", "pflicht": False},
    {"key": "soc.sla_compliance", "typ": "zahl",
     "beschreibung": "SLA-Einhaltung 0–1 (#1325)", "pflicht": False},
    {"key": "projekt", "typ": "text",
     "beschreibung": "Optionaler Firmen-/Label-Filter; SOC ist nicht "
                     "projekt-gebunden", "pflicht": False},
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
            # Vorgabe 0.0 statt None: Jinja druckt None wörtlich ins Dokument,
            # und ohne SLA-Daten stand dann "None" im Kundenbericht (#1731).
            "mtta_hours": sla.get("mtta_hours") or 0.0,
            "mttr_hours": sla.get("mttr_hours") or 0.0,
            "sla_compliance": sla.get("sla_compliance") or 0.0,
        },
        "projekt": projekt or "",
    }
