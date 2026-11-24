"""DS13 (#1113) — DSMS-Gesamtbericht: Kontext-Builder + Report-Export.

Prüft, dass ``build_dsgvo_context`` die neuen Bereiche (TOM-Katalog,
Betroffenenrechte, Transfers, Löschkonzept, Einwilligungen, DSB) einsammelt und
in ``DSGVO_VARIABLES`` dokumentiert, sowie dass ``export_report_docx`` /
``export_report_pdf`` mit übergebenem ``dsms`` eine Datei erzeugen.

Nutzt eine temporäre dsgvo-SQLite unter ``data/db/_pytest_*.sqlite`` (innerhalb
des Repo-Roots, von ``connect_sqlite`` zugelassen) und räumt hinterher auf.
"""
import uuid
from pathlib import Path

import pytest

from dsgvo import db as ddb
from dsgvo import (
    tom_katalog,
    betroffenenrechte_db,
    transfer_db,
    loeschkonzept_db,
    einwilligung_db,
    dsb_db,
)
from dsgvo.template_context import build_dsgvo_context, DSGVO_VARIABLES
from dsgvo.report_export import export_report_docx, export_report_pdf

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJEKT = "DSMS-Test"


@pytest.fixture()
def db_path():
    p = REPO_ROOT / "data" / "db" / f"_pytest_dsms_{uuid.uuid4().hex}.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    yield p
    for suffix in ("", "-wal", "-shm"):
        f = Path(str(p) + suffix)
        if f.exists():
            f.unlink()


@pytest.fixture()
def out_dir():
    d = REPO_ROOT / "out" / f"_pytest_dsms_{uuid.uuid4().hex}"
    yield d
    if d.exists():
        for f in d.iterdir():
            f.unlink()
        d.rmdir()


def _seed_all(db_path: Path) -> None:
    ddb.ensure_db(db_path)
    ddb.save_projekt(db_path, PROJEKT, unternehmen="Acme GmbH")

    tom_katalog.upsert_massnahme(db_path, PROJEKT, {
        "ziel": "Vertraulichkeit", "massnahme_key": "zugriffskontrolle",
        "titel": "Rollenbasierte Zugriffskontrolle", "status": 3, "soll": 5,
        "verantwortlich": "IT-Sec",
    })
    betroffenenrechte_db.create_antrag(
        db_path, PROJEKT, typ="auskunft15", eingang_datum="2026-02-01",
        antrag_id="BR-001",
    )
    transfer_db.upsert_transfer(
        db_path, PROJEKT, "T-001", empfaenger="AWS Inc.", drittland="USA",
        grundlage="SCC", tia_status="abgeschlossen",
    )
    loeschkonzept_db.save_regel(
        db_path, PROJEKT, "L-001", datenkategorie="Bewerberdaten",
        aufbewahrungsfrist="6 Monate", status="aktiv",
    )
    einwilligung_db.save_einwilligung(
        db_path, projekt_name=PROJEKT, einwilligung_id="E-001",
        zweck="Newsletter", kanal="Web", status="aktiv",
    )
    dsb_db.upsert_dsb(
        db_path, PROJEKT, typ="intern", name="Erika Mustermann",
        kontakt_email="dsb@acme.test", bestelldatum="2026-01-01",
    )


# ── Variablen-Schema (#1092) ────────────────────────────────────────────────

def test_variables_include_dsms_keys():
    keys = {v["key"] for v in DSGVO_VARIABLES}
    for k in ("tom_katalog", "betroffenenrechte", "transfers",
              "loeschregeln", "einwilligungen", "dsb"):
        assert k in keys, f"{k} fehlt in DSGVO_VARIABLES"
    # Meta-Zähler dokumentiert
    assert "meta.anzahl_tom_katalog" in keys
    assert "meta.dsb_vorhanden" in keys
    # jeder Eintrag well-formed
    for v in DSGVO_VARIABLES:
        assert {"key", "typ", "beschreibung", "pflicht"} <= set(v.keys())


# ── Kontext-Builder ─────────────────────────────────────────────────────────

