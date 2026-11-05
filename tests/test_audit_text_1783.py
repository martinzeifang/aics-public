"""Compliance-Audit: der formulierte Text ist überarbeitbar (#1783).

Die Wasserstandsmeldung trug den Hinweis „KI-generiert — fachlich zu prüfen"
und war nur ansehbar. Prüfen hieß: neu erzeugen lassen. Damit war der Hinweis
eine Sackgasse, und beim Kunden landete entweder ein ungeprüfter Text oder
keiner.

Zwei Zusagen hält dieses Modul fest: Der **gerechnete** Stand bleibt beim
Überarbeiten unberührt — er ist das Ergebnis der Antworten und nicht
verhandelbar —, und die KI-Fassung bleibt daneben erhalten, damit später
unterscheidbar ist, was die Maschine formuliert und was ein Mensch verantwortet
hat.
"""
from __future__ import annotations

from pathlib import Path

import pytest

PROJ = 'pytest-audit-text-1783'

# Historischer Dateiname: Die Audit-Tabellen liegen in der Gutachten-DB (#1713).
DB = Path('data/db/gutachten.sqlite')


@pytest.fixture
def meldung(pg):
    """Eine abgelegte Wasserstandsmeldung samt gerechnetem Stand."""
    from compliance_audit import db as adb

    adb.ensure_db(DB)
    status = {'stufe': 'teilweise', 'quote_prozent': 50.0,
              'fragen': {'gesamt': 2, 'erfuellt': 1}}
    ki = {'kundenmitteilung': 'Von der KI formuliert.',
          'je_framework': [], 'top_massnahmen': [], 'fazit': ''}
    rid = adb.save_wasserstand(DB, PROJ, status=status, ki=ki,
                               provider='copy-paste', erstellt_von='ki@test')
    return rid


def test_text_ueberarbeiten_laesst_den_stand_unberuehrt(meldung):
    from compliance_audit import db as adb

    vorher = adb.load_wasserstand(DB, meldung)
    neu = adb.update_wasserstand_text(
        DB, meldung,
        {'kundenmitteilung': 'Von der Prüferin überarbeitet.',
         'je_framework': [], 'top_massnahmen': [], 'fazit': 'Trägt.'},
        von='Martina Prüferin')

    assert neu['ki']['kundenmitteilung'] == 'Von der Prüferin überarbeitet.'
    # Der gerechnete Stand ist nicht verhandelbar.
    assert neu['status'] == vorher['status']
    assert neu['stufe'] == vorher['stufe']
    assert neu['quote_prozent'] == vorher['quote_prozent']


def test_die_ki_fassung_bleibt_erhalten(meldung):
    """Sonst wäre nach dem ersten Überarbeiten nicht mehr unterscheidbar,
    was formuliert und was verantwortet wurde."""
    from compliance_audit import db as adb

    adb.update_wasserstand_text(DB, meldung,
                                {'kundenmitteilung': 'Fassung 2'}, von='A')
    adb.update_wasserstand_text(DB, meldung,
                                {'kundenmitteilung': 'Fassung 3'}, von='B')
    rec = adb.load_wasserstand(DB, meldung)

    assert rec['ki']['kundenmitteilung'] == 'Fassung 3'
    # Nicht „Fassung 2" — das Original ist die KI-Fassung, nicht die vorherige.
    assert rec['ki_original']['kundenmitteilung'] == 'Von der KI formuliert.'


def test_wer_ueberarbeitet_hat_steht_dabei(meldung):
    from compliance_audit import db as adb

    rec = adb.update_wasserstand_text(DB, meldung,
                                      {'kundenmitteilung': 'Geprüft.'},
                                      von='Martina Prüferin')
    assert rec['bearbeitet_von'] == 'Martina Prüferin'
    assert rec['bearbeitet_am']
    # Vor der Überarbeitung steht dort nichts — die Oberfläche unterscheidet
    # daran „KI-Entwurf" von „fachlich verantwortet".
    zweite = adb.save_wasserstand(DB, PROJ, status={'stufe': 'nicht'},
                                  ki={'kundenmitteilung': 'x'})
    assert adb.load_wasserstand(DB, zweite)['bearbeitet_von'] == ''


def test_unbekannte_meldung_meldet_sich(pg):
    from compliance_audit import db as adb

    assert adb.update_wasserstand_text(DB, 999999, {'a': 1}) is None


def test_rest_endpunkt_speichert_und_schuetzt(pg, client, auth_headers):
    """Über die REST-Schicht, inklusive Projektbindung."""
    from compliance_audit import db as adb
    from gutachten.db import save_project

    save_project(DB, name=PROJ, frameworks=['ISO 27001'], pruefungsfokus='')
    rid = adb.save_wasserstand(DB, PROJ, status={'stufe': 'teilweise'},
                               ki={'kundenmitteilung': 'KI'})

    res = client.put(f'/api/compliance-audit/{PROJ}/wasserstand/{rid}',
                     json={'ki': {'kundenmitteilung': 'Mensch'}},
                     headers=auth_headers)
    assert res.status_code == 200, res.get_data(as_text=True)
    assert res.get_json()['ki']['kundenmitteilung'] == 'Mensch'

    # Fremdes Projekt kommt nicht an die Meldung.
    res = client.put(f'/api/compliance-audit/anderes-projekt/wasserstand/{rid}',
                     json={'ki': {'kundenmitteilung': 'fremd'}},
                     headers=auth_headers)
    assert res.status_code == 404
