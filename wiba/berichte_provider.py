"""WiBA-Adapter für das geteilte Berichts-Center (Sprint #35).

Liefert Katalog + Render-Callable; die eigentliche Dokumenterzeugung bleibt im
bestehenden :mod:`wiba.report_export` (kein Re-Write). Der WiBA-Generator kennt
keine Options-Flags (offene Punkte sind ohnehin Teil des Nachweis-Berichts),
daher gibt es genau einen Berichtstyp ``gesamt``.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from shared.reports.core import ReportSpec

DB_PATH = Path("data/db/wiba.sqlite")

CATALOG: list[ReportSpec] = [
    ReportSpec("gesamt", "Nachweis-Gesamtbericht", "BSI WiBA",
               "Vollständiger WiBA-Nachweis: Prüffragen je Thema, Reifegrad, offene Punkte."),
]


def catalog() -> list[ReportSpec]:
    return CATALOG


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, **_ctx: Any) -> bytes:
    """Erzeugt den WiBA-Nachweis für ``projekt`` als DOCX/PDF-Bytes (kein Zeitraum)."""
    from wiba.report_export import export_report_docx, export_report_pdf

    out_dir = Path(tempfile.mkdtemp(prefix="wiba_report_"))
    if fmt == "docx":
        path = export_report_docx(out_dir=out_dir, projekt_name=projekt, db_path=DB_PATH)
    else:
        path = export_report_pdf(out_dir=out_dir, projekt_name=projekt, db_path=DB_PATH)
    return Path(path).read_bytes()
