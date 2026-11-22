"""Ein gelöschtes CRA-Projekt lässt nichts zurück (#1752).

``delete_projekt`` nannte fünf Tabellen direkt im Code und ließ mindestens acht
stehen — darunter ``cra_vuln`` (Schwachstellen mit CVE-Bezug und
Triage-Kommentaren) und ``cra_psirt`` (Kontaktdaten von Personen). Bei einem
Mandanten, der die Löschung seiner Daten verlangt, ist das keine Formalie.

Unter Postgres fiel es zusätzlich nicht auf: SQLite-Pfade sind nur
Schema-Selektoren (#1332), das ``unlink()``-Teardown älterer Tests ist dort ein
No-op. Zeilen sammelten sich über Läufe hinweg, und ein neuer Test sah Daten
eines alten Projekts gleichen Namens — ein Testergebnis, das von der Reihenfolge
abhängt.

Der wichtigste Test hier ist nicht der, der das Löschen prüft, sondern
``test_jede_tabelle_ist_zugeordnet``: Er bemerkt die **nächste** neue Tabelle.
Ohne ihn fehlt beim nächsten Register wieder eine.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJ = 'pytest-cleanup-1752'
REPO = Path(__file__).resolve().parent.parent


def test_jede_tabelle_ist_zugeordnet():
    """Jede ``cra_``-Tabelle steht entweder in der Aufräum-Liste oder
    ausdrücklich in der Gegenliste. Eine neue Tabelle, die in keiner von beiden
    steht, lässt diesen Test rot werden — und genau das ist der Zweck."""
    from cra.db import PROJEKT_TABELLEN, TABELLEN_OHNE_PROJEKTBEZUG

    gefunden: set[str] = set()
    for pfad in (REPO / 'cra').glob('*.py'):
        gefunden |= set(re.findall(r'CREATE TABLE IF NOT EXISTS (cra_\w+)',
                                   pfad.read_text(encoding='utf-8')))
    zugeordnet = {t for t, _ in PROJEKT_TABELLEN} | set(TABELLEN_OHNE_PROJEKTBEZUG)
    offen = gefunden - zugeordnet
    assert not offen, (
        f'Diese CRA-Tabellen sind beim Löschen eines Projekts nicht zugeordnet: '
        f'{sorted(offen)}. Entweder in PROJEKT_TABELLEN aufnehmen oder in '
        f'TABELLEN_OHNE_PROJEKTBEZUG begründen.')


def test_liste_nennt_keine_tabelle_zweimal():
    from cra.db import PROJEKT_TABELLEN

    namen = [t for t, _ in PROJEKT_TABELLEN]
    assert len(namen) == len(set(namen)), [n for n in namen if namen.count(n) > 1]


def test_die_fruehere_luecke_ist_geschlossen():
    """Die im Issue genannten Tabellen namentlich — damit niemand sie
    versehentlich wieder herausnimmt."""
    from cra.db import PROJEKT_TABELLEN

    namen = {t for t, _ in PROJEKT_TABELLEN}
    for tbl in ('cra_vuln', 'cra_sbom', 'cra_psirt', 'cra_support_period'):
        assert tbl in namen, tbl


def test_loeschen_raeumt_alle_tabellen(tmp_path):
    from cra import db as cdb
    from cra import konformitaet_db as kdb
    from cra import release_db as rdb

    db = tmp_path / 'cra.sqlite'
    cdb.save_projekt(db, name=PROJ, unternehmen='pytest-firma-1752')
    # In mehreren der zuvor übersehenen Tabellen Spuren anlegen.
    cdb.save_bewertung(db, PROJ, 'CRA-A-01', 3, kommentar='x')
    cdb.upsert_vuln(db, PROJ, {'cve_id': 'CVE-2026-0001', 'schwere': 'high',
                               'titel': 'Testbefund'})
    kdb.save_konformitaet(db, PROJ, {'release_version': '1.0.0', 'bewertungsweg': 'A'})
    rdb.save_release(db, PROJ, {'aktuelle_version': '1.0.0'})
    rdb.snapshot_einfrieren(db, PROJ, '1.0.0', grund='Test')

    cdb.delete_projekt(db, PROJ)

    con = cdb._connect(db)
    try:
        uebrig = []
        for tbl, spalte in cdb.PROJEKT_TABELLEN:
            try:
                r = con.execute(
                    f'SELECT COUNT(*) AS n FROM {tbl} WHERE {spalte}=?', (PROJ,)
                ).fetchone()
            except Exception:      # Tabelle in dieser Installation nicht angelegt
                con.rollback()
                continue
            anzahl = (dict(r) if not isinstance(r, dict) else r).get('n', 0)
            if anzahl:
                uebrig.append(f'{tbl}={anzahl}')
        assert not uebrig, f'nach dem Löschen übrig: {uebrig}'
    finally:
        con.close()
    assert cdb.load_projekt(db, PROJ) is None


def test_loeschen_scheitert_nicht_an_ungenutzten_tabellen(tmp_path):
    """Eine Tabelle kann fehlen, wenn das Vertikal nie genutzt wurde. Ohne
    Savepoint bricht die Transaktion ab und das Projekt selbst bliebe stehen —
    das Löschen würde an einer ungenutzten Tabelle scheitern."""
    from cra import db as cdb

    db = tmp_path / 'cra.sqlite'
    cdb.save_projekt(db, name=PROJ, unternehmen='pytest-firma-1752')
    cdb.delete_projekt(db, PROJ)
    cdb.delete_projekt(db, PROJ)        # zweimal: idempotent
    assert cdb.load_projekt(db, PROJ) is None


def test_archiv_dateien_gehen_mit(tmp_path, monkeypatch):
    """Eine Datei ohne Datenbankzeile ist für die Anwendung unsichtbar — also
    kann sie niemand mehr finden oder löschen. Beim Löschen eines Mandanten
    wäre das das schlechtere Ergebnis als die Löschung selbst.

    Folge, die jemand wissen muss: Mit dem Projekt verschwindet sein
    Konformitäts-Archiv. Wer den Nachweis behalten will, lädt ihn vorher
    herunter.
    """
    from cra import db as cdb

    datei = tmp_path / 'nachweis.pdf'
    datei.write_bytes(b'%PDF-1.4 Test')

    monkeypatch.setattr(
        'cra.konformitaet_final_db.list_final',
        lambda db_path, name: [{'pdf_path': str(datei), 'sha256': 'x'}])

    db = tmp_path / 'cra.sqlite'
    cdb.save_projekt(db, name=PROJ, unternehmen='pytest-firma-1752')
    cdb.delete_projekt(db, PROJ)
    assert not datei.exists(), 'die archivierte PDF liegt noch auf der Platte'


def test_unloeschbare_datei_haelt_das_loeschen_nicht_auf(tmp_path, monkeypatch):
    """Best effort: Ein nicht löschbarer Pfad darf das Löschen des Projekts
    nicht verhindern — sonst blockiert ein Dateisystemproblem eine
    Löschanfrage, die erfüllt werden muss."""
    from cra import db as cdb

    monkeypatch.setattr(
        'cra.konformitaet_final_db.list_final',
        lambda db_path, name: [{'pdf_path': '/gibt/es/nicht/x.pdf'},
                               {'pdf_path': ''}])

    db = tmp_path / 'cra.sqlite'
    cdb.save_projekt(db, name=PROJ, unternehmen='pytest-firma-1752')
    cdb.delete_projekt(db, PROJ)
    assert cdb.load_projekt(db, PROJ) is None
