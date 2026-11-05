"""DS-EUV (#1219) — Tests EU-Vertreter-Benennung (Art. 27 DSGVO)."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from dsgvo import eu_vertreter_db as euv

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_path():
    db_dir = REPO_ROOT / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    p = db_dir / f"_pytest_euv_{uuid.uuid4().hex}.sqlite"
    try:
        yield p
    finally:
        for suffix in ("", "-wal", "-shm"):
            f = Path(str(p) + suffix)
            if f.exists():
                f.unlink()


def test_ensure_table_idempotent(db_path):
    euv.ensure_table(db_path)
    euv.ensure_table(db_path)
    assert euv.get_vertreter(db_path, "Proj") is None


def test_einschlaegig_logic():
    assert euv.is_einschlaegig({"niederlassung_ausserhalb_eu": 1, "angebot_eu_betroffene": 1}) is True
    assert euv.is_einschlaegig({"niederlassung_ausserhalb_eu": 1, "verhaltensbeobachtung": 1}) is True
    # EU-niedergelassen ⇒ nicht einschlägig.
    assert euv.is_einschlaegig({"niederlassung_ausserhalb_eu": 0, "angebot_eu_betroffene": 1}) is False
    # Niederlassung außerhalb, aber kein EU-Bezug ⇒ nicht einschlägig.
    assert euv.is_einschlaegig({"niederlassung_ausserhalb_eu": 1}) is False
    # Ausnahme Art. 27(2) ⇒ nicht einschlägig.
    assert euv.is_einschlaegig({"niederlassung_ausserhalb_eu": 1, "angebot_eu_betroffene": 1,
                                "ausnahme_art27_2": 1}) is False
    assert euv.is_einschlaegig({}) is False


def test_upsert_and_get(db_path):
    rec = euv.upsert_vertreter(db_path, "Proj", {
        "niederlassung_ausserhalb_eu": 1, "angebot_eu_betroffene": 1,
        "vertreter_name": "EU-Rep GmbH", "vertreter_anschrift": "Berlin, DE",
        "mandat_vorhanden": 1, "in_datenschutzhinweis": 1})
    assert rec["einschlaegig"] is True
    assert rec["benennung_vollstaendig"] is True
    got = euv.get_vertreter(db_path, "Proj")
    assert got["vertreter_name"] == "EU-Rep GmbH"


def test_upsert_updates_single_record(db_path):
    euv.upsert_vertreter(db_path, "Proj", {"vertreter_name": "A"})
    euv.upsert_vertreter(db_path, "Proj", {"vertreter_name": "B"})
    rec = euv.get_vertreter(db_path, "Proj")
    assert rec["vertreter_name"] == "B"
    # Genau ein Datensatz pro Projekt.
    con = euv._connect(db_path)
    try:
        n = con.execute("SELECT COUNT(*) FROM dsgvo_eu_vertreter WHERE projekt_name=?",
                        ("Proj",)).fetchone()[0]
    finally:
        con.close()
    assert n == 1


def test_benennung_unvollstaendig_when_no_mandat(db_path):
    rec = euv.upsert_vertreter(db_path, "Proj", {
        "niederlassung_ausserhalb_eu": 1, "angebot_eu_betroffene": 1,
        "vertreter_name": "EU-Rep", "vertreter_anschrift": "Berlin",
        "mandat_vorhanden": 0, "in_datenschutzhinweis": 1})
    assert rec["benennung_vollstaendig"] is False


def test_project_isolation(db_path):
    euv.upsert_vertreter(db_path, "ProjA", {"vertreter_name": "A"})
    assert euv.get_vertreter(db_path, "ProjA") is not None
    assert euv.get_vertreter(db_path, "ProjB") is None


def test_delete(db_path):
    euv.upsert_vertreter(db_path, "Proj", {"vertreter_name": "X"})
    assert euv.delete_vertreter(db_path, "Proj") is True
    assert euv.delete_vertreter(db_path, "Proj") is False
    assert euv.get_vertreter(db_path, "Proj") is None


# ── Cockpit: Pflicht-Check NUR wenn einschlägig (#1219) ──────────────────────

def test_cockpit_leer_when_not_einschlaegig(db_path):
    euv.upsert_vertreter(db_path, "Proj", {"niederlassung_ausserhalb_eu": 0})
    s = euv.cockpit_summary(db_path, "Proj")
    assert s["status"] == "leer"
    assert s["aufgaben"] == []


def test_cockpit_leer_when_no_record(db_path):
    s = euv.cockpit_summary(db_path, "Proj")
    assert s["status"] == "leer"


def test_cockpit_offen_when_einschlaegig_and_incomplete(db_path):
    euv.upsert_vertreter(db_path, "Proj", {
        "niederlassung_ausserhalb_eu": 1, "angebot_eu_betroffene": 1})
    s = euv.cockpit_summary(db_path, "Proj")
    assert s["status"] == "rot"
    assert s["offen"] == 1
    assert len(s["aufgaben"]) >= 1


def test_cockpit_gruen_when_complete(db_path):
    euv.upsert_vertreter(db_path, "Proj", {
        "niederlassung_ausserhalb_eu": 1, "angebot_eu_betroffene": 1,
        "vertreter_name": "EU-Rep", "vertreter_anschrift": "Berlin",
        "mandat_vorhanden": 1, "in_datenschutzhinweis": 1})
    s = euv.cockpit_summary(db_path, "Proj")
    assert s["status"] == "gruen"
    assert s["reifegrad_pct"] == 100


def test_cockpit_includes_eu_vertreter_area(db_path):
    from dsgvo import db as core_db
    from dsgvo.dsms_cockpit import AREA_META, build_cockpit
    core_db.ensure_db(db_path)
    euv.upsert_vertreter(db_path, "Proj", {
        "niederlassung_ausserhalb_eu": 1, "angebot_eu_betroffene": 1})
    cockpit = build_cockpit(db_path, "Proj")
    keys = {a["key"] for a in cockpit["areas"]}
    assert "eu_vertreter" in keys
    assert "eu_vertreter" in {m["key"] for m in AREA_META}


# ── Datenschutzhinweis-Generator: EU-Vertreter-Variable (#1219) ──────────────

def _privacy_text(tmp_path, intake) -> str:
    from dsgvo import privacy
    from docx import Document
    out = privacy.export_privacy_docx(out_dir=tmp_path, projekt_name="Proj", intake=intake)
    doc = Document(str(out))
    return "\n".join(p.text for p in doc.paragraphs)


def test_privacy_generator_renders_eu_vertreter(tmp_path):
    text = _privacy_text(tmp_path, {
        "betreiber": "Acme Inc.", "land": "USA",
        "eu_vertreter_anwendbar": True,
        "eu_vertreter_name": "EU-Rep GmbH",
        "eu_vertreter_anschrift": "Berlin, DE",
        "eu_vertreter_kontakt": "rep@example.eu",
    })
    assert "Vertreter in der Union" in text
    assert "EU-Rep GmbH" in text
    assert "Art. 27" in text


def test_privacy_generator_omits_eu_vertreter_when_not_applicable(tmp_path):
    text = _privacy_text(tmp_path, {"betreiber": "Inland GmbH"})
    assert "Vertreter in der Union" not in text
