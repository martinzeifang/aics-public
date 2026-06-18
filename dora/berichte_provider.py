"""DORA-Adapter für das geteilte Berichts-Center (Sprint #35, #1384).

Liefert Katalog + Render-Callable; die eigentliche Dokumenterzeugung bleibt im
bestehenden :mod:`dora.report_export` (kein Re-Write). Der DORA-Generator kennt
keine Options-Flags → nur ein Berichtstyp "gesamt". DORA ist nicht
zeitraum-basiert.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from shared.reports.core import ReportSpec

DB_PATH = Path("data/db/dora.sqlite")

CATALOG: list[ReportSpec] = [
    ReportSpec("gesamt", "Gesamtbericht", "DORA (EU) 2022/2554",
               "Vollständiger DORA-Bericht: Reifegrad, Anforderungen (5 Pfeiler), "
               "Drittanbieter-Register (TPP) und Testing-Plan."),
]


def catalog() -> list[ReportSpec]:
    return CATALOG


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, **_ctx: Any) -> bytes:
    """Erzeugt den DORA-Bericht für ``projekt`` als DOCX/PDF-Bytes (kein Zeitraum)."""
    from dora.db import load_projekt
    from dora.report_export import export_report_docx, export_report_pdf

    if not load_projekt(DB_PATH, projekt):
        raise ValueError("Projekt nicht gefunden")
    out_dir = Path(tempfile.mkdtemp(prefix="dora_report_"))
    kwargs = dict(db_path=DB_PATH, projekt_name=projekt, out_dir=out_dir)
    path = export_report_docx(**kwargs) if fmt == "docx" else export_report_pdf(**kwargs)
    return Path(path).read_bytes()
