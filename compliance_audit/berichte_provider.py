"""Compliance-Audit-Adapter für das geteilte Berichts-Center (#1725).

Liefert Katalog, Render-Callable und den Kontext für die KI-Zusammenfassung — nach
demselben Muster wie CRA/NIS2/DSGVO/WiBA. Die Typ-IDs sind modulübergreifend
identisch (#1502/#1504): ``gesamt``, ``anforderungen``, ``massnahmen``. Nur die
Labels sind fachlich: Im Audit heißen „Anforderungen" **Fragen**.

Grundlage jedes Berichts ist der **berechnete** Compliance-Stand aus
:mod:`compliance_audit.status` — derselbe, den die Wasserstandsmeldung ausweist.
So können Bericht und Meldung nicht auseinanderlaufen, und die Stufe im Bericht
ist ebenso reproduzierbar wie dort.

Liegt ein KI-Entwurf vor (``gutachten_drafts``, erzeugt über
``/bericht/{prompt,import}``), übernimmt der Gesamtbericht dessen Formulierungen
(Zusammenfassung, Einordnung je Framework, Maßnahmen). Ohne Entwurf entsteht der
Bericht rein aus den Daten — er ist also nie von einem KI-Lauf abhängig.
"""
from __future__ import annotations

import json
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from shared.reports.core import ReportSpec

DB_PATH = Path('data/db/gutachten.sqlite')

CATALOG: list[ReportSpec] = [
    ReportSpec('gesamt', 'Auditbericht (Gesamt)', 'Framework-abhängig',
               'Vollständiger Auditbericht: Compliance-Stand, Einordnung je Framework, '
               'Feststellungen und Maßnahmen. Nutzt den KI-Entwurf, wenn vorhanden.'),
    ReportSpec('anforderungen', 'Fragen-Status', 'Framework-abhängig',
               'Alle Prüffragen je Framework mit Antwort und Erfüllung — ohne '
               'Maßnahmenteil.'),
    ReportSpec('massnahmen', 'Maßnahmenplan', 'Framework-abhängig',
               'Lücken (nicht erfüllt, teilweise, offen) als Maßnahmenplan, '
               'nach Dringlichkeit sortiert.'),
]

#: Anzeigetexte der Erfüllung im Bericht.
_ERF_LABEL = {
    'erfuellt': 'erfüllt',
    'teilweise': 'teilweise erfüllt',
    'nicht_erfuellt': 'nicht erfüllt',
    'nicht_anwendbar': 'nicht anwendbar',
    'offen': 'offen',
}


def catalog() -> list[ReportSpec]:
    return CATALOG


# ── Datenbeschaffung ─────────────────────────────────────────────────────────

def _sammeln(projekt: str) -> dict[str, Any]:
    """Projekt, Fragen, berechneter Stand und KI-Entwurf in einem Zug."""
    from gutachten.db import load_project, load_questions, load_gutachten_draft

    from compliance_audit.status import build_status, erfuellung_of

    proj = load_project(DB_PATH, projekt) or {}
    fragen = load_questions(DB_PATH, projekt)
    stand = build_status(fragen)

    entwurf: dict[str, Any] = {}
    roh = load_gutachten_draft(DB_PATH, projekt)
    if roh:
        try:
            geladen = json.loads(roh)
            if isinstance(geladen, dict):
                entwurf = geladen
        except (ValueError, TypeError):
            entwurf = {}   # kaputter Entwurf darf den Bericht nicht verhindern

    # Fragen je Framework, Reihenfolge wie im Projekt
    nach_fw: dict[str, list[dict[str, Any]]] = {}
    for q in fragen:
        nach_fw.setdefault(str(q.get('framework') or '(ohne Framework)'), []).append(q)
    for liste in nach_fw.values():
        liste.sort(key=lambda q: (str(q.get('section_ref') or ''),
                                  q.get('question_num') or 0))

    return {'projekt': proj, 'fragen': fragen, 'stand': stand, 'entwurf': entwurf,
            'nach_framework': nach_fw, 'erfuellung_of': erfuellung_of}


