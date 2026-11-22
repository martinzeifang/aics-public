"""Firmen-Adapter für das geteilte Berichts-Center (v7.0.0).

Berichte auf Firmenebene — modulübergreifend aus :func:`firmen.uebersicht.build_uebersicht`:

* ``gesamt``  — Firmen-Gesamtbericht (Management): Umsetzungsgrad je Modul/Projekt,
  Risiko-Lage, DSGVO-TOM/WiBA, offene Aufgaben, Produkte/Nachweise.
* ``risiken`` — Risikobericht: alle offenen Risiken/Schwachstellen des Risiko-Cockpits.

DOCX via python-docx; PDF per Gotenberg/LibreOffice (gleicher Weg wie die Modul-Berichte).

DIE SPRACHE GEHÖRT DEM MANDANTEN (#1954)
Hier **ist** das „Projekt" der Mandant: ``render(projekt=…)`` bekommt den
Firmennamen. Die Sprache wird deshalb über :func:`_sprache` direkt aus der
Firma gelesen und **nicht** über ``shared.reports.texte.aufloesen`` — der löst
über ``shared/templates/schema.MODULE_DB`` auf, und ``firmen`` hat dort keinen
Eintrag (das Modul hat bewusst keinen Vorlagen-Adapter, #1735). Ein
``aufloesen('firmen', …)`` käme also **immer** auf Deutsch heraus, und zwar
lautlos: Es sähe aus wie „bei diesem Mandanten ist keine Sprache gesetzt".
Genau die Klasse aus #1805/#1892.

Am Vorlagen-Adapter ändert sich nichts: Das Modul hat weiter keinen, und die
Berichts-Center-Antwort zeigt deshalb keine Vorlagen-Auswahl (#1735).

Die Modul-Beschriftungen (``m['label']``: „CRA", „NIS2", „Risikobewertung" …)
kommen aus :func:`firmen.uebersicht.build_uebersicht` und bleiben, wie sie dort
stehen — eine zweite Zuordnung derselben Namen wäre die Spiegel-Liste aus
#1731/#1735.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from shared.reports import texte as _rt
from shared.reports.core import ReportSpec

DB_PATH = Path('data/db/firmen.sqlite')

CATALOG: list[ReportSpec] = [
    ReportSpec('gesamt', 'Firmen-Gesamtbericht', 'CRA · NIS2 · AI Act · DSGVO · WiBA',
               'Management-Überblick: Umsetzungsgrad aller Module und Projekte, Risiko-Lage, '
               'TOM/WiBA, offene Aufgaben.',
               titel_en='Company overall report',
               beschreibung_en='Management overview: degree of implementation '
                               'across all modules and projects, risk '
                               'situation, TOM/WiBA, open tasks.',
               norm_en='CRA · NIS 2 · AI Act · GDPR · WiBA'),
    ReportSpec('risiken', 'Risikobericht (Risiko-Cockpit)', 'firmenweit',
               'Alle offenen Risiken und Schwachstellen der Firma nach Schwere, mit Herkunft.',
               titel_en='Risk report (risk cockpit)',
               beschreibung_en='All open risks and vulnerabilities of the '
                               'company by severity, with their origin.',
               norm_en='company-wide'),
]

#: Schwere-Beschriftung je Sprache. Der **Schlüssel** ist der Datenwert aus dem
#: Risiko-Cockpit (``critical``…``unknown``) und bleibt unberührt — übersetzt
#: wird nur, was gedruckt wird (BERICHTE.md, Regel 7).
SEV_LABEL_JE_SPRACHE: dict[str, dict[str, str]] = {
    'de': {'critical': 'kritisch', 'high': 'hoch', 'medium': 'mittel',
           'low': 'gering', 'unknown': 'unbewertet'},
    'en': {'critical': 'critical', 'high': 'high', 'medium': 'medium',
           'low': 'low', 'unknown': 'not assessed'},
}

#: Die deutsche Zuordnung bleibt unter ihrem alten Namen erreichbar — sie steht
#: seit v7.0.0 im Modul und ist eine öffentliche Zusage dieses Adapters.
SEV_LABEL = SEV_LABEL_JE_SPRACHE['de']
SEV_ORDER = ['critical', 'high', 'medium', 'low', 'unknown']


def _sev_label(sev: str, sp: str) -> str:
    tabelle = SEV_LABEL_JE_SPRACHE.get(sp) or SEV_LABEL
    return tabelle.get(sev, SEV_LABEL.get(sev, sev))


#: Die Prosa der beiden Firmen-Berichte je Sprache (#1954).
#:
#: Die deutschen Werte sind zeichengenau die aus 8.3.4 — einschließlich der
#: drei Leerzeichen um die Trenner („   ·   "), des Leerzeichens vor dem
#: Prozentzeichen und der Gedankenstriche.
#:
#: ``Mandant`` → *client*, ``Firma`` → *company*, ``Reifegrad``/
#: ``Umsetzungsgrad`` → *maturity*/*degree of implementation*, ``TOM`` bleibt
#: ``TOM`` (Begriffsliste #1954). ``Art. 32`` und ``DSGVO-DSMS`` bleiben.
TEXTE: dict[str, dict[str, str]] = {
    'de': {
        'titel_gesamt': 'Firmen-Gesamtbericht',
        'titel_risiken': 'Risikobericht',
        'kopf': '{titel} — {firma}',
        'l_erstellt': 'Erstellt: ',
        # Datumsformat statt eines festen Musters: `%B` wäre von der
        # Server-Locale abhängig. Englisch bekommt ISO 8601.
        'datum_format': '%d.%m.%Y',
        'l_unternehmen': '   ·   Unternehmen: ',
        'l_berater': '   ·   Berater: ',
        'prozent': '{wert} %',
        'leer': '—',

        'h1': '1. Zusammenfassung',
        'summary': ('Gesamt-Umsetzungsgrad (Ø der Module CRA, NIS2, AI Act, '
                    'DSGVO, WiBA): {pct}. Offene Risiken/Schwachstellen: '
                    '{total} (kritisch {critical}, hoch {high}, mittel '
                    '{medium}, gering {low}). Produkte: {produkte}, '
                    'Nachweise: {nachweise}.'),

        'h2': '2. Umsetzungsgrad je Modul',
        'k_modul': 'Modul',
        'k_umsetzungsgrad': 'Umsetzungsgrad',
        'k_projekte': 'Projekte',
        'rb_bewertung': 'Bewertung',
        'rb_framework': 'Framework',
        'rb_risiken': 'Risiken',
        'rb_offen': 'offen',
        'rb_unbewertet': 'unbewertet',
        'p_projekt': 'Projekt',
        'p_produkt': 'Produkt',

        'h3': '3. Risiko-Lage (Risiko-Cockpit)',
        'keine_firmen_id': ('Die Firma ist keiner Firmen-ID zugeordnet — '
                            'Risiko-Cockpit nicht verfügbar.'),
        'keine_risiken': 'Keine offenen Risiken oder Schwachstellen.',
        'r_schwere': 'Schwere',
        'r_quelle': 'Quelle',
        'r_projekt': 'Projekt',
        'r_risiko': 'Risiko',
        'volle_liste': 'Vollständige Liste: Risikobericht (Risiko-Cockpit).',

        'h4': '4. DSGVO — TOM (Art. 32) und BSI-WiBA',
        't_projekt': 'DSGVO-Projekt',
        't_tom': 'TOM',
        't_erfuellung': 'Erfüllung',
        't_aus_wiba': 'Status aus WiBA',
        't_mit_umsetzung': 'mit Umsetzungsbeschreibung',

        'h5': '5. Offene Aufgaben und Fristen (DSGVO-DSMS)',
        'a_bereich': 'Bereich',
        'a_aufgabe': 'Aufgabe',
        'a_frist': 'Frist',
        'a_ueberfaellig': ' (überfällig)',

        'hinweis': ('Hinweis: Werte aus der AI Compliance Suite, Stand '
                    'Berichtserstellung. Umsetzungsgrade sind '
                    'Selbstbewertungen bzw. aus BSI-WiBA abgeleitet.'),

        'sev_kopf': '{label} ({anzahl})',
        'v_quelle': 'Quelle',
        'v_projekt': 'Projekt',
        'v_risiko': 'Risiko / Schwachstelle',
        'v_beschreibung': 'Beschreibung',
    },
    'en': {
        'titel_gesamt': 'Company overall report',
        'titel_risiken': 'Risk report',
        'kopf': '{titel} — {firma}',
        'l_erstellt': 'Created: ',
        'datum_format': '%Y-%m-%d',
        'l_unternehmen': '   ·   Company: ',
        'l_berater': '   ·   Consultant: ',
        'prozent': '{wert} %',
        'leer': '—',

        'h1': '1. Summary',
        'summary': ('Overall degree of implementation (average of the '
                    'modules CRA, NIS2, AI Act, DSGVO, WiBA): {pct}. Open '
                    'risks/vulnerabilities: {total} (critical {critical}, '
                    'high {high}, medium {medium}, low {low}). Products: '
                    '{produkte}, evidence documents: {nachweise}.'),

        'h2': '2. Degree of implementation per module',
        'k_modul': 'Module',
        'k_umsetzungsgrad': 'Implementation',
        'k_projekte': 'Projects',
        'rb_bewertung': 'Assessment',
        'rb_framework': 'Framework',
        'rb_risiken': 'Risks',
        'rb_offen': 'open',
        'rb_unbewertet': 'not assessed',
        'p_projekt': 'Project',
        'p_produkt': 'Product',

        'h3': '3. Risk situation (risk cockpit)',
        'keine_firmen_id': ('The company is not linked to a company ID — '
                            'risk cockpit not available.'),
        'keine_risiken': 'No open risks or vulnerabilities.',
        'r_schwere': 'Severity',
        'r_quelle': 'Source',
        'r_projekt': 'Project',
        'r_risiko': 'Risk',
        'volle_liste': 'Complete list: risk report (risk cockpit).',

        'h4': '4. DSGVO — TOM (Art. 32) and BSI WiBA',
        't_projekt': 'DSGVO project',
        't_tom': 'TOM',
        't_erfuellung': 'Fulfilment',
        't_aus_wiba': 'Status from WiBA',
        't_mit_umsetzung': 'with implementation description',

        'h5': '5. Open tasks and deadlines (DSGVO DSMS)',
        'a_bereich': 'Area',
        'a_aufgabe': 'Task',
        'a_frist': 'Deadline',
        'a_ueberfaellig': ' (overdue)',

        'hinweis': ('Note: figures from the AI Compliance Suite as at the '
                    'time the report was created. Degrees of implementation '
                    'are self-assessments or derived from BSI WiBA.'),

        'sev_kopf': '{label} ({anzahl})',
        'v_quelle': 'Source',
        'v_projekt': 'Project',
        'v_risiko': 'Risk / vulnerability',
        'v_beschreibung': 'Description',
    },
}

_t = _rt.macher(TEXTE)


def _sprache(firma: str, sprache: str | None = None) -> str:
    """Die Sprache dieses Berichts — die des Mandanten (#1954).

    Hier ist der Mandant das Projekt, also wird er **über seinen Namen**
    gelesen (``shared.sprache.firma_sprache_nach_name``) statt über
    ``shared.reports.texte.aufloesen``; die Begründung steht im Modul-Kopf.
    Fail-open auf die Standardsprache: Ein nicht erzeugter Bericht ist der
    teurere Ausgang als einer in der falschen Sprache.
    """
    from shared import sprache as _sp

    if sprache:
        return _sp.oder_standard(sprache)
    return _sp.firma_sprache_nach_name(DB_PATH, firma) or _rt.STANDARD


def catalog() -> list[ReportSpec]:
    return CATALOG


def summary_context(firma: str) -> dict:
    """Kennzahlen für die KI-Management-Zusammenfassung (#1393) — firmenweit."""
    from firmen.uebersicht import build_uebersicht
    u = build_uebersicht(firma)
    return {
        'gesamt_umsetzungsgrad_pct': u['gesamt_pct'],
        'module': [{'modul': m['label'], 'umsetzungsgrad_pct': m['pct'],
                    'projekte': [{k: p.get(k) for k in ('name', 'pct', 'risiken', 'offen')}
                                 for p in m['projekte']]}
                   for m in u['module'] if m['projekte']],
        'risiken': {'offen_gesamt': u['risiken']['total'], 'nach_schwere': u['risiken']['by_severity'],
                    'top': u['risiken']['top']},
        'dsgvo_tom': u['tom'],
        'offene_aufgaben': u['aufgaben'],
    }


def _table(doc, header: list[str], rows: list[list[Any]]):
    tbl = doc.add_table(rows=len(rows) + 1, cols=len(header))
    tbl.style = 'Light Grid Accent 1'
    for ci, h in enumerate(header):
        tbl.cell(0, ci).paragraphs[0].add_run(h).bold = True
    for ri, row in enumerate(rows, start=1):
        for ci, val in enumerate(row):
            tbl.cell(ri, ci).text = '' if val is None else str(val)
    return tbl


def _pct(v: Any, sp: str = 'de') -> str:
    return _t(sp, 'leer') if v is None else _t(sp, 'prozent', wert=f"{float(v):.0f}")


def _kopf(doc, titel: str, u: dict[str, Any], sp: str = 'de') -> None:
    from docx.shared import Inches
    for s in doc.sections:
        s.left_margin = Inches(0.85)
        s.right_margin = Inches(0.85)
    doc.add_heading(_t(sp, 'kopf', titel=titel, firma=u['firma']), level=0)
    p = doc.add_paragraph()
    p.add_run(_t(sp, 'l_erstellt')).bold = True
    p.add_run(date.today().strftime(_t(sp, 'datum_format')))
    if u.get('unternehmen'):
        p.add_run(_t(sp, 'l_unternehmen')).bold = True
        p.add_run(u['unternehmen'])
    if u.get('berater'):
        p.add_run(_t(sp, 'l_berater')).bold = True
        p.add_run(u['berater'])


def _gesamt_docx(u: dict[str, Any], sp: str = 'de') -> bytes:
    from docx import Document
    doc = Document()
    _kopf(doc, _t(sp, 'titel_gesamt'), u, sp)

    doc.add_heading(_t(sp, 'h1'), level=1)
    r = u['risiken']
    sev = r.get('by_severity') or {}
    doc.add_paragraph(
        _t(sp, 'summary', pct=_pct(u['gesamt_pct'], sp), total=r.get('total', 0),
           critical=sev.get('critical', 0), high=sev.get('high', 0),
           medium=sev.get('medium', 0), low=sev.get('low', 0),
           produkte=len(u['produkte']), nachweise=u['nachweise']))

    doc.add_heading(_t(sp, 'h2'), level=1)
    _table(doc, [_t(sp, 'k_modul'), _t(sp, 'k_umsetzungsgrad'), _t(sp, 'k_projekte')],
           [[m['label'], _pct(m['pct'], sp) if m['key'] != 'risikobewertung' else _t(sp, 'leer'),
             len(m['projekte'])]
            for m in u['module'] if m['projekte']])
    for m in u['module']:
        if not m['projekte']:
            continue
        # `m['label']` kommt aus `firmen.uebersicht` — siehe Modul-Kopf.
        doc.add_heading(m['label'], level=2)
        if m['key'] == 'risikobewertung':
            _table(doc, [_t(sp, 'rb_bewertung'), _t(sp, 'rb_framework'),
                         _t(sp, 'rb_risiken'), _t(sp, 'rb_offen'),
                         _t(sp, 'rb_unbewertet')],
                   [[p['name'], p.get('framework', ''), p.get('risiken', 0), p.get('offen', 0),
                     p.get('unbewertet', 0)] for p in m['projekte']])
        else:
            _table(doc, [_t(sp, 'p_projekt'), _t(sp, 'p_produkt'),
                         _t(sp, 'k_umsetzungsgrad')],
                   [[p['name'], p.get('produkt') or _t(sp, 'leer'), _pct(p.get('pct'), sp)]
                    for p in m['projekte']])

    doc.add_heading(_t(sp, 'h3'), level=1)
    if r.get('unassigned'):
        doc.add_paragraph(_t(sp, 'keine_firmen_id'))
    elif not r.get('top'):
        doc.add_paragraph(_t(sp, 'keine_risiken'))
    else:
        _table(doc, [_t(sp, 'r_schwere'), _t(sp, 'r_quelle'), _t(sp, 'r_projekt'),
                     _t(sp, 'r_risiko')],
               [[_sev_label(t.get('severity'), sp), (t.get('source') or '').upper(),
                 t.get('projekt'), t.get('titel')] for t in r['top']])
        doc.add_paragraph(_t(sp, 'volle_liste'))

    if u['tom']:
        doc.add_heading(_t(sp, 'h4'), level=1)
        _table(doc, [_t(sp, 't_projekt'), _t(sp, 't_tom'), _t(sp, 't_erfuellung'),
                     _t(sp, 't_aus_wiba'), _t(sp, 't_mit_umsetzung')],
               [[t['projekt'], t['anzahl'], _pct(t['pct'], sp), t['aus_wiba'], t['mit_umsetzung']]
                for t in u['tom']])

    if u['aufgaben']:
        doc.add_heading(_t(sp, 'h5'), level=1)
        _table(doc, [_t(sp, 'a_bereich'), _t(sp, 'a_aufgabe'), _t(sp, 'a_frist')],
               [[a.get('area_label') or a.get('area') or '', a.get('text') or '',
                 f"{a.get('due') or _t(sp, 'leer')}"
                 f"{_t(sp, 'a_ueberfaellig') if a.get('overdue') else ''}"]
                for a in u['aufgaben']])

    doc.add_paragraph()
    doc.add_paragraph(_t(sp, 'hinweis'))
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _risiken_docx(u: dict[str, Any], items: list[dict[str, Any]],
                  sp: str = 'de') -> bytes:
    from docx import Document
    doc = Document()
    _kopf(doc, _t(sp, 'titel_risiken'), u, sp)
    if u['risiken'].get('unassigned'):
        doc.add_paragraph(_t(sp, 'keine_firmen_id'))
    for sev in SEV_ORDER:
        rows = [it for it in items if it.get('severity') == sev]
        if not rows:
            continue
        doc.add_heading(_t(sp, 'sev_kopf', label=_sev_label(sev, sp).capitalize(),
                           anzahl=len(rows)), level=1)
        _table(doc, [_t(sp, 'v_quelle'), _t(sp, 'v_projekt'), _t(sp, 'v_risiko'),
                     _t(sp, 'v_beschreibung')],
               [[(it.get('source') or '').upper(), it.get('projekt'), it.get('titel'),
                 it.get('beschreibung') or ''] for it in rows])
    if not items and not u['risiken'].get('unassigned'):
        doc.add_paragraph(_t(sp, 'keine_risiken'))
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, sprache: str | None = None,
           **_ctx: Any) -> bytes:
    """``projekt`` = Firmenname.

    ``sprache`` übersteuert die Sprache des Mandanten für diesen einen Lauf;
    ohne Angabe entscheidet ``firmen.sprache`` (#1954). Der Parameter **muss**
    in dieser Signatur stehen — das Berichts-Center reicht ihn nur durch, wenn
    der Renderer ihn führt (``shared/reports/api._zusatz``).
    """
    from firmen.uebersicht import build_uebersicht
    sp = _sprache(projekt, sprache)
    u = build_uebersicht(projekt)
    if typ == 'risiken':
        items: list[dict[str, Any]] = []
        if u['firmen_id'] is not None:
            from shared.risk_cockpit import build_cockpit
            items = build_cockpit(u['firmen_id']).get('items') or []
        docx_bytes = _risiken_docx(u, items, sp)
    else:
        docx_bytes = _gesamt_docx(u, sp)
    if fmt == 'pdf':
        from shared.templates.pdf_converter import convert_docx_to_pdf
        return convert_docx_to_pdf(docx_bytes)
    return docx_bytes
