"""DS2 (#1102) — Tests für das Accountability-/DSMS-Cockpit (Art. 5 Abs. 2 DSGVO).

Aggregations-Tests gegen eine temporäre dsgvo-SQLite unter
``data/db/_pytest_*.sqlite`` (innerhalb des Repo-Roots, von ``connect_sqlite``
zugelassen). Das Blueprint wird NICHT benötigt; getestet wird ``build_cockpit``.
"""
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

from dsgvo import db as core_db
from dsgvo import betroffenenrechte_db as br_db
from dsgvo import dsb_db
from dsgvo import einwilligung_db
from dsgvo import loeschkonzept_db
from dsgvo import tom_katalog
from dsgvo import transfer_db
from dsgvo.dsms_cockpit import AREA_META, build_cockpit

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJEKT = 'Cockpit-Projekt'


@pytest.fixture()
def db_path():
    p = REPO_ROOT / 'data' / 'db' / f'_pytest_cockpit_{uuid.uuid4().hex}.sqlite'
    p.parent.mkdir(parents=True, exist_ok=True)
    core_db.ensure_db(p)
    yield p
    for suffix in ('', '-wal', '-shm'):
        f = Path(str(p) + suffix)
        if f.exists():
            f.unlink()


def _area(cockpit, key):
    return next(a for a in cockpit['areas'] if a['key'] == key)


def test_empty_project_shape(db_path):
    cockpit = build_cockpit(db_path, PROJEKT)
    # Grundstruktur + ein Bereich je AREA_META.
    assert cockpit['projekt'] == PROJEKT
    assert {a['key'] for a in cockpit['areas']} == {m['key'] for m in AREA_META}
    # Gesamt = Durchschnitt; bei leerem Projekt nur durch Betroffenenrechte (100 %)
    # über 0 gehoben — bleibt aber im niedrigen Bereich. (#1216: Joint-Controller-
    # Bereich kam als weitere 'leer'-Area hinzu ⇒ Obergrenze leicht angehoben.)
    assert 0 <= cockpit['gesamt_reifegrad'] <= 20
    # Leere Bereiche melden 'leer' (außer Betroffenenrechte: 0 Anträge ⇒ 100 %).
    assert _area(cockpit, 'vvt')['status'] == 'leer'
    assert _area(cockpit, 'betroffenenrechte')['reifegrad_pct'] == 100
    # DSB fehlt ⇒ eine offene Aufgabe.
    assert any(a['area'] == 'dsb' for a in cockpit['offene_aufgaben'])


def test_vvt_reifegrad(db_path):
    core_db.save_vvt(db_path, PROJEKT, {'vvt_id': 'VVT-1', 'name': 'A', 'rechtsgrundlage': 'Art. 6 Abs. 1 b'})
    core_db.save_vvt(db_path, PROJEKT, {'vvt_id': 'VVT-2', 'name': 'B'})  # keine Rechtsgrundlage
    cockpit = build_cockpit(db_path, PROJEKT)
    vvt = _area(cockpit, 'vvt')
    assert vvt['reifegrad_pct'] == 50
    assert vvt['offen'] == 1
    assert any(a['area'] == 'vvt' for a in cockpit['offene_aufgaben'])


def test_tom_reifegrad_and_faellige_pruefung(db_path):
    tom_katalog.seed_projekt(db_path, PROJEKT)
    items = tom_katalog.list_massnahmen(db_path, PROJEKT)
    assert items, 'Seed sollte Maßnahmen anlegen'
    # Erste Maßnahme voll umsetzen (status==soll) + überfällige Wirksamkeitsprüfung.
    yesterday = (date.today() - timedelta(days=5)).isoformat()
    tom_katalog.upsert_massnahme(db_path, PROJEKT, {
        'massnahme_key': items[0]['massnahme_key'],
        'status': 5, 'soll': 5,
        'wirksamkeit_datum': yesterday,
    })
    cockpit = build_cockpit(db_path, PROJEKT)
    tom = _area(cockpit, 'tom')
    assert 0 < tom['reifegrad_pct'] < 100
    assert tom['faellig'] >= 1
    overdue = [a for a in cockpit['offene_aufgaben']
               if a['area'] == 'tom' and a['overdue']]
    assert overdue, 'Überfällige Wirksamkeitsprüfung sollte als Aufgabe erscheinen'


