"""Tests für XLSX-Formula-Injection-Härtung (#804).

Unit: shared.xlsx_safety.safe_cell_value neutralisiert führende Formelzeichen.
Roundtrip: ein realer Export (CRA) schreibt einen bösartigen Kommentar
NICHT als Formel, sondern mit führendem Apostroph.
"""

import datetime as _dt

import pytest

from shared.xlsx_safety import safe_cell_value


@pytest.mark.parametrize("raw,expected", [
    ("=1+1", "'=1+1"),
    ("+49 170", "'+49 170"),
    ("-5 Punkte", "'-5 Punkte"),
    ("@SUM(A1)", "'@SUM(A1)"),
    ("=cmd|'/c calc'!A1", "'=cmd|'/c calc'!A1"),
    ("\tTab-Start", "'\tTab-Start"),
])
def test_formula_triggers_are_prefixed(raw, expected):
    assert safe_cell_value(raw) == expected


@pytest.mark.parametrize("value", [
    "Normaler Text",
    "Betrag: 5 EUR",
    "",
    0,
    5,
    3.14,
    True,
    None,
])
def test_safe_values_unchanged(value):
    assert safe_cell_value(value) == value


def test_non_string_types_keep_type():
    # Datetime/Zahlen dürfen NICHT zu Strings werden.
    d = _dt.date(2026, 5, 29)
    assert safe_cell_value(d) is d
    assert isinstance(safe_cell_value(42), int)


def test_already_quoted_is_left_alone():
    # Ein Wert, der schon mit ' beginnt, ist unkritisch.
    assert safe_cell_value("'=harmlos") == "'=harmlos"


def test_cra_export_neutralizes_formula(tmp_path, monkeypatch):
    """End-to-End: ein bösartiger Bewertungskommentar landet escaped in der Zelle."""
    openpyxl = pytest.importorskip("openpyxl")
    from pathlib import Path

    from cra import io_xlsx

    # Bewertungen mit Formel-Injection im Kommentar
    evil = '=HYPERLINK("http://evil")'
    bewertungen = {"AI1-01": {"bewertung": 2, "kommentar": evil,
                              "massnahme": "", "verantwortlich": "", "zieldatum": ""}}

    # safe_generated_file verlangt Workspace-Pfad → unter data/ schreiben
    out_dir = Path("data/db/_test804_cra")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = None
    try:
        out_path = io_xlsx.export_fragebogen(
            out_dir=out_dir, projekt_name="P", unternehmen="U", produkt="X",
            produktklasse="default", berater="B", bestehende_bewertungen=bewertungen,
        )
        wb = openpyxl.load_workbook(str(out_path))
        sheet = wb.active
        found = False
        for row in sheet.iter_rows(values_only=True):
            for cell in row:
                if isinstance(cell, str) and "HYPERLINK" in cell:
                    found = True
                    assert cell.startswith("'="), f"Kommentar nicht neutralisiert: {cell!r}"
        assert found, "Test-Kommentar wurde im Export nicht gefunden"
    finally:
        if out_path:
            Path(out_path).unlink(missing_ok=True)
        try:
            out_dir.rmdir()
        except OSError:
            pass