def _dokument(titel: str, proj: dict[str, Any], stand: dict[str, Any]):
    """Neues DOCX mit Kopf, A4 und Basis-Schrift (#1617)."""
    from docx import Document

    from shared.reports.docx_pdf import apply_base_font, set_a4

    doc = Document()
    set_a4(doc)
    apply_base_font(doc)

    doc.add_heading(f"{titel} — {proj.get('name', '')}", level=0)
    doc.add_paragraph(f"Erstellt: {date.today().strftime('%d.%m.%Y')}")

    meta = doc.add_paragraph()
    meta.add_run('Unternehmen: ').bold = True
    meta.add_run(f"{proj.get('unternehmen') or '—'}\n")
    meta.add_run('Frameworks: ').bold = True
    meta.add_run(f"{', '.join(proj.get('frameworks') or []) or '—'}\n")
    meta.add_run('Compliance-Stand: ').bold = True
    meta.add_run(f"{stand.get('label')} ({stand.get('quote_prozent')} % Erfüllungsquote)")
    if proj.get('pruefungsfokus'):
        fokus = doc.add_paragraph()
        fokus.add_run('Prüfungsfokus: ').bold = True
        fokus.add_run(str(proj['pruefungsfokus'])[:2000])
    return doc


def _stand_tabelle(doc, stand: dict[str, Any]) -> None:
    """Kennzahlen + Stufe je Framework."""
    f = stand.get('fragen') or {}
    doc.add_heading('Compliance-Stand', level=1)
    doc.add_paragraph(
        f"{f.get('gesamt', 0)} Fragen · {f.get('erfuellt', 0)} erfüllt · "
        f"{f.get('teilweise', 0)} teilweise · {f.get('nicht_erfuellt', 0)} nicht erfüllt · "
        f"{f.get('offen', 0)} offen · {f.get('nicht_anwendbar', 0)} nicht anwendbar")
    doc.add_paragraph(
        f"Abdeckung {stand.get('abdeckung_prozent')} % — offene Fragen zählen in der "
        'Quote als nicht nachgewiesen. Quote nur der bewerteten Fragen: '
        f"{stand.get('quote_bewertet_prozent')} %.")

    fws = stand.get('frameworks') or []
    if not fws:
        return
    tbl = doc.add_table(rows=len(fws) + 1, cols=4)
    tbl.style = 'Light Grid Accent 1'
    for ci, hdr in enumerate(['Framework', 'Stufe', 'Quote', 'offen / anwendbar']):
        tbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
    for ri, fw in enumerate(fws, start=1):
        ff = fw.get('fragen') or {}
        tbl.cell(ri, 0).text = str(fw.get('framework', ''))
        tbl.cell(ri, 1).text = str(fw.get('label', ''))
        tbl.cell(ri, 2).text = f"{fw.get('quote_prozent')} %"
        tbl.cell(ri, 3).text = f"{ff.get('offen', 0)} / {ff.get('anwendbar', 0)}"


# ── Berichtstypen ────────────────────────────────────────────────────────────

