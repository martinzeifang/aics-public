"""Compliance-Audit-Adapter für das geteilte Berichts-Center (#1726).

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

DIE SPRACHE GEHÖRT DEM MANDANTEN (#1954)
Die Prosa dieses Adapters liegt in :data:`TEXTE` und wird in der Sprache des
Mandanten gedruckt (Modulschlüssel ``compliance_audit``). Drei Dinge bleiben
dabei bewusst **unberührt**:

* **Der gerechnete Stand.** Stufe, Quote und Erfüllungsgrade kommen aus
  :mod:`compliance_audit.status` und werden hier nur **durchgereicht**
  (``stand['label']``, ``ERFUELLUNG_LABELS``). Seit #1954 gibt es sie in
  beiden Sprachen (``status.labels(sprache)``); ``stand['label']`` kommt
  weiter gerechnet aus ``status.py`` und ist dort deutsch
  vorhanden — siehe Bericht zu #1954. Eine eigene englische Tabelle hier wäre
  eine zweite Quelle für dieselben Begriffe, die die Word-Vorlage
  (``compliance_audit/template_context.py``) anders lesen würde (#1731/#1735);
  und zwei Fassungen desselben Compliance-Stands sind zwei Wahrheiten
  (#1726/#1727).
* **Die Fragen, Antworten und Framework-Namen.** Sie stehen so in der Akte.
* **Der Marker „🤖 KI-generiert".** Er wird per Präfix aus Bestandstexten
  gelesen (``shared/ki_herkunft``) und bleibt deutsch, auch im englischen
  Dokument — wer die englische Fassung liest und danach in seiner Akte sucht,
  findet sonst nichts (BERICHTE.md, Regel 7). Übersetzt ist nur der Satz
  dahinter.
"""
from __future__ import annotations

import json
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from shared.reports import texte as _rt
from shared.reports.core import ReportSpec

DB_PATH = Path('data/db/gutachten.sqlite')

#: Modulschlüssel für die Sprachauflösung. So heißt das Modul in
#: ``shared/templates/schema.MODULE_DB`` (→ ``data/db/gutachten.sqlite``,
#: historischer Dateiname seit #1713), und von dort findet
#: ``shared/firmen_link.MODULE_PROJECT_TABLES`` die Projekt-Tabelle
#: ``gutachten_projects``. Der Paketname wäre hier derselbe — aber geprüft
#: wurde die Engine-Seite, denn sie entscheidet (die Lehre aus #1892).
MODUL = 'compliance_audit'

CATALOG: list[ReportSpec] = [
    ReportSpec('gesamt', 'Auditbericht (Gesamt)', 'Framework-abhängig',
               'Vollständiger Auditbericht: Compliance-Stand, Einordnung je Framework, '
               'Feststellungen und Maßnahmen. Nutzt den KI-Entwurf, wenn vorhanden.',
               titel_en='Audit report (complete)',
               beschreibung_en='Complete audit report: compliance status, '
                               'assessment per framework, findings and '
                               'measures. Uses the AI draft where available.',
               norm_en='depends on the framework'),
    ReportSpec('anforderungen', 'Fragen-Status', 'Framework-abhängig',
               'Alle Prüffragen je Framework mit Antwort und Erfüllung — ohne '
               'Maßnahmenteil.',
               titel_en='Question status',
               beschreibung_en='All test questions per framework with answer '
                               'and degree of fulfilment — without the '
                               'measures section.',
               norm_en='depends on the framework'),
    ReportSpec('massnahmen', 'Maßnahmenplan', 'Framework-abhängig',
               'Lücken (nicht erfüllt, teilweise, offen) als Maßnahmenplan, '
               'nach Dringlichkeit sortiert.',
               titel_en='Action plan',
               beschreibung_en='Gaps (not fulfilled, partially, open) as an '
                               'action plan, sorted by urgency.',
               norm_en='depends on the framework'),
]

#: Anzeigetexte der Erfüllung im Bericht — Quelle ist das Status-Modul (#1730),
#: damit Bericht und Word-Vorlage nicht auseinanderlaufen.
# #1954: `labels(sprache)` ist die eine Stelle, die über die Sprache
# entscheidet — zwei Konstanten im Aufrufer hiessen, dass jeder
# Renderer den Rückfall selbst wählt, und beim dritten weicht er ab.
from compliance_audit.status import (  # noqa: E402
    ERFUELLUNG_LABELS as _ERF_LABEL,
    labels as _stand_labels,
)

