"""DS10 (#1110) — DB-Level-Tests für das DSGVO-Löschkonzept.

Arbeitet auf einer temporären DSGVO-SQLite unter ``data/db/_pytest_*.sqlite``
(unterhalb des Repo-Roots) und ruft ``ensure_table`` + CRUD direkt — ohne dass
das Blueprint registriert sein muss.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from dsgvo import loeschkonzept_db as lk

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_path():
    db_dir = REPO_ROOT / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    p = db_dir / f"_pytest_loeschkonzept_{uuid.uuid4().hex}.sqlite"
    try:
        yield p
    finally:
        for suffix in ("", "-wal", "-shm"):
            f = Path(str(p) + suffix)
            if f.exists():
                f.unlink()


def test_ensure_table_idempotent(db_path):
    lk.ensure_table(db_path)
    lk.ensure_table(db_path)  # zweimal => keine Exception
    assert lk.list_regeln(db_path, "Proj") == []


def test_save_and_list_and_get(db_path):
    pk = lk.save_regel(
        db_path,
        "Proj",
        "LK-001",
        datenkategorie="Bewerberdaten",
        aufbewahrungsfrist="6 Monate",
        rechtsgrundlage_frist="zweckbindung",
        loeschklasse="LK 2",
        loesch_trigger="Absage",
        verantwortlich="HR",
        status="aktiv",
        vvt_ref="VVT-12",
    )
    assert pk > 0
    regeln = lk.list_regeln(db_path, "Proj")
    assert len(regeln) == 1
    r = regeln[0]
    assert r["regel_id"] == "LK-001"
    assert r["datenkategorie"] == "Bewerberdaten"
    assert r["rechtsgrundlage_frist"] == "zweckbindung"
    assert r["loeschklasse"] == "LK 2"

    got = lk.get_regel(db_path, pk)
    assert got is not None
    assert got["id"] == pk


def test_upsert_on_conflict(db_path):
    pk1 = lk.save_regel(db_path, "Proj", "LK-001", datenkategorie="A", status="offen")
    pk2 = lk.save_regel(db_path, "Proj", "LK-001", datenkategorie="B", status="aktiv")
    assert pk1 == pk2
    regeln = lk.list_regeln(db_path, "Proj")
    assert len(regeln) == 1
    assert regeln[0]["datenkategorie"] == "B"
    assert regeln[0]["status"] == "aktiv"


def test_grouping_sort_by_kategorie(db_path):
    lk.save_regel(db_path, "Proj", "LK-002", datenkategorie="Zeta")
    lk.save_regel(db_path, "Proj", "LK-001", datenkategorie="Alpha")
    regeln = lk.list_regeln(db_path, "Proj")
    assert [r["datenkategorie"] for r in regeln] == ["Alpha", "Zeta"]


def test_update_status_and_delete(db_path):
    pk = lk.save_regel(db_path, "Proj", "LK-001", loesch_trigger="X", status="aktiv")
    assert lk.update_status(db_path, pk, "erledigt") is True
    assert lk.get_regel(db_path, pk)["status"] == "erledigt"
    assert lk.delete_regel(db_path, pk) is True
    assert lk.get_regel(db_path, pk) is None
    assert lk.update_status(db_path, pk, "offen") is False
    assert lk.delete_regel(db_path, pk) is False


def test_list_faellig(db_path):
    # fällig: status nicht erledigt/deaktiviert + Trigger gesetzt
    lk.save_regel(db_path, "Proj", "LK-A", loesch_trigger="Ende", status="aktiv")
    # nicht fällig: erledigt
    lk.save_regel(db_path, "Proj", "LK-B", loesch_trigger="Ende", status="erledigt")
    # nicht fällig: kein Trigger
    lk.save_regel(db_path, "Proj", "LK-C", loesch_trigger="", status="offen")
    faellig = lk.list_faellig(db_path, "Proj")
    ids = [r["regel_id"] for r in faellig]
    assert ids == ["LK-A"]


def test_project_isolation(db_path):
    lk.save_regel(db_path, "ProjA", "LK-1")
    lk.save_regel(db_path, "ProjB", "LK-1")
    assert len(lk.list_regeln(db_path, "ProjA")) == 1
    assert len(lk.list_regeln(db_path, "ProjB")) == 1
