"""Release-Checkliste in drei Arten (#1744).

Der Anwender hat die Anforderung in einem Satz formuliert: „Vieles ist jedes Mal
gleich, anderes muss ich prüfen." Daraus folgen die drei Arten von Prüfpunkten —
und zwei Regeln, die über den Wert des ganzen Nachweises entscheiden:

* Ein ``gerechnet``-Punkt darf nicht von Hand gesetzt werden. Wäre er es, ließe
  sich der Nachweis mit einem Klick erzeugen, statt ihn zu erbringen.
* Ein ``entscheidung``-Punkt braucht eine Begründung. „Erledigt" ohne Begründung
  ist kein Nachweis, sondern ein Haken.
"""
from __future__ import annotations

import pytest

PROJ = 'pytest-checkliste-1744'
VER = '2.1.0'


# ── Katalog ─────────────────────────────────────────────────────────────────
def test_jeder_punkt_hat_rechtsbezug_und_art():
    """Ein Prüfpunkt ohne Rechtsstelle ist im Nachweis nicht verwertbar — der
    Prüfer fragt als erstes, woraus die Pflicht folgt."""
    from cra import release_checkliste as rc

    assert rc.KATALOG, 'leerer Katalog'
    ohne_recht = [i.id for i in rc.KATALOG if not i.rechtsbezug.strip()]
    assert not ohne_recht, f'ohne Rechtsbezug: {ohne_recht}'
    arten = {i.art for i in rc.KATALOG}
    # `neubewertung` kam mit #1755 dazu: die vier Punkte, die eine wesentliche
    # Änderung (Art. 3 Nr. 30) auslöst. Sie sind eine eigene Art, weil sie nur
    # dann gelten und — anders als alle übrigen — das Release **rot** machen.
    assert arten == {'gerechnet', 'entscheidung', 'gleichbleibend',
                     'neubewertung'}, arten


def test_ids_sind_eindeutig():
    """Die ID ist der Persistenz-Schlüssel des Ist-Stands; eine doppelte würde
    einen fremden Stand überschreiben."""
    from cra import release_checkliste as rc

    ids = [i.id for i in rc.KATALOG]
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]


def test_wesentliche_aenderung_ist_eine_entscheidung():
    """Art. 3 Nr. 30 lässt sich nicht rechnen: Ob eine Änderung wesentlich ist,
    hängt davon ab, ob sich Funktion oder Sicherheitseigenschaften ändern."""
    from cra import release_checkliste as rc

    item = rc.item('wesentliche_aenderung')
    assert item is not None and item.art == 'entscheidung'
    assert 'Art. 3' in item.rechtsbezug
    assert item.id in rc.BEGRUENDUNG_PFLICHT


def test_gerechnete_punkte_zeigen_auf_eine_quelle():
    """``quelle`` nennt den Schlüssel, unter dem das Gate (#1745) das Ergebnis
    liefert. Ohne ihn wüsste der Bericht nicht, woher die Zeile stammt."""
    from cra import release_checkliste as rc

    ohne = [i.id for i in rc.KATALOG if i.art == 'gerechnet' and not i.quelle]
    assert not ohne, f'gerechnete Punkte ohne Quelle: {ohne}'


def test_begruendungspflicht_deckt_genau_die_entscheidungen():
    from cra import release_checkliste as rc

    # #1755: Auch die Neubewertungs-Punkte brauchen eine Begründung. „Erledigt"
    # ohne Aussage wäre gerade dort wertlos, wo die Konformitätsbewertung
    # wiederholt werden muss.
    assert rc.BEGRUENDUNG_PFLICHT == frozenset(
        i.id for i in rc.KATALOG if i.art in ('entscheidung', 'neubewertung'))


def test_leerer_stand_hat_nichts_vorbelegt():
    """Ein vorbelegtes „erledigt" wäre eine Aussage, die niemand getroffen hat."""
    from cra import release_checkliste as rc

    stand = rc.leerer_stand()
    assert set(stand) == {i.id for i in rc.KATALOG}
    assert all(e['status'] == 'offen' for e in stand.values())


