"""Phase 1: CRA-Ready als ausdrückliche Feststellung (#1746).

Vor 8.0.0 war Phase 1 nur ein Rechenergebnis: Das Gate sagt grün, und damit galt
ein Produkt als marktfähig. Für einen Nachweis fehlt die Aussage eines Menschen —
wer hat wann auf welcher Datenlage erklärt, dass dieses Produkt CRA-ready ist?
Ohne sie beginnt das Tagesgeschäft auf einer Annahme.

Die zweite Entscheidung, die hier festgehalten wird: Kippt die Ampel später, wird
die Feststellung **nicht** gelöscht, sondern als überholt angezeigt. Ein
Rechenlauf darf eine menschliche Aussage nicht entfernen — unwidersprochen
stehenbleiben darf sie aber auch nicht.
"""
from __future__ import annotations

import pytest

PROJ = 'pytest-craready-1746'
GRUEN = {'ampel': 'gruen', 'offene_punkte': []}
ROT = {'ampel': 'rot', 'offene_punkte': [{'titel': 'DoC fehlt'},
                                         {'titel': 'Anhang VII unvollständig'}]}


def test_feststellung_nur_bei_gruener_ampel(tmp_path):
    from cra import release_db as rdb

    db = tmp_path / 'cra.sqlite'
    with pytest.raises(ValueError) as e:
        rdb.cra_ready_feststellen(db, PROJ, von='c@example.com', gate=ROT)
    # Die Meldung muss sagen, was fehlt — sonst sucht der Anwender selbst.
    assert 'DoC fehlt' in str(e.value)


def test_feststellung_haelt_person_zeit_und_stand(tmp_path):
    from cra import release_db as rdb

    db = tmp_path / 'cra.sqlite'
    rec = rdb.cra_ready_feststellen(db, PROJ, von='compliance@example.com', gate=GRUEN)
    assert rec['bereit_status'] == 'bereit'
    assert rec['bereit_von'] == 'compliance@example.com' and rec['bereit_am']
    assert rec['bereit_gate']['ampel'] == 'gruen', (
        'ohne den eingefrorenen Stand sagt die Feststellung nicht, worauf sie '
        'sich bezog')


def test_entzug_braucht_begruendung(tmp_path):
    from cra import release_db as rdb

    db = tmp_path / 'cra.sqlite'
    rdb.cra_ready_feststellen(db, PROJ, von='c@example.com', gate=GRUEN)
    with pytest.raises(ValueError, match='Begründung'):
        rdb.cra_ready_entziehen(db, PROJ, von='c@example.com', grund='weg')

    rec = rdb.cra_ready_entziehen(db, PROJ, von='c@example.com',
                                  grund='Wesentliche Änderung in 3.0.0')
    assert rec['bereit_status'] == 'entzogen'
    assert 'Wesentliche' in rec['bereit_entzug_grund']


def test_entzug_ohne_feststellung_abgewiesen(tmp_path):
    from cra import release_db as rdb

    db = tmp_path / 'cra.sqlite'
    with pytest.raises(ValueError, match='keine Feststellung'):
        rdb.cra_ready_entziehen(db, PROJ, von='c@example.com', grund='x' * 20)


def test_ueberholt_statt_stillem_entzug():
    """Reine Funktion, bewusst ohne Datenbank: Die Regel ist eine Aussage über
    Zuständigkeit — rechnen darf widersprechen, nicht löschen."""
    from cra import release_db as rdb

    bereit = {'bereit_status': 'bereit'}
    assert rdb.bereit_ueberholt(bereit, ROT) is True
    assert rdb.bereit_ueberholt(bereit, GRUEN) is False
    # Ohne Feststellung gibt es nichts zu überholen.
    assert rdb.bereit_ueberholt({'bereit_status': 'offen'}, ROT) is False
    assert rdb.bereit_ueberholt({'bereit_status': 'entzogen'}, ROT) is False
    assert rdb.bereit_ueberholt(None, ROT) is False


def test_feststellung_ueberschreibt_einen_entzug(tmp_path):
    """Nach dem Nachbessern muss eine erneute Feststellung möglich sein —
    sonst wäre ein Entzug endgültig und der Anwender umgeht das Verfahren."""
    from cra import release_db as rdb

    db = tmp_path / 'cra.sqlite'
    rdb.cra_ready_feststellen(db, PROJ, von='c@example.com', gate=GRUEN)
    rdb.cra_ready_entziehen(db, PROJ, von='c@example.com', grund='Befund aus dem Audit')
    rec = rdb.cra_ready_feststellen(db, PROJ, von='c2@example.com', gate=GRUEN)
    assert rec['bereit_status'] == 'bereit'
    assert rec['bereit_entzug_grund'] == '', 'alter Entzugsgrund darf nicht stehenbleiben'


def test_snapshot_je_release_ist_idempotent(tmp_path):
    """#1744: Jede Einreichung friert ein. Zweimal dieselbe Version darf keine
    zwei Snapshots erzeugen — sonst wächst die Historie bei jeder Nachbesserung
    und niemand erkennt den geprüften Stand."""
    from cra import release_db as rdb

    db = tmp_path / 'cra.sqlite'
    rdb.snapshot_einfrieren(db, PROJ, '1.0.0', grund='Einreichung')
    res = rdb.snapshot_einfrieren(db, PROJ, '1.0.0', grund='Einreichung nach Nachbesserung')
    eigene = [s for s in res['snapshots'] if s['version'] == '1.0.0']
    assert len(eigene) == 1, eigene
    assert 'Nachbesserung' in eigene[0]['grund']

    rdb.snapshot_einfrieren(db, PROJ, '1.1.0', grund='Einreichung')
    res = rdb.snapshot_einfrieren(db, PROJ, '1.0.0', grund='nochmal')
    assert len({s['version'] for s in res['snapshots']}) == 2
