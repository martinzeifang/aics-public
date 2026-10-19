"""CRA-Adapter für das geteilte Berichts-Center (Sprint #35, #1384).

Liefert Katalog + Render-Callable; die eigentliche Dokumenterzeugung bleibt im
bestehenden :mod:`cra.report_export` (kein Re-Write). Mehrere Berichtstypen werden
auf Options-Kombinationen desselben Generators abgebildet — gleiche Optik wie SOC.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from shared.reports.core import ReportSpec

DB_PATH = Path("data/db/cra.sqlite")

CATALOG: list[ReportSpec] = [
    ReportSpec("gesamt", "Gesamtbericht", "CRA (EU) 2024/2847",
               "Vollständiger CRA-Bericht: Anforderungen, OWASP, Maßnahmenplan, Quellen."),
    ReportSpec("anforderungen", "Anforderungs-Status", "CRA Annex I",
               "Kapitelweise Bewertung der CRA-Anforderungen (ohne OWASP/Maßnahmenplan)."),
    ReportSpec("massnahmen", "Maßnahmenplan", "CRA Art. 13/14",
               "Offene Lücken als Maßnahmenplan (Owner, Zieldatum)."),
]

# Berichtstyp → Options-Flags des bestehenden Generators
_OPTS: dict[str, dict[str, bool]] = {
    "gesamt": dict(incl_massnahmen=True, incl_details=True, incl_owasp=True, incl_referenzen=True),
    "anforderungen": dict(incl_massnahmen=False, incl_details=True, incl_owasp=False, incl_referenzen=True),
    "massnahmen": dict(incl_massnahmen=True, incl_details=False, incl_owasp=False, incl_referenzen=False),
}


def catalog() -> list[ReportSpec]:
    return CATALOG


def summary_context(projekt: str) -> dict:
    """Kennzahlen-Kontext für die KI-Management-Zusammenfassung (#1393)."""
    from cra.db import load_bewertungen
    from cra.requirements import berechne_reifegrad, load_merged_anforderungen
    bew = load_bewertungen(DB_PATH, projekt)
    scores = {rid: int(b.get("bewertung", 0) or 0) for rid, b in bew.items()}
    anf = load_merged_anforderungen(DB_PATH)
    reif = berechne_reifegrad(scores, anforderungen=anf)
    offene = [{"id": a["id"], "titel": a.get("titel", ""), "bewertung": scores.get(a["id"], 0)}
              for a in anf if scores.get(a["id"], 0) < 3][:50]
    return {"reifegrad": reif, "offene": offene}


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, **_ctx: Any) -> bytes:
    """Erzeugt den CRA-Bericht für ``projekt`` als DOCX/PDF-Bytes (kein Zeitraum)."""
    from cra.db import load_bewertungen, load_projekt
    from cra.report_export import export_report_docx, export_report_pdf

    proj = load_projekt(DB_PATH, projekt)
    if not proj:
        raise ValueError("Projekt nicht gefunden")
    opts = _OPTS.get(typ, _OPTS["gesamt"])
    out_dir = Path(tempfile.mkdtemp(prefix="cra_report_"))
    kwargs = dict(
        out_dir=out_dir,
        projekt_name=projekt,
        unternehmen=proj.get("unternehmen", ""),
        produkt=proj.get("produkt", ""),
        produktklasse=proj.get("produktklasse", "default"),
        berater=proj.get("berater", ""),
        bewertungen_raw=load_bewertungen(DB_PATH, projekt),
        db_path=DB_PATH,
        **opts,
    )
    path = export_report_docx(**kwargs) if fmt == "docx" else export_report_pdf(**kwargs)
    return Path(path).read_bytes()
