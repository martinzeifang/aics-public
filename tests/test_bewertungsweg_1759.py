"""Bewertungsweg gegen die Produktklasse (#1759).

Der schwerwiegendste Fund der CRA-Lückenanalyse: ``save_konformitaet`` prüfte nur,
ob der gewählte Bewertungsweg **einer der vier** aus Anhang VIII ist. Ob er für die
**Produktklasse** zulässig ist, prüfte niemand. Ein als ``critical`` (Anhang IV)
klassifiziertes Produkt ließ sich damit über Modul A selbstdeklarieren, eine
EU-Konformitätserklärung ausstellen und bekam im Release-Check eine grüne Ampel —
das Werkzeug bestätigte einen unzulässigen Weg.

Geprüft wird hier an den Stellen, an denen die Regel falsch liegen kann:

* Die **Ablehnung** beim Speichern, und dass sie sagt, was weiterhilft: welche
  Klasse, welche Wege.
* Die **Umgehung** über ein leeres Feld: Die Oberfläche schickt im Konformitäts-
  Formular keine Produktklasse mit, die Kopie im Record stand deshalb immer auf
  ``default``. Gegen die Kopie allein zu prüfen hieße, die Prüfung mit einem
  weggelassenen Wert aushebeln zu können.
* **Bestandsdaten** werden nicht angefasst — aber das Gate meldet sie, und zwar
  ``rot`` in beiden Phasen. Ein unzulässiger Weg ist keine Lücke in der Akte,
  sondern eine Nicht-Konformität.
* Der **Quellenausfall**: Ein Prüfpunkt, der nicht laufen konnte, erscheint mit
  ``ungeprueft`` und schließt grün aus (#1751). Ein stilles ``except: pass`` wäre
  hier gefährlicher als eine Exception, weil er wie ein gutes Ergebnis aussieht.
* Die **Invariante** zwischen Matrix und ``PRODUKTKLASSEN``: Eine neue Klasse ohne
  Matrix-Zeile würde als ``default`` behandelt — also als die mildeste Annahme.
"""
from __future__ import annotations

import pytest

from cra import db as cdb
from cra import konformitaet_db as kdb
from cra import release_checkliste as rc
from cra import requirements as req
from cra import traceability_db as tdb
from cra.konformitaet_gate import evaluate

FIRMA = 'pytest-firma-1759'
VER = '9.1.0'


def _leeren(db_path, projekt: str) -> None:
    """Projektspuren aus allen beteiligten Tabellen entfernen.

    Unter Postgres leitet ``shared/db.py`` das Schema aus dem **Dateinamen** ab
    (``cra.sqlite`` → Schema ``cra``), nicht aus dem Pfad: Alle CRA-Tests teilen
    sich dieselben Tabellen, und ``tmp_path`` ist kein Teardown (#1706).
    """
    con = cdb._connect(db_path)
    try:
        for tbl in ('cra_konformitaet', 'cra_bewertungen', 'cra_dokumente',
                    'cra_managed_docs', 'cra_vuln', 'cra_sbom'):
            con.try_execute(f'DELETE FROM {tbl} WHERE projekt_name=?', (projekt,))
        con.commit()
    finally:
        con.close()


@pytest.fixture
def umgebung(tmp_path, monkeypatch, request):
    """Eigenes Projekt je Test — sonst hängt das Ergebnis an der Reihenfolge.

    Liefert ``(db_path, projekt_name)``. Die Produktklasse setzt jeder Test
    selbst: Sie ist der Gegenstand der Prüfung.
    """
    db_path = tmp_path / 'cra.sqlite'
    monkeypatch.setattr('cra.konformitaet_gate.CRA_DB', db_path)
    projekt = f'pytest-1759-{request.node.name[:50]}'
    cdb.ensure_db(db_path)
    _leeren(db_path, projekt)
    cdb.delete_projekt(db_path, projekt)
    yield db_path, projekt
    _leeren(db_path, projekt)
    cdb.delete_projekt(db_path, projekt)


def _projekt(db_path, projekt: str, klasse: str) -> None:
    cdb.save_projekt(db_path, name=projekt, unternehmen=FIRMA, produktklasse=klasse)


