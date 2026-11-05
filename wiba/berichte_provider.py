"""WiBA-Adapter für das geteilte Berichts-Center (Sprint #35).

Liefert Katalog + Render-Callable. Der Gesamt-Nachweis delegiert an den bestehenden
:mod:`wiba.report_export` (kein Re-Write). Für Parität zu CRA/NIS2 (#1504) gibt es
zusätzlich die Teil-Berichte ``anforderungen`` (Prüffragen je Thema mit Status) und
``massnahmen`` (mit „Nein“ beantwortete Prüffragen als Maßnahmenplan). Die Typ-IDs
sind modulübergreifend identisch; das Label heißt fachlich „Prüffragen-Status“.
Teil-Berichte werden direkt als DOCX gebaut; PDF entsteht daraus per Gotenberg/
LibreOffice (gleicher Weg wie die geteilte Vorlagen-Engine).

DIE SPRACHE GEHÖRT DEM MANDANTEN (#1954)
Die Prosa der beiden Teil-Berichte liegt in :data:`TEXTE` und wird in der
Sprache des Mandanten gedruckt (Modulschlüssel ``wiba``). Vier Dinge bleiben
dabei bewusst **deutsch**, auch im englischen Dokument:

* **Die BSI-Prüffragen und die Themennamen.** Sie kommen aus dem
  Katalog in der Datenbank; es gibt keine amtliche englische Fassung, und der
  Katalogtext ist urheberrechtlich geschützt (BSI). Eine maschinelle
  Übersetzung würde eine Prüffrage durch eine wahrscheinliche ersetzen — in
  einem Nachweis das Gegenteil von hilfreich.
* **Der Eigenname „Weg in die Basis-Absicherung"** und „BSI IT-Grundschutz".
  Im englischen Dokument folgen nur die **Anführungszeichen** der Sprache.
* **Die Antwortwerte.** „Nein" ist der Wert des BSI-Antwortmodells
  (``wiba.constants.STATUS_NEIN``) und wird in der Oberfläche so angezeigt;
  wer im englischen Bericht „No" liest und danach in seiner Akte sucht, findet
  nichts (BERICHTE.md, Regel 7). Die englische Prosa nennt den Wert deshalb
  wörtlich und setzt die Übersetzung in Klammern dahinter.
* **Die Status-Beschriftungen** (``wiba.constants.STATUS_META``) liegen
  außerhalb dieses Moduls und sind (noch) nur deutsch vorhanden — siehe
  Bericht zu #1954.

Der ``gesamt``-Nachweis geht weiter durch :mod:`wiba.report_export`; der führt
(noch) keinen Sprachparameter und bleibt deutsch.
"""
from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from shared.reports import texte as _rt
from shared.reports.core import ReportSpec

DB_PATH = Path("data/db/wiba.sqlite")

#: Modulschlüssel für die Sprachauflösung — so heißt WiBA in
#: ``shared/templates/schema.MODULE_DB`` und in ``shared/firmen_link.
#: MODULE_PROJECT_TABLES`` (``wiba.sqlite`` → ``wiba_projekte``).
MODUL = "wiba"

CATALOG: list[ReportSpec] = [
    ReportSpec("gesamt", "Nachweis-Gesamtbericht", "BSI WiBA",
               "Vollständiger WiBA-Nachweis: Prüffragen je Thema, Reifegrad, offene Punkte.",
               titel_en="Overall evidence report",
               beschreibung_en="Complete WiBA evidence: test questions per "
                               "topic, maturity, open items."),
    ReportSpec("anforderungen", "Prüffragen-Status", "BSI WiBA",
               "Prüffragen je Thema mit Antwort/Status (ohne separaten Maßnahmenplan).",
               titel_en="Test question status",
               beschreibung_en="Test questions per topic with answer/status "
                               "(without a separate action plan)."),
    ReportSpec("massnahmen", "Maßnahmenplan", "BSI WiBA",
               "Mit „Nein“ beantwortete Prüffragen als Maßnahmenplan (Verantwortlich, Zieldatum).",
               titel_en="Action plan",
               beschreibung_en="Test questions answered „Nein“ as an action "
                               "plan (responsible person, target date)."),
]