def _fragen_docx(projekt: str) -> bytes:
    d = _sammeln(projekt)
    doc = _dokument('Fragen-Status', d['projekt'], d['stand'])
    _stand_tabelle(doc, d['stand'])

    for fw, fragen in d['nach_framework'].items():
        doc.add_heading(fw, level=1)
        tbl = doc.add_table(rows=len(fragen) + 1, cols=4)
        tbl.style = 'Light Grid Accent 1'
        for ci, hdr in enumerate(['Fundstelle', 'Frage', 'Antwort', 'Erfüllung']):
            tbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
        for ri, q in enumerate(fragen, start=1):
            tbl.cell(ri, 0).text = str(q.get('section_ref') or '')[:60]
            tbl.cell(ri, 1).text = str(q.get('frage') or '')[:500]
            tbl.cell(ri, 2).text = str(q.get('antwort') or '')[:800] or '—'
            tbl.cell(ri, 3).text = _ERF_LABEL.get(d['erfuellung_of'](q), 'offen')

    from shared.reports.docx_pdf import fit_tables
    fit_tables(doc)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _massnahmen_docx(projekt: str) -> bytes:
    d = _sammeln(projekt)
    doc = _dokument('Maßnahmenplan', d['projekt'], d['stand'])

    # Zuerst die KI-Maßnahmen aus dem Entwurf, falls vorhanden — sie sind
    # priorisiert und begruendet.
    empf = d['entwurf'].get('handlungsempfehlungen') or []
    if empf:
        doc.add_heading('Empfohlene Maßnahmen', level=1)
        tbl = doc.add_table(rows=len(empf) + 1, cols=4)
        tbl.style = 'Light Grid Accent 1'
        for ci, hdr in enumerate(['Maßnahme', 'Priorität', 'Aufwand', 'Begründung']):
            tbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
        for ri, m in enumerate(empf, start=1):
            if not isinstance(m, dict):
                m = {'massnahme': str(m)}
            tbl.cell(ri, 0).text = str(m.get('massnahme', ''))[:400]
            tbl.cell(ri, 1).text = str(m.get('prioritaet', '') or '—')
            tbl.cell(ri, 2).text = str(m.get('aufwand', '') or '—')
            tbl.cell(ri, 3).text = str(m.get('begruendung', ''))[:600]

    luecken = d['stand'].get('luecken') or []
    doc.add_heading('Offene Punkte aus dem Fragenkatalog', level=1)
    if not luecken:
        doc.add_paragraph('Keine Lücken — alle anwendbaren Fragen sind erfüllt.')
    else:
        doc.add_paragraph(
            f"{len(luecken)} Punkte, sortiert nach Dringlichkeit "
            '(nicht erfüllt, dann teilweise, dann offen).')
        tbl = doc.add_table(rows=len(luecken) + 1, cols=4)
        tbl.style = 'Light Grid Accent 1'
        for ci, hdr in enumerate(['Framework', 'Fundstelle', 'Frage', 'Status']):
            tbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
        for ri, lk in enumerate(luecken, start=1):
            tbl.cell(ri, 0).text = str(lk.get('framework', ''))
            tbl.cell(ri, 1).text = str(lk.get('section_ref', ''))[:60]
            tbl.cell(ri, 2).text = str(lk.get('frage', ''))[:500]
            tbl.cell(ri, 3).text = _ERF_LABEL.get(lk.get('erfuellung'), '')

    from shared.reports.docx_pdf import fit_tables
    fit_tables(doc)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _gesamt_docx(projekt: str) -> bytes:
    d = _sammeln(projekt)
    e = d['entwurf']
    doc = _dokument('Auditbericht', d['projekt'], d['stand'])

    if e.get('gesamtbewertung'):
        doc.add_heading('Gesamtbewertung', level=1)
        doc.add_paragraph(str(e['gesamtbewertung']))
    if e.get('zusammenfassung'):
        doc.add_heading('Zusammenfassung', level=1)
        doc.add_paragraph(str(e['zusammenfassung']))
        doc.add_paragraph('🤖 KI-generiert — fachlich zu prüfen.').italic = True
    elif not e:
        doc.add_heading('Zusammenfassung', level=1)
        doc.add_paragraph(
            'Für dieses Audit liegt noch kein ausformulierter Entwurf vor. Der Bericht '
            'enthält den berechneten Stand und die Datenlage; die Einordnung lässt sich '
            'im Bericht-Tab erzeugen („Auditbericht erzeugen").')

    _stand_tabelle(doc, d['stand'])

    for fw in e.get('framework_bewertungen') or []:
        if not isinstance(fw, dict):
            continue
        doc.add_heading(str(fw.get('framework', '')), level=1)
        if fw.get('bewertung'):
            doc.add_paragraph(str(fw['bewertung']))
        for titel, schluessel in (('Stärken', 'staerken'), ('Lücken', 'luecken')):
            werte = fw.get(schluessel) or []
            if werte:
                doc.add_heading(titel, level=2)
                for w in werte:
                    doc.add_paragraph(str(w), style='List Bullet')

    empf = e.get('handlungsempfehlungen') or []
    if empf:
        doc.add_heading('Handlungsempfehlungen', level=1)
        tbl = doc.add_table(rows=len(empf) + 1, cols=4)
        tbl.style = 'Light Grid Accent 1'
        for ci, hdr in enumerate(['Maßnahme', 'Priorität', 'Aufwand', 'Begründung']):
            tbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
        for ri, m in enumerate(empf, start=1):
            if not isinstance(m, dict):
                m = {'massnahme': str(m)}
            tbl.cell(ri, 0).text = str(m.get('massnahme', ''))[:400]
            tbl.cell(ri, 1).text = str(m.get('prioritaet', '') or '—')
            tbl.cell(ri, 2).text = str(m.get('aufwand', '') or '—')
            tbl.cell(ri, 3).text = str(m.get('begruendung', ''))[:600]

    # Datenlage immer anhaengen — der Bericht soll ohne Rueckfragen pruefbar sein.
    doc.add_heading('Anhang: Fragen und Antworten', level=1)
    for fw, fragen in d['nach_framework'].items():
        doc.add_heading(fw, level=2)
        tbl = doc.add_table(rows=len(fragen) + 1, cols=4)
        tbl.style = 'Light Grid Accent 1'
        for ci, hdr in enumerate(['Fundstelle', 'Frage', 'Antwort', 'Erfüllung']):
            tbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
        for ri, q in enumerate(fragen, start=1):
            tbl.cell(ri, 0).text = str(q.get('section_ref') or '')[:60]
            tbl.cell(ri, 1).text = str(q.get('frage') or '')[:500]
            tbl.cell(ri, 2).text = str(q.get('antwort') or '')[:800] or '—'
            tbl.cell(ri, 3).text = _ERF_LABEL.get(d['erfuellung_of'](q), 'offen')

    if e.get('fazit'):
        doc.add_heading('Fazit', level=1)
        doc.add_paragraph(str(e['fazit']))

    from shared.reports.docx_pdf import fit_tables
    fit_tables(doc)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