def _phase1_gruen(db_path, projekt: str) -> None:
    """Produktzustand herstellen, in dem Phase 1 grün ist — die Null-Linie.

    Nur gegen eine grüne Null-Linie lässt sich die Wirkung **eines** Prüfpunktes
    auf die Ampel messen; bei rotem Produktzustand wäre jede Aussage überdeckt.
    """
    from cra.requirements import CRA_ANFORDERUNGEN

    for r in CRA_ANFORDERUNGEN:
        cdb.save_bewertung(db_path, projekt, r['id'], 5, kommentar='Test')
    for b in tdb.ANNEX_VII_BAUSTEINE:
        tdb.create_dokument(db_path, projekt, f"Nachweis {b['key']}",
                            doc_type='resource', annex_baustein=b['key'])


def _setze_weg_direkt(db_path, projekt: str, release: str, weg: str) -> None:
    """Bestandsdatensatz nachbilden: unzulässiger Weg direkt in der DB.

    Bewusst an ``save_konformitaet`` vorbei — genau so liegen die Daten, die vor
    #1759 entstanden sind, und genau die darf die Migration nicht anfassen.
    """
    con = cdb._connect(db_path)
    try:
        con.execute('UPDATE cra_konformitaet SET bewertungsweg=? '
                    'WHERE projekt_name=? AND release_version=?',
                    (weg, projekt, release))
        con.commit()
    finally:
        con.close()


# ── Die Ablehnung beim Speichern ─────────────────────────────────────────────

def test_kritisches_produkt_kann_nicht_selbstdeklariert_werden(umgebung):
    """Der Kern des Issues: Anhang IV + Modul A wird abgelehnt."""
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'critical')
    with pytest.raises(ValueError) as exc:
        kdb.save_konformitaet(db_path, projekt, {'bewertungsweg': 'A'})
    meldung = str(exc.value)
    # Die Meldung muss beides nennen, was weiterhilft: die Klasse, an der es
    # liegt, und die Wege, die offenstehen. „Ungültig" allein lässt den
    # Anwender raten.
    assert req.klasse_label('critical') in meldung, meldung
    for weg in req.zulaessige_wege('critical'):
        assert weg in meldung, meldung
    assert 'Art. 32' in meldung, meldung
    # Und nichts wurde gespeichert.
    assert kdb.get_konformitaet(db_path, projekt, '') is None


def test_important_ii_kann_nicht_selbstdeklariert_werden(umgebung):
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'important_ii')
    with pytest.raises(ValueError):
        kdb.save_konformitaet(db_path, projekt, {'bewertungsweg': 'A'})


def test_zulaessige_kombination_wird_gespeichert(umgebung):
    """Gegenprobe — ohne sie prüft der Test oben nur, dass irgendetwas scheitert."""
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'critical')
    rec = kdb.save_konformitaet(db_path, projekt, {
        'bewertungsweg': 'EUCC', 'eucc_level': 'substanziell',
        'bewertung_abgeschlossen': True})
    assert rec['bewertungsweg'] == 'EUCC'
    assert rec['bewertung_abgeschlossen'] is True
    # Gespeichert wird die geprüfte Klasse, nicht der Spaltenstandard: Sonst
    # stünde im Nachweis eine andere Klasse als in der Prüfung.
    assert rec['produktklasse'] == 'critical'


def test_strengere_wege_bleiben_ueberall_zulaessig(umgebung):
    """Wer freiwillig eine notifizierte Stelle einschaltet, wird nicht abgewiesen.

    Eine Anwendung, die hier abweist, entscheidet über die Arbeitsweise statt
    über die Konformität.
    """
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'default')
    rec = kdb.save_konformitaet(db_path, projekt, {'bewertungsweg': 'H',
                                                   'nb_kennnummer': '0123'})
    assert rec['bewertungsweg'] == 'H'


def test_modul_a_bleibt_fuer_default_und_klasse_i_moeglich(umgebung):
    """Anhang III Klasse I lässt Modul A unter einer Bedingung zu, die diese
    Anwendung nicht entscheiden kann (vollständig angewandte harmonisierte
    Normen, Art. 32 Abs. 2). Sie wird als Hinweis gesagt, nicht als Ablehnung."""
    db_path, projekt = umgebung
    for klasse in ('default', 'important_i'):
        _projekt(db_path, projekt, klasse)
        rec = kdb.save_konformitaet(db_path, projekt, {'bewertungsweg': 'A'})
        assert rec['bewertungsweg'] == 'A'
    assert req.weg_bedingung('important_i', 'A'), 'Bedingung fehlt'
    assert not req.weg_bedingung('default', 'A')


