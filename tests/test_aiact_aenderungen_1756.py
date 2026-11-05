"""Änderungsverwaltung je KI-System — Art. 43 Abs. 4 (#1756).

Die Tests halten die drei Punkte fest, an denen sich dieser Vorgang vom
CRA-Release-Vorgang unterscheidet und an denen eine Kopie falsch gewesen wäre:

1. Der Auslöser ist eine Änderung am System, nicht ein Build — der Vorgang trägt
   einen Änderungsgrund und Modell-/Datenstände.
2. **Die Kernfrage hat drei Antworten.** ``vorab_bewertet`` ist ein eigener
   Zustand: Art. 43 Abs. 4 nimmt vorab festgelegte und mitbewertete Änderungen
   aus, und bei fortlernenden Systemen ist das der Normalfall. Ein
   Zwei-Zustands-Feld hätte entweder Daueralarm erzeugt oder die
   Dokumentationspflicht verschwinden lassen.
3. Der Vorgang hängt am KI-System. Eine Organisation mit KI-Systemen antwortet
   wie bei jedem anderen Register mit 409 ``org_controls_locked``.

Dazu die Mechanik, die der CRA-Weg schon teuer gelernt hat: Vier-Augen-Prüfung,
Begründungspflichten, gerechnete Punkte sind nicht von Hand setzbar, und
„ungeprüft ist nicht erfüllt" (#1751).
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token

from server.models.permission import allowed_modules_for, resolve_permissions

BASE = '/api/aiact'
AEND = '/api/aiact-aenderungen'
FIRMA = 'pytest-1756-firma'
SYSTEM = f'{FIRMA} – Chatbot'
STAND = 'modell-2026-10'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


# ═══════════════════════════════════════════════════════════════════════════
# Rechte (#1756 — eigene Permission, kein Durchfallen über _ALL_WRITE)
# ═══════════════════════════════════════════════════════════════════════════

def test_approve_ist_ein_signoff_recht():
    """``AIACT_APPROVE`` darf nicht über die generische ``editor``-Rolle
    mitkommen — sonst gibt der Ersteller sich selbst frei."""
    from server.models.permission import (MODULE_PERMISSIONS, Permission,
                                          SIGN_OFF_PERMISSIONS)

    assert Permission.AIACT_APPROVE in SIGN_OFF_PERMISSIONS
    # Fachlich gehört das Recht weiter zum Modul: sonst verschwindet es aus dem
    # Rechte-Feintuning der Benutzerverwaltung.
    assert Permission.AIACT_APPROVE in MODULE_PERMISSIONS['aiact']

    editor = set(resolve_permissions(['editor']))
    assert 'aiact:approve' not in editor
    assert 'aiact:write' in editor, 'der Fix darf dem Editor nichts nehmen'


def test_aiact_editor_schreibt_aber_gibt_nicht_frei():
    rechte = set(resolve_permissions(['aiact_editor']))
    assert 'aiact:write' in rechte and 'aiact:read' in rechte
    assert 'aiact:approve' not in rechte


def test_aiact_approver_gibt_frei_aber_schreibt_nicht():
    rechte = set(resolve_permissions(['aiact_approver']))
    assert 'aiact:approve' in rechte and 'aiact:read' in rechte
    assert 'aiact:write' not in rechte, (
        'ein Prüfer mit Schreibrecht kann den Gegenstand seiner Prüfung ändern')


def test_rolle_erscheint_im_katalog():
    """Die Benutzerverwaltung liest den Rollen-Katalog aus dem Enum — eine
    Rolle, die dort fehlt, kann niemand zuweisen."""
    from server.models.permission import ROLE_PERMISSIONS, RoleEnum

    assert RoleEnum.AIACT_APPROVER in ROLE_PERMISSIONS
    assert RoleEnum('aiact_approver') is RoleEnum.AIACT_APPROVER
    assert 'aiact' in allowed_modules_for(['aiact_approver'])


def test_signoff_pfade_tragen_die_bekannten_endungen():
    """#1754: Der Modul-Guard erkennt ``/freigeben``/``/zurueckweisen`` und
    akzeptiert dort ``approve``. Eigene Pfadnamen würden die Freigabe-Rolle
    vor dem Endpunkt abweisen."""
    from server.middleware.authz import _SIGNOFF_MARKERS

    for pfad in (f'{AEND}/projekte/P/aenderungen/S/freigeben',
                 f'{AEND}/projekte/P/aenderungen/S/zurueckweisen'):
        assert any(m in pfad.lower() for m in _SIGNOFF_MARKERS), pfad


# ═══════════════════════════════════════════════════════════════════════════
# Katalog
# ═══════════════════════════════════════════════════════════════════════════

def test_katalog_fuehrt_die_drei_arten_mit_rechtsbezug():
    from ai_act import aenderung_checkliste as ac

    arten = {i.art for i in ac.KATALOG}
    assert arten == {'gerechnet', 'entscheidung', 'gleichbleibend'}
    assert all(i.rechtsbezug for i in ac.KATALOG), 'jeder Punkt braucht eine Norm'

    # Der Rechts-Kanon des AI Act — nicht der des CRA.
    bezuege = ' '.join(i.rechtsbezug for i in ac.KATALOG)
    for norm in ('Art. 11', 'Art. 9', 'Art. 10', 'Art. 47', 'Art. 48',
                 'Art. 49', 'Art. 72', 'Art. 73', 'Art. 12', 'Art. 14',
                 'Art. 43 Abs. 4'):
        assert norm in bezuege, f'{norm} fehlt im Katalog'
    assert 'Anhang IV' in bezuege


def test_vorab_bewertet_blendet_nur_die_neubewertung_aus():
    """Der fachliche Kern: Die Ausnahme des Art. 43 Abs. 4 nimmt die erneute
    Konformitätsbewertung samt DoC/CE heraus — und **nur** die. Anhang IV,
    Protokollierung und Beobachtungsplan bleiben."""
    from ai_act import aenderung_checkliste as ac

    rel = {i['id']: i for i in ac.relevanter_katalog('vorab_bewertet', 'nachtraining')}
    assert rel['doc_ce_aktuell']['relevant'] is False
    assert rel['konformitaetsbewertung_durchlaufen']['relevant'] is False
    assert 'Art. 43 Abs. 4' in rel['doc_ce_aktuell']['nicht_relevant_grund']

    for weiter in ('annex_iv_aktuell', 'protokollierung_geprueft',
                   'pmm_plan_angepasst', 'eu_registrierung_aktuell',
                   'keine_offene_vorfallmeldung'):
        assert rel[weiter]['relevant'] is True, weiter

    # Bei „ja" gilt beides.
    ja = {i['id']: i for i in ac.relevanter_katalog('ja', 'nachtraining')}
    assert ja['doc_ce_aktuell']['relevant'] is True


def test_unbeantwortete_kernfrage_blendet_nichts_aus():
    """Solange niemand geantwortet hat, ist nicht entschieden, ob die Ausnahme
    greift. Ein ausgeblendeter Punkt sähe aus wie ein erledigter."""
    from ai_act import aenderung_checkliste as ac

    rel = ac.relevanter_katalog('', '')
    assert all(i['relevant'] for i in rel)


def test_anlass_steuert_die_datenpflichten():
    from ai_act import aenderung_checkliste as ac

    daten = {i['id']: i for i in ac.relevanter_katalog('nein', 'daten')}
    zweck = {i['id']: i for i in ac.relevanter_katalog('nein', 'zweck')}
    assert daten['daten_governance_geprueft']['relevant'] is True
    assert zweck['daten_governance_geprueft']['relevant'] is False
    assert zweck['menschliche_aufsicht_geprueft']['relevant'] is True


# ═══════════════════════════════════════════════════════════════════════════
# Statusmaschine, Kernfrage, Begründungen (Datenbankschicht)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def vorgang(tmp_path):
    from ai_act import aenderungen_db as adb

    db = tmp_path / 'ai_act.sqlite'
    adb.ensure_table(db)
    # Reste aus einem früheren Lauf: Schema ist je Modul geteilt (#1340).
    from shared import db as _sdb
    with _sdb.connect(db) as con:
        con.execute("DELETE FROM aiact_aenderungen WHERE projekt_name=?", (SYSTEM,))
    rec = adb.create_aenderung(db, SYSTEM, {
        'stand': STAND, 'grund_art': 'nachtraining',
        'beschreibung': 'Nachtraining auf Daten aus Q3',
        'modell_version': 'm-4.2', 'daten_version': 'ds-2026-09'}, von='dev@example.com')
    assert rec['status'] == 'entwurf'
    return db, adb


def test_auslöser_ist_eine_aenderung_kein_build(vorgang):
    """Der Vorgang muss Modell- und Datenstand führen können — ein Build-Tag
    allein beschreibt ein Nachtraining nicht."""
    db, adb = vorgang
    rec = adb.get_aenderung(db, SYSTEM, STAND)
    assert rec['grund_art'] == 'nachtraining'
    assert rec['modell_version'] == 'm-4.2' and rec['daten_version'] == 'ds-2026-09'


def test_drei_antworten_auf_die_kernfrage(vorgang):
    db, adb = vorgang
    for wert, neubewertung in (('ja', True), ('nein', False)):
        rec = adb.set_wesentlich(db, SYSTEM, STAND, wert,
                                 'Begründung mit ausreichender Länge', von='dev@example.com')
        assert rec['wesentlich'] == wert
        assert rec['neubewertung_erforderlich'] is neubewertung

    rec = adb.set_wesentlich(
        db, SYSTEM, STAND, 'vorab_bewertet',
        'Im Rahmen des vorgesehenen Nachtrainings vorab festgelegt und bewertet',
        von='dev@example.com', vorab_referenz='TechDoc Anhang IV Nr. 2 f, Abschnitt 4.3')
    assert rec['wesentlich'] == 'vorab_bewertet'
    # Der Punkt dieses Issues: eigener Zustand, KEINE Neubewertung.
    assert rec['neubewertung_erforderlich'] is False
    assert rec['vorab_referenz']
    assert rec['wesentlich_von'] == 'dev@example.com' and rec['wesentlich_am']


def test_vierter_wert_wird_abgelehnt(vorgang):
    db, adb = vorgang
    with pytest.raises(ValueError):
        adb.set_wesentlich(db, SYSTEM, STAND, 'vielleicht', 'Begründung lang genug')


def test_jede_antwort_braucht_eine_begruendung(vorgang):
    """Auch „nein" — gerade die Aussage „das war keine wesentliche Änderung"
    ist die, die später hinterfragt wird."""
    db, adb = vorgang
    for wert in ('ja', 'nein', 'vorab_bewertet'):
        with pytest.raises(ValueError, match='Begründung'):
            adb.set_wesentlich(db, SYSTEM, STAND, wert, 'kurz')


def test_vorab_bewertet_braucht_eine_fundstelle(vorgang):
    """Ohne Fundstelle wäre die Ausnahme der bequemste Weg, jede
    Änderungspflicht abzuräumen."""
    db, adb = vorgang
    with pytest.raises(ValueError, match='Fundstelle'):
        adb.set_wesentlich(db, SYSTEM, STAND, 'vorab_bewertet',
                           'War von Anfang an so vorgesehen')


def test_gerechnete_punkte_sind_nicht_setzbar(vorgang):
    db, adb = vorgang
    with pytest.raises(ValueError, match='gerechnet'):
        adb.set_checkliste(db, SYSTEM, STAND, 'annex_iv_aktuell', 'erledigt',
                           'Dokumentation nachgezogen am 20.10.')


def test_kernfrage_laeuft_nicht_ueber_die_checkliste(vorgang):
    """Sie hat drei Antworten und eigene Felder — ein Haken könnte das nicht
    tragen."""
    db, adb = vorgang
    with pytest.raises(ValueError, match='drei Antworten'):
        adb.set_checkliste(db, SYSTEM, STAND, 'wesentliche_aenderung', 'erledigt',
                           'Haben wir geprüft und entschieden')


def test_entscheidung_braucht_begruendung_auch_bei_nicht_anwendbar(vorgang):
    db, adb = vorgang
    with pytest.raises(ValueError, match='Begründung'):
        adb.set_checkliste(db, SYSTEM, STAND, 'risikomanagement_aktualisiert',
                           'nicht_anwendbar', '')
    rec = adb.set_checkliste(db, SYSTEM, STAND, 'risikomanagement_aktualisiert',
                             'erledigt', 'Risikoregister am 21.10. fortgeschrieben',
                             von='dev@example.com')
    eintrag = rec['checkliste']['risikomanagement_aktualisiert']
    assert eintrag['status'] == 'erledigt' and eintrag['von'] == 'dev@example.com'


def test_einreichen_verlangt_die_beantwortete_kernfrage(vorgang):
    """Ein Vorgang ohne Antwort auf Art. 43 Abs. 4 legt dem Prüfer nichts vor."""
    db, adb = vorgang
    with pytest.raises(ValueError, match='Art. 43 Abs. 4'):
        adb.einreichen(db, SYSTEM, STAND, von='dev@example.com')


def test_statusmaschine_bis_umgesetzt(vorgang):
    db, adb = vorgang
    adb.set_wesentlich(db, SYSTEM, STAND, 'nein', 'Keine Änderung an Zweck oder Leistung',
                       von='dev@example.com')

    rec = adb.einreichen(db, SYSTEM, STAND, von='dev@example.com',
                         gate={'ampel': 'bedingt'})
    assert rec['status'] == 'in_pruefung' and rec['gesperrt'] is True
    assert rec['erstellt_von'] == 'dev@example.com' and rec['eingereicht_am']
    # Der Rechenstand ist eingefroren — sonst prüft die zweite Instanz gegen
    # eine Datenlage, die sich bis zur Freigabe verschiebt.
    assert rec['gate'] == {'ampel': 'bedingt'}

    # Gesperrt heißt gesperrt: weder Stammdaten noch Checkliste noch Kernfrage.
    with pytest.raises(ValueError, match='gesperrt'):
        adb.update_stammdaten(db, SYSTEM, STAND, {'beschreibung': 'anders'})
    with pytest.raises(ValueError, match='gesperrt'):
        adb.set_checkliste(db, SYSTEM, STAND, 'protokollierung_geprueft', 'erledigt',
                           'Protokollierung geprüft und angepasst')
    with pytest.raises(ValueError, match='gesperrt'):
        adb.set_wesentlich(db, SYSTEM, STAND, 'ja', 'Doch wesentlich, zweiter Blick')

    rec = adb.freigeben(db, SYSTEM, STAND, von='compliance@example.com')
    assert rec['status'] == 'freigegeben'
    assert rec['freigegeben_von'] == 'compliance@example.com'

    rec = adb.umsetzen(db, SYSTEM, STAND)
    assert rec['status'] == 'umgesetzt' and rec['umgesetzt_am']


def test_vier_augen_der_einreicher_gibt_nicht_frei(vorgang):
    db, adb = vorgang
    adb.set_wesentlich(db, SYSTEM, STAND, 'nein', 'Keine wesentliche Änderung',
                       von='dev@example.com')
    adb.einreichen(db, SYSTEM, STAND, von='dev@example.com')
    with pytest.raises(ValueError, match='Vier-Augen'):
        adb.freigeben(db, SYSTEM, STAND, von='DEV@example.com')


def test_erneutes_einreichen_macht_den_einreicher_nicht_zum_freigeber(vorgang):
    """Sonst reicht man zweimal ein — einmal unter fremdem, einmal unter
    eigenem Namen — und gibt sich dann selbst frei."""
    db, adb = vorgang
    adb.set_wesentlich(db, SYSTEM, STAND, 'nein', 'Keine wesentliche Änderung',
                       von='dev@example.com')
    adb.einreichen(db, SYSTEM, STAND, von='dev@example.com')
    adb.zurueckweisen(db, SYSTEM, STAND, von='compliance@example.com',
                      grund='Anhang-IV-Doku fehlt noch')
    rec = adb.einreichen(db, SYSTEM, STAND, von='compliance@example.com')
    assert rec['erstellt_von'] == 'dev@example.com'
    with pytest.raises(ValueError, match='Vier-Augen'):
        adb.freigeben(db, SYSTEM, STAND, von='dev@example.com')


def test_freigabe_setzt_eine_einreichung_voraus(vorgang):
    db, adb = vorgang
    with pytest.raises(ValueError, match='Einreichung'):
        adb.freigeben(db, SYSTEM, STAND, von='compliance@example.com')


def test_umsetzen_setzt_eine_freigabe_voraus(vorgang):
    db, adb = vorgang
    with pytest.raises(ValueError, match='Freigabe'):
        adb.umsetzen(db, SYSTEM, STAND)


def test_zurueckweisung_braucht_eine_begruendung(vorgang):
    db, adb = vorgang
    adb.set_wesentlich(db, SYSTEM, STAND, 'nein', 'Keine wesentliche Änderung',
                       von='dev@example.com')
    adb.einreichen(db, SYSTEM, STAND, von='dev@example.com')
    with pytest.raises(ValueError, match='Begründung'):
        adb.zurueckweisen(db, SYSTEM, STAND, von='compliance@example.com', grund='nein')
    rec = adb.zurueckweisen(db, SYSTEM, STAND, von='compliance@example.com',
                            grund='Beobachtungsplan nicht angepasst (Art. 72)')
    assert rec['status'] == 'zurueckgewiesen' and rec['gesperrt'] is False
    assert rec['zurueckweisung_grund']


def test_eingereichter_vorgang_wird_nicht_geloescht(vorgang):
    db, adb = vorgang
    adb.set_wesentlich(db, SYSTEM, STAND, 'nein', 'Keine wesentliche Änderung',
                       von='dev@example.com')
    adb.einreichen(db, SYSTEM, STAND, von='dev@example.com')
    with pytest.raises(ValueError, match='Entwurf'):
        adb.delete_aenderung(db, SYSTEM, STAND)


def test_anlegen_ist_idempotent(vorgang):
    db, adb = vorgang
    wieder = adb.create_aenderung(db, SYSTEM, {'stand': STAND, 'grund_art': 'daten'})
    # Idempotent heißt: derselbe Vorgang, nicht ein überschriebener.
    assert wieder['grund_art'] == 'nachtraining'
    assert len(adb.list_aenderungen(db, SYSTEM)) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Gate — „ungeprüft ist nicht erfüllt" (#1751)
# ═══════════════════════════════════════════════════════════════════════════

def test_quellenausfall_wird_sichtbar_und_verhindert_gruen(monkeypatch):
    """Ein stilles ``except: pass`` würde den Punkt verschwinden lassen und die
    Ampel grün färben — in einem Konformitäts-Gate der gefährlichste Fehler,
    weil er wie ein gutes Ergebnis aussieht."""
    from ai_act import aenderung_gate as g
    from ai_act import incidents as inc

    def kaputt(*_a, **_k):
        raise RuntimeError('Tabelle nicht erreichbar')

    monkeypatch.setattr(inc, 'list_incidents', kaputt)
    # Nur die Vorfall-Prüfung laufen lassen: so ist die Aussage über den
    # Quellenausfall nicht von der Datenlage der übrigen Register abhängig.
    monkeypatch.setattr(g, '_CHECKS', (g._check_vorfaelle,))

    res = g.evaluate('egal', wesentlich='nein')
    assert res['ampel'] != 'gruen'
    assert res['ungeprueft'], 'der Ausfall ist nicht sichtbar'
    punkt = next(p for p in res['offene_punkte'] if p.get('ungeprueft'))
    assert 'Tabelle nicht erreichbar' in punkt['hinweis']
    assert res['befunde']['ueberfaellige_meldungen'] is None, (
        'ein 0 oder [] hier wäre die Aussage „keine überfälligen Meldungen"')


def test_gruen_nur_ohne_jeden_offenen_punkt(monkeypatch):
    """Gegenprobe zum Test davor — ohne sie belegt er nicht, dass der Ausfall
    das Grün verhindert hat."""
    from ai_act import aenderung_gate as g

    monkeypatch.setattr(g, '_CHECKS', ())
    assert g.evaluate('egal', wesentlich='nein')['ampel'] == 'gruen'


def test_eine_kaputte_pruefung_nimmt_die_folgenden_nicht_mit(monkeypatch):
    from ai_act import aenderung_gate as g

    def kaputt(_ctx, _b, _p):
        raise RuntimeError('boom')

    gesehen: list[str] = []

    def danach(_ctx, befunde, _p):
        gesehen.append('ja')
        befunde['danach'] = True

    monkeypatch.setattr(g, '_CHECKS', (kaputt, danach))
    res = g.evaluate('egal')
    assert gesehen == ['ja'] and res['befunde'].get('danach') is True
    assert res['ungeprueft']


def test_jede_gerechnete_quelle_kommt_im_gate_an():
    """Der Katalog verspricht bei jedem ``gerechnet``-Punkt, unter welchem
    Schlüssel das Gate das Ergebnis liefert. Ein Tippfehler dort wäre im
    Nachweis eine leere Zeile — und zwar eine, die wie „nicht beanstandet"
    aussieht."""
    from ai_act import aenderung_checkliste as ac
    from ai_act import aenderung_gate as g

    befunde = g.evaluate('pytest-1756-quellen', wesentlich='ja')['befunde']
    for i in ac.KATALOG:
        if i.art == 'gerechnet':
            assert i.quelle, f'{i.id} nennt keine Quelle'
            assert i.quelle in befunde, f'{i.id}: „{i.quelle}" fehlt im Gate'


def test_gate_liest_die_echte_dokumententabelle(tmp_path, monkeypatch):
    """Regression auf einen Schlüssel, der leicht falsch ist: Das Dokumente-
    Register führt AI Act unter ``ai_act``, der REST-Prefix heißt ``aiact``.
    Mit dem falschen Schlüssel wirft ``table_name`` — und weil die Prüfung ihre
    Fehler kapselt, hätte sie dauerhaft „ungeprüft" gemeldet, ohne dass es
    auffällt.
    """
    from shared.documents.db import MODULES, create_document, table_name
    from ai_act import aenderung_gate as g

    assert 'ai_act' in MODULES and table_name('ai_act') == 'ai_act_managed_docs'

    db = tmp_path / 'ai_act.sqlite'
    projekt = 'pytest-1756-docs'
    from shared import db as _sdb
    create_document(db, 'ai_act', projekt=projekt,
                    doc_type='technische_doku_annex_iv', titel='TechDoc')
    monkeypatch.setattr(g, '_CHECKS', (g._check_annex_iv,))
    res = g.evaluate(projekt, db_path=db)
    assert res['befunde']['annex_iv']['dokumente'] == 1, res['befunde']
    with _sdb.connect(db) as con:
        con.execute("DELETE FROM ai_act_managed_docs WHERE projekt=?", (projekt,))


def test_annex_iv_nicht_nachgezogen_wird_gemeldet(tmp_path, monkeypatch):
    """Die Pflicht aus Art. 11 ist nicht „Dokumentation vorhanden", sondern
    „Dokumentation aktuell". Eine Doku, die den Vorgänger-Modellstand
    beschreibt, belegt das System nicht, das in Betrieb ist."""
    from shared.documents.db import create_document
    from shared import db as _sdb
    from ai_act import aenderung_gate as g

    db = tmp_path / 'ai_act.sqlite'
    projekt = 'pytest-1756-annexiv'
    create_document(db, 'ai_act', projekt=projekt,
                    doc_type='technische_doku_annex_iv', titel='TechDoc')
    monkeypatch.setattr(g, '_CHECKS', (g._check_annex_iv,))

    # Änderung liegt NACH dem Dokumentationsstand → offener Punkt.
    spaet = g.evaluate(projekt, seit='2099-01-01 00:00:00', db_path=db)
    assert spaet['befunde']['annex_iv_aktuell'] is False
    assert any(p['typ'] == 'annex_iv' for p in spaet['offene_punkte'])

    # Änderung liegt davor → nachgezogen, kein Punkt.
    frueh = g.evaluate(projekt, seit='2000-01-01 00:00:00', db_path=db)
    assert frueh['befunde']['annex_iv_aktuell'] is True
    assert not frueh['offene_punkte']

    with _sdb.connect(db) as con:
        con.execute("DELETE FROM ai_act_managed_docs WHERE projekt=?", (projekt,))


def test_vorab_bewertet_erzeugt_keinen_konformitaets_punkt(monkeypatch):
    """Der Daueralarm, den das Issue verhindern will: Bei einem fortlernenden
    System darf eine vorab bewertete Anpassung keine erneute
    Konformitätsbewertung verlangen."""
    from ai_act import aenderung_gate as g

    monkeypatch.setattr(g, '_CHECKS', (g._check_doc_ce,))

    offen = g.evaluate(SYSTEM, wesentlich='ja')
    assert any(p['typ'] == 'konformitaet' for p in offen['offene_punkte'])
    assert offen['neubewertung_erforderlich'] is True

    for wert in ('nein', 'vorab_bewertet'):
        res = g.evaluate(SYSTEM, wesentlich=wert)
        assert not res['offene_punkte'], (wert, res['offene_punkte'])
        assert res['neubewertung_erforderlich'] is False
        # Dass nicht geprüft wurde, steht trotzdem in der Akte — mit Grund.
        assert res['befunde']['doc_ce_geprueft'] is False
        assert res['befunde']['doc_ce_grund']


# ═══════════════════════════════════════════════════════════════════════════
# REST — Scope, Anlegen nur per POST, Rechtetrennung über den Guard
# ═══════════════════════════════════════════════════════════════════════════

def _h(app, roles, ident: str | None = None):
    """Header für eine Rollenkombination.

    ``ident`` ist wichtig: Die Vier-Augen-Prüfung vergleicht die Identität, nicht
    die Rolle. Ein Test, der dieselbe Person mit zusätzlichem Freigaberecht
    nachstellen will, muss dieselbe Identität verwenden — sonst prüft er nur,
    dass zwei verschiedene Benutzer nacheinander arbeiten können.
    """
    with app.app_context():
        token = create_access_token(
            identity=ident or f'u-1756-{"-".join(roles)}',
            additional_claims={'roles': roles,
                               'permissions': resolve_permissions(roles, []),
                               'extra_permissions': [],
                               'allowed_modules': allowed_modules_for(roles, [], None)},
            expires_delta=timedelta(hours=1))
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def system(client, auth_headers):
    """Organisation + KI-System. Beides wird gebraucht: Der Vorgang hängt am
    System, und die Organisation ist damit für Register gesperrt (#1562)."""
    for n in (SYSTEM, FIRMA):
        client.delete(f'{BASE}/projekte/{n}', headers=auth_headers)
    r = client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': FIRMA, 'organisation': FIRMA})
    assert r.status_code == 201, r.get_json()
    r = client.post(f'{BASE}/projekte/{FIRMA}/systeme', headers=auth_headers,
                    json={'produkt': 'Chatbot', 'uebernehmen': False})
    assert r.status_code == 201, r.get_json()
    yield SYSTEM
    for n in (SYSTEM, FIRMA):
        client.delete(f'{BASE}/projekte/{n}', headers=auth_headers)


def test_get_legt_nichts_an(client, auth_headers, system):
    """#1747-Lehre: Ein Deep-Link mit Tippfehler darf keinen Entwurf hinterlassen."""
    r = client.get(f'{AEND}/projekte/{system}/aenderungen/tippfehler',
                   headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d['vorgang'] is None and d['existiert'] is False
    # Die Ampel steht trotzdem bereit: Man will den Stand kennen, bevor man
    # einen Vorgang eröffnet.
    assert d['gate']['ampel'] in ('gruen', 'bedingt', 'rot')
    assert d['katalog'] and d['stand']

    liste = client.get(f'{AEND}/projekte/{system}/aenderungen', headers=auth_headers)
    assert [a['stand'] for a in liste.get_json()['aenderungen']] == []


def test_post_legt_an_und_liste_zeigt_den_scope(client, auth_headers, system):
    r = client.post(f'{AEND}/projekte/{system}/aenderungen', headers=auth_headers,
                    json={'stand': STAND, 'grund_art': 'nachtraining',
                          'beschreibung': 'Nachtraining Q3'})
    assert r.status_code == 201, r.get_json()
    assert r.get_json()['status'] == 'entwurf'

    liste = client.get(f'{AEND}/projekte/{system}/aenderungen',
                       headers=auth_headers).get_json()
    assert liste['ist_ki_system'] is True and liste['scope'] == 'system'
    assert [a['stand'] for a in liste['aenderungen']] == [STAND]


def test_unbekanntes_projekt_ist_404(client, auth_headers):
    r = client.get(f'{AEND}/projekte/gibt-es-nicht-1756/aenderungen',
                   headers=auth_headers)
    assert r.status_code == 404, r.get_json()


def test_organisation_mit_ki_systemen_antwortet_409(client, auth_headers, system):
    """Wie jedes andere Register (#1562) — kein eigenes Fehlerbild."""
    r = client.post(f'{AEND}/projekte/{FIRMA}/aenderungen', headers=auth_headers,
                    json={'stand': 'org-stand'})
    assert r.status_code == 409, r.get_json()
    assert r.get_json()['code'] == 'org_controls_locked'


def test_editor_kann_nicht_freigeben(client, app, system, auth_headers):
    client.post(f'{AEND}/projekte/{system}/aenderungen', headers=auth_headers,
                json={'stand': STAND, 'grund_art': 'daten'})
    h = _h(app, ['aiact_editor'])
    r = client.post(f'{AEND}/projekte/{system}/aenderungen/{STAND}/freigeben', headers=h)
    assert r.status_code == 403, r.get_json()


def test_approver_erreicht_die_freigabe_aber_schreibt_nicht(client, app, system,
                                                            auth_headers):
    """Erwartet wird **nicht** 200: Ohne Einreichung lehnt der Endpunkt mit 409
    ab. Entscheidend ist, dass es kein 403 ist — die Entscheidung gehört zum
    Endpunkt, nicht zur Methoden-Heuristik des Guards (#1754)."""
    client.post(f'{AEND}/projekte/{system}/aenderungen', headers=auth_headers,
                json={'stand': STAND, 'grund_art': 'daten'})
    h = _h(app, ['aiact_approver'])

    frei = client.post(f'{AEND}/projekte/{system}/aenderungen/{STAND}/freigeben',
                       headers=h)
    assert frei.status_code == 409, frei.get_json()

    # Schreiben bleibt verwehrt — sonst wäre die Lockerung ein Loch.
    assert client.post(f'{AEND}/projekte/{system}/aenderungen', headers=h,
                       json={'stand': 'x'}).status_code == 403
    assert client.post(
        f'{AEND}/projekte/{system}/aenderungen/{STAND}/einreichen',
        headers=h).status_code == 403
    assert client.put(
        f'{AEND}/projekte/{system}/aenderungen/{STAND}/wesentliche-aenderung',
        headers=h, json={'wert': 'nein', 'grund': 'Begründung lang genug'}
    ).status_code == 403


def test_vier_augen_ueber_die_api(client, app, system, auth_headers):
    """Derselbe Durchlauf wie in der Datenbankschicht, aber über den Guard —
    nur so ist belegt, dass beide Rollen ihre Schritte wirklich erreichen."""
    dev = _h(app, ['aiact_editor'], ident='u-1756-dev')
    pruefer = _h(app, ['aiact_approver'], ident='u-1756-compliance')

    client.post(f'{AEND}/projekte/{system}/aenderungen', headers=dev,
                json={'stand': STAND, 'grund_art': 'zweck',
                      'beschreibung': 'Neue Zweckbestimmung'})
    r = client.put(f'{AEND}/projekte/{system}/aenderungen/{STAND}/wesentliche-aenderung',
                   headers=dev, json={'wert': 'ja',
                                      'grund': 'Zweckbestimmung geändert, Art. 3 Nr. 23'})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['vorgang']['neubewertung_erforderlich'] is True

    assert client.post(f'{AEND}/projekte/{system}/aenderungen/{STAND}/einreichen',
                       headers=dev).status_code == 200

    # Der Einreicher darf nicht freigeben — auch nicht, wenn man ihm zusätzlich
    # das Freigaberecht gibt. Das ist der Fall, der vor #1743 überall möglich war.
    selbst = _h(app, ['aiact_editor', 'aiact_approver'], ident='u-1756-dev')
    r = client.post(f'{AEND}/projekte/{system}/aenderungen/{STAND}/freigeben',
                    headers=selbst)
    assert r.status_code == 409, r.get_json()
    assert 'Vier-Augen' in r.get_json()['error']

    r = client.post(f'{AEND}/projekte/{system}/aenderungen/{STAND}/freigeben',
                    headers=pruefer)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['status'] == 'freigegeben'

    assert client.post(f'{AEND}/projekte/{system}/aenderungen/{STAND}/umsetzen',
                       headers=dev).status_code == 200


def test_vorab_bewertet_ueber_die_api(client, app, system, auth_headers):
    dev = _h(app, ['aiact_editor'])
    client.post(f'{AEND}/projekte/{system}/aenderungen', headers=dev,
                json={'stand': STAND, 'grund_art': 'nachtraining'})
    ohne = client.put(
        f'{AEND}/projekte/{system}/aenderungen/{STAND}/wesentliche-aenderung',
        headers=dev, json={'wert': 'vorab_bewertet',
                           'grund': 'Vorgesehenes Nachtraining, bereits mitbewertet'})
    assert ohne.status_code == 409, 'Fundstelle fehlt — muss abgelehnt werden'

    mit = client.put(
        f'{AEND}/projekte/{system}/aenderungen/{STAND}/wesentliche-aenderung',
        headers=dev, json={'wert': 'vorab_bewertet',
                           'grund': 'Vorgesehenes Nachtraining, bereits mitbewertet',
                           'vorab_referenz': 'TechDoc 4.3 (Anhang IV Nr. 2 f)'})
    assert mit.status_code == 200, mit.get_json()
    d = mit.get_json()
    assert d['vorgang']['neubewertung_erforderlich'] is False
    assert d['gate']['neubewertung_erforderlich'] is False
    rel = {i['id']: i for i in d['katalog']}
    assert rel['doc_ce_aktuell']['relevant'] is False


def test_katalog_endpunkt_liefert_relevanz(client, auth_headers, system):
    r = client.get(f'{AEND}/projekte/{system}/aenderungen/katalog',
                   headers=auth_headers,
                   query_string={'wesentlich': 'vorab_bewertet',
                                 'grund_art': 'nachtraining'})
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d['kernfrage_id'] == 'wesentliche_aenderung'
    assert 'annex_iv_aktuell' in d['gerechnet']
    rel = {i['id']: i for i in d['katalog']}
    assert rel['doc_ce_aktuell']['relevant'] is False
    # Nicht relevante Punkte bleiben sichtbar: Im Nachweis soll stehen, dass
    # eine Pflicht geprüft und warum sie nicht einschlägig war.
    assert len(d['katalog']) == len(
        client.get(f'{AEND}/projekte/{system}/aenderungen/katalog',
                   headers=auth_headers).get_json()['katalog'])