def test_betroffenenrechte_overdue(db_path):
    long_ago = (date.today() - timedelta(days=90)).isoformat()
    br_db.create_antrag(db_path, PROJEKT, typ='auskunft15', eingang_datum=long_ago)
    cockpit = build_cockpit(db_path, PROJEKT)
    br = _area(cockpit, 'betroffenenrechte')
    assert br['offen'] == 1
    assert br['faellig'] == 1
    assert any(a['area'] == 'betroffenenrechte' and a['overdue']
               for a in cockpit['offene_aufgaben'])


def test_transfer_tia_status(db_path):
    transfer_db.upsert_transfer(db_path, PROJEKT, 'T-1', drittland='USA', tia_status='offen')
    transfer_db.upsert_transfer(db_path, PROJEKT, 'T-2', drittland='IN', tia_status='abgeschlossen')
    cockpit = build_cockpit(db_path, PROJEKT)
    tr = _area(cockpit, 'transfer')
    assert tr['reifegrad_pct'] == 50
    assert tr['offen'] == 1


def test_loeschkonzept_faellig(db_path):
    loeschkonzept_db.save_regel(db_path, PROJEKT, 'L-1', datenkategorie='Bewerber',
                                loesch_trigger='nach Absage', status='offen')
    cockpit = build_cockpit(db_path, PROJEKT)
    lk = _area(cockpit, 'loeschkonzept')
    assert lk['faellig'] == 1
    assert any(a['area'] == 'loeschkonzept' for a in cockpit['offene_aufgaben'])


def test_einwilligung_aktiv_ratio(db_path):
    einwilligung_db.save_einwilligung(db_path, projekt_name=PROJEKT,
                                      einwilligung_id='E-1', status='aktiv')
    einwilligung_db.save_einwilligung(db_path, projekt_name=PROJEKT,
                                      einwilligung_id='E-2', status='widerrufen')
    cockpit = build_cockpit(db_path, PROJEKT)
    ew = _area(cockpit, 'einwilligung')
    assert ew['reifegrad_pct'] == 50


def test_dsb_completeness(db_path):
    dsb_db.upsert_dsb(db_path, PROJEKT, typ='intern', name='Max',
                      kontakt_email='dsb@example.com',
                      kontakt_veroeffentlicht=1, gemeldet_aufsicht=1)
    cockpit = build_cockpit(db_path, PROJEKT)
    dsb = _area(cockpit, 'dsb')
    assert dsb['reifegrad_pct'] == 100
    assert dsb['status'] == 'gruen'
    assert not any(a['area'] == 'dsb' for a in cockpit['offene_aufgaben'])


def test_gesamt_reifegrad_is_average(db_path):
    cockpit = build_cockpit(db_path, PROJEKT)
    avg = round(sum(a['reifegrad_pct'] for a in cockpit['areas']) / len(cockpit['areas']))
    assert cockpit['gesamt_reifegrad'] == avg


def test_aufgaben_overdue_sorted_first(db_path):
    # Überfälliger Antrag + fehlender DSB (nicht überfällig) ⇒ overdue zuerst.
    long_ago = (date.today() - timedelta(days=90)).isoformat()
    br_db.create_antrag(db_path, PROJEKT, typ='auskunft15', eingang_datum=long_ago)
    cockpit = build_cockpit(db_path, PROJEKT)
    aufgaben = cockpit['offene_aufgaben']
    assert aufgaben
    assert aufgaben[0]['overdue'] is True