def test_weggelassene_klasse_hebt_die_pruefung_nicht_auf(umgebung):
    """Die Umgehung: Die Oberfläche schickt im Konformitäts-Formular **keine**
    Produktklasse mit, die Kopie im Record stand deshalb immer auf ``default``.
    Geprüft wird gegen die strengste aus Eingabe und Projekt."""
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'critical')
    with pytest.raises(ValueError):
        # genau der Aufruf, den das Panel macht
        kdb.save_konformitaet(db_path, projekt, {'bewertungsweg': 'A',
                                                 'produktklasse': 'default'})
    assert kdb.effektive_produktklasse(db_path, projekt, {}) == 'critical'


# ── Punkt 4: Abschluss ohne notifizierte Stelle ──────────────────────────────

@pytest.mark.parametrize('weg', ['B+C', 'H'])
def test_abschluss_ohne_notifizierte_stelle_nicht_setzbar(umgebung, weg):
    """Bei B+C/H/EUCC ist eine dritte Stelle beteiligt. „Abgeschlossen" ohne jede
    Angabe zu ihr trägt anschließend Freigabe, DoC und CE-Kennzeichnung — die
    NB-Pflicht griff bisher erst im DoC-Formular, eine Station zu spät."""
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'important_ii')
    with pytest.raises(ValueError) as exc:
        kdb.save_konformitaet(db_path, projekt, {'bewertungsweg': weg,
                                                 'bewertung_abgeschlossen': True})
    assert 'notifizierte' in str(exc.value).lower()
    # Ohne Abschluss-Haken bleibt derselbe Datensatz speicherbar: Der Weg darf
    # gewählt werden, bevor die Stelle beauftragt ist.
    rec = kdb.save_konformitaet(db_path, projekt, {'bewertungsweg': weg})
    assert rec['bewertung_abgeschlossen'] is False
    # Und mit Kennnummer geht es.
    rec = kdb.save_konformitaet(db_path, projekt, {
        'bewertungsweg': weg, 'nb_kennnummer': '0123',
        'bewertung_abgeschlossen': True})
    assert rec['bewertung_abgeschlossen'] is True


def test_eucc_braucht_das_vertrauensniveau(umgebung):
    """Beim EUCC-Weg ist die Aussage nicht die Kennnummer, sondern das
    Vertrauensniveau (mindestens „substanziell", Art. 32 Abs. 4)."""
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'critical')
    with pytest.raises(ValueError) as exc:
        kdb.save_konformitaet(db_path, projekt, {'bewertungsweg': 'EUCC',
                                                 'bewertung_abgeschlossen': True})
    assert 'substanziell' in str(exc.value)
    rec = kdb.save_konformitaet(db_path, projekt, {
        'bewertungsweg': 'EUCC', 'eucc_level': 'hoch',
        'bewertung_abgeschlossen': True})
    assert rec['bewertung_abgeschlossen'] is True


def test_vorgang_ohne_angegebenen_weg_bekommt_einen_zulaessigen(umgebung):
    """``POST /releases/<version>`` legt den Vorgang **ohne** Weg an.

    Der frühere Festwert ``A`` war die Lücke an einer zweiten Stelle: Bei einem
    Anhang-IV-Produkt stand danach Modul A im Datensatz — und mit der neuen
    Prüfung ließe sich kein Release mehr anlegen. Ohne Angabe gilt der bisherige
    Weg, sonst der erste zulässige der Klasse.
    """
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'critical')
    rec = kdb.save_konformitaet(db_path, projekt, {'release_version': VER})
    assert rec['bewertungsweg'] in req.zulaessige_wege('critical')
    assert rec['bewertungsweg'] == 'EUCC'
    # Ein gewählter Weg wird durch eine Angabe-lose Speicherung nicht ersetzt.
    kdb.save_konformitaet(db_path, projekt, {'release_version': VER,
                                             'bewertungsweg': 'H',
                                             'nb_kennnummer': '0123'})
    rec = kdb.save_konformitaet(db_path, projekt, {'release_version': VER,
                                                   'notizen': 'Zwischenstand'})
    assert rec['bewertungsweg'] == 'H'
    # Und bei nicht gelisteten Produkten bleibt es Modul A wie bisher.
    _projekt(db_path, projekt, 'default')
    assert kdb.save_konformitaet(db_path, projekt, {})['bewertungsweg'] == 'A'