#: Die Prosa der drei Berichte je Sprache (#1954).
#:
#: Die deutschen Werte sind zeichengenau die aus 8.3.4. ``Erfüllungsgrad`` →
#: *degree of fulfilment*, ``Wasserstandsmeldung`` → *status report* und
#: ``vollständig/weitgehend/teilweise/nicht compliant`` →
#: *fully/largely/partially/not compliant* (Begriffsliste #1954) — Letztere
#: nur dort, wo **dieser** Adapter die Wörter selbst schreibt; die
#: **gerechneten** Stufen kommen weiter aus ``status.py`` (Modul-Kopf).
TEXTE: dict[str, dict[str, str]] = {
    'de': {
        'kopf': '{titel} — {projekt}',
        'erstellt': 'Erstellt: {datum}',
        # Datumsformat statt eines festen Musters: `%B` wäre von der
        # Server-Locale abhängig. Englisch bekommt ISO 8601.
        'datum_format': '%d.%m.%Y',
        'leer': '—',

        'titel_gesamt': 'Auditbericht',
        'titel_fragen': 'Fragen-Status',
        'titel_massnahmen': 'Maßnahmenplan',

        'quote_zeile': 'Erfüllungsquote {quote} % · Abdeckung {abdeckung} %',

        'm_angabe': 'Angabe',
        'm_wert': 'Wert',
        'm_unternehmen': 'Unternehmen',
        'm_frameworks': 'Frameworks',
        'm_fokus': 'Prüfungsfokus',

        'h_stand': 'Compliance-Stand',
        's_erfuellung': 'Erfüllung',
        's_anzahl': 'Anzahl',
        's_hinweis': ('{gesamt} Fragen gesamt. Offene Fragen zählen in der '
                      'Quote als nicht nachgewiesen; nur die bewerteten '
                      'Fragen ergäben {bewertet} %.'),
        'f_framework': 'Framework',
        'f_stufe': 'Stufe',
        'f_quote': 'Quote',
        'f_verlauf': 'Verlauf',
        'f_offen': 'offen / anwendbar',
        'f_prozent': '{wert} %',

        'q_fundstelle': 'Fundstelle',
        'q_frage': 'Frage',
        'q_antwort': 'Antwort',
        'q_erfuellung': 'Erfüllung',

        'h_empfohlen': 'Empfohlene Maßnahmen',
        'e_massnahme': 'Maßnahme',
        'e_prio': 'Priorität',
        'e_aufwand': 'Aufwand',
        'e_begruendung': 'Begründung',

        'h_offene': 'Offene Punkte aus dem Fragenkatalog',
        'keine_luecken': 'Keine Lücken — alle anwendbaren Fragen sind erfüllt.',
        'luecken_hinweis': ('{anzahl} Punkte, sortiert nach Dringlichkeit '
                            '(nicht erfüllt, dann teilweise, dann offen).'),
        'l_status': 'Status',

        'h_gesamtbewertung': 'Gesamtbewertung',
        'h_zusammenfassung': 'Zusammenfassung',
        # Der Marker bleibt deutsch (Modul-Kopf), nur der Satz folgt der
        # Sprache.
        'ki_hinweis': '🤖 KI-generiert — fachlich zu prüfen.',
        'kein_entwurf': ('Für dieses Audit liegt noch kein ausformulierter '
                         'Entwurf vor. Der Bericht enthält den berechneten '
                         'Stand und die Datenlage; die Einordnung lässt sich '
                         'im Bericht-Tab erzeugen („Auditbericht erzeugen").'),
        'h_staerken': 'Stärken',
        'h_luecken': 'Lücken',
        'h_empfehlungen': 'Handlungsempfehlungen',
        'h_anhang': 'Anhang: Fragen und Antworten',
        'h_fazit': 'Fazit',
    },
    'en': {
        'kopf': '{titel} — {projekt}',
        'erstellt': 'Created: {datum}',
        'datum_format': '%Y-%m-%d',
        'leer': '—',

        'titel_gesamt': 'Audit report',
        'titel_fragen': 'Question status',
        'titel_massnahmen': 'Action plan',

        'quote_zeile': ('Degree of fulfilment {quote} % · Coverage '
                        '{abdeckung} %'),

        'm_angabe': 'Item',
        'm_wert': 'Value',
        'm_unternehmen': 'Company',
        'm_frameworks': 'Frameworks',
        'm_fokus': 'Scope of the audit',

        'h_stand': 'Compliance status',
        's_erfuellung': 'Fulfilment',
        's_anzahl': 'Count',
        's_hinweis': ('{gesamt} questions in total. Open questions count in '
                      'the ratio as not demonstrated; the assessed questions '
                      'alone would give {bewertet} %.'),
        'f_framework': 'Framework',
        'f_stufe': 'Level',
        'f_quote': 'Ratio',
        'f_verlauf': 'Bar',
        'f_offen': 'open / applicable',
        'f_prozent': '{wert} %',

        'q_fundstelle': 'Reference',
        'q_frage': 'Question',
        'q_antwort': 'Answer',
        'q_erfuellung': 'Fulfilment',

        'h_empfohlen': 'Recommended measures',
        'e_massnahme': 'Measure',
        'e_prio': 'Priority',
        'e_aufwand': 'Effort',
        'e_begruendung': 'Rationale',

        'h_offene': 'Open items from the question catalogue',
        'keine_luecken': ('No gaps — all applicable questions are '
                          'fulfilled.'),
        'luecken_hinweis': ('{anzahl} items, sorted by urgency (not '
                            'fulfilled, then partially, then open).'),
        'l_status': 'Status',

        'h_gesamtbewertung': 'Overall assessment',
        'h_zusammenfassung': 'Summary',
        'ki_hinweis': '🤖 KI-generiert — subject to professional review.',
        # Der deutsche Text nennt die Schaltfläche „Auditbericht erzeugen"
        # wörtlich. Im englischen Dokument steht sie **nicht**: Die
        # Oberfläche ist seit #1954 zweisprachig, und eine Wegbeschreibung
        # auf eine Beschriftung, die dort nicht vorkommt, ist schlechter als
        # keine (die Lehre aus #1805). Benannt wird deshalb nur der Reiter.
        'kein_entwurf': ('No drafted assessment exists for this audit yet. '
                         'The report contains the calculated status and the '
                         'underlying data; the assessment can be produced in '
                         'the report tab.'),
        'h_staerken': 'Strengths',
        'h_luecken': 'Gaps',
        'h_empfehlungen': 'Recommended actions',
        'h_anhang': 'Annex: questions and answers',
        'h_fazit': 'Conclusion',
    },
}