def test_context_empty_project_has_dsms_keys(db_path):
    ddb.ensure_db(db_path)
    ddb.save_projekt(db_path, "Leer")
    ctx = build_dsgvo_context(db_path, "Leer")
    for k in ("tom_katalog", "betroffenenrechte", "transfers",
              "loeschregeln", "einwilligungen"):
        assert ctx[k] == []
    assert ctx["dsb"]["vorhanden"] is False
    assert ctx["meta"]["anzahl_tom_katalog"] == 0
    assert ctx["meta"]["dsb_vorhanden"] is False


def test_context_gathers_all_areas(db_path):
    _seed_all(db_path)
    ctx = build_dsgvo_context(db_path, PROJEKT)

    assert len(ctx["tom_katalog"]) == 1
    assert ctx["tom_katalog"][0]["ziel"] == "Vertraulichkeit"
    assert ctx["tom_katalog"][0]["status"] == 3

    assert len(ctx["betroffenenrechte"]) == 1
    assert ctx["betroffenenrechte"][0]["typ"] == "auskunft15"

    assert len(ctx["transfers"]) == 1
    assert ctx["transfers"][0]["drittland"] == "USA"

    assert len(ctx["loeschregeln"]) == 1
    assert ctx["loeschregeln"][0]["datenkategorie"] == "Bewerberdaten"

    assert len(ctx["einwilligungen"]) == 1
    assert ctx["einwilligungen"][0]["zweck"] == "Newsletter"

    assert ctx["dsb"]["vorhanden"] is True
    assert ctx["dsb"]["name"] == "Erika Mustermann"

    meta = ctx["meta"]
    assert meta["anzahl_tom_katalog"] == 1
    assert meta["anzahl_betroffenenrechte"] == 1
    assert meta["anzahl_transfers"] == 1
    assert meta["anzahl_loeschregeln"] == 1
    assert meta["anzahl_einwilligungen"] == 1
    assert meta["dsb_vorhanden"] is True


def test_context_never_none(db_path):
    _seed_all(db_path)
    ctx = build_dsgvo_context(db_path, PROJEKT)

    def _no_none(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                _no_none(v)
        elif isinstance(obj, list):
            for v in obj:
                _no_none(v)
        else:
            assert obj is not None

    for k in ("tom_katalog", "betroffenenrechte", "transfers",
              "loeschregeln", "einwilligungen", "dsb"):
        _no_none(ctx[k])


# ── Report-Export ───────────────────────────────────────────────────────────

def test_docx_export_with_dsms(db_path, out_dir):
    _seed_all(db_path)
    ctx = build_dsgvo_context(db_path, PROJEKT)
    path = export_report_docx(
        out_dir=out_dir, projekt_name=PROJEKT, unternehmen="Acme GmbH",
        bewertungen_raw={}, incl_details=False, incl_massnahmen=False,
        incl_referenzen=False, dsms=ctx,
    )
    assert path.exists()
    assert path.stat().st_size > 0


def test_docx_export_without_dsms_still_works(db_path, out_dir):
    _seed_all(db_path)
    path = export_report_docx(
        out_dir=out_dir, projekt_name=PROJEKT, bewertungen_raw={},
        incl_details=False, incl_massnahmen=False, incl_referenzen=False,
    )
    assert path.exists()


def test_docx_export_empty_dsms_skips_sections(db_path, out_dir):
    ddb.ensure_db(db_path)
    ddb.save_projekt(db_path, "Leer")
    ctx = build_dsgvo_context(db_path, "Leer")
    path = export_report_docx(
        out_dir=out_dir, projekt_name="Leer", bewertungen_raw={},
        incl_details=False, incl_massnahmen=False, incl_referenzen=False,
        dsms=ctx,
    )
    assert path.exists()


def test_pdf_export_with_dsms(db_path, out_dir):
    _seed_all(db_path)
    ctx = build_dsgvo_context(db_path, PROJEKT)
    path = export_report_pdf(
        out_dir=out_dir, projekt_name=PROJEKT, unternehmen="Acme GmbH",
        bewertungen_raw={}, incl_details=False, incl_massnahmen=False,
        incl_referenzen=False, dsms=ctx,
    )
    assert path.exists()
    assert path.stat().st_size > 0
