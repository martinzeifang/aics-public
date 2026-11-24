"""DS-SUB (#1214) — Tests Subprozessor-Register + Genehmigungs-Workflow."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from dsgvo import subprozessoren_db as sub_db

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_path():
    db_dir = REPO_ROOT / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    p = db_dir / f"_pytest_sub_{uuid.uuid4().hex}.sqlite"
    try:
        yield p
    finally:
        for suffix in ("", "-wal", "-shm"):
            f = Path(str(p) + suffix)
            if f.exists():
                f.unlink()


def test_ensure_table_idempotent(db_path):
    sub_db.ensure_table(db_path)
    sub_db.ensure_table(db_path)
    assert sub_db.list_subprozessoren(db_path, "Proj", 1) == []


def test_create_with_fk_and_fields(db_path):
    pk = sub_db.save_subprozessor(db_path, "Proj", 5, {
        "name": "AWS", "leistung": "Hosting", "drittland": 1,
        "drittland_garantie": "SCC", "genehmigung_status": "ausstehend",
        "pflichten_backtoback": 1})
    assert pk > 0
    subs = sub_db.list_subprozessoren(db_path, "Proj", 5)
    assert len(subs) == 1
    s = subs[0]
    assert s["avv_pk"] == 5
    assert s["drittland"] == 1
    assert s["drittland_garantie"] == "SCC"
    assert s["pflichten_backtoback"] == 1
    assert s["genehmigung_status"] == "ausstehend"


def test_name_required(db_path):
    with pytest.raises(ValueError):
        sub_db.save_subprozessor(db_path, "Proj", 1, {"leistung": "x"})


def test_invalid_status_rejected(db_path):
    with pytest.raises(ValueError):
        sub_db.save_subprozessor(db_path, "Proj", 1, {"name": "X", "genehmigung_status": "bad"})


def test_approval_workflow(db_path):
    pk = sub_db.save_subprozessor(db_path, "Proj", 1, {"name": "Sub"})
    assert sub_db.set_genehmigung(db_path, pk, "Proj", "genehmigt", datum="2026-02-01") is True
    s = sub_db.get_subprozessor(db_path, pk)
    assert s["genehmigung_status"] == "genehmigt"
    assert s["genehmigung_datum"] == "2026-02-01"


def test_review_faellig_trigger(db_path):
    avv_pk = 7
    sub_db.save_subprozessor(db_path, "Proj", avv_pk, {"name": "Sub1", "genehmigung_status": "genehmigt"})
    # noch ausstehend → review-faellig
    pk2 = sub_db.save_subprozessor(db_path, "Proj", avv_pk, {"name": "Sub2"})
    assert sub_db.avv_review_faellig(db_path, "Proj", avv_pk) is True
    sub_db.set_genehmigung(db_path, pk2, "Proj", "genehmigt")
    assert sub_db.avv_review_faellig(db_path, "Proj", avv_pk) is False


def test_counts_by_avv(db_path):
    sub_db.save_subprozessor(db_path, "Proj", 1, {"name": "A", "genehmigung_status": "genehmigt"})
    sub_db.save_subprozessor(db_path, "Proj", 1, {"name": "B"})
    sub_db.save_subprozessor(db_path, "Proj", 2, {"name": "C"})
    counts = sub_db.counts_by_avv(db_path, "Proj")
    assert counts[1] == {"gesamt": 2, "ausstehend": 1}
    assert counts[2] == {"gesamt": 1, "ausstehend": 1}


def test_update_idor_scoped(db_path):
    pk = sub_db.save_subprozessor(db_path, "ProjA", 1, {"name": "A"})
    # Update aus falschem Projekt → ValueError(not found)
    with pytest.raises(ValueError):
        sub_db.save_subprozessor(db_path, "ProjB", 1, {"name": "B"}, pk=pk)
    # Update aus richtigem Projekt → ok
    sub_db.save_subprozessor(db_path, "ProjA", 1, {"leistung": "neu"}, pk=pk)
    assert sub_db.get_subprozessor(db_path, pk)["leistung"] == "neu"


def test_delete_idor_scoped(db_path):
    pk = sub_db.save_subprozessor(db_path, "ProjA", 1, {"name": "A"})
    assert sub_db.delete_subprozessor(db_path, pk, "ProjB") is False
    assert sub_db.delete_subprozessor(db_path, pk, "ProjA") is True
    assert sub_db.get_subprozessor(db_path, pk) is None


def test_genehmigung_404_for_wrong_project(db_path):
    pk = sub_db.save_subprozessor(db_path, "ProjA", 1, {"name": "A"})
    assert sub_db.set_genehmigung(db_path, pk, "ProjB", "genehmigt") is False
