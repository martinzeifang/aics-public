"""DS-JC (#1216) — Tests Joint-Controller-Register (Art. 26 DSGVO)."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from dsgvo import joint_controller_db as jc_db

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_path():
    db_dir = REPO_ROOT / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    p = db_dir / f"_pytest_jc_{uuid.uuid4().hex}.sqlite"
    try:
        yield p
    finally:
        for suffix in ("", "-wal", "-shm"):
            f = Path(str(p) + suffix)
            if f.exists():
                f.unlink()


def test_ensure_table_idempotent(db_path):
    jc_db.ensure_table(db_path)
    jc_db.ensure_table(db_path)
    assert jc_db.list_jc(db_path, "Proj") == []


def test_save_and_get_pflichtenverteilung(db_path):
    pk = jc_db.save_jc(db_path, "Proj", {
        "jc_id": "JC-1", "partner": "Acme GmbH", "vvt_ref": "VVT-3",
        "verarbeitung": "Co-Marketing", "zweck_mittel": "gemeinsame Kampagne",
        "anlaufstelle_betroffene": "wir",
        "pflicht_information": "Art. 13 durch uns",
        "pflicht_tom": "Partner stellt Verschlüsselung",
        "pflicht_meldung": "wir melden Art. 33",
        "vereinbarung_vorhanden": 1, "vereinbarung_url": "https://example.com/jc",
        "zusammenfassung_status": "veroeffentlicht",
        "zusammenfassung_text": "Wesentliches: ...",
    })
    assert pk > 0
    r = jc_db.get_jc(db_path, pk)
    assert r["partner"] == "Acme GmbH"
    assert r["anlaufstelle_betroffene"] == "wir"
    assert r["vereinbarung_vorhanden"] == 1
    assert r["zusammenfassung_status"] == "veroeffentlicht"


def test_upsert_on_conflict(db_path):
    pk1 = jc_db.save_jc(db_path, "Proj", {"jc_id": "JC-1", "partner": "A"})
    pk2 = jc_db.save_jc(db_path, "Proj", {"jc_id": "JC-1", "partner": "B",
                                          "vereinbarung_vorhanden": 1})
    assert pk1 == pk2
    items = jc_db.list_jc(db_path, "Proj")
    assert len(items) == 1
    assert items[0]["partner"] == "B"
    assert items[0]["vereinbarung_vorhanden"] == 1


def test_review_date_computed(db_path):
    pk = jc_db.save_jc(db_path, "Proj", {
        "jc_id": "JC-R", "review_datum": "2026-03-10", "review_zyklus_monate": 12})
    r = jc_db.get_jc(db_path, pk)
    assert r["naechstes_review"] == "2027-03-10"


def test_invalid_anlaufstelle_raises(db_path):
    with pytest.raises(ValueError):
        jc_db.save_jc(db_path, "Proj", {"jc_id": "X", "anlaufstelle_betroffene": "bad"})


def test_invalid_zusammenfassung_status_raises(db_path):
    with pytest.raises(ValueError):
        jc_db.save_jc(db_path, "Proj", {"jc_id": "X", "zusammenfassung_status": "bad"})


def test_missing_jc_id_raises(db_path):
    with pytest.raises(ValueError):
        jc_db.save_jc(db_path, "Proj", {"partner": "no id"})


def test_idor_scoped_get_and_delete(db_path):
    pk = jc_db.save_jc(db_path, "ProjA", {"jc_id": "JC-A"})
    assert jc_db.get_jc(db_path, pk, "ProjA") is not None
    assert jc_db.get_jc(db_path, pk, "ProjB") is None
    assert jc_db.delete_jc(db_path, pk, "ProjB") is False
    assert jc_db.delete_jc(db_path, pk, "ProjA") is True
    assert jc_db.get_jc(db_path, pk) is None


def test_project_isolation(db_path):
    jc_db.save_jc(db_path, "ProjA", {"jc_id": "JC-1"})
    jc_db.save_jc(db_path, "ProjB", {"jc_id": "JC-1"})
    assert len(jc_db.list_jc(db_path, "ProjA")) == 1
    assert len(jc_db.list_jc(db_path, "ProjB")) == 1


def test_cockpit_summary_empty_is_leer(db_path):
    s = jc_db.cockpit_summary(db_path, "Proj")
    assert s["status"] == "leer"
    assert s["offen"] == 0
    assert s["aufgaben"] == []


def test_cockpit_summary_incomplete_yields_tasks(db_path):
    jc_db.save_jc(db_path, "Proj", {"jc_id": "JC-1", "partner": "Acme"})
    s = jc_db.cockpit_summary(db_path, "Proj")
    assert s["status"] != "leer"
    assert s["offen"] == 1
    # Vereinbarung fehlt, Anlaufstelle offen, Zusammenfassung nicht veröffentlicht.
    assert len(s["aufgaben"]) == 3


def test_cockpit_summary_complete_is_gruen(db_path):
    jc_db.save_jc(db_path, "Proj", {
        "jc_id": "JC-1", "partner": "Acme", "vereinbarung_vorhanden": 1,
        "anlaufstelle_betroffene": "beide", "zusammenfassung_status": "veroeffentlicht"})
    s = jc_db.cockpit_summary(db_path, "Proj")
    assert s["reifegrad_pct"] == 100
    assert s["status"] == "gruen"
    assert s["aufgaben"] == []


def test_cockpit_includes_joint_controller_area(db_path):
    from dsgvo import db as core_db
    from dsgvo.dsms_cockpit import AREA_META, build_cockpit
    core_db.ensure_db(db_path)
    jc_db.save_jc(db_path, "Proj", {"jc_id": "JC-1", "partner": "Acme"})
    cockpit = build_cockpit(db_path, "Proj")
    keys = {a["key"] for a in cockpit["areas"]}
    assert "joint_controller" in keys
    assert "joint_controller" in {m["key"] for m in AREA_META}
