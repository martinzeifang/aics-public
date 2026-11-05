"""DS-ZA (#1215) — Tests Kompatibilitätstest Zweckänderung (Art. 6(4))."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from dsgvo import zweckaenderung_db as za

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_path():
    db_dir = REPO_ROOT / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    p = db_dir / f"_pytest_za_{uuid.uuid4().hex}.sqlite"
    try:
        yield p
    finally:
        for suffix in ("", "-wal", "-shm"):
            f = Path(str(p) + suffix)
            if f.exists():
                f.unlink()


def test_ensure_table_idempotent(db_path):
    za.ensure_table(db_path)
    za.ensure_table(db_path)
    assert za.list_za(db_path, "Proj") == []


def test_save_five_criteria_and_result(db_path):
    pk = za.save_za(db_path, "Proj", {
        "za_id": "ZA-1", "vvt_ref": "VVT-3",
        "urspruenglicher_zweck": "Vertragsabwicklung", "neuer_zweck": "KI-Training",
        "krit_zusammenhang": "a", "krit_kontext": "b", "krit_datenart": "c",
        "krit_folgen": "d", "krit_garantien": "e",
        "ergebnis": "unvereinbar", "neue_rechtsgrundlage": "Einwilligung Art. 6(1)(a)"})
    assert pk > 0
    r = za.get_za(db_path, pk)
    assert r["krit_zusammenhang"] == "a"
    assert r["krit_kontext"] == "b"
    assert r["krit_datenart"] == "c"
    assert r["krit_folgen"] == "d"
    assert r["krit_garantien"] == "e"
    assert r["ergebnis"] == "unvereinbar"
    assert r["neue_rechtsgrundlage"] == "Einwilligung Art. 6(1)(a)"


def test_upsert_on_conflict(db_path):
    pk1 = za.save_za(db_path, "Proj", {"za_id": "ZA-1", "neuer_zweck": "A"})
    pk2 = za.save_za(db_path, "Proj", {"za_id": "ZA-1", "neuer_zweck": "B", "ergebnis": "vereinbar"})
    assert pk1 == pk2
    items = za.list_za(db_path, "Proj")
    assert len(items) == 1
    assert items[0]["neuer_zweck"] == "B"
    assert items[0]["ergebnis"] == "vereinbar"


def test_missing_id_raises(db_path):
    with pytest.raises(ValueError):
        za.save_za(db_path, "Proj", {"neuer_zweck": "X"})


def test_invalid_ergebnis_raises(db_path):
    with pytest.raises(ValueError):
        za.save_za(db_path, "Proj", {"za_id": "X", "ergebnis": "bad"})


def test_idor_scoped(db_path):
    pk = za.save_za(db_path, "ProjA", {"za_id": "ZA-A"})
    assert za.get_za(db_path, pk, "ProjA") is not None
    assert za.get_za(db_path, pk, "ProjB") is None
    assert za.delete_za(db_path, pk, "ProjB") is False
    assert za.delete_za(db_path, pk, "ProjA") is True


def test_project_isolation(db_path):
    za.save_za(db_path, "ProjA", {"za_id": "ZA-1"})
    za.save_za(db_path, "ProjB", {"za_id": "ZA-1"})
    assert len(za.list_za(db_path, "ProjA")) == 1
    assert len(za.list_za(db_path, "ProjB")) == 1
