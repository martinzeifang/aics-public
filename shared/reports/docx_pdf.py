"""Einheitliche A4-/PDF-Erzeugung für alle Modul-Berichte (#1614).

Historie: mehrere Module erzeugten ihr PDF als **PIL-Rasterbild** (unscharf, keine
Textebene) und setzten im DOCX kein A4 (python-docx-Default = US-Letter). Dieser
Helfer vereinheitlicht beides:

- :func:`set_a4` setzt für alle Sektionen eines ``python-docx``-Dokuments A4 (210×297 mm).
- :func:`docx_to_pdf_bytes` / :func:`docx_bytes_to_pdf` erzeugen ein **vektorielles**
  PDF über den vorhandenen Konverter (Gotenberg/LibreOffice, ``shared/templates/pdf_converter``).

Ziel: scharfe, A4-formatige, durchsuchbare Berichts-PDFs in allen Modulen.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

# A4 in EMU-freien python-docx-Einheiten.
try:  # pragma: no cover - import guard
    from docx.shared import Mm
    from docx.enum.section import WD_ORIENT
    _A4_W = Mm(210)
    _A4_H = Mm(297)
except Exception:  # noqa: BLE001
    Mm = None  # type: ignore
    WD_ORIENT = None  # type: ignore
    _A4_W = _A4_H = None


# #1617: Arial-ähnliche Basis-Schrift. LibreOffice/Gotenberg mappt „Arial" auf
# „Liberation Sans" (metrik-kompatibel) — unter allen Umgebungen sauber.
_BASE_FONT = "Arial"


def apply_base_font(doc: Any, name: str = _BASE_FONT, *,
                    sprache: str | None = None) -> Any:
    """Setzt eine Arial-ähnliche Basis-Schrift für Standard- und Überschriften-Stile.

    ``sprache`` setzt zusätzlich die **Dokumentsprache** (``w:lang``, #1954).
    Ohne sie unterstreicht Word in einem englischen Bericht jedes Wort rot —
    das Dokument sieht fehlerhaft aus, obwohl es richtig ist, und ein Kunde
    liest das als Schlamperei. Gesetzt wird sie an der Stelle, durch die
    **jeder** Modul-Bericht geht; bis #1954 stand sie an genau einer Stelle
    hart auf ``de-DE`` (``gutachten/gerichtsgutachten_gen.py``).

    ``None`` heißt **nicht anfassen** und ist bewusst die Vorgabe: Dieser Helfer
    läuft über ``_normalize_docx_bytes`` ein zweites Mal über jedes bereits
    fertige Dokument, bevor es ins PDF geht. Mit einem Vorgabewert würde dieser
    Durchlauf die am Dokument gesetzte Sprache wieder auf Deutsch stellen —
    dieselbe Klasse wie der ``artefakt``-Verlust in #1771: Ein Teil-Update, das
    stillschweigend überschreibt, was der Aufrufer nicht erwähnt.
    """
    try:
        from docx.shared import Pt as _Pt
        for sname in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3",
                      "Heading 4", "List Paragraph", "Table Grid"):
            try:
                st = doc.styles[sname]
                if st.font is not None:
                    st.font.name = name
            except Exception:  # noqa: BLE001 — Stil evtl. nicht vorhanden
                pass
        try:
            doc.styles["Normal"].font.size = doc.styles["Normal"].font.size or _Pt(10)
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass
    if sprache:
        set_doc_lang(doc, sprache)
    return doc


def set_doc_lang(doc: Any, sprache: str) -> Any:
    """Dokumentsprache am Stil ``Normal`` setzen (``w:lang``, #1954).

    Am **Stil** und nicht an jedem Run: Ein Run ohne eigene Angabe erbt vom
    Stil, also wirkt eine Zuweisung auch für Absätze, die erst nach diesem
    Aufruf entstehen. python-docx bietet dafür keine Eigenschaft — ``w:lang``
    ist ein reines XML-Element der Run-Eigenschaften.

    ``w:eastAsia`` wird bewusst mitgesetzt: Fehlt es, zieht Word dort seine
    eigene Vorgabe und prüft Teile des Textes gegen die falsche Sprache.
    """
    from shared import sprache as _sprache

    code = _sprache.docx_lang(sprache)
    try:
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement

        st = doc.styles["Normal"]
        rPr = st.element.get_or_add_rPr()
        for el in rPr.findall(qn("w:lang")):
            rPr.remove(el)
        lang = OxmlElement("w:lang")
        lang.set(qn("w:val"), code)
        lang.set(qn("w:eastAsia"), code)
        rPr.append(lang)
    except Exception:  # noqa: BLE001 — eine Sprachangabe darf nie den Bericht brechen
        pass
    return doc


def fit_tables(doc: Any) -> Any:
    """#1617: Tabellen auf die Seitenbreite begrenzen (Autofit, 100 % Breite, kein Überlauf)."""
    try:
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        for tbl in doc.tables:
            try:
                tbl.autofit = True
                tbl.allow_autofit = True
                tblPr = tbl._tbl.tblPr
                # feste Layout-Angaben entfernen, Breite auf 100 % setzen
                for tag in ("tblW", "tblLayout"):
                    for el in tblPr.findall(qn("w:" + tag)):
                        tblPr.remove(el)
                tblW = OxmlElement("w:tblW"); tblW.set(qn("w:type"), "pct"); tblW.set(qn("w:w"), "5000")
                tblPr.append(tblW)
                layout = OxmlElement("w:tblLayout"); layout.set(qn("w:type"), "autofit")
                tblPr.append(layout)
                # explizite Zellbreiten entfernen (erzwingen sonst Überlauf)
                for row in tbl.rows:
                    for cell in row.cells:
                        tcPr = cell._tc.get_or_add_tcPr()
                        for el in tcPr.findall(qn("w:tcW")):
                            tcPr.remove(el)
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass
    return doc


def set_a4(doc: Any, *, landscape: bool = False, sprache: str | None = None) -> Any:
    """Setzt für alle Sektionen des Dokuments A4 (Portrait, optional Landscape) +
    Arial-ähnliche Basis-Schrift (#1617), optional die Dokumentsprache (#1954)."""
    apply_base_font(doc, sprache=sprache)
    if _A4_W is None:
        return doc
    w, h = (_A4_H, _A4_W) if landscape else (_A4_W, _A4_H)
    for sec in doc.sections:
        try:
            if WD_ORIENT is not None:
                sec.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
            sec.page_width = w
            sec.page_height = h
        except Exception:  # noqa: BLE001 — best effort
            pass
    return doc


def _normalize_docx_bytes(docx_bytes: bytes) -> bytes:
    """#1617: vor der PDF-Konvertierung Arial + A4-taugliche Tabellen erzwingen (zentral)."""
    try:
        from docx import Document
        d = Document(BytesIO(docx_bytes))
        apply_base_font(d)
        fit_tables(d)
        out = BytesIO(); d.save(out)
        return out.getvalue()
    except Exception:  # noqa: BLE001 — Normalisierung darf nie die Erzeugung brechen
        return docx_bytes


def docx_bytes_to_pdf(docx_bytes: bytes, *, timeout_s: int = 90) -> bytes:
    """DOCX-Bytes → vektorielles PDF über den gemeinsamen Konverter (Arial + A4-Tabellen)."""
    from shared.templates.pdf_converter import convert_docx_to_pdf
    return convert_docx_to_pdf(_normalize_docx_bytes(docx_bytes), timeout_s=timeout_s)


def docx_to_pdf_bytes(docx_path: str | Path, *, timeout_s: int = 90) -> bytes:
    """DOCX-Datei → vektorielles PDF (Bytes)."""
    return docx_bytes_to_pdf(Path(docx_path).read_bytes(), timeout_s=timeout_s)


def save_doc_as_pdf(doc: Any, out_path: str | Path, *, a4: bool = True,
                    landscape: bool = False, timeout_s: int = 90) -> Path:
    """python-docx-Dokument (A4) → PDF-Datei. Gibt den Zielpfad zurück."""
    if a4:
        set_a4(doc, landscape=landscape)
    bio = BytesIO()
    doc.save(bio)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(docx_bytes_to_pdf(bio.getvalue(), timeout_s=timeout_s))
    return out