_BAUER = {
    'gesamt': _gesamt_docx,
    'anforderungen': _fragen_docx,
    'massnahmen': _massnahmen_docx,
}


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, **_ctx: Any) -> bytes:
    """Bericht als DOCX- oder PDF-Bytes (kein Zeitraum — ein Audit ist ein Stand)."""
    bauer = _BAUER.get(typ)
    if bauer is None:
        raise ValueError(f'Unbekannter Berichtstyp: {typ}')
    docx_bytes = bauer(projekt)
    if fmt == 'pdf':
        from shared.reports.docx_pdf import docx_bytes_to_pdf
        return docx_bytes_to_pdf(docx_bytes)
    return docx_bytes


def summary_context(projekt: str) -> dict[str, Any]:
    """Kontext für die geteilte KI-Zusammenfassung des Berichts-Centers.

    Bewusst knapp und ohne Freitext-Antworten: Die Zusammenfassung soll den Stand
    einordnen, nicht die Rohdaten wiederholen.
    """
    d = _sammeln(projekt)
    stand = d['stand']
    return {
        'modul': 'Compliance-Audit',
        'projekt': projekt,
        'unternehmen': d['projekt'].get('unternehmen', ''),
        'frameworks': d['projekt'].get('frameworks') or [],
        'pruefungsfokus': d['projekt'].get('pruefungsfokus', ''),
        'stufe': stand.get('label'),
        'quote_prozent': stand.get('quote_prozent'),
        'abdeckung_prozent': stand.get('abdeckung_prozent'),
        'fragen': stand.get('fragen'),
        'je_framework': [
            {'framework': fw.get('framework'), 'stufe': fw.get('label'),
             'quote_prozent': fw.get('quote_prozent')}
            for fw in (stand.get('frameworks') or [])
        ],
        'luecken_anzahl': len(stand.get('luecken') or []),
        'top_luecken': [
            {'framework': lk.get('framework'), 'fundstelle': lk.get('section_ref'),
             'frage': lk.get('frage'), 'status': lk.get('erfuellung')}
            for lk in (stand.get('luecken') or [])[:15]
        ],
    }
