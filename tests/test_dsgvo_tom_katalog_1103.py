"""DB-Level-Tests für den DSGVO-TOM-Katalog (#1103/#1104).

Testet ``ensure_table`` + CRUD + Seed + Wirksamkeit + KI-Stub direkt auf einer
temporären SQLite unter ``data/db/`` (unterhalb des Repo-Roots) — ohne dass das
Flask-Blueprint registriert sein muss.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from dsgvo import tom_katalog as tk

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_path() -> Path:
    db_dir = REPO_ROOT / 'data' / 'db'
    db_dir.mkdir(parents=True, exist_ok=True)
    path = db_dir / f'_pytest_tom_{uuid.uuid4().hex}.sqlite'
    try:
        yield path
    finally:
        for suffix in ('', '-wal', '-shm'):
            p = Path(str(path) + suffix)
            if p.exists():
                p.unlink()


def test_ensure_table_idempotent(db_path: Path):
    tk.ensure_table(db_path)
    tk.ensure_table(db_path)  # zweimal -> kein Fehler
    assert tk.list_massnahmen(db_path, 'P1') == []


def test_upsert_and_get(db_path: Path):
    saved = tk.upsert_massnahme(db_path, 'P1', {
        'ziel': 'Vertraulichkeit',
        'massnahme_key': 'VT-99',
        'titel': 'Custom-Maßnahme',
        'beschreibung': 'Test',
        'status': 3,
        'soll': 5,
        'verantwortlich': 'CISO',
        'vvt_ref': 'VVT-7',
    })
    assert saved['massnahme_key'] == 'VT-99'
    assert saved['status'] == 3
    assert saved['soll'] == 5

    fetched = tk.get_massnahme(db_path, 'P1', 'VT-99')
    assert fetched is not None
    assert fetched['titel'] == 'Custom-Maßnahme'
    assert fetched['verantwortlich'] == 'CISO'


def test_upsert_updates_existing(db_path: Path):
    tk.upsert_massnahme(db_path, 'P1', {'massnahme_key': 'X-1', 'ziel': 'Integrität', 'status': 1})
    tk.upsert_massnahme(db_path, 'P1', {'massnahme_key': 'X-1', 'ziel': 'Integrität', 'status': 4, 'titel': 'neu'})
    items = tk.list_massnahmen(db_path, 'P1')
    assert len(items) == 1
    assert items[0]['status'] == 4
    assert items[0]['titel'] == 'neu'


def test_status_clamped(db_path: Path):
    saved = tk.upsert_massnahme(db_path, 'P1', {'massnahme_key': 'C-1', 'ziel': 'Transparenz', 'status': 99, 'soll': -3})
    assert saved['status'] == 5
    assert saved['soll'] == 0


def test_invalid_ziel_rejected(db_path: Path):
    with pytest.raises(ValueError):
        tk.upsert_massnahme(db_path, 'P1', {'massnahme_key': 'Z-1', 'ziel': 'Nichtexistent'})


def test_missing_key_rejected(db_path: Path):
    with pytest.raises(ValueError):
        tk.upsert_massnahme(db_path, 'P1', {'massnahme_key': '  '})


def test_seed_idempotent_and_full(db_path: Path):
    inserted = tk.seed_projekt(db_path, 'P1')
    assert inserted == len(tk.SEED_KATALOG)
    items = tk.list_massnahmen(db_path, 'P1')
    assert len(items) == len(tk.SEED_KATALOG)
    # alle 7 Ziele vertreten
    assert {m['ziel'] for m in items} == set(tk.ZIELE)

    # zweites Seed fügt nichts hinzu
    inserted2 = tk.seed_projekt(db_path, 'P1')
    assert inserted2 == 0
    assert len(tk.list_massnahmen(db_path, 'P1')) == len(tk.SEED_KATALOG)


def test_seed_preserves_manual_status(db_path: Path):
    tk.seed_projekt(db_path, 'P1')
    key = tk.SEED_KATALOG[0]['massnahme_key']
    tk.set_wirksamkeit(db_path, 'P1', key, '2026-01-01', 'wirksam', status=5)
    # erneutes Seed (auch force) darf Status/Wirksamkeit nicht zurücksetzen
    tk.seed_projekt(db_path, 'P1', force=True)
    m = tk.get_massnahme(db_path, 'P1', key)
    assert m is not None
    assert m['status'] == 5
    assert m['wirksamkeit_ergebnis'] == 'wirksam'


def test_sorted_by_ziel_order(db_path: Path):
    tk.seed_projekt(db_path, 'P1')
    items = tk.list_massnahmen(db_path, 'P1')
    ziel_seq = [m['ziel'] for m in items]
    order = {z: i for i, z in enumerate(tk.ZIELE)}
    assert ziel_seq == sorted(ziel_seq, key=lambda z: order[z])


def test_set_wirksamkeit(db_path: Path):
    tk.upsert_massnahme(db_path, 'P1', {'massnahme_key': 'W-1', 'ziel': 'Verfügbarkeit'})
    m = tk.set_wirksamkeit(db_path, 'P1', 'W-1', '2026-06-08', 'teilweise wirksam', status=2)
    assert m is not None
    assert m['wirksamkeit_datum'] == '2026-06-08'
    assert m['wirksamkeit_ergebnis'] == 'teilweise wirksam'
    assert m['status'] == 2

    # ohne Status-Übergabe bleibt Status erhalten
    m2 = tk.set_wirksamkeit(db_path, 'P1', 'W-1', '2026-07-01', 'wirksam')
    assert m2 is not None
    assert m2['status'] == 2
    assert m2['wirksamkeit_ergebnis'] == 'wirksam'


def test_delete(db_path: Path):
    tk.upsert_massnahme(db_path, 'P1', {'massnahme_key': 'D-1', 'ziel': 'Integrität'})
    assert tk.delete_massnahme(db_path, 'P1', 'D-1') is True
    assert tk.get_massnahme(db_path, 'P1', 'D-1') is None
    assert tk.delete_massnahme(db_path, 'P1', 'D-1') is False


def test_project_isolation(db_path: Path):
    tk.upsert_massnahme(db_path, 'P1', {'massnahme_key': 'M-1', 'ziel': 'Transparenz'})
    tk.upsert_massnahme(db_path, 'P2', {'massnahme_key': 'M-1', 'ziel': 'Transparenz'})
    assert len(tk.list_massnahmen(db_path, 'P1')) == 1
    assert len(tk.list_massnahmen(db_path, 'P2')) == 1


def test_ki_vorschlag_stub(db_path: Path):
    res = tk.ki_vorschlag(db_path, 'P1')
    assert res['stub'] is True
    # leeres Projekt -> alle 7 Ziele als hohe Priorität
    assert len(res['vorschlaege']) == len(tk.ZIELE)
    assert all(v['prioritaet'] == 'hoch' for v in res['vorschlaege'])

    # nach Seed + voller Bewertung eines Ziels reduziert sich der Bedarf
    tk.seed_projekt(db_path, 'P1')
    res2 = tk.ki_vorschlag(db_path, 'P1')
    # Seed setzt status=0 < soll=5 -> mittel-Vorschläge je Ziel
    assert all(v['prioritaet'] in ('hoch', 'mittel') for v in res2['vorschlaege'])