def test_unbekannter_weg_bleibt_abgelehnt(umgebung):
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'default')
    with pytest.raises(ValueError, match='Ungültiger Bewertungsweg'):
        kdb.save_konformitaet(db_path, projekt, {'bewertungsweg': 'Modul Z'})


def test_modul_a_braucht_keine_stelle(umgebung):
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'default')
    rec = kdb.save_konformitaet(db_path, projekt, {'bewertungsweg': 'A',
                                                   'bewertung_abgeschlossen': True})
    assert rec['bewertung_abgeschlossen'] is True


# ── Bestandsdaten: das Gate meldet sie ───────────────────────────────────────

def test_bestandsdaten_mit_unzulaessigem_weg_sind_rot_in_beiden_phasen(umgebung):
    """Der zweite Teil des Fixes: Alt-Datensätze werden nicht verändert — aber
    sie dürfen nicht grün sein.

    Gemessen gegen eine grüne Null-Linie, damit die Aussage dem **einen** neuen
    Prüfpunkt gehört und nicht dem rohen Zustand eines frischen Projekts.
    """
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'critical')
    _phase1_gruen(db_path, projekt)
    for release in ('', VER):
        kdb.save_konformitaet(db_path, projekt, {
            'release_version': release, 'bewertungsweg': 'EUCC',
            'eucc_level': 'substanziell', 'bewertung_abgeschlossen': True})
        kdb.issue_doc(db_path, projekt, {'produkt_name': 'X'}, release)

    assert evaluate(projekt)['ampel'] == 'gruen', 'Null-Linie Phase 1 nicht grün'
    phase2_vorher = evaluate(projekt, version=VER)['ampel']
    assert phase2_vorher != 'rot', 'Null-Linie Phase 2 schon rot'

    # Bestandsdaten: Modul A bei einem Anhang-IV-Produkt.
    _setze_weg_direkt(db_path, projekt, '', 'A')
    _setze_weg_direkt(db_path, projekt, VER, 'A')

    p1 = evaluate(projekt)
    punkte1 = [p for p in p1['produkt_punkte'] if p['typ'] == 'bewertungsweg']
    assert len(punkte1) == 1, p1['produkt_punkte']
    assert p1['ampel'] == 'rot', p1['offene_punkte']
    assert p1['bewertungsweg_unzulaessig'] is True
    assert req.klasse_label('critical') in punkte1[0]['titel']
    assert punkte1[0]['link'] == 'konformitaet'
    assert punkte1[0]['ref'], 'Punkt ohne Rechtsstelle ist im Nachweis wertlos'
    # Phase-1-Punkte tragen die Phase-2-Felder nicht (Panel-Vertrag, #1745).
    assert set(punkte1[0]) <= {'typ', 'titel', 'hinweis', 'link', 'ref', 'ungeprueft'}

    p2 = evaluate(projekt, version=VER)
    # Erst der gerechnete Befund, dann der Punkt: Schlägt es fehl, sagt die
    # Meldung, ob der Weg falsch gelesen oder der Punkt nicht gebaut wurde.
    assert p2['release_befunde']['bewertungsweg'] == {
        'klasse': 'critical', 'weg': 'A', 'zulaessig': False}
    punkte2 = [p for p in p2['release_punkte'] if p['typ'] == 'bewertungsweg']
    assert len(punkte2) == 1, p2['release_punkte']
    assert punkte2[0]['ampel_wirkung'] == 'rot', punkte2[0]
    assert p2['ampel'] == 'rot'
    assert p2['bewertungsweg_unzulaessig'] is True
    assert p2['release_befunde']['bewertungsweg']['klasse'] == 'critical'


