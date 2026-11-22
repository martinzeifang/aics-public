"""Wesentliche Änderung erzwingt die Neubewertung (#1755).

Aus der Rückfrage des Anwenders: „Bei wesentlichen Änderungen muss ich für die
neuen Teile vermutlich eine Risikobewertung machen — wenn ja, sollten wir das
hart verknüpfen."

Das ist richtig, und der eigene Anforderungskatalog sagt es bei ``ART13-01``
(Art. 13 Abs. 1) selbst: „Regelmäßige Aktualisierung bei wesentlichen
Produktänderungen." Erzwungen wurde davon nichts — man konnte „wesentliche
Änderung: ja" eintragen, einreichen und freigeben, ohne die verknüpfte
Risikobewertung je anzufassen.

Der Unterschied zu allen anderen Release-Punkten: Diese vier wirken **rot**.
Eine wesentliche Änderung ohne wiederholte Konformitätsbewertung ist eine
Nicht-Konformität, keine Lücke in der Akte.
"""
from __future__ import annotations

import pytest

from cra import db as cdb
from cra import konformitaet_db as kdb
from cra.konformitaet_gate import evaluate

PROJ = 'pytest-neubewertung-1755'
FIRMA = 'pytest-firma-1755'
VER = '5.0.0'


@pytest.fixture
def projekt(tmp_path, monkeypatch, request):
    """Eigenes Projekt je Test.

    ``shared/db.py`` leitet das Postgres-Schema aus dem **Dateinamen** ab
    (``cra.sqlite`` → Schema ``cra``), nicht aus dem Pfad. Alle Tests dieser
    Datei — und alle anderen CRA-Tests — teilen sich damit dasselbe Schema;
    ein fester Projektname lässt sie einander beeinflussen, und das Ergebnis
    hängt an der Reihenfolge. Der Testname im Projektnamen schließt das aus.
    """
    global PROJ
    PROJ = f'pytest-1755-{request.node.name[:40]}'
    monkeypatch.setattr('cra.konformitaet_gate.CRA_DB', cdb_pfad := tmp_path / 'cra.sqlite')
    cdb.delete_projekt(cdb_pfad, PROJ)
    cdb.save_projekt(cdb_pfad, name=PROJ, unternehmen=FIRMA)
    kdb.save_konformitaet(cdb_pfad, PROJ, {'release_version': VER, 'bewertungsweg': 'A',
                                           'bewertung_abgeschlossen': True})
    yield cdb_pfad
    cdb.delete_projekt(cdb_pfad, PROJ)


def test_ohne_wesentliche_aenderung_keine_neubewertung(projekt):
    g = evaluate(PROJ, version=VER)
    assert [p for p in g['release_punkte'] if p['typ'] == 'neubewertung'] == []
    assert g['release_befunde'].get('wesentliche_aenderung') is None


def test_ja_macht_das_release_rot(projekt):
    """Der Kern: Vier offene Neubewertungs-Punkte, und die Ampel steht auf rot."""
    kdb.set_wesentliche_aenderung(projekt, PROJ, VER, wert='ja',
                                  grund='Neues Authentifizierungsverfahren eingeführt')
    g = evaluate(PROJ, version=VER)
    punkte = [p for p in g['release_punkte'] if p['typ'] == 'neubewertung']
    assert punkte, 'keine Neubewertungs-Punkte trotz wesentlicher Änderung'
    assert all(p['ampel_wirkung'] == 'rot' for p in punkte), punkte
    assert g['ampel'] == 'rot'
    # Jeder Punkt nennt seine Rechtsstelle — sonst ist er im Nachweis wertlos.
    assert all(p.get('ref') for p in punkte), punkte


