"""WiBA-Modul – Berichtsgenerator für Word (.docx) und PDF.

Erzeugt einen „Nachweis sicherer IT-Betrieb (BSI WiBA)" mit:
  - Deckblatt (Projekt, Unternehmen, Berater, Datum, Katalog-Version)
  - Management-Summary (Gesamt-Reifegrad %, beantwortet/offen)
  - Je Thema (Titel + BSI-Bausteine + Reifegrad %) eine Tabelle der Prüffragen
    (Nr | Frage | Status | Notiz)
  - Abschnitt „Offene Punkte / Maßnahmen" (alle status=nein mit
    Notiz/Verantwortlich/Zieldatum)

Konventionen (Farben, DOCX-Helfer, PDF via PIL) sind an ``cra/report_export.py``
angelehnt; der PDF-Export nutzt denselben PIL-Render-Ansatz wie CRA.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

from wiba import db as wdb
from wiba.constants import STATUS_META, normalize_status

# ── Farb-Palette ──────────────────────────────────────────────────────────────
_BSI_BLUE = "#003d6b"
_DARK = "#00284a"
_SOFT = "#e3eef5"
_AMPEL_GREEN = "#1b5e20"
_AMPEL_ORANGE = "#e65100"
_AMPEL_RED = "#c62828"


def _safe_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "-", s or "")
    s = re.sub(r"\s+", "_", s).strip("_")
    return s[:100] or "WiBA_Nachweis"


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = (h or "#000000").lstrip("#")
    if len(h) != 6:
        h = "000000"
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex_to_word(h: str) -> str:
    return (h or "#000000").lstrip("#").upper()


def _status_label(status: str) -> str:
    return STATUS_META.get(normalize_status(status), STATUS_META["offen"])["label"]


def _status_color(status: str) -> str:
    return STATUS_META.get(normalize_status(status), STATUS_META["offen"])["farbe"]


def _ampel_color(pct: float) -> str:
    if pct >= 80:
        return _AMPEL_GREEN
    if pct >= 50:
        return _AMPEL_ORANGE
    return _AMPEL_RED


def _load_font(size: int, bold: bool = False):
    candidates = (
        (["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"] if bold else [])
        + ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ── Daten-Aufbereitung ────────────────────────────────────────────────────────

def _collect(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Lädt + strukturiert alle für den Bericht benötigten WiBA-Daten.

    Robust: fehlende Werte werden zu leeren Strings / 0; nichts wirft None-Fehler.
    """
    projekt = wdb.load_projekt(db_path, projekt_name) or {}
    themen = wdb.list_themen(db_path) or []
    fragen = wdb.list_prueffragen(db_path) or []
    antworten = wdb.load_antworten(db_path, projekt_name) or {}
    reife = wdb.compute_reifegrad(db_path, projekt_name) or {}
    cat = wdb.catalog_meta(db_path) or {}

    fragen_by_theme: dict[str, list[dict[str, Any]]] = {}
    for f in fragen:
        fragen_by_theme.setdefault(str(f.get("theme_key") or ""), []).append(f)

    reife_themen = reife.get("themen") or {}

    themen_out: list[dict[str, Any]] = []
    offene_punkte: list[dict[str, Any]] = []
    beantwortet = 0
    offen = 0

    for t in themen:
        tk = str(t.get("theme_key") or "")
        tinfo = reife_themen.get(tk, {})
        rows: list[dict[str, Any]] = []
        for f in sorted(fragen_by_theme.get(tk, []), key=lambda x: x.get("nr", 0) or 0):
            cid = str(f.get("control_id") or "")
            a = antworten.get(cid, {})
            st = normalize_status(a.get("status"))
            notiz = str(a.get("notiz") or "")
            rows.append({
                "nr": f.get("nr", 0) or 0,
                "control_id": cid,
                "frage": str(f.get("frage") or ""),
                "status": st,
                "notiz": notiz,
            })
            if st in ("ja", "nein"):
                beantwortet += 1
            elif st == "offen":
                offen += 1
            if st == "nein":
                offene_punkte.append({
                    "theme": str(t.get("titel") or tk),
                    "nr": f.get("nr", 0) or 0,
                    "control_id": cid,
                    "frage": str(f.get("frage") or ""),
                    "notiz": notiz,
                    "verantwortlich": str(a.get("verantwortlich") or ""),
                    "zieldatum": str(a.get("zieldatum") or ""),
                })
        themen_out.append({
            "theme_key": tk,
            "titel": str(t.get("titel") or tk),
            "bausteine": str(t.get("bausteine") or ""),
            "pct": float(tinfo.get("pct", 0.0) or 0.0),
            "prueffragen": rows,
        })

    return {
        "projekt": {
            "name": str(projekt.get("name") or projekt_name),
            "unternehmen": str(projekt.get("unternehmen") or ""),
            "berater": str(projekt.get("berater") or ""),
            "beschreibung": str(projekt.get("beschreibung") or ""),
        },
        "gesamt_pct": float(reife.get("gesamt_pct", 0.0) or 0.0),
        "beantwortet": beantwortet,
        "offen": offen,
        "katalog_version": str(cat.get("version") or "–"),
        "themen": themen_out,
        "offene_punkte": offene_punkte,
    }