#: Die Prosa der beiden Teil-Berichte je Sprache (#1954).
#:
#: ``Prüffrage`` → *test question*, ``Basis-Absicherung`` → *basic
#: protection*, ``Reifegrad`` → *maturity* (Begriffsliste #1954). Die
#: deutschen Werte sind zeichengenau die aus 8.3.4 — einschließlich der
#: typografischen Anführungszeichen („…“) und der drei Leerzeichen vor der
#: Klammer in der Reifegrad-Zeile.
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        "titel_prueffragen": "WiBA Prüffragen-Status — {projekt}",
        "titel_massnahmen": "WiBA Maßnahmenplan — {projekt}",
        "erstellt": "Erstellt: {datum} · BSI „Weg in die Basis-Absicherung“",
        # Datumsformat statt eines festen Musters: `%B` wäre von der
        # Server-Locale abhängig. Englisch bekommt ISO 8601 — in einem
        # Nachweis ist `03.11.2026` sonst zweideutig.
        "datum_format": "%d.%m.%Y",
        "l_unternehmen": "Unternehmen: ",
        "l_reifegrad": "Gesamt-Reifegrad: ",
        "reifegrad_wert": "{pct}   (beantwortet: {beantwortet}, offen: {offen})",
        "thema": "{titel} — {pct}",
        "bausteine": "BSI-Bausteine: {bausteine}",
        "keine_prueffragen": "Keine Prüffragen im Katalog.",
        "h_nr": "Nr",
        "h_frage": "Frage",
        "h_status": "Status",
        "h_notiz": "Notiz",
        "hinweis_massnahmen": ("Die folgenden Prüffragen wurden mit „Nein“ "
                               "beantwortet und erfordern Maßnahmen zur "
                               "Erreichung der BSI-Basis-Absicherung."),
        "keine_offenen": "Keine offenen Punkte (Status „Nein“) erfasst.",
        "h_thema_nr": "Thema / Nr",
        "h_verantwortlich": "Verantwortlich",
        "h_zieldatum": "Zieldatum",
        "leer": "–",
    },
    "en": {
        "titel_prueffragen": "WiBA test question status — {projekt}",
        "titel_massnahmen": "WiBA action plan — {projekt}",
        # Der Eigenname bleibt; nur die Anführungszeichen folgen der Sprache.
        "erstellt": "Created: {datum} · BSI “Weg in die Basis-Absicherung”",
        "datum_format": "%Y-%m-%d",
        "l_unternehmen": "Company: ",
        "l_reifegrad": "Overall maturity: ",
        "reifegrad_wert": "{pct}   (answered: {beantwortet}, open: {offen})",
        "thema": "{titel} — {pct}",
        # „Bausteine" heißen im BSI IT-Grundschutz amtlich englisch *modules*.
        "bausteine": "BSI modules: {bausteine}",
        "keine_prueffragen": "No test questions in the catalogue.",
        "h_nr": "No.",
        "h_frage": "Question",
        "h_status": "Status",
        "h_notiz": "Note",
        # „Nein" bleibt wörtlich: Es ist der Antwortwert, nach dem der Leser
        # in seiner Akte sucht. Die Übersetzung steht in Klammern dahinter.
        "hinweis_massnahmen": ("The following test questions were answered "
                               "„Nein“ (no) and require measures to achieve "
                               "BSI basic protection."),
        "keine_offenen": "No open items recorded (status „Nein“).",
        "h_thema_nr": "Topic / no.",
        "h_verantwortlich": "Responsible",
        "h_zieldatum": "Target date",
        "leer": "–",
    },
}

_t = _rt.macher(TEXTE)


def catalog() -> list[ReportSpec]:
    return CATALOG


# ── Teil-Berichte (DOCX) ─────────────────────────────────────────────────────

