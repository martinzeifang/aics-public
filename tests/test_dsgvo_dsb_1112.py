"""DS12 (#1112) — DB-Level-Tests für die DSB-Verwaltung (Art. 37-39 DSGVO).

Verwendet eine temporäre dsgvo-SQLite unter ``data/db/_pytest_*.sqlite`` (innerhalb
des Repo-Roots, von ``connect_sqlite`` zugelassen) und räumt sie hinterher auf.
Das Blueprint wird NICHT benötigt.
"""
import uuid
from pathlib import Path

import pytest

from dsgvo.dsb_db import (
    ensure_table,
    get_dsb,
    upsert_dsb,
    delete_dsb,
    TYPEN,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_path():
    p = REPO_ROOT / 'data' / 'db' / f'_pytest_dsb_{uuid.uuid4().hex}.sqlite'
    p.parent.mkdir(parents=True, exist_ok=True)
    yield p
    for suffix in ('', '-wal', '-shm'):
        f = Path(str(p) + suffix)
        if f.exists():
            f.unlink()


def test_ensure_table_idempotent(db_path):
    ensure_table(db_path)
    ensure_table(db_path)  # zweiter Aufruf darf nicht scheitern
    assert get_dsb(db_path, 'Projekt-X') is None


def test_upsert_inserts(db_path):
    dsb = upsert_dsb(
        db_path, 'Projekt-X',
        typ='intern',
        name='Max Mustermann',
        bestelldatum='2026-01-15',
        kontakt_email='dsb@example.com',
        kontakt_veroeffentlicht=1,
        gemeldet_aufsicht=1,
        aufgaben_nachweis='Beratung, Überwachung, Schulung',
        taetigkeitsbericht='Jahresbericht 2026',
        notizen='—',
    )
    assert dsb['id'] > 0
    assert dsb['projekt_name'] == 'Projekt-X'
    assert dsb['typ'] == 'intern'
    assert dsb['name'] == 'Max Mustermann'
    assert dsb['kontakt_veroeffentlicht'] == 1
    assert dsb['gemeldet_aufsicht'] == 1

    fetched = get_dsb(db_path, 'Projekt-X')
    assert fetched is not None
    assert fetched['kontakt_email'] == 'dsb@example.com'


def test_upsert_updates_same_record(db_path):
    first = upsert_dsb(db_path, 'P', typ='intern', name='Alice')
    second = upsert_dsb(db_path, 'P', typ='extern', name='Bob GmbH')
    # Gleicher Datensatz (Upsert auf projekt_name) → gleiche id.
    assert second['id'] == first['id']
    assert second['typ'] == 'extern'
    assert second['name'] == 'Bob GmbH'


def test_upsert_partial_keeps_existing(db_path):
    upsert_dsb(db_path, 'P', typ='intern', name='Alice', kontakt_email='a@x.de')
    # Nur Notizen aktualisieren → Name/E-Mail bleiben erhalten.
    upd = upsert_dsb(db_path, 'P', notizen='neue Notiz')
    assert upd['name'] == 'Alice'
    assert upd['kontakt_email'] == 'a@x.de'
    assert upd['notizen'] == 'neue Notiz'


def test_upsert_booleans_normalized(db_path):
    dsb = upsert_dsb(db_path, 'P', kontakt_veroeffentlicht=True, gemeldet_aufsicht=False)
    assert dsb['kontakt_veroeffentlicht'] == 1
    assert dsb['gemeldet_aufsicht'] == 0


def test_upsert_rejects_invalid_typ(db_path):
    with pytest.raises(ValueError):
        upsert_dsb(db_path, 'P', typ='quatsch')


def test_upsert_requires_projekt_name(db_path):
    with pytest.raises(ValueError):
        upsert_dsb(db_path, '', typ='intern')


def test_all_typen_accepted(db_path):
    for i, t in enumerate(TYPEN):
        dsb = upsert_dsb(db_path, f'P{i}', typ=t)
        assert dsb['typ'] == t


def test_one_record_per_projekt(db_path):
    upsert_dsb(db_path, 'A', name='DSB-A')
    upsert_dsb(db_path, 'B', name='DSB-B')
    assert get_dsb(db_path, 'A')['name'] == 'DSB-A'
    assert get_dsb(db_path, 'B')['name'] == 'DSB-B'


def test_delete(db_path):
    upsert_dsb(db_path, 'P', name='X')
    assert delete_dsb(db_path, 'P') is True
    assert get_dsb(db_path, 'P') is None
    assert delete_dsb(db_path, 'P') is False