def test_zulaessiger_weg_ist_in_beiden_phasen_kein_punkt(umgebung):
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'critical')
    kdb.save_konformitaet(db_path, projekt, {
        'bewertungsweg': 'EUCC', 'eucc_level': 'substanziell'})
    kdb.save_konformitaet(db_path, projekt, {
        'release_version': VER, 'bewertungsweg': 'EUCC', 'eucc_level': 'substanziell'})
    p1 = evaluate(projekt)
    p2 = evaluate(projekt, version=VER)
    assert not [p for p in p1['produkt_punkte'] if p['typ'] == 'bewertungsweg']
    assert not [p for p in p2['release_punkte'] if p['typ'] == 'bewertungsweg']
    assert p1['bewertungsweg_unzulaessig'] is False
    assert p2['bewertungsweg_unzulaessig'] is False


def test_ohne_gewaehlten_weg_entsteht_kein_befund(umgebung):
    """Kein gewählter Weg ist kein unzulässiger: Dass die Erklärung fehlt, meldet
    der DoC-Prüfpunkt. Ohne Wahl gibt es hier nichts zu beurteilen — sonst
    bekäme jedes frische Projekt eine Nicht-Konformität gemeldet."""
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'critical')
    p1 = evaluate(projekt)
    assert not [p for p in p1['produkt_punkte'] if p['typ'] == 'bewertungsweg']
    assert p1['bewertungsweg_unzulaessig'] is None
    assert [p for p in p1['produkt_punkte'] if p['typ'] == 'doc']


def test_release_ohne_eigenen_vorgang_faellt_auf_die_produktsicht_zurueck(umgebung):
    """Hat ein Release keinen eigenen Konformitäts-Record, gilt der Weg des
    Produkts. Ein ``None`` wäre hier „nicht geprüft", obwohl geprüft wurde."""
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'critical')
    kdb.save_konformitaet(db_path, projekt, {'bewertungsweg': 'EUCC',
                                             'eucc_level': 'substanziell'})
    _setze_weg_direkt(db_path, projekt, '', 'A')
    g = evaluate(projekt, version=VER)
    assert g['bewertungsweg_unzulaessig'] is True
    assert g['ampel'] == 'rot'


# ── Quellenausfall: ungeprüft ist nicht erfüllt (#1751) ──────────────────────

def test_quellenausfall_ist_ungeprueft_und_nie_gruen(umgebung, monkeypatch):
    """Ein stilles ``except: pass`` wäre hier gefährlicher als eine Exception:
    Die Ampel würde grün, und der Anwender hielte für geprüft, was niemand
    geprüft hat."""
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'critical')
    _phase1_gruen(db_path, projekt)
    kdb.save_konformitaet(db_path, projekt, {
        'bewertungsweg': 'EUCC', 'eucc_level': 'substanziell',
        'bewertung_abgeschlossen': True})
    kdb.issue_doc(db_path, projekt, {'produkt_name': 'X'}, '')
    assert evaluate(projekt)['ampel'] == 'gruen', 'Null-Linie nicht grün'

    def _kaputt(*_a, **_k):
        raise RuntimeError('DB weg')

    monkeypatch.setattr('cra.konformitaet_db.get_konformitaet', _kaputt)

    p1 = evaluate(projekt)
    punkte = [p for p in p1['produkt_punkte'] if p['typ'] == 'bewertungsweg']
    assert len(punkte) == 1 and punkte[0]['ungeprueft'] is True, p1['produkt_punkte']
    assert 'RuntimeError' in punkte[0]['hinweis']
    assert p1['ampel'] != 'gruen'
    assert p1['bewertungsweg_unzulaessig'] is None

    p2 = evaluate(projekt, version=VER)
    punkte = [p for p in p2['release_punkte'] if p['typ'] == 'bewertungsweg']
    assert punkte and all(p['ungeprueft'] for p in punkte), p2['release_punkte']
    assert p2['ampel'] != 'gruen'
    assert p2['bewertungsweg_unzulaessig'] is None


def test_speichern_bleibt_moeglich_wenn_das_projekt_unlesbar_ist(umgebung, monkeypatch):
    """Best effort bei der Klassen-Auflösung: Ein unlesbares Projekt darf das
    Speichern nicht verhindern — geprüft wird dann gegen die mitgeschickte
    Klasse. Das ist bewusst die mildere Seite; das Gate meldet den Record
    anschließend trotzdem, weil es die Klasse selbst auflöst."""
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'critical')

    def _kaputt(*_a, **_k):
        raise RuntimeError('DB weg')

    monkeypatch.setattr('cra.db.load_projekt', _kaputt)
    assert kdb.produktklasse_projekt(db_path, projekt) == ''
    rec = kdb.save_konformitaet(db_path, projekt, {'bewertungsweg': 'A'})
    assert rec['bewertungsweg'] == 'A'
    # Mitgeschickte Klasse wird auch ohne Projekt geprüft.
    with pytest.raises(ValueError):
        kdb.save_konformitaet(db_path, projekt, {'bewertungsweg': 'A',
                                                 'produktklasse': 'critical'})


