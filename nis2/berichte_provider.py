"""NIS2-Adapter für das geteilte Berichts-Center (Sprint #35).

Liefert Katalog + Render-Callable; die eigentliche Dokumenterzeugung bleibt im
bestehenden :mod:`nis2.report_export` (kein Re-Write). Mehrere Berichtstypen werden
auf Options-Kombinationen desselben Generators abgebildet — gleiche Optik wie CRA.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from shared.reports.core import ReportSpec

DB_PATH = Path("data/db/nis2.sqlite")

CATALOG: list[ReportSpec] = [
    ReportSpec("gesamt", "Gesamtbericht", "NIS2-Richtlinie (EU) 2022/2555",
               "Vollständiger NIS2-Bericht: Anforderungen (N1–N5), Maßnahmenplan, Quellen."),
    ReportSpec("anforderungen", "Anforderungs-Status", "NIS2 Art. 21",
               "Kapitelweise Bewertung der NIS2-Anforderungen (N1–N5, ohne Maßnahmenplan)."),
    ReportSpec("massnahmen", "Maßnahmenplan", "NIS2 Art. 21/23",
               "Offene Lücken als Maßnahmenplan (Owner, Zieldatum)."),
]

# Berichtstyp → Options-Flags des bestehenden Generators
_OPTS: dict[str, dict[str, bool]] = {
    "gesamt": dict(incl_massnahmen=True, incl_details=True, incl_referenzen=True),
    "anforderungen": dict(incl_massnahmen=False, incl_details=True, incl_referenzen=True),
    "massnahmen": dict(incl_massnahmen=True, incl_details=False, incl_referenzen=False),
}


def catalog() -> list[ReportSpec]:
    return CATALOG


def summary_context(projekt: str) -> dict:
    """Kennzahlen-Kontext für die KI-Management-Zusammenfassung (#1393)."""
    from nis2.db import load_bewertungen
    from nis2.requirements import berechne_reifegrad, load_merged_anforderungen
    bew = load_bewertungen(DB_PATH, projekt)
    anf = load_merged_anforderungen(DB_PATH)
    reif = berechne_reifegrad(bew, anf)
    scores = {rid: int((b or {}).get("bewertung", 0) or 0) for rid, b in bew.items()}
    offene = [{"id": a["id"], "titel": a.get("titel", ""), "bewertung": scores.get(a["id"], 0)}
              for a in anf if scores.get(a["id"], 0) < 3][:50]
    return {"reifegrad": reif, "offene": offene}


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, **_ctx: Any) -> bytes:
    """Erzeugt den NIS2-Bericht für ``projekt`` als DOCX/PDF-Bytes (kein Zeitraum)."""
    from nis2.db import (
        load_bewertungen,
        load_projekt,
        list_assets as db_list_assets,
        list_risiken as db_list_risiken,
        load_incident_response as db_load_ir,
        list_vendors as db_list_vendors,
        load_bcp as db_load_bcp,
    )
    from nis2.report_export import export_report_docx, export_report_pdf

    proj = load_projekt(DB_PATH, projekt)
    if not proj:
        raise ValueError("Projekt nicht gefunden")

    # Pflicht-Doku-Daten — identisch zum bestehenden /report-Endpoint.
    pflicht_doku = {
        "assets": db_list_assets(DB_PATH, projekt),
        "risiken": db_list_risiken(DB_PATH, projekt),
        "incident_response": db_load_ir(DB_PATH, projekt) or {},
        "vendors": db_list_vendors(DB_PATH, projekt),
        "bcp": db_load_bcp(DB_PATH, projekt) or {},
    }
    try:
        from nis2 import governance_db as _gov
        pflicht_doku["governance"] = _gov.list_nachweise(DB_PATH, projekt)
    except Exception:  # noqa: BLE001
        pflicht_doku["governance"] = []

    klassifikator: dict[str, Any] = {}
    try:
        meta = json.loads(proj.get("meta_json") or "{}")
        klassifikator = (meta.get("nis2") or {}).get("klassifikator") or {}
    except Exception:  # noqa: BLE001
        pass

    opts = _OPTS.get(typ, _OPTS["gesamt"])
    out_dir = Path(tempfile.mkdtemp(prefix="nis2_report_"))
    kwargs = dict(
        out_dir=out_dir,
        projekt_name=projekt,
        unternehmen=proj.get("unternehmen", ""),
        einrichtungsklasse=proj.get("einrichtungsklasse", "wesentlich"),
        berater=proj.get("berater", ""),
        bewertungen_raw=load_bewertungen(DB_PATH, projekt),
        pflicht_doku=pflicht_doku,
        klassifikator=klassifikator,
        **opts,
    )
    path = export_report_docx(**kwargs) if fmt == "docx" else export_report_pdf(**kwargs)
    return Path(path).read_bytes()