def test_erledigte_punkte_verschwinden(projekt):
    kdb.set_wesentliche_aenderung(projekt, PROJ, VER, wert='ja',
                                  grund='Neues Authentifizierungsverfahren eingeführt')
    for item in ('neubewertung_risikobewertung', 'neubewertung_konformitaetsbewertung',
                 'neubewertung_technische_doku', 'neubewertung_doc'):
        kdb.set_release_checkliste(projekt, PROJ, VER, item, status='erledigt',
                                   begruendung='Für die Änderung durchgeführt und dokumentiert',
                                   von='dev@example.com')
    g = evaluate(PROJ, version=VER)
    # Was bleibt, ist der Hinweis auf die fehlende Verknüpfung — und der wirkt
    # jetzt `bedingt` statt `rot`: Die Aussage steht, nur zeigt der Nachweis auf
    # kein Projekt. Wer seine Risikoabschätzung außerhalb der Suite führt, wird
    # sonst nie grün, und das Werkzeug hätte über die Arbeitsweise entschieden
    # statt über die Konformität.
    offen = [p for p in g['release_punkte'] if p['typ'] == 'neubewertung']
    assert [p['titel'] for p in offen] == ['Keine Risikobewertung verknüpft'], offen
    assert offen[0]['ampel_wirkung'] == 'bedingt'
    # Bewusst NICHT die Gesamtampel prüfen: Das Testprojekt hat keine bewerteten
    # Anforderungen, Phase 1 ist also ohnehin rot. Geprüft wird, dass die
    # **Neubewertung** das Release nicht mehr rot macht — die Phasen sind seit
    # #1745 getrennt, und eine Zusicherung, die beide vermischt, prüft nichts.
    assert not any(p['ampel_wirkung'] == 'rot' for p in offen)


def test_ohne_verknuepfte_risikobewertung_fehlt_die_grundlage(projekt):
    """Art. 13 verweist auf die Risikoabschätzung. Ohne verknüpftes Projekt
    gibt es nichts, worauf sich die Neubewertung stützen könnte."""
    kdb.set_wesentliche_aenderung(projekt, PROJ, VER, wert='ja',
                                  grund='Neues Authentifizierungsverfahren eingeführt')
    g = evaluate(PROJ, version=VER)
    titel = [p['titel'] for p in g['release_punkte']]
    assert any('Keine Risikobewertung verknüpft' in t for t in titel), titel
    assert g['release_befunde'].get('rb_neue_risiken') is None


def test_verknuepfte_risikobewertung_wird_gezaehlt(projekt, monkeypatch):
    """Der gerechnete Hinweis ersetzt die Aussage des Menschen nicht — er macht
    den Unterschied sichtbar zwischen „geprüft und nichts gefunden" und
    „niemand hat nachgesehen"."""
    cdb.save_projekt(projekt, name=PROJ, unternehmen=FIRMA,
                     meta={'linked_risk_projekt': 'RB-Test'})
    kdb.set_wesentliche_aenderung(projekt, PROJ, VER, wert='ja',
                                  grund='Neues Authentifizierungsverfahren eingeführt')
    monkeypatch.setattr('risikobewertung.db.load_risiken',
                        lambda db, name: [{'updated_at': '2099-01-01', 'name': 'R-99'},
                                          {'updated_at': '2000-01-01', 'name': 'R-01'}])
    g = evaluate(PROJ, version=VER)
    assert g['release_befunde']['rb_neue_risiken'] == 1
    assert g['release_befunde']['rb_projekt'] == 'RB-Test'
    assert not any('Keine Risikobewertung verknüpft' in p['titel']
                   for p in g['release_punkte'])


def test_unlesbare_risikobewertung_wird_nicht_verschwiegen(projekt, monkeypatch):
    """„Ungeprüft ist nicht erfüllt" gilt auch hier (#1751)."""
    cdb.save_projekt(projekt, name=PROJ, unternehmen=FIRMA,
                     meta={'linked_risk_projekt': 'RB-Test'})
    kdb.set_wesentliche_aenderung(projekt, PROJ, VER, wert='ja',
                                  grund='Neues Authentifizierungsverfahren eingeführt')

    def _kaputt(*a, **k):
        raise RuntimeError('RB nicht lesbar')

    monkeypatch.setattr('risikobewertung.db.load_risiken', _kaputt)
    g = evaluate(PROJ, version=VER)
    assert any(p.get('ungeprueft') for p in g['release_punkte'])
    assert g['release_befunde']['rb_neue_risiken'] is None
    assert g['ampel'] != 'gruen'