# ── Invarianten: eine Quelle, kein Nebenher ──────────────────────────────────

def test_matrix_und_produktklassen_haengen_zusammen():
    """Jede Klasse hat einen Eintrag, kein Eintrag ohne Klasse.

    Eine neue Produktklasse ohne Matrix-Zeile würde als ``default`` behandelt —
    also als die mildeste Annahme, und das ist genau der Fehler, den #1759
    schließt.
    """
    assert set(req.KLASSEN_BEWERTUNGSWEGE) == set(req.PRODUKTKLASSEN)
    assert set(req.KLASSEN_STRENGE) == set(req.PRODUKTKLASSEN)
    for klasse, regel in req.KLASSEN_BEWERTUNGSWEGE.items():
        assert regel['wege'], klasse
        assert set(regel['wege']) <= set(req.BEWERTUNGSWEGE), klasse
        assert set(regel['bedingt']) <= set(regel['wege']), klasse
        assert regel['referenz'].strip() and regel['begruendung'].strip(), klasse
        assert '2024/2847' in regel['referenz'], klasse


def test_wege_haben_genau_eine_quelle():
    """``konformitaet_db.WEGE`` und die Nachweis-Checkliste lesen die Matrix —
    eine eigene Liste daneben wäre die zweite Wahrheit (#1731/#1735)."""
    assert kdb.WEGE == tuple(req.BEWERTUNGSWEGE)
    assert set(kdb.CHECKLISTE) == set(req.BEWERTUNGSWEGE)


def test_selbstbewertung_ist_genau_dort_ausgeschlossen_wo_eine_stelle_pflicht_ist():
    """Die eine Regel, auf die es ankommt — und die Klassenliste der KI-Prompts
    liest sie (``ai_wizards._NB_PFLICHT_KLASSEN``), statt sie zu wiederholen."""
    from cra.ai_wizards import _NB_PFLICHT_KLASSEN

    assert 'A' not in req.zulaessige_wege('important_ii')
    assert 'A' not in req.zulaessige_wege('critical')
    assert 'A' in req.zulaessige_wege('default')
    assert _NB_PFLICHT_KLASSEN == {'important_i', 'important_ii', 'critical'}
    assert not req.weg_braucht_notifizierte_stelle('A')
    assert all(req.weg_braucht_notifizierte_stelle(w) for w in ('B+C', 'H', 'EUCC'))


def test_strengste_klasse_waehlt_die_strengere():
    assert req.strengste_klasse('default', 'critical') == 'critical'
    assert req.strengste_klasse('', None) == 'default'
    assert req.strengste_klasse('important_i', 'important_ii') == 'important_ii'
    # Unbekanntes zählt nicht mit — es darf die bekannte Klasse nicht verdrängen.
    assert req.strengste_klasse('quatsch', 'important_ii') == 'important_ii'


def test_release_katalog_kennt_den_neuen_punkt(umgebung):
    """Der gerechnete Punkt steht im Katalog (#1744) und seine ``quelle`` findet
    im Gate einen Wert. Läuft der Name auseinander, zeigt der Nachweis eine
    leere Zelle statt eines Befundes — und niemand merkt es."""
    db_path, projekt = umgebung
    _projekt(db_path, projekt, 'default')
    item = rc.item('bewertungsweg_zulaessig')
    assert item is not None and item.art == 'gerechnet'
    assert item.quelle == 'bewertungsweg_unzulaessig'
    assert item.rechtsbezug.strip() and item.link == 'konformitaet'
    # Gerechnete Punkte sind nicht von Hand setzbar — sonst ließe sich der
    # Nachweis mit einem Klick erzeugen, statt ihn zu erbringen.
    assert item.id in rc.gerechnete_ids()
    assert item.quelle in evaluate(projekt, version=VER)