_t = _rt.macher(TEXTE)


# ── Farbgebung (#1727) ───────────────────────────────────────────────────────
# python-docx kann Zellen-/Absatzschattierung nicht ueber die hohe Schnittstelle,
# deshalb direkt als w:shd-Element. Die Palette ist dieselbe wie in der Oberflaeche,
# damit Bericht und Bildschirm zusammenpassen.

FARBEN = {
    'kopf':        '1565C0',   # Blau — Tabellenkopf, Ueberschriften-Akzent
    'vollstaendig':'2E7D32',   # Gruen
    'weitgehend':  'F9A825',   # Gelb
    'teilweise':   'EF6C00',   # Orange
    'nicht':       'C62828',   # Rot
    'unbewertet':  '90A4AE',   # Grau
}

#: Zellenhintergrund je Erfuellung — hell, damit der Text lesbar bleibt.
ERF_FARBE = {
    'erfuellt':       'E8F5E9',
    'teilweise':      'FFF3E0',
    'nicht_erfuellt': 'FFEBEE',
    'nicht_anwendbar':'F5F5F5',
    'offen':          'E3F2FD',
}

PRIO_FARBE = {'hoch': 'FFEBEE', 'mittel': 'FFF8E1', 'niedrig': 'E8F5E9'}


def _schattieren(zelle, hex_farbe: str) -> None:
    """Zellenhintergrund setzen (w:shd — kein High-Level-API in python-docx)."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_farbe)
    zelle._tc.get_or_add_tcPr().append(shd)


def _weiss_fett(zelle, text: str) -> None:
    """Kopfzellen-Text: weiss auf Blau."""
    from docx.shared import RGBColor

    run = zelle.paragraphs[0].add_run(text)
    run.bold = True
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def _tabelle(doc, kopf: list[str], zeilen: int):
    """Tabelle mit farbigem Kopf anlegen."""
    tbl = doc.add_table(rows=zeilen + 1, cols=len(kopf))
    tbl.style = 'Table Grid'
    for ci, titel in enumerate(kopf):
        z = tbl.cell(0, ci)
        _schattieren(z, FARBEN['kopf'])
        _weiss_fett(z, titel)
    return tbl


def _ueberschrift(doc, text: str, level: int = 1):
    """Ueberschrift mit farbigem Akzent — Word-Blau wirkt sonst beliebig."""
    from docx.shared import RGBColor

    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x0D, 0x47, 0xA1)
    return h


def _stand_banner(doc, stand: dict[str, Any], sp: str = 'de') -> None:
    """Farbiges Band mit Stufe und Quote — das Erste, was man sehen soll."""
    from docx.shared import Pt, RGBColor

    stufe = str(stand.get('stufe') or 'unbewertet')
    tbl = doc.add_table(rows=1, cols=1)
    tbl.style = 'Table Grid'
    z = tbl.cell(0, 0)
    _schattieren(z, FARBEN.get(stufe, FARBEN['unbewertet']))
    para = z.paragraphs[0]
    # `label` ist die **gerechnete** Stufe aus `compliance_audit.status` und
    # wird durchgereicht — siehe Modul-Kopf.
    run = para.add_run(f"{stand.get('label', '')}")
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    zweite = z.add_paragraph()
    r2 = zweite.add_run(
        _t(sp, 'quote_zeile', quote=stand.get('quote_prozent'),
           abdeckung=stand.get('abdeckung_prozent')))
    r2.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    r2.font.size = Pt(10)
    doc.add_paragraph()


def _balken(prozent: Any, breite: int = 20) -> str:
    """Einfacher Textbalken — funktioniert in DOCX und PDF ohne Grafik."""
    try:
        anteil = max(0.0, min(100.0, float(prozent))) / 100.0
    except (TypeError, ValueError):
        return ''
    voll = int(round(anteil * breite))
    return '█' * voll + '░' * (breite - voll)


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


def _dokument(titel: str, proj: dict[str, Any], stand: dict[str, Any],
              sp: str = 'de'):
    """Neues DOCX mit Kopf, A4 und Basis-Schrift (#1617)."""
    from docx import Document

    from shared.reports.docx_pdf import apply_base_font, set_a4

    doc = Document()
    # Die Dokumentsprache (`w:lang`) wird nur gesetzt, wenn sie vom Standard
    # abweicht: `None` heißt im Helfer ausdrücklich „nicht anfassen", und das
    # war das Verhalten vor #1954 — so bleibt die deutsche Fassung
    # byte-identisch, während Word im englischen Bericht nicht jedes Wort rot
    # unterstreicht.
    set_a4(doc, sprache=sp if sp != 'de' else None)
    apply_base_font(doc)

    from docx.shared import RGBColor

    h = doc.add_heading(
        _t(sp, 'kopf', titel=titel, projekt=proj.get('name', '')), level=0)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x0D, 0x47, 0xA1)
    doc.add_paragraph(
        _t(sp, 'erstellt', datum=date.today().strftime(_t(sp, 'datum_format'))))

    # Stand als farbiges Band direkt unter dem Titel.
    _stand_banner(doc, stand, sp)

    leer = _t(sp, 'leer')
    meta = _tabelle(doc, [_t(sp, 'm_angabe'), _t(sp, 'm_wert')], 3)
    for ri, (k, v) in enumerate((
        (_t(sp, 'm_unternehmen'), proj.get('unternehmen') or leer),
        (_t(sp, 'm_frameworks'), ', '.join(proj.get('frameworks') or []) or leer),
        (_t(sp, 'm_fokus'), str(proj.get('pruefungsfokus') or leer)[:1500]),
    ), start=1):
        meta.cell(ri, 0).paragraphs[0].add_run(k).bold = True
        meta.cell(ri, 1).text = str(v)
    doc.add_paragraph()
    return doc


