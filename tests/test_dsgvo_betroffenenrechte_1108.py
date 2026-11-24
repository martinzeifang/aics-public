"""DS8 (#1108) — DB-Level-Tests für das Betroffenenrechte-Register.

Verwendet eine temporäre dsgvo-SQLite unter ``data/db/_pytest_*.sqlite`` (innerhalb
des Repo-Roots, von ``connect_sqlite`` zugelassen) und räumt sie hinterher auf.
Das Blueprint wird NICHT benötigt.
"""
import uuid
from datetime import date
from pathlib import Path

import pytest

from dsgvo.betroffenenrechte_db import (
    ensure_table,
    compute_frist,
    create_antrag,
    list_antraege,
    get_antrag,
    update_antrag,
    delete_antrag,
    TYPEN,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_path():
    p = REPO_ROOT / 'data' / 'db' / f'_pytest_br_{uuid.uuid4().hex}.sqlite'
    p.parent.mkdir(parents=True, exist_ok=True)
    yield p
    for suffix in ('', '-wal', '-shm'):
        f = Path(str(p) + suffix)
        if f.exists():
            f.unlink()


def test_ensure_table_idempotent(db_path):
    ensure_table(db_path)
    ensure_table(db_path)  # zweiter Aufruf darf nicht scheitern
    assert list_antraege(db_path, 'Projekt-X') == []


def test_compute_frist_one_month():
    assert compute_frist('2026-01-15', 0) == '2026-02-15'


def test_compute_frist_with_extension():
    assert compute_frist('2026-01-15', 1) == '2026-04-15'


def test_compute_frist_month_end_clamp():
    # 31. Jan + 1 Monat → 28. Feb (kein Schaltjahr)
    assert compute_frist('2026-01-31', 0) == '2026-02-28'


def test_compute_frist_invalid():
    assert compute_frist('', 0) == ''
    assert compute_frist('not-a-date', 0) == ''


def test_create_and_get(db_path):
    a = create_antrag(
        db_path, 'Projekt-X',
        typ='auskunft15',
        eingang_datum='2026-03-01',
        antrag_id='BR-001',
        bearbeiter='Alice',
    )
    assert a['id'] > 0
    assert a['frist_datum'] == '2026-04-01'
    assert a['typ'] == 'auskunft15'
    assert isinstance(a['overdue'], bool)  # overdue ist datums-relativ; siehe overdue-Test

    fetched = get_antrag(db_path, a['id'])
    assert fetched is not None
    assert fetched['antrag_id'] == 'BR-001'
    assert fetched['bearbeiter'] == 'Alice'


def test_create_rejects_invalid_typ(db_path):
    with pytest.raises(ValueError):
        create_antrag(db_path, 'P', typ='quatsch', eingang_datum='2026-03-01')


def test_overdue_flag_past_due(db_path):
    # Eingang vor langer Zeit → Frist in der Vergangenheit, Status offen.
    a = create_antrag(
        db_path, 'Projekt-X', typ='loeschung17', eingang_datum='2020-01-01',
    )
    assert a['overdue'] is True
    # Abgeschlossene Anträge gelten nie als überfällig.
    # #1218: Löschung (Art. 17) ist ein Art.-19-Typ → Empfänger-Status vor
    # Abschluss setzen (hier 'entfällt', keine Empfänger).
    upd = update_antrag(db_path, a['id'], status='abgeschlossen',
                        empfaenger_status='entfaellt')
    assert upd['overdue'] is False


def test_update_recomputes_frist(db_path):
    a = create_antrag(db_path, 'P', typ='auskunft15', eingang_datum='2026-03-01')
    assert a['frist_datum'] == '2026-04-01'
    upd = update_antrag(db_path, a['id'], verlaengert=1)
    assert upd['verlaengert'] == 1
    assert upd['frist_datum'] == '2026-06-01'
    upd2 = update_antrag(db_path, a['id'], eingang_datum='2026-05-10')
    # Eingang neu + Verlängerung bleibt aktiv → +3 Monate
    assert upd2['frist_datum'] == '2026-08-10'


def test_update_rejects_invalid_typ(db_path):
    a = create_antrag(db_path, 'P', typ='auskunft15', eingang_datum='2026-03-01')
    with pytest.raises(ValueError):
        update_antrag(db_path, a['id'], typ='nope')


def test_update_missing_returns_none(db_path):
    ensure_table(db_path)
    assert update_antrag(db_path, 99999, status='abgeschlossen') is None


def test_list_filters_by_projekt(db_path):
    create_antrag(db_path, 'A', typ='auskunft15', eingang_datum='2026-03-01')
    create_antrag(db_path, 'B', typ='widerspruch21', eingang_datum='2026-03-02')
    a_list = list_antraege(db_path, 'A')
    assert len(a_list) == 1
    assert a_list[0]['projekt_name'] == 'A'


def test_delete(db_path):
    a = create_antrag(db_path, 'P', typ='profiling22', eingang_datum='2026-03-01')
    assert delete_antrag(db_path, a['id']) is True
    assert get_antrag(db_path, a['id']) is None
    assert delete_antrag(db_path, a['id']) is False


def test_all_typen_accepted(db_path):
    for t in TYPEN:
        a = create_antrag(db_path, 'P', typ=t, eingang_datum='2026-03-01')
        assert a['typ'] == t