def test_katalog_ist_json_faehig():
    import json

    from cra import release_checkliste as rc

    json.dumps(rc.katalog())     # wirft, wenn ein Feld nicht serialisierbar ist


# ── Ist-Stand ───────────────────────────────────────────────────────────────
@pytest.fixture
def vorgang(tmp_path):
    from cra import konformitaet_db as kdb

    db = tmp_path / 'cra.sqlite'
    kdb.save_konformitaet(db, PROJ, {'release_version': VER, 'bewertungsweg': 'A',
                                     'bewertung_abgeschlossen': True})
    return db


def test_gerechneter_punkt_ist_nicht_setzbar(vorgang):
    """Die wichtigste Regel: Was die Anwendung rechnet, darf niemand abhaken."""
    from cra import konformitaet_db as kdb

    with pytest.raises(ValueError, match='gerechnet'):
        kdb.set_release_checkliste(vorgang, PROJ, VER, 'advisory_zu_behobenen',
                                   status='erledigt', begruendung='passt',
                                   von='dev@example.com')


def test_entscheidung_braucht_begruendung(vorgang):
    from cra import konformitaet_db as kdb

    with pytest.raises(ValueError, match='Begründung'):
        kdb.set_release_checkliste(vorgang, PROJ, VER, 'release_notes_veroeffentlicht',
                                   status='erledigt', begruendung='ok',
                                   von='dev@example.com')

    rec = kdb.set_release_checkliste(
        vorgang, PROJ, VER, 'release_notes_veroeffentlicht', status='erledigt',
        begruendung='Release Notes unter /security/advisories veröffentlicht',
        von='dev@example.com')
    eintrag = rec['release_checkliste']['release_notes_veroeffentlicht']
    assert eintrag['status'] == 'erledigt'
    assert eintrag['von'] == 'dev@example.com' and eintrag['am']


def test_nicht_anwendbar_braucht_auch_eine_begruendung(vorgang):
    """„Gilt hier nicht" ist eine Aussage über das Produkt, keine Formalie.

    Geprüft wird das an ``advisory_veroeffentlicht``. Vorher stand hier
    ``fremdkomponenten_bewertet``; der Punkt ist seit #1761 ``gerechnet`` und
    damit gar nicht mehr setzbar — eine eigene Regel, geprüft in
    ``test_sbom_komponenten_1761.py``.
    """
    from cra import konformitaet_db as kdb

    with pytest.raises(ValueError, match='Begründung'):
        kdb.set_release_checkliste(vorgang, PROJ, VER, 'advisory_veroeffentlicht',
                                   status='nicht_anwendbar', begruendung='',
                                   von='dev@example.com')


def test_gleichbleibender_punkt_braucht_keine_begruendung(vorgang):
    """Support-Zeitraum und PSIRT-Kontakt werden bestätigt, nicht erklärt —
    sonst tippt jemand jedes Release dieselbe Begründung."""
    from cra import konformitaet_db as kdb

    rec = kdb.set_release_checkliste(vorgang, PROJ, VER, 'support_zeitraum',
                                     status='erledigt', begruendung='',
                                     von='dev@example.com')
    assert rec['release_checkliste']['support_zeitraum']['status'] == 'erledigt'


def test_unbekannter_punkt_wird_abgewiesen(vorgang):
    from cra import konformitaet_db as kdb

    with pytest.raises(ValueError, match='Unbekannter'):
        kdb.set_release_checkliste(vorgang, PROJ, VER, 'gibt_es_nicht',
                                   status='erledigt', begruendung='x' * 20,
                                   von='dev@example.com')


def test_nach_einreichung_gesperrt(vorgang):
    from cra import konformitaet_db as kdb

    kdb.einreichen(vorgang, PROJ, VER, von='dev@example.com')
    with pytest.raises(ValueError, match='gesperrt'):
        kdb.set_release_checkliste(vorgang, PROJ, VER, 'support_zeitraum',
                                   status='erledigt', begruendung='',
                                   von='dev@example.com')