def _stand_tabelle(doc, stand: dict[str, Any], sp: str = 'de') -> None:
    """Kennzahlen + Stufe je Framework."""
    f = stand.get('fragen') or {}
    _ueberschrift(doc, _t(sp, 'h_stand'), level=1)

    # Verteilung als farbige Tabelle — auf einen Blick erkennbar.
    #
    # #1954: Die Beschriftungen standen hier **ein zweites Mal** als Literale
    # („erfüllt", „teilweise erfüllt", …) — zeichengleich mit
    # `status.ERFUELLUNG_LABELS`, obwohl der Dateikopf diese Tabelle
    # ausdrücklich als die eine Quelle benennt (#1730). Jetzt wird sie
    # gelesen: Das deutsche Ergebnis ist unverändert, und eine englische
    # Fassung muss später nur an **einer** Stelle entstehen.
    vert = _tabelle(doc, [_t(sp, 's_erfuellung'), _t(sp, 's_anzahl')], 5)
    for ri, schluessel in enumerate((
        'erfuellt', 'teilweise', 'nicht_erfuellt', 'offen', 'nicht_anwendbar',
    ), start=1):
        z = vert.cell(ri, 0)
        _schattieren(z, ERF_FARBE[schluessel])
        z.text = _ERF_LABEL[schluessel]
        vert.cell(ri, 1).text = str(f.get(schluessel, 0))
    doc.add_paragraph(
        _t(sp, 's_hinweis', gesamt=f.get('gesamt', 0),
           bewertet=stand.get('quote_bewertet_prozent')))

    fws = stand.get('frameworks') or []
    if not fws:
        return
    tbl = _tabelle(doc, [_t(sp, 'f_framework'), _t(sp, 'f_stufe'),
                         _t(sp, 'f_quote'), _t(sp, 'f_verlauf'),
                         _t(sp, 'f_offen')],
                   len(fws))
    for ri, fw in enumerate(fws, start=1):
        ff = fw.get('fragen') or {}
        tbl.cell(ri, 0).text = str(fw.get('framework', ''))
        z = tbl.cell(ri, 1)
        _schattieren(z, ERF_FARBE.get(
            {'vollstaendig': 'erfuellt', 'weitgehend': 'teilweise',
             'teilweise': 'offen', 'nicht': 'nicht_erfuellt'}.get(
                str(fw.get('stufe')), 'nicht_anwendbar'), 'F5F5F5'))
        # Gerechnete Stufe aus `status.py` — durchgereicht, siehe Modul-Kopf.
        z.text = str(fw.get('label', ''))
        tbl.cell(ri, 2).text = _t(sp, 'f_prozent', wert=fw.get('quote_prozent'))
        tbl.cell(ri, 3).text = _balken(fw.get('quote_prozent'))
        tbl.cell(ri, 4).text = f"{ff.get('offen', 0)} / {ff.get('anwendbar', 0)}"


