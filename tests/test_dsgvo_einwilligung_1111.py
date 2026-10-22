"""DS11 (#1111) — DB-Level-Tests für das Einwilligungs-Management (Art. 7).

Arbeitet auf einer temporären SQLite unter ``data/db/_pytest_*.sqlite`` (innerhalb
des Repo-Roots, da ``_connect`` Pfade gegen den Repo-Anker validiert). Kein
Blueprint-Registrierung nötig.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from dsgvo.einwilligung_db import (
    ensure_table,
    list_einwilligungen,
    get_einwilligung,
    save_einwilligung,
    delete_einwilligung,
    widerruf_einwilligung,
    import_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_path() -> Path:
    db_dir = REPO_ROOT / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    p = db_dir / f"_pytest_einwilligung_{uuid.uuid4().hex}.sqlite"
    yield p
    for suffix in ("", "-wal", "-shm"):
        f = Path(str(p) + suffix)
        if f.exists():
            f.unlink()


def test_ensure_table_idempotent(db_path: Path):
    ensure_table(db_path)
    ensure_table(db_path)  # zweiter Aufruf darf nicht fehlschlagen
    assert list_einwilligungen(db_path, "P1") == []


def test_save_and_get(db_path: Path):
    item = save_einwilligung(
        db_path,
        projekt_name="P1",
        einwilligung_id="EW-001",
        zweck="Newsletter",
        text_version="1",
        einwilligung_text="Ich willige ein…",
        zeitpunkt="2026-06-01T10:00",
        kanal="Web",
        betroffener_quelle="Kunde 4711",
    )
    assert item["status"] == "aktiv"
    assert item["zweck"] == "Newsletter"

    fetched = get_einwilligung(db_path, "P1", "EW-001")
    assert fetched is not None
    assert fetched["einwilligung_id"] == "EW-001"


def test_upsert_updates_and_text_versioning(db_path: Path):
    save_einwilligung(db_path, projekt_name="P1", einwilligung_id="EW-001",
                      text_version="1", zweck="alt")
    save_einwilligung(db_path, projekt_name="P1", einwilligung_id="EW-001",
                      text_version="2", zweck="neu")
    items = list_einwilligungen(db_path, "P1")
    assert len(items) == 1  # Upsert, kein Duplikat
    assert items[0]["text_version"] == "2"
    assert items[0]["zweck"] == "neu"


def test_widerruf_sets_status_and_timestamp(db_path: Path):
    save_einwilligung(db_path, projekt_name="P1", einwilligung_id="EW-001")
    res = widerruf_einwilligung(db_path, "P1", "EW-001")
    assert res is not None
    assert res["status"] == "widerrufen"
    assert res["widerruf_zeitpunkt"]  # automatisch gesetzt


def test_widerruf_explicit_timestamp(db_path: Path):
    save_einwilligung(db_path, projekt_name="P1", einwilligung_id="EW-001")
    res = widerruf_einwilligung(db_path, "P1", "EW-001",
                                widerruf_zeitpunkt="2026-06-05")
    assert res is not None
    assert res["widerruf_zeitpunkt"] == "2026-06-05"


def test_widerruf_missing_returns_none(db_path: Path):
    assert widerruf_einwilligung(db_path, "P1", "GIBTS-NICHT") is None


def test_delete(db_path: Path):
    save_einwilligung(db_path, projekt_name="P1", einwilligung_id="EW-001")
    assert delete_einwilligung(db_path, "P1", "EW-001") is True
    assert delete_einwilligung(db_path, "P1", "EW-001") is False
    assert get_einwilligung(db_path, "P1", "EW-001") is None


def test_invalid_status_falls_back_to_aktiv(db_path: Path):
    item = save_einwilligung(db_path, projekt_name="P1",
                             einwilligung_id="EW-001", status="bogus")
    assert item["status"] == "aktiv"


def test_projekt_isolation(db_path: Path):
    save_einwilligung(db_path, projekt_name="P1", einwilligung_id="EW-001")
    save_einwilligung(db_path, projekt_name="P2", einwilligung_id="EW-001")
    assert len(list_einwilligungen(db_path, "P1")) == 1
    assert len(list_einwilligungen(db_path, "P2")) == 1


def test_csv_import_stub(db_path: Path):
    csv_text = (
        "einwilligung_id,zweck,zeitpunkt,kanal,status\n"
        "EW-100,Newsletter,2026-06-01,Web,aktiv\n"
        "EW-101,Werbung,2026-06-02,Mail,aktiv\n"
        ",ohne_id,2026-06-03,Mail,aktiv\n"  # wird übersprungen
    )
    res = import_csv(db_path, "P1", csv_text)
    assert res["imported"] == 2
    assert res["skipped"] == 1
    assert len(list_einwilligungen(db_path, "P1")) == 2