def test_wesentliche_aenderung_auch_nein_braucht_grund(vorgang):
    """Gerade „das war keine wesentliche Änderung" ist die Aussage, die später
    hinterfragt wird."""
    from cra import konformitaet_db as kdb

    with pytest.raises(ValueError, match='Begründung'):
        kdb.set_wesentliche_aenderung(vorgang, PROJ, VER, wert='nein', grund='nein')
    with pytest.raises(ValueError, match="'ja' oder 'nein'"):
        kdb.set_wesentliche_aenderung(vorgang, PROJ, VER, wert='vielleicht',
                                      grund='x' * 20)

    rec = kdb.set_wesentliche_aenderung(
        vorgang, PROJ, VER, wert='nein',
        grund='Nur Fehlerbehebung, keine Änderung der Sicherheitsfunktionen')
    assert rec['wesentliche_aenderung'] == 'nein'
    assert 'Fehlerbehebung' in rec['wesentliche_aenderung_grund']


def test_einreichen_friert_den_rechenstand_ein(vorgang):
    """Ohne Einfrieren prüft Compliance gegen eine Datenlage, die sich bis zur
    Freigabe verschoben haben kann — und der Nachweis sagt später nicht, auf
    welcher Grundlage freigegeben wurde."""
    from cra import konformitaet_db as kdb

    rec = kdb.einreichen(vorgang, PROJ, VER, von='dev@example.com',
                         gate={'ampel': 'bedingt', 'offen': 1})
    assert rec['gate'] == {'ampel': 'bedingt', 'offen': 1}
    # Der eingefrorene Stand bleibt nach der Freigabe erhalten.
    rec = kdb.freigeben(vorgang, PROJ, VER, von='compliance@example.com')
    assert rec['gate']['ampel'] == 'bedingt'


# ── Neubewertung bei wesentlicher Änderung (#1755) ──────────────────────────
def test_ja_friert_den_stand_ein_und_oeffnet_die_neubewertung(vorgang):
    """Die Kernfrage löst aus, statt nur dokumentiert zu werden.

    `release_db.substantial_modification` existiert seit #1609 und wurde von
    niemandem aufgerufen: Die Frage wurde beantwortet und abgelegt, und damit
    blieb folgenlos, was die Konformitätsbewertung erneut auslöst.
    """
    from cra import konformitaet_db as kdb
    from cra import release_db as rdb

    kdb.set_wesentliche_aenderung(
        vorgang, PROJ, VER, wert='ja',
        grund='Neues Authentifizierungsverfahren, Sicherheitseigenschaften geändert')

    snaps = rdb.list_snapshots(vorgang, PROJ)
    assert snaps, 'der bisherige Stand wurde nicht eingefroren'
    rel = rdb.get_release(vorgang, PROJ)
    assert rel['aktuelle_version'] == VER
    assert set(rel['reassess']) == set(rdb.REASSESS_ITEMS)


def test_nein_friert_nichts_ein(vorgang):
    """Ohne wesentliche Änderung gibt es nichts nachzubewerten — und keinen
    Grund, die Historie mit Snapshots zu füllen."""
    from cra import konformitaet_db as kdb
    from cra import release_db as rdb

    kdb.set_wesentliche_aenderung(vorgang, PROJ, VER, wert='nein',
                                  grund='Nur Fehlerbehebungen ohne Sicherheitsbezug')
    assert rdb.list_snapshots(vorgang, PROJ) == []


def test_neubewertungs_punkte_brauchen_eine_begruendung(vorgang):
    from cra import konformitaet_db as kdb

    with pytest.raises(ValueError, match='Begründung'):
        kdb.set_release_checkliste(vorgang, PROJ, VER, 'neubewertung_risikobewertung',
                                   status='erledigt', begruendung='ok', von='dev@example.com')

    rec = kdb.set_release_checkliste(
        vorgang, PROJ, VER, 'neubewertung_risikobewertung', status='erledigt',
        begruendung='Risiken R-12 bis R-15 für das neue Verfahren ergänzt und bewertet',
        von='dev@example.com')
    assert rec['release_checkliste']['neubewertung_risikobewertung']['status'] == 'erledigt'
