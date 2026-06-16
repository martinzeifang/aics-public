"""DSGVO-Adapter für das geteilte Berichts-Center (Sprint #35, #1387).

Liefert Katalog + Render-Callable; die eigentliche Dokumenterzeugung bleibt in
:mod:`dsgvo.report_export` (Gesamt-Compliance-Bericht) bzw.
:mod:`dsgvo.einzelberichte` (8 DSMS-Bereichsberichte) — kein Re-Write. Ein
einheitliches Berichts-Center deckt damit den Gesamtbericht **und** alle
Bereichsberichte als Berichtstypen ab. (Der Jahresbericht mit Sign-off bleibt ein
eigener Tab und wird hier bewusst NICHT abgebildet.)
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from shared.reports.core import ReportSpec
from dsgvo.einzelberichte import AREA_REPORTS

DB_PATH = Path("data/db/dsgvo.sqlite")

CATALOG: list[ReportSpec] = [
    ReportSpec(
        "gesamt", "DSMS-Gesamtbericht", "Verordnung (EU) 2016/679",
        "Vollständiger DSGVO-Compliance-Bericht: Reifegrad, Anforderungen, "
        "Pflicht-Doku und DSMS-Bereiche.",
    ),
] + [
    ReportSpec(area, cfg["titel"], cfg.get("norm", ""),
               f"Bereichsbericht: {cfg['titel']} ({cfg.get('norm', '')}).")
    for area, cfg in AREA_REPORTS.items()
]


def catalog() -> list[ReportSpec]:
    return CATALOG


def summary_context(projekt: str) -> dict:
    """Kennzahlen-Kontext für die KI-Management-Zusammenfassung (#1393)."""
    from dsgvo.db import load_bewertungen
    from dsgvo.requirements import berechne_reifegrad, load_merged_anforderungen
    bew = load_bewertungen(DB_PATH, projekt)
    scores = {rid: int((b or {}).get("bewertung", 0) or 0) for rid, b in bew.items()}
    reif = berechne_reifegrad(scores)
    anf = load_merged_anforderungen(DB_PATH)
    offene = [{"id": a["id"], "titel": a.get("titel", ""), "bewertung": scores.get(a["id"], 0)}
              for a in anf if scores.get(a["id"], 0) < 3][:50]
    return {"reifegrad": reif, "offene": offene}


def _render_gesamt(fmt: str, projekt: str) -> bytes:
    """Gesamt-Compliance-Bericht — kwargs wie der bestehende /report-Endpoint."""
    from dsgvo.db import (
        load_projekt, load_bewertungen,
        list_vvt, list_tom, list_dpia, list_avv, list_pannen,
    )
    from dsgvo.report_export import export_report_docx, export_report_pdf

    projekt_obj = load_projekt(DB_PATH, projekt)
    if not projekt_obj:
        raise ValueError("Projekt nicht gefunden")

    out_dir = Path(tempfile.mkdtemp(prefix="dsgvo_report_"))
    bewertungen = load_bewertungen(DB_PATH, projekt)
    pflicht_doku = {
        "vvt": list_vvt(DB_PATH, projekt),
        "tom": list_tom(DB_PATH, projekt),
        "dpia": list_dpia(DB_PATH, projekt),
        "avv": list_avv(DB_PATH, projekt),
        "datenpannen": list_pannen(DB_PATH, projekt),
    }
    try:
        from dsgvo.template_context import build_dsgvo_context
        dsms = build_dsgvo_context(DB_PATH, projekt)
    except Exception:  # noqa: BLE001
        dsms = None

    common = dict(
        out_dir=out_dir,
        projekt_name=projekt,
        unternehmen=projekt_obj.get("unternehmen", ""),
        organisationstyp=projekt_obj.get("organisationstyp", ""),
        berater=projekt_obj.get("berater", ""),
        bewertungen_raw=bewertungen,
        pflicht_doku=pflicht_doku,
        dsms=dsms,
    )
    path = export_report_docx(**common) if fmt == "docx" else export_report_pdf(**common)
    return Path(path).read_bytes()


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, **_ctx: Any) -> bytes:
    """Erzeugt den DSGVO-Bericht für ``projekt`` als DOCX/PDF-Bytes (kein Zeitraum)."""
    if typ == "gesamt":
        return _render_gesamt(fmt, projekt)
    if typ in AREA_REPORTS:
        from dsgvo import einzelberichte
        if fmt == "pdf":
            return einzelberichte.build_pdf(DB_PATH, projekt, typ)
        return einzelberichte.build_docx(DB_PATH, projekt, typ)
    raise ValueError(f"Unbekannter Berichtstyp: {typ}")
