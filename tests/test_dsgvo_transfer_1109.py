"""DS9 (#1109) – DB-Level-Tests für Drittlandtransfer + TIA.

Arbeitet direkt auf der transfer_db-Schicht (kein registrierter Blueprint nötig).
Legt eine temporäre DSGVO-SQLite unter ``data/db/_pytest_*.sqlite`` an (innerhalb
der Repo-Wurzel) und räumt sie nach jedem Test wieder auf.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from dsgvo import transfer_db


@pytest.fixture()
def db_path():
    base = Path("data/db")
    base.mkdir(parents=True, exist_ok=True)
    p = base / f"_pytest_transfer_{uuid.uuid4().hex}.sqlite"
    try:
        transfer_db.ensure_table(p)
        yield p
    finally:
        for suffix in ("", "-wal", "-shm"):
            f = Path(str(p) + suffix)
            if f.exists():
                f.unlink()


def test_ensure_table_idempotent(db_path):
    # Doppelter Aufruf darf nicht fehlschlagen.
    transfer_db.ensure_table(db_path)
    transfer_db.ensure_table(db_path)
    assert transfer_db.list_transfers(db_path, "P1") == []


def test_upsert_and_get(db_path):
    t = transfer_db.upsert_transfer(
        db_path,
        "P1",
        "T-001",
        empfaenger="Cloud Inc.",
        drittland="USA",
        grundlage="scc46",
        garantie_detail="SCC Modul 2",
        tia=dict(rechtslage="FISA 702", zusatzgarantien="AES-256",
                 risikoabwaegung="niedrig", ergebnis="zulässig"),
        vvt_ref="VVT-12",
        avv_ref="AVV-7",
    )
    assert t["transfer_id"] == "T-001"
    assert t["grundlage"] == "scc46"
    assert t["tia_json"]["rechtslage"] == "FISA 702"
    assert t["tia_json"]["ergebnis"] == "zulässig"

    fetched = transfer_db.get_transfer(db_path, "P1", "T-001")
    assert fetched is not None
    assert fetched["empfaenger"] == "Cloud Inc."
    assert isinstance(fetched["tia_json"], dict)


def test_upsert_idempotent_update(db_path):
    transfer_db.upsert_transfer(db_path, "P1", "T-001", empfaenger="A")
    transfer_db.upsert_transfer(db_path, "P1", "T-001", empfaenger="B", drittland="UK")
    rows = transfer_db.list_transfers(db_path, "P1")
    assert len(rows) == 1
    assert rows[0]["empfaenger"] == "B"
    assert rows[0]["drittland"] == "UK"


def test_save_tia_preserves_fields(db_path):
    transfer_db.upsert_transfer(db_path, "P1", "T-002", empfaenger="X", tia_status="offen")
    updated = transfer_db.save_tia(
        db_path,
        "P1",
        "T-002",
        tia=dict(rechtslage="r", zusatzgarantien="z",
                 risikoabwaegung="ra", ergebnis="ok"),
        tia_status="abgeschlossen",
    )
    assert updated is not None
    assert updated["tia_status"] == "abgeschlossen"
    assert updated["tia_json"]["risikoabwaegung"] == "ra"
    # Stammdaten unverändert.
    assert updated["empfaenger"] == "X"


def test_save_tia_unknown_transfer_returns_none(db_path):
    assert transfer_db.save_tia(db_path, "P1", "nope", tia={}) is None


def test_tia_normalization_drops_extra_keys(db_path):
    t = transfer_db.upsert_transfer(
        db_path, "P1", "T-003",
        tia={"rechtslage": "x", "boese_extra": "weg", "ergebnis": "ok"},
    )
    assert "boese_extra" not in t["tia_json"]
    assert set(t["tia_json"].keys()) == {
        "rechtslage", "zusatzgarantien", "risikoabwaegung", "ergebnis"
    }


def test_list_isolated_per_projekt(db_path):
    transfer_db.upsert_transfer(db_path, "P1", "T-1")
    transfer_db.upsert_transfer(db_path, "P2", "T-2")
    assert {r["transfer_id"] for r in transfer_db.list_transfers(db_path, "P1")} == {"T-1"}
    assert {r["transfer_id"] for r in transfer_db.list_transfers(db_path, "P2")} == {"T-2"}


def test_delete(db_path):
    transfer_db.upsert_transfer(db_path, "P1", "T-del")
    assert transfer_db.delete_transfer(db_path, "P1", "T-del") is True
    assert transfer_db.get_transfer(db_path, "P1", "T-del") is None
    assert transfer_db.delete_transfer(db_path, "P1", "T-del") is False
