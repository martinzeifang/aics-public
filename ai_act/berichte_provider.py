"""AI-Act-Adapter für das geteilte Berichts-Center (Sprint #35, #1384).

Liefert Katalog + Render-Callable. Der Gesamtbericht delegiert an den bestehenden
:mod:`ai_act.report_export` (kein Re-Write). Für die Teil-Berichte ``anforderungen``
(nur die Bewertungen der AI-Act-Anforderungen) und ``massnahmen`` (nur die erfassten
Maßnahmen offener Anforderungen) — Parität zu CRA/NIS2 (#1504) — erzeugt dieser
Adapter fokussierte DOCX-Dokumente direkt; PDF entsteht daraus per Gotenberg/
LibreOffice (gleicher Weg wie die geteilte Vorlagen-Engine). DOCX-first.

DIE SPRACHE GEHÖRT DEM MANDANTEN (#1954)
Die Prosa der beiden Teil-Berichte liegt in :data:`TEXTE` und wird über
``shared/reports/texte`` in der Sprache des Mandanten gedruckt
(Modulschlüssel ``aiact`` — derselbe, den die Vorlagen-Engine führt,
``shared/templates/schema.MODULE_DB``). Die **Titel in der Auswahlliste**
stehen dagegen als ``titel_en``/``beschreibung_en`` am ``ReportSpec``: Die
Liste ist Bedienoberfläche und folgt der Anzeigesprache des Bedieners. Das
sind zwei Dinge und sie dürfen auseinanderfallen.

Der Gesamtbericht geht weiter durch :mod:`ai_act.report_export`; der führt
(noch) keinen Sprachparameter und bleibt deutsch.
"""
from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from shared.reports import texte as _rt
from shared.reports.core import ReportSpec

DB_PATH = Path("data/db/ai_act.sqlite")

#: Modulschlüssel für die Sprachauflösung. **Nicht** ``ai_act``: Aufgelöst
#: wird über ``shared/templates/schema.MODULE_DB``, und dort heißt das Modul
#: ``aiact`` (``shared/reports/vorlagen._ALIASE`` bildet beides ab, aber nur
#: der Engine-Schlüssel ist direkt eingetragen). Ein falscher Schlüssel fällt
#: nicht auf — er sieht aus wie „kein Mandant hinterlegt" (#1892).
MODUL = "aiact"

CATALOG: list[ReportSpec] = [
    ReportSpec(
        "gesamt", "Gesamtbericht", "EU AI Act (2024/1689)",
        "Vollständiger AI-Act-Bericht inkl. Pflicht-Doku-Nachweise (Art. 11/Annex IV).",
        titel_en="Overall report",
        beschreibung_en="Complete AI Act report including evidence of the "
                        "mandatory documentation (Art. 11/Annex IV).",
    ),
    ReportSpec(
        "anforderungen", "Anforderungs-Status", "EU AI Act Art. 8–15",
        "Kapitelweise Bewertung der AI-Act-Anforderungen (ohne Pflicht-Doku/Maßnahmenplan).",
        titel_en="Requirement status",
        beschreibung_en="Chapter-by-chapter assessment of the AI Act "
                        "requirements (without mandatory documentation or "
                        "action plan).",
    ),
    ReportSpec(
        "massnahmen", "Maßnahmenplan", "EU AI Act Art. 9",
        "Offene Anforderungen mit erfassten Maßnahmen als Maßnahmenplan.",
        titel_en="Action plan",
        beschreibung_en="Open requirements with the measures recorded for "
                        "them, as an action plan.",
    ),
]

#: Die Prosa der beiden Teil-Berichte je Sprache (#1954).
#:
#: Amtliche englische Begriffe der KI-VO: ``Anbieter`` → *provider*,
#: ``Hochrisiko-KI-System`` → *high-risk AI system*. Die Fundstellen bleiben
#: unangetastet, nur die Bezeichnung der Anlage folgt dem Amtsblatt
#: (``Anhang IV`` → *Annex IV*) — die Ziffern nie (#1763/#1792).
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        "titel_anforderungen": "AI-Act Anforderungs-Status — {projekt}",
        "titel_massnahmen": "AI-Act Maßnahmenplan — {projekt}",
        "erstellt": "Erstellt: {datum} · Verordnung (EU) 2024/1689 (AI Act)",
        # Datumsformat statt eines festen Musters: `%B` wäre von der
        # Server-Locale abhängig und schriebe im englischen Bericht deutsche
        # Monatsnamen. Englisch bekommt ISO 8601 — in einem Dokument, das ein
        # Prüfer liest, ist `03.11.2026` sonst zweideutig.
        "datum_format": "%d.%m.%Y",
        "l_organisation": "Organisation: ",
        "l_produkt": "Produkt/System: ",
        "l_reifegrad": "Reifegrad: ",
        "kapitel": "Kapitel {kap}",
        "h_id": "ID",
        "h_anforderung": "Anforderung",
        "h_bewertung": "Bewertung",
        "h_kommentar": "Kommentar",
        "h_massnahme": "Maßnahme",
        "hinweis_massnahmen": ("Die folgenden Anforderungen sind noch nicht "
                               "vollständig umgesetzt bzw. mit Maßnahmen "
                               "hinterlegt."),
        "keine_offenen": "Keine offenen Anforderungen / Maßnahmen erfasst.",
        "keine_massnahme": "– (keine Maßnahme erfasst)",
    },
    "en": {
        "titel_anforderungen": "AI Act requirement status — {projekt}",
        "titel_massnahmen": "AI Act action plan — {projekt}",
        "erstellt": "Created: {datum} · Regulation (EU) 2024/1689 (AI Act)",
        "datum_format": "%Y-%m-%d",
        "l_organisation": "Organisation: ",
        "l_produkt": "Product/system: ",
        "l_reifegrad": "Maturity: ",
        "kapitel": "Chapter {kap}",
        "h_id": "ID",
        "h_anforderung": "Requirement",
        "h_bewertung": "Assessment",
        "h_kommentar": "Comment",
        "h_massnahme": "Measure",
        "hinweis_massnahmen": ("The following requirements are not yet fully "
                               "implemented or have measures recorded "
                               "against them."),
        "keine_offenen": "No open requirements or measures recorded.",
        "keine_massnahme": "– (no measure recorded)",
    },
}

