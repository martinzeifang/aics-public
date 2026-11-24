"""Freie Audit-Frage + Fragenzahl-Empfehlung im Compliance-Audit (#2133).

Der Audit war an die Norm gebunden („Wie weit ist das Unternehmen mit Norm X?").
Jetzt lässt sich eine **frei formulierte Audit-Frage** stellen („Unterliegt
Software XY der CRA?") und der Assistent empfiehlt, wie viele Fragen zu ihrer
Beantwortung nötig sind.

Die tragende Zusage ist dieselbe wie bei ``evidence_section`` (#1483): **Ohne**
Audit-Frage ist jeder Prompt byte-identisch zu vorher — der Normfall bleibt
unverändert. Der Rest prüft, dass die Empfehlung einen Vorschlag absichert, statt
ihn blind zu übernehmen (Linie aus #1773).
"""
from __future__ import annotations

import json
from pathlib import Path

from compliance_audit import frageplan, prompts, status
from gutachten.prompts import _build_fragen_prompt

from tests.i18n_text import vue_text  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
FRONTEND = REPO / 'frontend/src'

_FRAGEN_BASIS = dict(
    projekt_name='P', pruefungsfokus='Fokus', frameworks=['CRA'],
    sections=[{'framework': 'CRA', 'section_ref': 'Art. 5', 'title': 'T', 'text': 'x'}],
    batch_size=6, header='', bewertung_skala=[])

_STATUS = {
    'stufe': 'teilweise', 'label': 'teilweise', 'quote_prozent': 50,
    'quote_bewertet_prozent': 60, 'abdeckung_prozent': 80,
    'fragen': {'gesamt': 10, 'erfuellt': 3, 'teilweise': 2, 'nicht_erfuellt': 1,
               'offen': 4, 'nicht_anwendbar': 0},
    'frameworks': [{'framework': 'CRA', 'label': 'teilweise', 'quote_prozent': 50,
                    'fragen': {'offen': 4, 'anwendbar': 10}}],
    'luecken': [],
}
_PROJEKT = {'name': 'P', 'unternehmen': 'U', 'pruefungsfokus': 'F'}


# ── Byte-Identität ohne Audit-Frage (der Normfall bleibt) ────────────────────

def test_fragen_prompt_byte_identisch_ohne_auditfrage():
    assert _build_fragen_prompt(**_FRAGEN_BASIS) == \
        _build_fragen_prompt(**_FRAGEN_BASIS, audit_frage='')


def test_status_prompt_byte_identisch_ohne_auditfrage():
    assert prompts.build_status_prompt(_PROJEKT, _STATUS) == \
        prompts.build_status_prompt(_PROJEKT, _STATUS, audit_frage='')


def test_bericht_prompt_byte_identisch_ohne_auditfrage():
    fragen = [{'framework': 'CRA', 'frage': 'f', 'antwort': 'a', 'erfuellung': 'erfuellt'}]
    assert prompts.build_bericht_prompt(_PROJEKT, fragen) == \
        prompts.build_bericht_prompt(_PROJEKT, fragen, audit_frage='')


# ── Mit Audit-Frage: sie steuert Generierung und Antwort ─────────────────────

def test_auditfrage_steuert_fragengenerierung():
    p = _build_fragen_prompt(**_FRAGEN_BASIS, audit_frage='Unterliegt XY der CRA?')
    assert 'Unterliegt XY der CRA?' in p
    assert 'ZIEL DIESES FRAGENKATALOGS' in p


def test_status_feld_nur_mit_auditfrage():
    ohne = prompts.build_status_prompt(_PROJEKT, _STATUS)
    mit = prompts.build_status_prompt(_PROJEKT, _STATUS, audit_frage='Unterliegt XY der CRA?')
    assert 'antwort_auf_auditfrage' in mit
    assert 'antwort_auf_auditfrage' not in ohne


def test_parser_liest_antwort_auf_auditfrage():
    out = prompts.parse_status_response(json.dumps({
        'antwort_auf_auditfrage': 'Ja, XY unterliegt der CRA.',
        'kundenmitteilung': 'km', 'je_framework': [], 'top_massnahmen': [], 'fazit': 'f'}))
    assert out['antwort_auf_auditfrage'] == 'Ja, XY unterliegt der CRA.'


# ── Empfehlung: Vorschlag absichern, nicht blind übernehmen ──────────────────

def test_empfehlung_verwirft_erfundenes_framework_und_summiert():
    r = frageplan.parse_empfehlung_response(json.dumps({
        'gesamt': 99,  # bewusst falsch; Gesamt ist die Summe, nicht diese Zahl
        'verteilung': [
            {'framework': 'CRA', 'anzahl': 6, 'begruendung': 'Kern'},
            {'framework': 'ERFUNDEN', 'anzahl': 30},
            {'framework': 'Produktsicherheit', 'anzahl': 2}],
        'begruendung': 'weil'}), ['CRA', 'Produktsicherheit'])
    assert r['gesamt'] == 8
    fws = {v['framework'] for v in r['verteilung']}
    assert fws == {'CRA', 'Produktsicherheit'}  # erfundenes verworfen


