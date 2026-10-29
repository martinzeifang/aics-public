"""DS-P (#1193) — Tests Art.-33-72h-Frist + Aufsichts-Meldeformular.

DB-Level-Tests auf temporärer DSGVO-SQLite. Deterministisch via injizierter Zeit.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dsgvo import deadlines as dl
from dsgvo import db as core_db
from dsgvo import dsb_db
from dsgvo import datenpannen_frist as pf

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_path():
    db_dir = REPO_ROOT / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    p = db_dir / f"_pytest_datenpannen_{uuid.uuid4().hex}.sqlite"
    core_db.ensure_db(p)
    try:
        yield p
    finally:
        for suffix in ("", "-wal", "-shm"):
            f = Path(str(p) + suffix)
            if f.exists():
                f.unlink()


def _mk_panne(db_path, projekt="Proj", **over):
    data = {
        "panne_id": over.pop("panne_id", "DSGVO-P-001"),
        "titel": "Leak",
        "festgestellt_am": "2026-01-01",
        "art": "vertraulichkeit",
        "status": "offen",
    }
    data.update(over)
    return core_db.save_panne(db_path, projekt, data)


# ── Deadline-Engine ─────────────────────────────────────────────────────────

def test_deadline_engine_72h_within():
    base = "2026-01-01T00:00:00+00:00"
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)  # 12 h vergangen
    res = dl.evaluate(base, "dsgvo_art33", now=now)
    assert res["deadline_hours"] == 72
    assert res["overdue"] is False
    assert round(res["hours_left"]) == 60
    assert res["ampel"] == "gruen"


def test_deadline_engine_overdue():
    base = "2026-01-01T00:00:00+00:00"
    now = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)  # 96 h
    res = dl.evaluate(base, "dsgvo_art33", now=now)
    assert res["overdue"] is True
    assert res["ampel"] == "rot"


def test_deadline_engine_gelb_warnzone():
    base = "2026-01-01T00:00:00+00:00"
    now = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)  # 36 h → 36 h left = 50 %
    res = dl.evaluate(base, "dsgvo_art33", now=now)
    assert res["ampel"] == "gelb"


def test_deadline_engine_empty_base():
    res = dl.evaluate("", "dsgvo_art33")
    assert res["due_at"] == ""
    assert res["ampel"] == "grau"
    assert res["hours_left"] is None


def test_deadline_unknown_set_raises():
    with pytest.raises(ValueError):
        dl.evaluate("2026-01-01", "does_not_exist")


# ── Status-aware Frist je Panne ─────────────────────────────────────────────

def test_compute_frist_status_aware_terminal():
    now = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)  # weit überfällig
    offen = pf.compute_frist("2026-01-01", "offen", now=now)
    gemeldet = pf.compute_frist("2026-01-01", "gemeldet", now=now)
    assert offen["overdue"] is True and offen["ampel"] == "rot"
    # gemeldet/abgeschlossen → kein Alarm
    assert gemeldet["overdue"] is False and gemeldet["ampel"] == "grau"


def test_list_pannen_mit_frist_enriched(db_path):
    _mk_panne(db_path, panne_id="P-1", status="offen")
    rows = pf.list_pannen_mit_frist(db_path, "Proj")
    assert len(rows) == 1
    assert "frist" in rows[0]
    assert rows[0]["frist"]["deadline_hours"] == 72


def test_get_panne_idor_scoped(db_path):
    pk = _mk_panne(db_path, projekt="ProjA", panne_id="P-A")
    assert pf.get_panne(db_path, "ProjA", pk) is not None
    # Falsches Projekt → kein Treffer (IDOR-Schutz).
    assert pf.get_panne(db_path, "ProjB", pk) is None


def test_offene_fristen_aggregation(db_path):
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    _mk_panne(db_path, panne_id="P-overdue", status="offen", festgestellt_am="2026-01-01")
    _mk_panne(db_path, panne_id="P-gemeldet", status="gemeldet", festgestellt_am="2026-01-01")
    agg = pf.offene_fristen(db_path, "Proj", now=now)
    assert agg["gesamt"] == 2
    assert agg["offen"] == 1          # nur die offene zählt
    assert agg["overdue"] == 1
    assert agg["ok"] is False


def test_offene_fristen_ok_when_all_terminal(db_path):
    _mk_panne(db_path, panne_id="P-done", status="abgeschlossen")
    agg = pf.offene_fristen(db_path, "Proj")
    assert agg["overdue"] == 0
    assert agg["ok"] is True


# ── Art.-33(3)-Meldeformular ─────────────────────────────────────────────────

def test_meldeformular_docx_with_dsb_prefill(db_path):
    dsb_db.upsert_dsb(db_path, "Proj", name="Max DSB",
                      kontakt_email="dsb@example.com", typ="intern")
    pk = _mk_panne(db_path, panne_id="P-form", datenkategorien="E-Mail, Name",
                   betroffene_anzahl=42, sofortmassnahmen="Passwörter zurückgesetzt")
    data = pf.build_meldeformular_docx(db_path, "Proj", pk)
    assert data[:2] == b"PK"  # DOCX = ZIP
    # Inhalt prüfen: DSB-Kontakt + Pflicht-Abschnitte a-d vorhanden.
    import io
    from docx import Document
    doc = Document(io.BytesIO(data))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "dsb@example.com" in text
    assert "Max DSB" in text
    assert "a) Art der Verletzung" in text
    assert "b) Kontaktstelle" in text
    assert "c) Wahrscheinliche Folgen" in text
    assert "d) Ergriffene" in text
    assert "42" in text


def test_meldeformular_missing_panne_raises(db_path):
    with pytest.raises(ValueError):
        pf.build_meldeformular_docx(db_path, "Proj", 99999)


# ── Cockpit-Integration ─────────────────────────────────────────────────────

def test_cockpit_registers_datenpannen_area(db_path):
    from dsgvo import dsms_cockpit
    assert "datenpannen" in dsms_cockpit._AREA_FUNCS
    keys = [m["key"] for m in dsms_cockpit.AREA_META]
    assert "datenpannen" in keys
    _mk_panne(db_path, panne_id="P-c", status="offen", festgestellt_am="2020-01-01")
    res = dsms_cockpit._area_datenpannen(db_path, "Proj")
    assert res["offen"] == 1
    assert res["faellig"] == 1  # längst überfällig
