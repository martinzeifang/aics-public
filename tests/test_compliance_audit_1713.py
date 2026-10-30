"""Compliance-Audit als eigenes Modul + Wasserstandsmeldung (#1713).

Schwerpunkt ist die **Stufenberechnung**: Sie ist eine Zusage an den Kunden und
muss reproduzierbar sein. Entsprechend wird hier vor allem geprüft, dass die KI
die Stufe nicht setzen kann und dass unbeantwortete Fragen nicht zu einer
geschmeichelten Aussage führen.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from compliance_audit import prompts, status
from shared.licensing import modules as lic


def _f(framework: str, erfuellung: str, **kw):
    return {'framework': framework, 'erfuellung': erfuellung,
            'frage': kw.pop('frage', 'Frage?'), **kw}


# ── Stufenberechnung ─────────────────────────────────────────────────────────

def test_alles_erfuellt_ist_vollstaendig():
    s = status.build_status([_f('ISO', 'erfuellt')] * 5)
    assert s['stufe'] == 'vollstaendig'
    assert s['quote_prozent'] == 100.0


def test_nicht_anwendbare_fragen_fallen_aus_der_rechnung():
    s = status.build_status([_f('ISO', 'erfuellt')] * 5 + [_f('ISO', 'nicht_anwendbar')] * 3)
    assert s['stufe'] == 'vollstaendig'
    assert s['fragen']['anwendbar'] == 5
    assert s['fragen']['nicht_anwendbar'] == 3


def test_offene_fragen_verhindern_vollstaendig():
    """Der wichtigste Fall: 10 von 50 Fragen beantwortet, alle erfüllt.

    Ohne diese Regel läge die Quote bei 100 % und das Audit würde dem Kunden
    „vollständig compliant" melden, obwohl 40 Fragen nie erhoben wurden.
    """
    s = status.build_status([_f('ISO', 'erfuellt')] * 10 + [_f('ISO', 'offen')] * 40)
    assert s['stufe'] == 'nicht'
    assert s['quote_prozent'] == 20.0
    # Für den Auditor bleibt sichtbar, dass die bewerteten Fragen sauber sind.
    assert s['quote_bewertet_prozent'] == 100.0
    assert s['abdeckung_prozent'] == 20.0


def test_teilweise_zaehlt_halb():
    s = status.build_status([_f('ISO', 'teilweise')] * 4)
    assert s['quote_prozent'] == 50.0
    assert s['stufe'] == 'teilweise'


@pytest.mark.parametrize('erfuellt,gesamt,erwartet', [
    (10, 10, 'vollstaendig'),
    (9, 10, 'weitgehend'),    # 90 %
    (8, 10, 'weitgehend'),    # 80 % — genau auf der Schwelle
    (7, 10, 'teilweise'),     # 70 %
    (4, 10, 'teilweise'),     # 40 % — genau auf der Schwelle
    (3, 10, 'nicht'),         # 30 %
    (0, 10, 'nicht'),
])
def test_schwellen(erfuellt, gesamt, erwartet):
    fragen = ([_f('ISO', 'erfuellt')] * erfuellt
              + [_f('ISO', 'nicht_erfuellt')] * (gesamt - erfuellt))
    assert status.build_status(fragen)['stufe'] == erwartet


def test_ohne_anwendbare_fragen_unbewertet():
    assert status.build_status([])['stufe'] == 'unbewertet'
    assert status.build_status([_f('ISO', 'nicht_anwendbar')])['stufe'] == 'unbewertet'


def test_stufe_je_framework_getrennt():
    s = status.build_status([_f('ISO', 'erfuellt')] * 4 + [_f('NIS2', 'nicht_erfuellt')] * 4)
    je = {f['framework']: f['stufe'] for f in s['frameworks']}
    assert je == {'ISO': 'vollstaendig', 'NIS2': 'nicht'}
    assert s['stufe'] == 'teilweise'  # gesamt 50 %


def test_reproduzierbar():
    fragen = [_f('ISO', 'erfuellt'), _f('ISO', 'teilweise'), _f('ISO', 'offen')]
    a = status.build_status(fragen)
    b = status.build_status(list(reversed(fragen)))
    assert a['stufe'] == b['stufe']
    assert a['quote_prozent'] == b['quote_prozent']


def test_luecken_sortiert_nicht_erfuellt_zuerst():
    s = status.build_status([
        _f('ISO', 'offen', question_num=3),
        _f('ISO', 'teilweise', question_num=2),
        _f('ISO', 'nicht_erfuellt', question_num=1),
        _f('ISO', 'erfuellt', question_num=4),
    ])
    assert [l['erfuellung'] for l in s['luecken']] == [
        'nicht_erfuellt', 'teilweise', 'offen']


def test_luecken_limit():
    s = status.build_status([_f('ISO', 'nicht_erfuellt')] * 50, luecken_limit=5)
    assert len(s['luecken']) == 5


# ── Altdaten (Projekte vor v7.4.0) ───────────────────────────────────────────

@pytest.mark.parametrize('alt,erwartet', [
    ('erfüllt', 'erfuellt'), ('ja', 'erfuellt'), ('konform', 'erfuellt'),
    ('teilweise erfüllt (Nachweis fehlt)', 'teilweise'), ('ausreichend', 'teilweise'),
    ('nicht erfüllt', 'nicht_erfuellt'), ('mangelhaft', 'nicht_erfuellt'),
    ('n/a', 'nicht_anwendbar'), ('entfällt', 'nicht_anwendbar'),
    ('', 'offen'), (None, 'offen'), ('Kauderwelsch', 'offen'),
])
def test_freitext_bewertung_wird_gemappt(alt, erwartet):
    assert status.normalize_erfuellung(alt) == erwartet


def test_altes_bewertungsfeld_wird_genutzt_wenn_erfuellung_fehlt():
    """Bestandsprojekte bekommen ohne Nachbearbeitung eine Stufe."""
    s = status.build_status([
        {'framework': 'ISO', 'bewertung': 'erfüllt', 'frage': 'A'},
        {'framework': 'ISO', 'bewertung': 'nicht erfüllt', 'frage': 'B'},
    ])
    assert s['quote_prozent'] == 50.0


def test_erfuellung_schlaegt_bewertung():
    frage = {'framework': 'ISO', 'erfuellung': 'nicht_erfuellt',
             'bewertung': 'erfüllt', 'frage': 'A'}
    assert status.erfuellung_of(frage) == 'nicht_erfuellt'


# ── Prompt: die KI darf die Stufe nicht setzen ────────────────────────────────

def test_prompt_gibt_die_stufe_vor():
    st = status.build_status([_f('ISO', 'erfuellt')] * 9 + [_f('ISO', 'nicht_erfuellt')])
    p = prompts.build_status_prompt({'name': 'A1', 'unternehmen': 'Acme'}, st)
    assert 'weitgehend compliant' in p
    assert 'VORGABE' in p
    assert 'nicht verändert' in p


def test_prompt_enthaelt_luecken_und_begrenzt_sie():
    st = status.build_status([_f('ISO', 'nicht_erfuellt', frage=f'Luecke {i}')
                              for i in range(100)], luecken_limit=10)
    p = prompts.build_status_prompt({'name': 'A1'}, st, luecken_limit=10)
    assert 'Luecke 0' in p
    assert 'Luecke 50' not in p


def test_parser_vertraegt_rahmen_und_zusatztext():
    roh = ('Hier die Auswertung:\n```json\n'
           '{"kundenmitteilung": "Text", "fazit": "Fazit", '
           '"je_framework": [{"framework": "ISO", "einschaetzung": "E", '
           '"hauptluecken": ["L1"], "naechste_schritte": ["S1"]}], '
           '"top_massnahmen": [{"massnahme": "M", "begruendung": "B", '
           '"prioritaet": "Hoch", "aufwand": "mittel"}]}\n```\nViel Erfolg!')
    out = prompts.parse_status_response(roh)
    assert out['kundenmitteilung'] == 'Text'
    assert out['je_framework'][0]['hauptluecken'] == ['L1']
    assert out['top_massnahmen'][0]['prioritaet'] == 'hoch'  # normalisiert


def test_parser_wirft_bei_unlesbarer_antwort():
    with pytest.raises(ValueError):
        prompts.parse_status_response('Dazu kann ich nichts sagen.')


# ── Lizenzierung: Grundpreis-Modul ───────────────────────────────────────────

def test_compliance_audit_ist_grundpreis_modul():
    assert 'compliance_audit' in lic.BASE_MODULES
    # Jede gültige Lizenz schließt es ein, auch ohne Nennung im Token.
    assert lic.is_allowed('compliance_audit', {'cra'}) is True
    assert lic.is_allowed('compliance_audit', None) is True


def test_ohne_bestaetigte_lizenz_gesperrt():
    assert lic.is_allowed('compliance_audit', set()) is False


def test_pfad_wird_auf_das_modul_abgebildet():
    assert lic.module_for_path('/api/compliance-audit/projekte') == 'compliance_audit'
    assert lic.module_for_path('/api/compliance-audit') == 'compliance_audit'
    assert lic.canonical('audit') == 'compliance_audit'


def test_gutachten_bleibt_explizit():
    """Die Trennung darf das Gutachten-Gating nicht aufweichen."""
    assert lic.is_allowed('gutachten', None) is False
    assert lic.is_allowed('gutachten', {'gutachten'}) is True
    assert 'gutachten' not in lic.BASE_MODULES


def test_effektive_module_enthalten_audit():
    assert 'compliance_audit' in lic.effective_modules({'cra'})


def test_audit_ist_nicht_abrechenbares_zusatzmodul():
    """Grundpreis heißt: keine eigene Rechnungsposition."""
    assert 'compliance_audit' not in lic.billable_modules(None)


def test_firmen_schalter_registriert():
    assert lic.FIRMEN_MODULE_COLUMNS['compliance_audit'] == 'module_compliance_audit'


# ── Datenhaltung + API ───────────────────────────────────────────────────────

@pytest.fixture
def audit_db(monkeypatch):
    """Wegwerf-Schema; der Pfad ist unter Postgres nur ein Schema-Selektor.

    Der Blueprint liest seinen Pfad aus einer Modul-Konstante — die wird hier
    mitgezogen, damit die API-Tests dasselbe Schema sehen wie die DB-Tests.
    """
    from compliance_audit import db as adb
    from gutachten.db import save_project

    p = Path('data/db/pytest_audit_1713.sqlite')
    p.parent.mkdir(parents=True, exist_ok=True)
    adb.ensure_db(p)
    con = adb._connect(p)
    try:
        for tabelle in ('audit_wasserstand', 'gutachten_questions', 'gutachten_projects'):
            con.execute(f'DELETE FROM {tabelle}')  # nosec B608 — Konstanten
        con.commit()
    finally:
        con.close()
    save_project(p, 'AuditTest', frameworks=['ISO 27001'],
                 pruefungsfokus='Testfokus', unternehmen='Acme')

    import server.api.compliance_audit as bp
    monkeypatch.setattr(bp, 'DB_PATH', p)
    return p


def test_erfuellung_spalte_existiert_und_validiert(audit_db):
    from compliance_audit import db as adb
    from gutachten.db import save_questions, load_questions

    save_questions(audit_db, 'AuditTest', [
        {'question_num': 1, 'framework': 'ISO 27001', 'frage': 'A', 'bewertung': 'erfüllt'},
    ])
    q = load_questions(audit_db, 'AuditTest')[0]
    assert 'erfuellung' in q
    assert adb.set_erfuellung(audit_db, q['id'], 'teilweise') is True
    assert adb.set_erfuellung(audit_db, q['id'], 'phantasiewert') is False


def test_backfill_ueberschreibt_gesetzte_werte_nicht(audit_db):
    from compliance_audit import db as adb
    from gutachten.db import save_questions, load_questions

    save_questions(audit_db, 'AuditTest', [
        {'question_num': 1, 'framework': 'ISO 27001', 'frage': 'A', 'bewertung': 'erfüllt'},
        {'question_num': 2, 'framework': 'ISO 27001', 'frage': 'B', 'bewertung': 'mangelhaft'},
    ])
    fragen = load_questions(audit_db, 'AuditTest')
    # Auditor-Entscheidung auf Frage 1 — die muss gewinnen.
    adb.set_erfuellung(audit_db, fragen[0]['id'], 'nicht_erfuellt')
    adb.backfill_erfuellung(audit_db, 'AuditTest')
    danach = {q['question_num']: q['erfuellung']
              for q in load_questions(audit_db, 'AuditTest')}
    assert danach[1] == 'nicht_erfuellt'   # nicht auf 'erfuellt' zurückgesetzt
    assert danach[2] == 'nicht_erfuellt'   # aus 'mangelhaft' abgeleitet


def test_wasserstand_speichert_rechnung_und_ki_getrennt(audit_db):
    from compliance_audit import db as adb

    st = status.build_status([_f('ISO', 'erfuellt')] * 8 + [_f('ISO', 'nicht_erfuellt')] * 2)
    rid = adb.save_wasserstand(audit_db, 'AuditTest', status=st,
                               ki={'kundenmitteilung': 'Text'}, provider='on_prem')
    w = adb.load_wasserstand(audit_db, rid)
    assert w['stufe'] == 'weitgehend'
    assert w['status']['quote_prozent'] == 80.0
    assert w['ki']['kundenmitteilung'] == 'Text'
    assert len(adb.list_wasserstand(audit_db, 'AuditTest')) == 1


def test_api_status_endpunkt(client, auth_headers, audit_db):
    from gutachten.db import save_questions

    save_questions(audit_db, 'AuditTest', [
        {'question_num': 1, 'framework': 'ISO 27001', 'frage': 'A', 'erfuellung': 'erfuellt'},
    ])
    r = client.get('/api/compliance-audit/AuditTest/status', headers=auth_headers)
    assert r.status_code == 200, r.data
    assert r.json['stufe'] in status.STUFEN or r.json['stufe'] == 'unbewertet'


def test_api_unbekanntes_projekt_404(client, auth_headers):
    r = client.get('/api/compliance-audit/GibtsNicht/status', headers=auth_headers)
    assert r.status_code == 404


def test_api_erfuellung_validiert(client, auth_headers, audit_db):
    from gutachten.db import save_questions, load_questions

    save_questions(audit_db, 'AuditTest', [
        {'question_num': 1, 'framework': 'ISO 27001', 'frage': 'A'},
    ])
    qid = load_questions(audit_db, 'AuditTest')[0]['id']
    r = client.put(f'/api/compliance-audit/questions/{qid}/erfuellung',
                   json={'erfuellung': 'quatsch'}, headers=auth_headers)
    assert r.status_code == 400
    r = client.put(f'/api/compliance-audit/questions/{qid}/erfuellung',
                   json={'erfuellung': 'erfuellt'}, headers=auth_headers)
    assert r.status_code == 200


def test_audit_endpunkte_nicht_mehr_unter_gutachten(client, auth_headers):
    """Die Trennung ist vollzogen — der alte Pfad liefert keine Audit-Daten mehr."""
    r = client.get('/api/gutachten/projekte', headers=auth_headers)
    assert r.status_code == 404
