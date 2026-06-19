"""Risikobewertungs-Adapter für das geteilte Berichts-Center (Sprint #35).

Liefert Katalog + Render-Callable; die eigentliche Dokumenterzeugung bleibt im
bestehenden :mod:`risikobewertung.report_export` (kein Re-Write). Die zwei
Berichtstypen bilden auf das ``include_recommendations``-Flag desselben
Generators ab — gleiche Optik wie CRA/SOC. Nicht zeitraum-basiert.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from shared.reports.core import ReportSpec

DB_PATH = Path("data/db/risikobewertung.sqlite")

CATALOG: list[ReportSpec] = [
    ReportSpec("gesamt", "Gesamtbericht", "Risikobewertung",
               "Risiken, Heatmap, Maßnahmen-Empfehlungen."),
    ReportSpec("ohne_empfehlungen", "Risiko-Register", "Risikobewertung",
               "Risiken ohne Maßnahmen-Empfehlungen."),
]


def catalog() -> list[ReportSpec]:
    return CATALOG


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, **_ctx: Any) -> bytes:
    """Erzeugt den Risikobewertungs-Bericht für ``projekt`` als DOCX/PDF-Bytes."""
    from risikobewertung.db import load_projekt, load_risiken
    from risikobewertung.report_export import export_report_docx, export_report_pdf

    proj = load_projekt(DB_PATH, projekt)
    if not proj:
        raise ValueError("Projekt nicht gefunden")

    risiken = load_risiken(DB_PATH, projekt)
    framework = proj.get("framework", "STRIDE")
    scope_label = proj.get("beschreibung") or framework
    out_dir = Path(tempfile.mkdtemp(prefix="rb_report_"))

    kwargs = dict(
        out_dir=out_dir,
        projekt_name=projekt,
        projekt_beschreibung=proj.get("beschreibung", ""),
        framework=framework,
        scope_label=scope_label,
        risks=risiken,
        include_recommendations=(typ != "ohne_empfehlungen"),
    )
    path = export_report_docx(**kwargs) if fmt == "docx" else export_report_pdf(**kwargs)
    return Path(path).read_bytes()