# ── DOCX-Helfer ───────────────────────────────────────────────────────────────

def _set_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), _hex_to_word(fill))
    tc_pr.append(shd)


def _set_border(cell, color: str = "DDDDDD") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = tc_pr.first_child_found_in("w:tcBorders")
    if tc_borders is None:
        tc_borders = OxmlElement("w:tcBorders")
        tc_pr.append(tc_borders)
    for edge in ("top", "left", "bottom", "right"):
        el = tc_borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            tc_borders.append(el)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), color.lstrip("#"))


def _banner(doc, text: str, bg: str, fg: str = "#FFFFFF", size: int = 14) -> None:
    tbl = doc.add_table(rows=1, cols=1)
    cell = tbl.cell(0, 0)
    _set_shading(cell, bg)
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(size)
    r, g, b = _hex_to_rgb(fg)
    run.font.color.rgb = RGBColor(r, g, b)


def _section_heading(doc, text: str, color: str = _BSI_BLUE) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(13)
    r, g, b = _hex_to_rgb(color)
    run.font.color.rgb = RGBColor(r, g, b)
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)


# ── DOCX-Export ───────────────────────────────────────────────────────────────

def export_report_docx(out_dir: Path, projekt_name: str, db_path: Path, **opts: Any) -> Path:
    """Erzeugt den WiBA-Nachweis als .docx und gibt den Pfad zurück."""
    out_dir = Path(out_dir)
    db_path = Path(db_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (
        f"WiBA_Nachweis_{_safe_filename(projekt_name)}_{date.today().isoformat()}.docx"
    )

    data = _collect(db_path, projekt_name)
    proj = data["projekt"]
    gesamt = data["gesamt_pct"]
    ampel = _ampel_color(gesamt)

    doc = Document()
    from shared.reports.docx_pdf import set_a4 as _a4; _a4(doc)  # #1614 A4
    sec = doc.sections[0]
    sec.top_margin = Inches(0.7)
    sec.bottom_margin = Inches(0.7)
    sec.left_margin = Inches(0.85)
    sec.right_margin = Inches(0.85)

    # ── 1. Deckblatt ──────────────────────────────────────────────────────────
    _banner(doc, "NACHWEIS SICHERER IT-BETRIEB", _BSI_BLUE, size=22)
    _banner(doc, "BSI WiBA  ·  Weg in die Basis-Absicherung", _DARK, size=11)

    meta_pairs = [
        ("Projekt:", proj["name"] or "–"),
        ("Unternehmen:", proj["unternehmen"] or "–"),
        ("Berater:", proj["berater"] or "–"),
        ("Berichtsdatum:", date.today().strftime("%d.%m.%Y")),
        ("Katalog-Version:", data["katalog_version"] or "–"),
    ]
    meta_tbl = doc.add_table(rows=len(meta_pairs), cols=2)
    for i, (label, value) in enumerate(meta_pairs):
        c0, c1 = meta_tbl.cell(i, 0), meta_tbl.cell(i, 1)
        _set_shading(c0, _BSI_BLUE)
        _set_shading(c1, _SOFT)
        r0 = c0.paragraphs[0].add_run(label)
        r0.bold = True
        r0.font.size = Pt(10)
        r0.font.color.rgb = RGBColor(255, 255, 255)
        c1.paragraphs[0].add_run(value).font.size = Pt(10)

    if proj["beschreibung"]:
        doc.add_paragraph()
        doc.add_paragraph(proj["beschreibung"]).runs[0].font.size = Pt(10)

    # ── 2. Management-Summary ─────────────────────────────────────────────────
    doc.add_page_break()
    _banner(doc, "1  MANAGEMENT-SUMMARY", _BSI_BLUE)

    summary_tbl = doc.add_table(rows=1, cols=3)
    kpis = [
        ("Gesamt-Reifegrad", f"{gesamt:.0f}%", ampel),
        ("Beantwortet", str(data["beantwortet"]), _BSI_BLUE),
        ("Offen", str(data["offen"]), _AMPEL_ORANGE),
    ]
    for i, (label, value, color) in enumerate(kpis):
        cell = summary_tbl.cell(0, i)
        _set_shading(cell, color)
        _set_border(cell, "FFFFFF")
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(6)
        a = p.add_run(label + "\n")
        a.font.size = Pt(9)
        a.font.color.rgb = RGBColor(220, 220, 220)
        b = p.add_run(value)
        b.bold = True
        b.font.size = Pt(20)
        b.font.color.rgb = RGBColor(255, 255, 255)

    doc.add_paragraph()
    _section_heading(doc, "Reifegrad je Thema")
    for t in data["themen"]:
        line = f"{t['titel']}  —  {t['pct']:.0f}%"
        if t["bausteine"]:
            line += f"   ({t['bausteine']})"
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(line).font.size = Pt(9)

    # ── 3. Themen + Prüffragen ────────────────────────────────────────────────
    for t in data["themen"]:
        doc.add_page_break()
        _banner(doc, f"{t['titel']}  ·  Reifegrad: {t['pct']:.0f}%", _BSI_BLUE)
        if t["bausteine"]:
            _banner(doc, f"BSI-Bausteine: {t['bausteine']}", _SOFT, _BSI_BLUE, size=9)
        doc.add_paragraph()

        tbl = doc.add_table(rows=1, cols=4)
        for i, hdr in enumerate(("Nr", "Frage", "Status", "Notiz")):
            cell = tbl.cell(0, i)
            _set_shading(cell, _BSI_BLUE)
            run = cell.paragraphs[0].add_run(hdr)
            run.bold = True
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(255, 255, 255)
        for i, w in enumerate([0.5, 3.4, 1.2, 1.9]):
            tbl.columns[i].width = Inches(w)

        if not t["prueffragen"]:
            row = tbl.add_row().cells
            for cell in row:
                _set_border(cell)
            row[1].paragraphs[0].add_run("Keine Prüffragen im Katalog.").font.size = Pt(8)

        for ridx, q in enumerate(t["prueffragen"]):
            row = tbl.add_row().cells
            row_bg = _SOFT if ridx % 2 == 0 else "#FFFFFF"
            for cell in row:
                _set_border(cell)
                _set_shading(cell, row_bg)
            row[0].paragraphs[0].add_run(str(q["nr"])).font.size = Pt(8)
            r1 = row[1].paragraphs[0].add_run(q["frage"][:400])
            r1.font.size = Pt(8)
            sfarbe = _status_color(q["status"])
            _set_shading(row[2], sfarbe)
            r2 = row[2].paragraphs[0].add_run(_status_label(q["status"]))
            r2.font.size = Pt(8)
            r2.bold = True
            r2.font.color.rgb = RGBColor(255, 255, 255)
            row[3].paragraphs[0].add_run((q["notiz"] or "–")[:300]).font.size = Pt(8)

    # ── 4. Offene Punkte / Maßnahmen ──────────────────────────────────────────
    doc.add_page_break()
    _banner(doc, "OFFENE PUNKTE / MAẞNAHMEN", _AMPEL_RED)
    doc.add_paragraph(
        "Die folgenden Prüffragen wurden mit „Nein“ beantwortet und erfordern "
        "Maßnahmen zur Erreichung der BSI-Basis-Absicherung."
    ).runs[0].font.size = Pt(10)
    doc.add_paragraph()

    if not data["offene_punkte"]:
        p = doc.add_paragraph("Keine offenen Punkte (Status „Nein“) erfasst.")
        p.runs[0].font.size = Pt(10)
        p.runs[0].italic = True
    else:
        ma_tbl = doc.add_table(rows=1, cols=5)
        for i, hdr in enumerate(("Thema / Nr", "Frage", "Notiz", "Verantwortlich", "Zieldatum")):
            cell = ma_tbl.cell(0, i)
            _set_shading(cell, _AMPEL_RED)
            run = cell.paragraphs[0].add_run(hdr)
            run.bold = True
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(255, 255, 255)
        for i, w in enumerate([1.3, 2.6, 1.7, 1.1, 0.9]):
            ma_tbl.columns[i].width = Inches(w)

        for ridx, op in enumerate(data["offene_punkte"]):
            row = ma_tbl.add_row().cells
            row_bg = "#FFF3E0" if ridx % 2 == 0 else "#FFFFFF"
            for cell in row:
                _set_border(cell)
                _set_shading(cell, row_bg)
            row[0].paragraphs[0].add_run(
                f"{op['theme']}\n#{op['nr']}").font.size = Pt(8)
            row[1].paragraphs[0].add_run(op["frage"][:300]).font.size = Pt(8)
            row[2].paragraphs[0].add_run((op["notiz"] or "–")[:250]).font.size = Pt(8)
            row[3].paragraphs[0].add_run(op["verantwortlich"] or "–").font.size = Pt(8)
            row[4].paragraphs[0].add_run(op["zieldatum"] or "–").font.size = Pt(8)

    doc.add_paragraph()
    _banner(doc, "Hinweis", "#455a64", size=9)
    disc = doc.add_paragraph(
        "Dieser Nachweis dokumentiert den Stand der WiBA-Selbstprüfung zum "
        "Berichtsdatum. Er ersetzt keine formale Zertifizierung nach "
        "ISO/IEC 27001 oder BSI IT-Grundschutz."
    )
    disc.runs[0].font.size = Pt(9)
    disc.runs[0].italic = True

    doc.save(str(out_path))
    return out_path


# ── PDF-Export (PIL-Render, analog cra/report_export.py) ──────────────────────

def _fit_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for para in str(text).splitlines() or [""]:
        words = para.split() or [""]
        cur = ""
        for word in words:
            trial = (cur + " " + word).strip()
            if draw.textlength(trial, font=font) <= max_width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        lines.append(cur)
    return lines or [""]


def export_report_pdf(**kwargs) -> Path:
    """#1614: PDF vektoriell aus dem DOCX (A4) statt Rasterbild."""
    from shared.reports.docx_pdf import docx_to_pdf_bytes
    docx_path = export_report_docx(**kwargs)
    pdf_path = Path(docx_path).with_suffix(".pdf")
    pdf_path.write_bytes(docx_to_pdf_bytes(docx_path))
    return pdf_path
