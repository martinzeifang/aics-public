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
from dsgvo.tom import ENTWURF_TYP as TOM_ENTWURF

DB_PATH = Path("data/db/dsgvo.sqlite")

CATALOG: list[ReportSpec] = [
    ReportSpec(
        "gesamt", "DSMS-Gesamtbericht", "Verordnung (EU) 2016/679",
        "Vollständiger DSGVO-Compliance-Bericht: Reifegrad, Anforderungen, "
        "Pflicht-Doku und DSMS-Bereiche.",
        norm_en="Regulation (EU) 2016/679",
    ),
] + [
    ReportSpec(area, cfg["titel"], cfg.get("norm", ""),
               f"Bereichsbericht: {cfg['titel']} ({cfg.get('norm', '')}).",
               # #1954: Titel und Fundstelle auf Englisch stehen in
               # `einzelberichte.AREA_REPORTS` — eine zweite
               # Zuordnung hier wäre die Spiegel-Liste (#1731/#1735).
               titel_en=cfg.get("titel_en", ""),
               norm_en=cfg.get("norm_en", ""),
               beschreibung_en=(
                   f"Area report: {cfg.get('titel_en') or cfg['titel']}"
                   f" ({cfg.get('norm_en') or cfg.get('norm', '')})."))
    for area, cfg in AREA_REPORTS.items()
] + [
    # #2005: Der TOM-**Entwurf** ist nicht der Bereichsbericht ``tom``. Jener
    # weist den erreichten Stand nach (Katalog, Status, SDM-Ziele), dieser ist
    # die Arbeitsgrundlage, aus der ein Mensch das TOM-Dokument schreibt. Zwei
    # Dokumente über dieselbe Sache — also zwei Berichtstypen und je **eine**
    # Vorlage. Dass er hier steht, ist der ganze Punkt: Nur ein Berichtstyp
    # kann im Admin-UI eine Vorlage tragen (``schema.berichte_typen``, #1777).
    #
    # ``vorgeschrieben`` ist **nicht** gesetzt. Das Kennzeichen gilt Dokumenten,
    # deren Aufbau dem Rechtstext gehört (Anhang V, Konformitätsnachweis).
    # Art. 32 DSGVO schreibt für ein TOM-Dokument keine Gliederung vor; die
    # Abschnitte TOM-A…TOM-J sind unsere. Es für „Dokument mit Entwurfsvermerk"
    # zu verwenden würde seine Bedeutung verschieben — und alle acht übrigen
    # DSGVO-Typen stehen ebenso auf ``False``.
    ReportSpec(
        TOM_ENTWURF, "TOM-Entwurf (Art. 32)", "Art. 32 DSGVO",
        "Arbeitsgrundlage für das TOM-Dokument: je TOM-Abschnitt vorhandene "
        "Maßnahmen, Lücken und Empfehlungen aus dem KI-Entwurf und den "
        "Firmen-Nachweisen.",
        titel_en="TOM draft (Art. 32)", norm_en="Art. 32 GDPR",
        beschreibung_en="Working basis for the TOM document: per TOM section the "
                        "existing measures, gaps and recommendations from the AI "
                        "draft and the company evidence.",
    ),
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


def _render_gesamt(fmt: str, projekt: str,
                   sprache: str | None = None) -> bytes:
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
    path = export_report_docx(sprache=sprache, **common) if fmt == "docx" else export_report_pdf(sprache=sprache, **common)
    return Path(path).read_bytes()


def _render_tom_entwurf(fmt: str, projekt: str,
                        sprache: str | None = None) -> bytes:
    """TOM-Entwurf — **dieselbe** Funktion wie der Knopf im TOM-Generator (#2005)."""
    from dsgvo.tom import export_entwurf_docx

    out_dir = Path(tempfile.mkdtemp(prefix="dsgvo_tom_entwurf_"))
    docx = Path(export_entwurf_docx(DB_PATH, projekt, out_dir=out_dir,
                                    sprache=sprache)).read_bytes()
    if (fmt or "docx").lower() != "pdf":
        return docx
    # Fehler des Konverters bewusst durchlassen: das Berichts-Center bildet sie
    # auf 503/504/502 ab und empfiehlt DOCX (#1903).
    from shared.reports.docx_pdf import docx_bytes_to_pdf
    return docx_bytes_to_pdf(docx)


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, sprache: str | None = None,
           **_ctx: Any) -> bytes:
    """Erzeugt den DSGVO-Bericht für ``projekt`` als DOCX/PDF-Bytes (kein Zeitraum)."""
    if typ == "gesamt":
        return _render_gesamt(fmt, projekt, sprache)
    if typ == TOM_ENTWURF:
        return _render_tom_entwurf(fmt, projekt, sprache)
    if typ in AREA_REPORTS:
        from dsgvo import einzelberichte
        if fmt == "pdf":
            return einzelberichte.build_pdf(DB_PATH, projekt, typ,
                                            sprache=sprache)
        return einzelberichte.build_docx(DB_PATH, projekt, typ,
                                         sprache=sprache)
    raise ValueError(f"Unbekannter Berichtstyp: {typ}")