def test_empfehlung_fehlende_verteilung_wird_gleichverteilt():
    r = frageplan.parse_empfehlung_response(json.dumps({'gesamt': 10, 'verteilung': []}),
                                            ['CRA', 'Produktsicherheit'])
    assert r['gesamt'] == 10
    assert sorted(v['anzahl'] for v in r['verteilung']) == [5, 5]


def test_empfehlung_deckelt_auf_maximum():
    r = frageplan.parse_empfehlung_response(json.dumps({
        'verteilung': [{'framework': 'CRA', 'anzahl': 999}]}), ['CRA'])
    assert r['gesamt'] <= frageplan.MAX_FRAGEN


def test_empfehlung_fehlende_norm_erscheint_mit_null():
    # Jede gewählte Norm muss sichtbar sein, auch wenn die KI sie wegließ.
    r = frageplan.parse_empfehlung_response(json.dumps({
        'verteilung': [{'framework': 'CRA', 'anzahl': 5}]}), ['CRA', 'DORA'])
    dora = [v for v in r['verteilung'] if v['framework'] == 'DORA']
    assert dora and dora[0]['anzahl'] == 0


# ── Verdrahtung in der Oberfläche ────────────────────────────────────────────

def test_view_bietet_auditfrage_und_empfehlung():
    txt = vue_text(FRONTEND / 'views/compliance-audit/ComplianceAuditView.vue')
    assert 'Audit-Frage' in txt
    assert 'Fragenzahl empfehlen lassen' in txt


def test_panel_zeigt_antwort_auf_auditfrage():
    txt = vue_text(FRONTEND / 'components/compliance-audit/WasserstandPanel.vue')
    assert 'Antwort auf die Audit-Frage' in txt


def test_store_hat_empfehlungs_aktionen():
    src = (FRONTEND / 'stores/complianceAudit.ts').read_text(encoding='utf-8')
    assert 'buildEmpfehlungPrompt' in src and 'parseEmpfehlung' in src
    assert 'fragen/empfehlung/prompt' in src and 'fragen/empfehlung/import' in src


# ── Audit-Modus: Erfüllungsgrad vs. freie Frage ──────────────────────────────

_FRAGEN_FREI = [
    {'framework': 'CRA', 'frage': 'In der EU bereitgestellt?', 'antwort': 'Ja.', 'erfuellung': 'offen'},
    {'framework': 'CRA', 'frage': 'Digitale Elemente?', 'antwort': '', 'erfuellung': 'offen'},
]


def test_normalize_modus_faellt_auf_erfuellungsgrad():
    assert status.normalize_modus('freie_frage') == 'freie_frage'
    assert status.normalize_modus('') == 'erfuellungsgrad'
    assert status.normalize_modus('quatsch') == 'erfuellungsgrad'


def test_build_status_freier_modus_abdeckung_statt_quote():
    st = status.build_status(_FRAGEN_FREI, modus='freie_frage')
    assert st['modus'] == 'freie_frage'
    assert st['beantwortung'] == {'gesamt': 2, 'beantwortet': 1, 'offen': 1}
    # Konformitätsstufe/Quote sind im freien Modus neutralisiert.
    assert st['stufe'] == 'frei'
    assert st['quote_prozent'] is None


def test_build_status_klassisch_unveraendert():
    st = status.build_status(_FRAGEN_FREI)  # Default erfuellungsgrad
    assert st['modus'] == 'erfuellungsgrad'
    assert st['stufe'] != 'frei'
    # Additive Schlüssel stören den klassischen Pfad nicht.
    assert 'quote_prozent' in st and 'fragen' in st


def test_freier_prompt_antwortorientiert_ohne_quote():
    st = status.build_status(_FRAGEN_FREI, modus='freie_frage')
    p = prompts.build_status_prompt(
        {'name': 'P', 'unternehmen': 'U'}, st,
        audit_frage='Unterliegt XY der CRA?', modus='freie_frage', fragen=_FRAGEN_FREI)
    assert 'antwort_auf_auditfrage' in p
    assert 'Ja.' in p                        # Antwort fließt ein
    assert '1 von 2' in p                    # Abdeckung statt Quote
    assert 'Vergib KEINE Compliance-Stufe' in p
    assert 'Gesamtstufe' not in p            # keine Stufen-Vorgabe


def test_status_prompt_klassisch_byte_identisch_mit_modus_default():
    st = status.build_status(_FRAGEN_FREI)
    a = prompts.build_status_prompt(_PROJEKT, st)
    b = prompts.build_status_prompt(_PROJEKT, st, modus='erfuellungsgrad')
    assert a == b


def test_view_hat_modus_auswahl_und_gating():
    src = (FRONTEND / 'views/compliance-audit/ComplianceAuditView.vue').read_text(encoding='utf-8')
    # Modus-Auswahl ganz am Anfang + beide Optionen
    assert "value=\"erfuellungsgrad\"" in src and "value=\"freie_frage\"" in src
    # Bewertung/Erfüllung nur im Erfüllungsgrad-Modus
    assert 'istFreieFrage' in src
    assert 'v-if="!istFreieFrage"' in src


def test_panel_hat_freien_modus():
    txt = vue_text(FRONTEND / 'components/compliance-audit/WasserstandPanel.vue')
    assert 'Freie Audit-Frage' in txt
    src = (FRONTEND / 'components/compliance-audit/WasserstandPanel.vue').read_text(encoding='utf-8')
    assert "status.value?.modus === 'freie_frage'" in src