def _prueffragen_docx(projekt: str, sp: str = "de") -> bytes:
    """Prüffragen je Thema mit Status als DOCX-Bytes."""
    from io import BytesIO

    from docx import Document
    from docx.shared import Inches

    from wiba.constants import (
        STATUS_META, STATUS_META_EN, normalize_status,
    )
    from wiba.report_export import _collect

    def _status_label(st: str) -> str:
        # #1954: `STATUS_META_EN` trägt die englischen Beschriftungen;
        # „Ja"/„Nein" bleiben darin stehen, weil es die Antwortwerte der
        # BSI-Prüffrage sind, nach denen der Anwender in seiner Akte sucht.
        # siehe Bericht zu #1954.
        if sp == "en":
            return STATUS_META_EN.get(normalize_status(st),
                                      STATUS_META_EN["offen"])
        return STATUS_META.get(normalize_status(st),
                               STATUS_META["offen"])["label"]

    data = _collect(DB_PATH, projekt)
    proj = data["projekt"]

    doc = Document()
    for section in doc.sections:
        section.left_margin = Inches(0.85)
        section.right_margin = Inches(0.85)

    doc.add_heading(_t(sp, "titel_prueffragen", projekt=projekt), level=0)
    doc.add_paragraph(
        _t(sp, "erstellt",
           datum=date.today().strftime(_t(sp, "datum_format"))))
    meta = doc.add_paragraph()
    meta.add_run(_t(sp, "l_unternehmen")).bold = True
    meta.add_run(f"{proj.get('unternehmen', '')}\n")
    meta.add_run(_t(sp, "l_reifegrad")).bold = True
    meta.add_run(_t(sp, "reifegrad_wert",
                    pct=f"{float(data.get('gesamt_pct', 0.0) or 0.0):.0f}%",
                    beantwortet=data.get('beantwortet', 0),
                    offen=data.get('offen', 0)))

    for t in data["themen"]:
        # `titel` ist der BSI-Themenname aus dem Katalog und bleibt deutsch.
        doc.add_heading(_t(sp, "thema", titel=t['titel'],
                           pct=f"{t['pct']:.0f}%"), level=1)
        if t.get("bausteine"):
            doc.add_paragraph(_t(sp, "bausteine", bausteine=t['bausteine']))
        rows = t.get("prueffragen") or []
        if not rows:
            doc.add_paragraph(_t(sp, "keine_prueffragen"))
            continue
        tbl = doc.add_table(rows=len(rows) + 1, cols=4)
        tbl.style = "Light Grid Accent 1"
        for ci, hdr in enumerate([_t(sp, "h_nr"), _t(sp, "h_frage"),
                                  _t(sp, "h_status"), _t(sp, "h_notiz")]):
            tbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
        for ri, q in enumerate(rows, start=1):
            tbl.cell(ri, 0).text = str(q.get("nr", ""))
            tbl.cell(ri, 1).text = str(q.get("frage", ""))[:400]
            tbl.cell(ri, 2).text = _status_label(q.get("status", "offen"))
            tbl.cell(ri, 3).text = str(q.get("notiz", "") or "")[:300]

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _massnahmen_docx(projekt: str, sp: str = "de") -> bytes:
    """Mit „Nein“ beantwortete Prüffragen als Maßnahmenplan (DOCX-Bytes)."""
    from io import BytesIO

    from docx import Document
    from docx.shared import Inches

    from wiba.report_export import _collect

    data = _collect(DB_PATH, projekt)
    proj = data["projekt"]
    offene = data.get("offene_punkte") or []

    doc = Document()
    for section in doc.sections:
        section.left_margin = Inches(0.85)
        section.right_margin = Inches(0.85)

    doc.add_heading(_t(sp, "titel_massnahmen", projekt=projekt), level=0)
    doc.add_paragraph(
        _t(sp, "erstellt",
           datum=date.today().strftime(_t(sp, "datum_format"))))
    meta = doc.add_paragraph()
    meta.add_run(_t(sp, "l_unternehmen")).bold = True
    meta.add_run(f"{proj.get('unternehmen', '')}")
    doc.add_paragraph(_t(sp, "hinweis_massnahmen"))

    if not offene:
        p = doc.add_paragraph(_t(sp, "keine_offenen"))
        p.runs[0].italic = True
    else:
        tbl = doc.add_table(rows=len(offene) + 1, cols=5)
        tbl.style = "Light Grid Accent 1"
        for ci, hdr in enumerate([_t(sp, "h_thema_nr"), _t(sp, "h_frage"),
                                  _t(sp, "h_notiz"), _t(sp, "h_verantwortlich"),
                                  _t(sp, "h_zieldatum")]):
            tbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
        for ri, op in enumerate(offene, start=1):
            tbl.cell(ri, 0).text = f"{op.get('theme', '')}\n#{op.get('nr', '')}"
            tbl.cell(ri, 1).text = str(op.get("frage", ""))[:300]
            tbl.cell(ri, 2).text = str(op.get("notiz", "") or "")[:250]
            tbl.cell(ri, 3).text = str(op.get("verantwortlich", "") or _t(sp, "leer"))
            tbl.cell(ri, 4).text = str(op.get("zieldatum", "") or _t(sp, "leer"))

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, sprache: str | None = None,
           **_ctx: Any) -> bytes:
    """Erzeugt den WiBA-Nachweis für ``projekt`` als DOCX/PDF-Bytes (kein Zeitraum).

    ``sprache`` übersteuert die Sprache des Mandanten für diesen einen Lauf;
    ohne Angabe entscheidet ``firmen.sprache`` (#1954). Aufgelöst wird hier und
    nicht beim Aufrufer — das Berichts-Center reicht den Parameter nur durch,
    wenn die Signatur ihn führt (``shared/reports/api._zusatz``).
    """
    sp = _rt.aufloesen(MODUL, projekt, sprache)
    if typ in ("anforderungen", "massnahmen"):
        docx_bytes = (_prueffragen_docx(projekt, sp) if typ == "anforderungen"
                      else _massnahmen_docx(projekt, sp))
        if fmt == "pdf":
            from shared.templates.pdf_converter import convert_docx_to_pdf
            return convert_docx_to_pdf(docx_bytes)
        return docx_bytes

    # gesamt → bestehender Generator. Der nimmt (noch) kein `sprache`; ihn hier
    # damit aufzurufen wäre ein TypeError, nicht ein deutscher Bericht.
    from wiba.report_export import export_report_docx, export_report_pdf

    out_dir = Path(tempfile.mkdtemp(prefix="wiba_report_"))
    if fmt == "docx":
        path = export_report_docx(out_dir=out_dir, projekt_name=projekt, db_path=DB_PATH)
    else:
        path = export_report_pdf(out_dir=out_dir, projekt_name=projekt, db_path=DB_PATH)
    return Path(path).read_bytes()