# ── Berichtstypen ────────────────────────────────────────────────────────────

def _fragen_docx(projekt: str, sp: str = 'de') -> bytes:
    d = _sammeln(projekt)
    doc = _dokument(_t(sp, 'titel_fragen'), d['projekt'], d['stand'], sp)
    _stand_tabelle(doc, d['stand'], sp)

    for fw, fragen in d['nach_framework'].items():
        _ueberschrift(doc, fw, level=1)
        tbl = _tabelle(doc, [_t(sp, 'q_fundstelle'), _t(sp, 'q_frage'),
                             _t(sp, 'q_antwort'), _t(sp, 'q_erfuellung')],
                       len(fragen))
        for ri, q in enumerate(fragen, start=1):
            tbl.cell(ri, 0).text = str(q.get('section_ref') or '')[:60]
            tbl.cell(ri, 1).text = str(q.get('frage') or '')[:500]
            tbl.cell(ri, 2).text = str(q.get('antwort') or '')[:800] or _t(sp, 'leer')
            z = tbl.cell(ri, 3)
            _schattieren(z, ERF_FARBE.get(d['erfuellung_of'](q), 'FFFFFF'))
            z.text = _ERF_LABEL.get(d['erfuellung_of'](q), 'offen')

    from shared.reports.docx_pdf import fit_tables
    fit_tables(doc)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _massnahmen_docx(projekt: str, sp: str = 'de') -> bytes:
    d = _sammeln(projekt)
    doc = _dokument(_t(sp, 'titel_massnahmen'), d['projekt'], d['stand'], sp)

    # Zuerst die KI-Maßnahmen aus dem Entwurf, falls vorhanden — sie sind
    # priorisiert und begruendet.
    empf = d['entwurf'].get('handlungsempfehlungen') or []
    if empf:
        _ueberschrift(doc, _t(sp, 'h_empfohlen'), level=1)
        tbl = _tabelle(doc, [_t(sp, 'e_massnahme'), _t(sp, 'e_prio'),
                             _t(sp, 'e_aufwand'), _t(sp, 'e_begruendung')],
                       len(empf))
        for ri, m in enumerate(empf, start=1):
            if not isinstance(m, dict):
                m = {'massnahme': str(m)}
            tbl.cell(ri, 0).text = str(m.get('massnahme', ''))[:400]
            # `prioritaet`/`aufwand` sind **Werte aus dem KI-Entwurf**
            # ('hoch'|'mittel'|'niedrig') und werden roh gedruckt — schon im
            # deutschen Bericht. Ein Datenwert wird nicht übersetzt
            # (BERICHTE.md, Regel 7).
            prio = str(m.get('prioritaet', '') or '').lower()
            z = tbl.cell(ri, 1)
            if prio in PRIO_FARBE:
                _schattieren(z, PRIO_FARBE[prio])
            z.text = prio or _t(sp, 'leer')
            tbl.cell(ri, 2).text = str(m.get('aufwand', '') or _t(sp, 'leer'))
            tbl.cell(ri, 3).text = str(m.get('begruendung', ''))[:600]

    luecken = d['stand'].get('luecken') or []
    _ueberschrift(doc, _t(sp, 'h_offene'), level=1)
    if not luecken:
        doc.add_paragraph(_t(sp, 'keine_luecken'))
    else:
        doc.add_paragraph(_t(sp, 'luecken_hinweis', anzahl=len(luecken)))
        tbl = _tabelle(doc, [_t(sp, 'f_framework'), _t(sp, 'q_fundstelle'),
                             _t(sp, 'q_frage'), _t(sp, 'l_status')],
                       len(luecken))
        for ri, lk in enumerate(luecken, start=1):
            tbl.cell(ri, 0).text = str(lk.get('framework', ''))
            tbl.cell(ri, 1).text = str(lk.get('section_ref', ''))[:60]
            tbl.cell(ri, 2).text = str(lk.get('frage', ''))[:500]
            z = tbl.cell(ri, 3)
            _schattieren(z, ERF_FARBE.get(lk.get('erfuellung'), 'FFFFFF'))
            z.text = _ERF_LABEL.get(lk.get('erfuellung'), '')

    from shared.reports.docx_pdf import fit_tables
    fit_tables(doc)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _gesamt_docx(projekt: str, sp: str = 'de') -> bytes:
    d = _sammeln(projekt)
    e = d['entwurf']
    doc = _dokument(_t(sp, 'titel_gesamt'), d['projekt'], d['stand'], sp)

    if e.get('gesamtbewertung'):
        _ueberschrift(doc, _t(sp, 'h_gesamtbewertung'), level=1)
        doc.add_paragraph(str(e['gesamtbewertung']))
    if e.get('zusammenfassung'):
        _ueberschrift(doc, _t(sp, 'h_zusammenfassung'), level=1)
        doc.add_paragraph(str(e['zusammenfassung']))
        doc.add_paragraph(_t(sp, 'ki_hinweis')).italic = True
    elif not e:
        _ueberschrift(doc, _t(sp, 'h_zusammenfassung'), level=1)
        doc.add_paragraph(_t(sp, 'kein_entwurf'))

    _stand_tabelle(doc, d['stand'], sp)

    for fw in e.get('framework_bewertungen') or []:
        if not isinstance(fw, dict):
            continue
        _ueberschrift(doc, str(fw.get('framework', '')), level=1)
        if fw.get('bewertung'):
            doc.add_paragraph(str(fw['bewertung']))
        for titel, schluessel in ((_t(sp, 'h_staerken'), 'staerken'),
                                  (_t(sp, 'h_luecken'), 'luecken')):
            werte = fw.get(schluessel) or []
            if werte:
                _ueberschrift(doc, titel, level=2)
                for w in werte:
                    doc.add_paragraph(str(w), style='List Bullet')

    empf = e.get('handlungsempfehlungen') or []
    if empf:
        _ueberschrift(doc, _t(sp, 'h_empfehlungen'), level=1)
        tbl = _tabelle(doc, [_t(sp, 'e_massnahme'), _t(sp, 'e_prio'),
                             _t(sp, 'e_aufwand'), _t(sp, 'e_begruendung')],
                       len(empf))
        for ri, m in enumerate(empf, start=1):
            if not isinstance(m, dict):
                m = {'massnahme': str(m)}
            tbl.cell(ri, 0).text = str(m.get('massnahme', ''))[:400]
            # Datenwerte aus dem KI-Entwurf — siehe `_massnahmen_docx`.
            prio = str(m.get('prioritaet', '') or '').lower()
            z = tbl.cell(ri, 1)
            if prio in PRIO_FARBE:
                _schattieren(z, PRIO_FARBE[prio])
            z.text = prio or _t(sp, 'leer')
            tbl.cell(ri, 2).text = str(m.get('aufwand', '') or _t(sp, 'leer'))
            tbl.cell(ri, 3).text = str(m.get('begruendung', ''))[:600]

    # Datenlage immer anhaengen — der Bericht soll ohne Rueckfragen pruefbar sein.
    _ueberschrift(doc, _t(sp, 'h_anhang'), level=1)
    for fw, fragen in d['nach_framework'].items():
        _ueberschrift(doc, fw, level=2)
        tbl = _tabelle(doc, [_t(sp, 'q_fundstelle'), _t(sp, 'q_frage'),
                             _t(sp, 'q_antwort'), _t(sp, 'q_erfuellung')],
                       len(fragen))
        for ri, q in enumerate(fragen, start=1):
            tbl.cell(ri, 0).text = str(q.get('section_ref') or '')[:60]
            tbl.cell(ri, 1).text = str(q.get('frage') or '')[:500]
            tbl.cell(ri, 2).text = str(q.get('antwort') or '')[:800] or _t(sp, 'leer')
            z = tbl.cell(ri, 3)
            _schattieren(z, ERF_FARBE.get(d['erfuellung_of'](q), 'FFFFFF'))
            z.text = _ERF_LABEL.get(d['erfuellung_of'](q), 'offen')

    if e.get('fazit'):
        _ueberschrift(doc, _t(sp, 'h_fazit'), level=1)
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
           bis: str | None = None, sprache: str | None = None,
           **_ctx: Any) -> bytes:
    """Bericht als DOCX- oder PDF-Bytes (kein Zeitraum — ein Audit ist ein Stand).

    ``sprache`` übersteuert die Sprache des Mandanten für diesen einen Lauf;
    ohne Angabe entscheidet ``firmen.sprache`` (#1954). Aufgelöst wird hier und
    nicht beim Aufrufer — das Berichts-Center reicht den Parameter nur durch,
    wenn die Signatur ihn führt (``shared/reports/api._zusatz``).
    """
    bauer = _BAUER.get(typ)
    if bauer is None:
        raise ValueError(f'Unbekannter Berichtstyp: {typ}')
    docx_bytes = bauer(projekt, _rt.aufloesen(MODUL, projekt, sprache))
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
    luecken = stand.get('luecken') or []
    return {
        # 'reifegrad'/'offene' sind der Vertrag von shared.reports.summary — nur so
        # landen die Zahlen im Prompt (#1725).
        'reifegrad': {
            'stufe': stand.get('label'),
            'erfuellungsquote_prozent': stand.get('quote_prozent'),
            'abdeckung_prozent': stand.get('abdeckung_prozent'),
            # 'fragen' ist die Zählung je Erfüllungsgrad (gesamt/bewertet/erfuellt/…).
            'fragen': stand.get('fragen'),
            'je_framework': [
                {'framework': fw.get('framework'), 'stufe': fw.get('label'),
                 'erfuellungsquote_prozent': fw.get('quote_prozent'),
                 'fragen': fw.get('fragen')}
                for fw in (stand.get('frameworks') or [])
            ],
        },
        'offene': [
            # Ohne 'bewertung': Das Audit bewertet nicht 0–5, sondern Erfüllungsgrade.
            {'id': ' '.join(x for x in (lk.get('framework'), lk.get('section_ref')) if x),
             'titel': lk.get('frage'),
             'status': _ERF_LABEL.get(str(lk.get('erfuellung')), str(lk.get('erfuellung')))}
            for lk in luecken[:40]
        ],
        'unternehmen': d['projekt'].get('unternehmen', ''),
        'frameworks': d['projekt'].get('frameworks') or [],
        'pruefungsfokus': d['projekt'].get('pruefungsfokus', ''),
        'luecken_anzahl': len(luecken),
    }
