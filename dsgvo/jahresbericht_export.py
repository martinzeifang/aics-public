"""DS-J2 (#1133) — Jahresbericht-Export (DOCX + PDF).

Rendert den aggregierten Jahresbericht-Kontext (dsgvo/jahresbericht.py) als DOCX;
PDF über den zentralen Konverter (Gotenberg/soffice).
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from dsgvo.jahresbericht import build_jahresbericht_context
from shared.reports import texte as _rt

#: Die Texte des Jahresberichts je Sprache (#1954).
#:
#: Der Jahresbericht wird von der Geschäftsführung freigegeben und von der
#: DSB-Rolle signiert (#1132–#1134) — er ist ein Dokument des **Mandanten**,
#: also entscheidet ``firmen.sprache`` über seine Sprache. Die deutschen Werte
#: sind zeichengenau die aus 8.3.4, einschließlich des Halbgeviertstrichs in
#: „Art. 15–22" und des Leerzeichens vor dem Prozentzeichen.
#:
#: Artikelangaben bleiben unverändert; auf Englisch heißt die Verordnung
#: amtlich „GDPR" und die DSFA „DPIA" (Begriffsliste #1954).
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        "leer": "— keine Einträge —",
        "titel": "Datenschutz-Jahresbericht {jahr}",
        "organisation": "Organisation: {wert}",
        "projekt": "Projekt: {wert}",
        "beratung": "Datenschutzberatung: {wert}",
        "erstellt_am": "Erstellt am: {wert}",

        "h1": "1. Management-Summary",
        "summary": (
            "Im Berichtsjahr wurden {gesamt} Datenschutz-Kontrollen geplant, "
            "davon {abgeschlossen} abgeschlossen. "
            "TOM-Reifegrad: {tom} %. "
            "DSFAs: {dsfa}, Datenpannen: {pannen}, "
            "Betroffenenrechte-Anträge: {betroffenenrechte}, "
            "offene Risiken (firmenweit): {risiken}."),

        "h2": "2. Durchgeführte Kontrollen",
        "k_bereich": "Bereich",
        "k_titel": "Titel",
        "k_status": "Status",
        "k_durchgefuehrt": "Durchgeführt",
        "k_ergebnis": "Ergebnis",

        "h3": "3. Datenschutz-Folgenabschätzungen (DSFA)",
        "d_id": "ID",
        "d_titel": "Titel",
        "d_restrisiko": "Restrisiko",
        "d_status": "Status",
        "d_review": "Review",

        "h4": "4. Datenpannen (Art. 33/34)",
        "p_art": "Art",
        "p_risiko": "Risiko",
        "p_status": "Status",

        "h5": "5. Betroffenenrechte (Art. 15–22)",
        "b_antrag": "Antrag",
        "b_typ": "Typ",
        "b_status": "Status",
        "b_eingang": "Eingang",

        "h6": "6. Einwilligungs-Widerrufe (Art. 7)",
        "e_id": "ID",
        "e_zweck": "Zweck",
        "e_status": "Status",

        "h7": "7. Offene Risiken (firmenweit)",
        "r_quelle": "Quelle",
        "r_titel": "Titel",
        "r_schwere": "Schwere",
        "r_projekt": "Projekt",

        "h8": "8. Freigabe & Signatur",
        "signoff_status": "Status: {wert}",
        "freigegeben": "Freigegeben (Geschäftsführung): {von} am {am}",
        "signiert": "Signiert (Datenschutzbeauftragte:r): {name} am {am}",
        "hash": "Dokument-Hash (SHA-256): {wert}",
    },
    "en": {
        "leer": "— no entries —",
        "titel": "Annual data protection report {jahr}",
        "organisation": "Organisation: {wert}",
        "projekt": "Project: {wert}",
        "beratung": "Data protection advice: {wert}",
        "erstellt_am": "Created on: {wert}",

        "h1": "1. Management summary",
        "summary": (
            "In the reporting year {gesamt} data protection controls were "
            "planned, {abgeschlossen} of which were completed. "
            "TOM maturity: {tom} %. "
            "DPIAs: {dsfa}, personal data breaches: {pannen}, "
            "data subject requests: {betroffenenrechte}, "
            "open risks (company-wide): {risiken}."),

        "h2": "2. Controls carried out",
        "k_bereich": "Area",
        "k_titel": "Title",
        "k_status": "Status",
        "k_durchgefuehrt": "Carried out",
        "k_ergebnis": "Result",

        "h3": "3. Data protection impact assessments (DPIA)",
        "d_id": "ID",
        "d_titel": "Title",
        "d_restrisiko": "Residual risk",
        "d_status": "Status",
        "d_review": "Review",

        "h4": "4. Personal data breaches (Art. 33/34)",
        "p_art": "Nature",
        "p_risiko": "Risk",
        "p_status": "Status",

        "h5": "5. Data subject rights (Art. 15–22)",
        "b_antrag": "Request",
        "b_typ": "Type",
        "b_status": "Status",
        "b_eingang": "Received",

        "h6": "6. Withdrawals of consent (Art. 7)",
        "e_id": "ID",
        "e_zweck": "Purpose",
        "e_status": "Status",

        "h7": "7. Open risks (company-wide)",
        "r_quelle": "Source",
        "r_titel": "Title",
        "r_schwere": "Severity",
        "r_projekt": "Project",

        "h8": "8. Approval & signature",
        "signoff_status": "Status: {wert}",
        "freigegeben": "Approved (management): {von} on {am}",
        "signiert": "Signed (data protection officer): {name} on {am}",
        "hash": "Document hash (SHA-256): {wert}",
    },
}

_t = _rt.macher(TEXTE)


def _h(doc, text, level=1):
    doc.add_heading(text, level=level)


def _table(doc, headers, rows, sp: str = "de"):
    if not rows:
        doc.add_paragraph(_t(sp, "leer"))
        return
    t = doc.add_table(rows=1, cols=len(headers))
    try:
        t.style = "Light Grid Accent 1"
    except Exception:  # noqa: BLE001
        pass
    for i, hh in enumerate(headers):
        t.rows[0].cells[i].text = str(hh)
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = "" if v is None else str(v)


def build_docx_bytes(ctx: dict[str, Any], *, sprache: str | None = None) -> bytes:
    """Jahresbericht als DOCX — in der Sprache des Mandanten (#1954).

    Die Sprache wird **hier** aufgelöst und nicht vom Aufrufer erwartet: Diese
    Funktion ist der Renderer, und sie hat mit ``ctx['projekt']['name']`` alles
    in der Hand, was dafür nötig ist (Regel 3 des Vorgangs). Ein Aufrufer, der
    nichts angibt, verhält sich damit unverändert.
    """
    from docx import Document
    doc = Document()
    p = ctx.get("projekt", {})
    sp = _rt.aufloesen("dsgvo", p.get("name") or "", sprache)
    if sp != "de":
        # Dokumentsprache (`w:lang`) nur bei abweichender Sprache: Für Deutsch
        # war sie vor #1954 nicht gesetzt, und „auf Deutsch byte-identisch" ist
        # der Regressionsschutz dieses Vorgangs.
        from shared.reports.docx_pdf import set_doc_lang
        set_doc_lang(doc, sp)
    doc.add_heading(_t(sp, "titel", jahr=ctx.get("jahr", "")), level=0)
    doc.add_paragraph(_t(sp, "organisation",
                         wert=p.get("unternehmen") or p.get("name", "")))
    doc.add_paragraph(_t(sp, "projekt", wert=p.get("name", "")))
    if p.get("berater"):
        doc.add_paragraph(_t(sp, "beratung", wert=p["berater"]))
    doc.add_paragraph(_t(sp, "erstellt_am", wert=ctx.get("erstellt_am", "")))

    m = ctx.get("meta", {})
    _h(doc, _t(sp, "h1"), 1)
    ks = ctx.get("kontrollen_summary", {})
    doc.add_paragraph(_t(
        sp, "summary",
        gesamt=ks.get("gesamt", 0),
        abgeschlossen=ks.get("abgeschlossen", 0),
        tom=m.get("tom_reifegrad", 0),
        dsfa=m.get("anzahl_dsfa", 0),
        pannen=m.get("anzahl_datenpannen", 0),
        betroffenenrechte=m.get("anzahl_betroffenenrechte", 0),
        risiken=m.get("anzahl_risiken", 0)))

    _h(doc, _t(sp, "h2"), 1)
    _table(doc, [_t(sp, "k_bereich"), _t(sp, "k_titel"), _t(sp, "k_status"),
                 _t(sp, "k_durchgefuehrt"), _t(sp, "k_ergebnis")],
           [[k["bereich"], k["titel"], k["status"], k["durchgefuehrt_am"], k["ergebnis"]]
            for k in ctx.get("kontrollen", [])], sp)

    _h(doc, _t(sp, "h3"), 1)
    _table(doc, [_t(sp, "d_id"), _t(sp, "d_titel"), _t(sp, "d_restrisiko"),
                 _t(sp, "d_status"), _t(sp, "d_review")],
           [[d.get("dpia_id"), d.get("titel"), d.get("restrisiko"), d.get("status"),
             d.get("naechstes_review")] for d in ctx.get("dsfa", [])], sp)

    _h(doc, _t(sp, "h4"), 1)
    _table(doc, [_t(sp, "p_art"), _t(sp, "p_risiko"), _t(sp, "p_status")],
           [[d.get("art"), d.get("risikoeinschaetzung"), d.get("status")]
            for d in ctx.get("datenpannen", [])], sp)

    _h(doc, _t(sp, "h5"), 1)
    _table(doc, [_t(sp, "b_antrag"), _t(sp, "b_typ"), _t(sp, "b_status"),
                 _t(sp, "b_eingang")],
           [[b.get("antrag_id"), b.get("typ"), b.get("status"), b.get("eingang_datum")]
            for b in ctx.get("betroffenenrechte", [])], sp)

    _h(doc, _t(sp, "h6"), 1)
    _table(doc, [_t(sp, "e_id"), _t(sp, "e_zweck"), _t(sp, "e_status")],
           [[e.get("einwilligung_id"), e.get("zweck"), e.get("status")]
            for e in ctx.get("einwilligung_widerrufe", [])], sp)

    _h(doc, _t(sp, "h7"), 1)
    _table(doc, [_t(sp, "r_quelle"), _t(sp, "r_titel"), _t(sp, "r_schwere"),
                 _t(sp, "r_projekt")],
           [[r.get("quelle"), r.get("titel"), r.get("schwere"), r.get("projekt")]
            for r in ctx.get("risiken", [])], sp)

    # Freigabe-/Signatur-Block
    so = ctx.get("signoff", {})
    _h(doc, _t(sp, "h8"), 1)
    # `status` ist ein **Datenwert** (entwurf/freigegeben/signiert) und bleibt
    # deshalb unübersetzt — er wird verglichen und gespeichert (Regel 7).
    doc.add_paragraph(_t(sp, "signoff_status", wert=so.get("status", "entwurf")))
    if so.get("freigabe_von"):
        doc.add_paragraph(_t(sp, "freigegeben", von=so["freigabe_von"],
                             am=so.get("freigabe_am", "")))
    if so.get("signatur_von"):
        doc.add_paragraph(_t(
            sp, "signiert",
            name=so.get("signatur_name") or so["signatur_von"],
            am=so.get("signatur_am", "")))
        if so.get("sha256"):
            doc.add_paragraph(_t(sp, "hash", wert=so["sha256"]))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_jahresbericht_docx(db_path: Path, projekt_name: str, jahr: int,
                            *, signoff: dict | None = None,
                            sprache: str | None = None) -> bytes:
    ctx = build_jahresbericht_context(db_path, projekt_name, jahr)
    if signoff:
        ctx["signoff"] = signoff
    return build_docx_bytes(ctx, sprache=sprache)


def build_jahresbericht_pdf(db_path: Path, projekt_name: str, jahr: int,
                           *, signoff: dict | None = None,
                           sprache: str | None = None) -> bytes:
    docx_bytes = build_jahresbericht_docx(db_path, projekt_name, jahr,
                                          signoff=signoff, sprache=sprache)
    from shared.templates.pdf_converter import convert_docx_to_pdf
    return convert_docx_to_pdf(docx_bytes)
