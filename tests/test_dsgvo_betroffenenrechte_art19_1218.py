"""#1218 (Art. 19) — Empfänger-Benachrichtigung im Betroffenenrechte-Workflow.

Erweitert das bestehende ``dsgvo_betroffenenrechte`` (DS8 #1108): Nachweis der
Mitteilung an Empfänger bei Berichtigung/Löschung/Einschränkung als Pflicht-
Schritt vor Abschluss + Ausgabe im Einzelbericht.
"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest

from dsgvo import betroffenenrechte_db as br
from dsgvo import einzelberichte

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_path():
    p = REPO_ROOT / "data" / "db" / f"_pytest_br19_{uuid.uuid4().hex}.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    yield p
    for suffix in ("", "-wal", "-shm"):
        f = Path(str(p) + suffix)
        if f.exists():
            f.unlink()


def test_new_columns_present(db_path):
    br.ensure_table(db_path)
    con = br._connect(db_path)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(dsgvo_betroffenenrechte)")}
    finally:
        con.close()
    assert {"empfaenger_status", "empfaenger_liste", "empfaenger_datum"} <= cols


def test_migration_adds_columns_to_legacy_table(db_path):
    # Lege eine ALTE Tabelle ohne Art.-19-Spalten an.
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "CREATE TABLE dsgvo_betroffenenrechte ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, projekt_name TEXT NOT NULL, "
            "antrag_id TEXT, typ TEXT, eingang_datum TEXT, frist_datum TEXT, "
            "verlaengert INTEGER DEFAULT 0, identitaet_geprueft INTEGER DEFAULT 0, "
            "status TEXT DEFAULT 'eingegangen', bearbeiter TEXT, ergebnis TEXT, "
            "notizen TEXT, created_at TEXT, updated_at TEXT)")
        con.commit()
    finally:
        con.close()
    # ensure_table migriert.
    br.ensure_table(db_path)
    con = sqlite3.connect(db_path)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(dsgvo_betroffenenrechte)")}
    finally:
        con.close()
    assert "empfaenger_status" in cols


def test_create_with_empfaenger_fields(db_path):
    a = br.create_antrag(db_path, "Proj", typ="loeschung17", eingang_datum="2026-01-10",
                         empfaenger_status="benachrichtigt",
                         empfaenger_liste="Hoster, CRM", empfaenger_datum="2026-01-20")
    assert a["empfaenger_status"] == "benachrichtigt"
    assert a["empfaenger_liste"] == "Hoster, CRM"
    assert a["empfaenger_datum"] == "2026-01-20"


def test_invalid_empfaenger_status_raises(db_path):
    with pytest.raises(ValueError):
        br.create_antrag(db_path, "Proj", typ="loeschung17",
                         eingang_datum="2026-01-10", empfaenger_status="bad")


def test_gate_blocks_abschluss_without_empfaenger_create(db_path):
    # Löschung kann nicht direkt abgeschlossen werden, solange Empfänger offen.
    with pytest.raises(ValueError):
        br.create_antrag(db_path, "Proj", typ="loeschung17",
                         eingang_datum="2026-01-10", status="abgeschlossen")


def test_gate_blocks_abschluss_on_update(db_path):
    a = br.create_antrag(db_path, "Proj", typ="berichtigung16", eingang_datum="2026-01-10")
    with pytest.raises(ValueError):
        br.update_antrag(db_path, a["id"], "Proj", status="abgeschlossen")


def test_gate_allows_abschluss_when_benachrichtigt(db_path):
    a = br.create_antrag(db_path, "Proj", typ="loeschung17", eingang_datum="2026-01-10")
    upd = br.update_antrag(db_path, a["id"], "Proj", status="abgeschlossen",
                           empfaenger_status="benachrichtigt",
                           empfaenger_datum="2026-01-22")
    assert upd["status"] == "abgeschlossen"
    assert upd["empfaenger_status"] == "benachrichtigt"


def test_gate_allows_abschluss_when_entfaellt(db_path):
    a = br.create_antrag(db_path, "Proj", typ="einschraenkung18", eingang_datum="2026-01-10")
    upd = br.update_antrag(db_path, a["id"], "Proj", status="abgeschlossen",
                           empfaenger_status="entfaellt")
    assert upd["status"] == "abgeschlossen"


def test_gate_not_applied_for_non_art19_types(db_path):
    # Auskunft (Art. 15) ist kein Art.-19-Typ ⇒ Abschluss ohne Empfänger ok.
    a = br.create_antrag(db_path, "Proj", typ="auskunft15", eingang_datum="2026-01-10",
                         status="abgeschlossen")
    assert a["status"] == "abgeschlossen"


def test_report_includes_empfaenger_columns(db_path):
    br.create_antrag(db_path, "Proj", typ="loeschung17", eingang_datum="2026-01-10",
                     antrag_id="BR-1", empfaenger_status="benachrichtigt",
                     empfaenger_datum="2026-01-20")
    data = einzelberichte.build_docx(db_path, "Proj", "betroffenenrechte")
    assert isinstance(data, bytes) and len(data) > 0
    from io import BytesIO
    from docx import Document
    doc = Document(BytesIO(data))
    text = "\n".join(
        cell.text for tbl in doc.tables for row in tbl.rows for cell in row.cells)
    assert "Art. 19" in text
    assert "Mitteilung am" in text
    assert "benachrichtigt" in text