_t = _rt.macher(TEXTE)


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


# ── Teil-Berichte (DOCX) ─────────────────────────────────────────────────────

# ── #1954: Katalogeinträge in der Sprache des Dokuments ──────────────────────
# Die Literale werden hier direkt gelesen; ohne diesen Helfer käme die
# englische Fassung (`titel_en`, `label_en`, `referenz_en`) nie an — die
# Übersetzung wäre vorhanden und wirkungslos (der Defekt aus #1735).
# `uebersetze` liefert **Kopien**: Das Modul-Literal wird von mehreren
# Anfragen gleichzeitig gelesen.
def _kat(eintrag: dict, sp: str) -> dict:
    from shared.katalog_sprache import uebersetze

    return uebersetze(eintrag or {}, sp)


def _anforderungen_docx(projekt: str, sp: str = "de") -> bytes:
    """Nur die Anforderungs-Bewertungen (kapitelweise) als DOCX-Bytes."""
    from io import BytesIO

    from docx import Document
    from docx.shared import Inches

    from ai_act.db import load_bewertungen, load_projekt
    from ai_act.requirements import (
        AI_ACT_REQUIREMENTS, BEWERTUNG_SKALA, KAPITEL, berechne_reifegrad,
    )

    proj = load_projekt(DB_PATH, projekt) or {}
    bew_raw = load_bewertungen(DB_PATH, projekt)
    scores = {rid: int((b or {}).get("bewertung", 0) or 0) for rid, b in bew_raw.items()}
    reife = berechne_reifegrad(scores)

    doc = Document()
    for section in doc.sections:
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)

    doc.add_heading(_t(sp, "titel_anforderungen", projekt=projekt), level=0)
    doc.add_paragraph(
        _t(sp, "erstellt",
           datum=date.today().strftime(_t(sp, "datum_format"))))
    meta = doc.add_paragraph()
    meta.add_run(_t(sp, "l_organisation")).bold = True
    meta.add_run(f"{proj.get('organisation', '')}\n")
    meta.add_run(_t(sp, "l_produkt")).bold = True
    meta.add_run(f"{proj.get('produkt', '')}\n")
    meta.add_run(_t(sp, "l_reifegrad")).bold = True
    # `ampel` ist der **Datenwert** ('gruen'|'orange'|'rot') und wird hier roh
    # gedruckt — schon im deutschen Bericht. Das bleibt so: Eine Übersetzung
    # nur für Englisch würde einen vorhandenen Mangel in einer Sprache
    # verdecken und in der anderen stehen lassen. Gemeldet, nicht geglättet.
    meta.add_run(f"{float(reife.get('gesamt_pct', 0.0) or 0.0):.0f}% ({reife.get('ampel', '')})")

    # Kapitelweise (HR/GOV/DATA/OPS), Rest unter „Sonstige".
    reqs_by_kap: dict[str, list[dict[str, Any]]] = {}
    for req in (_kat(r, sp) for r in AI_ACT_REQUIREMENTS):
        reqs_by_kap.setdefault(str(req.get("kapitel") or "Sonstige"), []).append(req)
    order = [k for k in KAPITEL if k in reqs_by_kap] + \
            [k for k in reqs_by_kap if k not in KAPITEL]

    for kap in order:
        doc.add_heading(_t(sp, "kapitel", kap=kap), level=1)
        reqs = reqs_by_kap[kap]
        tbl = doc.add_table(rows=len(reqs) + 1, cols=4)
        tbl.style = "Light Grid Accent 1"
        for ci, hdr in enumerate([_t(sp, "h_id"), _t(sp, "h_anforderung"),
                                  _t(sp, "h_bewertung"), _t(sp, "h_kommentar")]):
            tbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
        for ri, req in enumerate(reqs, start=1):
            rid = str(req.get("id") or "")
            b = bew_raw.get(rid, {})
            score = int(b.get("bewertung", 0) or 0)
            label = _kat(BEWERTUNG_SKALA.get(score, {}), sp).get(
                "label", str(score))
            tbl.cell(ri, 0).text = rid
            tbl.cell(ri, 1).text = str(req.get("titel", ""))[:60]
            tbl.cell(ri, 2).text = f"{score} – {label}"
            tbl.cell(ri, 3).text = str(b.get("kommentar", "") or "")[:300]

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _massnahmen_docx(projekt: str, sp: str = "de") -> bytes:
    """Nur die erfassten Maßnahmen offener Anforderungen als DOCX-Bytes."""
    from io import BytesIO

    from docx import Document
    from docx.shared import Inches

    from ai_act.db import load_bewertungen, load_projekt
    from ai_act.requirements import AI_ACT_REQUIREMENTS, BEWERTUNG_SKALA

    proj = load_projekt(DB_PATH, projekt) or {}
    bew_raw = load_bewertungen(DB_PATH, projekt)
    titel_by_id = {str(r.get("id")): str(_kat(r, sp).get("titel", ""))
                   for r in AI_ACT_REQUIREMENTS}

    # Offene Anforderungen (Bewertung < 5) mit erfasster Maßnahme oder Lücke.
    rows: list[dict[str, Any]] = []
    for req in (_kat(r, sp) for r in AI_ACT_REQUIREMENTS):
        rid = str(req.get("id") or "")
        b = bew_raw.get(rid, {})
        score = int(b.get("bewertung", 0) or 0)
        massnahme = str(b.get("massnahme", "") or "").strip()
        if score >= 5 and not massnahme:
            continue  # vollständig umgesetzt + keine offene Maßnahme
        rows.append({
            "id": rid,
            "titel": titel_by_id.get(rid, str(req.get("titel", ""))),
            "kapitel": str(req.get("kapitel", "")),
            "score": score,
            "label": _kat(BEWERTUNG_SKALA.get(score, {}), sp).get(
                "label", str(score)),
            "massnahme": massnahme,
        })

    doc = Document()
    for section in doc.sections:
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)

    doc.add_heading(_t(sp, "titel_massnahmen", projekt=projekt), level=0)
    doc.add_paragraph(
        _t(sp, "erstellt",
           datum=date.today().strftime(_t(sp, "datum_format"))))
    meta = doc.add_paragraph()
    meta.add_run(_t(sp, "l_organisation")).bold = True
    meta.add_run(f"{proj.get('organisation', '')}")
    doc.add_paragraph(_t(sp, "hinweis_massnahmen"))

    if not rows:
        p = doc.add_paragraph(_t(sp, "keine_offenen"))
        p.runs[0].italic = True
    else:
        tbl = doc.add_table(rows=len(rows) + 1, cols=4)
        tbl.style = "Light Grid Accent 1"
        for ci, hdr in enumerate([_t(sp, "h_id"), _t(sp, "h_anforderung"),
                                  _t(sp, "h_bewertung"), _t(sp, "h_massnahme")]):
            tbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
        for ri, r in enumerate(rows, start=1):
            tbl.cell(ri, 0).text = r["id"]
            tbl.cell(ri, 1).text = f"{r['titel'][:55]} ({r['kapitel']})"
            tbl.cell(ri, 2).text = f"{r['score']} – {r['label']}"
            tbl.cell(ri, 3).text = (r["massnahme"] or _t(sp, "keine_massnahme"))[:400]

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, sprache: str | None = None,
           **_ctx: Any) -> bytes:
    """Erzeugt den AI-Act-Bericht für ``projekt`` als DOCX/PDF-Bytes (kein Zeitraum).

    ``sprache`` übersteuert die Sprache des Mandanten für diesen einen Lauf;
    ohne Angabe entscheidet ``firmen.sprache`` (#1954). Aufgelöst wird hier und
    nicht beim Aufrufer — das Berichts-Center reicht den Parameter nur durch,
    wenn die Signatur ihn führt (``shared/reports/api._zusatz``).
    """
    sp = _rt.aufloesen(MODUL, projekt, sprache)
    if typ in ("anforderungen", "massnahmen"):
        docx_bytes = (_anforderungen_docx(projekt, sp) if typ == "anforderungen"
                      else _massnahmen_docx(projekt, sp))
        if fmt == "pdf":
            from shared.templates.pdf_converter import convert_docx_to_pdf
            return convert_docx_to_pdf(docx_bytes)
        return docx_bytes

    # gesamt → bestehender Generator
    from ai_act.report_export import export_docx, export_pdf

    out_dir = Path(tempfile.mkdtemp(prefix="aiact_report_"))
    if fmt == "pdf":
        path = export_pdf(db_path=DB_PATH, projekt_name=projekt,
                              out_dir=out_dir, sprache=sp)
    else:
        path = export_docx(db_path=DB_PATH, projekt_name=projekt,
                               out_dir=out_dir, sprache=sp)
    return Path(path).read_bytes()
