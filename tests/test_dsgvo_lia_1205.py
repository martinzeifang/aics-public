"""DS-LIA (#1205) — Tests LIA-Register (Drei-Stufen-Test, Art. 6(1)(f))."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from dsgvo import lia_db

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_path():
    db_dir = REPO_ROOT / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    p = db_dir / f"_pytest_lia_{uuid.uuid4().hex}.sqlite"
    try:
        yield p
    finally:
        for suffix in ("", "-wal", "-shm"):
            f = Path(str(p) + suffix)
            if f.exists():
                f.unlink()


def test_ensure_table_idempotent(db_path):
    lia_db.ensure_table(db_path)
    lia_db.ensure_table(db_path)
    assert lia_db.list_lia(db_path, "Proj") == []


def test_save_and_get_three_stage_fields(db_path):
    pk = lia_db.save_lia(db_path, "Proj", {
        "lia_id": "LIA-001", "vvt_ref": "VVT-1", "verarbeitung": "Newsletter",
        "zweck": "Direktwerbung", "berechtigtes_interesse": "Kundenbindung",
        "legitim": 1, "erforderlichkeit": "kein milderes Mittel",
        "mildere_mittel_geprueft": 1, "interessen_betroffener": "gering",
        "vernuenftige_erwartung": "ja", "garantien_optout": "Opt-out im Footer",
        "ergebnis": "ueberwiegt", "stage": "ergebnis",
    })
    assert pk > 0
    r = lia_db.get_lia(db_path, pk)
    assert r["berechtigtes_interesse"] == "Kundenbindung"
    assert r["legitim"] == 1
    assert r["mildere_mittel_geprueft"] == 1
    assert r["ergebnis"] == "ueberwiegt"


def test_upsert_on_conflict(db_path):
    pk1 = lia_db.save_lia(db_path, "Proj", {"lia_id": "LIA-1", "zweck": "A"})
    pk2 = lia_db.save_lia(db_path, "Proj", {"lia_id": "LIA-1", "zweck": "B", "ergebnis": "ueberwiegt"})
    assert pk1 == pk2
    items = lia_db.list_lia(db_path, "Proj")
    assert len(items) == 1
    assert items[0]["zweck"] == "B"
    assert items[0]["ergebnis"] == "ueberwiegt"


def test_review_date_computed(db_path):
    pk = lia_db.save_lia(db_path, "Proj", {
        "lia_id": "LIA-R", "review_datum": "2026-01-15", "review_zyklus_monate": 12})
    r = lia_db.get_lia(db_path, pk)
    assert r["naechstes_review"] == "2027-01-15"


def test_invalid_ergebnis_raises(db_path):
    with pytest.raises(ValueError):
        lia_db.save_lia(db_path, "Proj", {"lia_id": "X", "ergebnis": "bad"})


def test_invalid_stage_raises(db_path):
    with pytest.raises(ValueError):
        lia_db.save_lia(db_path, "Proj", {"lia_id": "X", "stage": "bad"})


def test_missing_lia_id_raises(db_path):
    with pytest.raises(ValueError):
        lia_db.save_lia(db_path, "Proj", {"zweck": "no id"})


def test_idor_scoped_get_and_delete(db_path):
    pk = lia_db.save_lia(db_path, "ProjA", {"lia_id": "LIA-A"})
    assert lia_db.get_lia(db_path, pk, "ProjA") is not None
    assert lia_db.get_lia(db_path, pk, "ProjB") is None
    assert lia_db.delete_lia(db_path, pk, "ProjB") is False
    assert lia_db.delete_lia(db_path, pk, "ProjA") is True
    assert lia_db.get_lia(db_path, pk) is None


def test_auto_trigger_ensure_for_vvt_idempotent(db_path):
    pk1 = lia_db.ensure_for_vvt(db_path, "Proj", vvt_ref="VVT-9", verarbeitung="X", zweck="Y")
    pk2 = lia_db.ensure_for_vvt(db_path, "Proj", vvt_ref="VVT-9")
    assert pk1 == pk2  # keine Doppelanlage
    items = lia_db.list_lia(db_path, "Proj")
    assert len(items) == 1
    assert items[0]["vvt_ref"] == "VVT-9"
    assert items[0]["ergebnis"] == "offen"


def test_project_isolation(db_path):
    lia_db.save_lia(db_path, "ProjA", {"lia_id": "LIA-1"})
    lia_db.save_lia(db_path, "ProjB", {"lia_id": "LIA-1"})
    assert len(lia_db.list_lia(db_path, "ProjA")) == 1
    assert len(lia_db.list_lia(db_path, "ProjB")) == 1
