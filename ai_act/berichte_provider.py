"""AI-Act-Adapter für das geteilte Berichts-Center (Sprint #35, #1384).

Liefert Katalog + Render-Callable; die eigentliche Dokumenterzeugung bleibt im
bestehenden :mod:`ai_act.report_export` (kein Re-Write). AI-Act hat nur einen
sinnvollen Gesamtreport — ein Typ genügt; DOCX-first.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from shared.reports.core import ReportSpec

DB_PATH = Path("data/db/ai_act.sqlite")

CATALOG: list[ReportSpec] = [
    ReportSpec(
        "gesamt", "Gesamtbericht", "EU AI Act (2024/1689)",
        "Vollständiger AI-Act-Bericht inkl. Pflicht-Doku-Nachweise (Art. 11/Annex IV).",
    ),
]


def catalog() -> list[ReportSpec]:
    return CATALOG


def summary_context(projekt: str) -> dict:
    """Kennzahlen-Kontext für die KI-Management-Zusammenfassung (#1393)."""
    from ai_act.db import load_bewertungen
    from ai_act.requirements import berechne_reifegrad
    bew = load_bewertungen(DB_PATH, projekt)
    scores = {rid: int((b or {}).get("bewertung", 0) or 0) for rid, b in bew.items()}
    reif = berechne_reifegrad(scores)
    offene = [{"id": rid, "titel": (b or {}).get("titel", "") or (b or {}).get("frage", ""),
               "bewertung": scores.get(rid, 0)}
              for rid, b in bew.items() if scores.get(rid, 0) < 3][:50]
    return {"reifegrad": reif, "offene": offene}


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, **_ctx: Any) -> bytes:
    """Erzeugt den AI-Act-Bericht für ``projekt`` als DOCX/PDF-Bytes (kein Zeitraum)."""
    from ai_act.report_export import export_docx, export_pdf

    out_dir = Path(tempfile.mkdtemp(prefix="aiact_report_"))
    if fmt == "pdf":
        path = export_pdf(db_path=DB_PATH, projekt_name=projekt, out_dir=out_dir)
    else:
        path = export_docx(db_path=DB_PATH, projekt_name=projekt, out_dir=out_dir)
    return Path(path).read_bytes()
