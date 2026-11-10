"""Escape schließt die oberste Schicht — an **einer** Stelle (#2045).

DER BEFUND
----------
Von 62 Dialogen schlossen **9** auf Escape — und alle neun waren die, die
``ModalRahmen`` benutzen (#1849). Die übrigen 53 fingen den Tastendruck nicht,
obwohl jeder von ihnen einen Klick auf den Hintergrund schon als „schließen"
versteht. Der Anwender drückt Escape, nichts passiert, und muss den ✕ suchen.

WARUM NICHT 43 EINBAUTEN
------------------------
Das wäre die Spiegel-Liste aus #1731/#1735 in ihrer teuersten Form: eine Regel,
die in 43 Dateien noch einmal stehen muss — und beim 44. Dialog fehlt sie, ohne
dass etwas fehlschlägt. Dazu bräuchte jede Einbaustelle die **Bedingung**,
unter der *ihr* Dialog offen ist; ``AdminSettingsView`` führt sieben Schichten
in einer Datei.

Stattdessen führt ``composables/useEscapeSchicht`` Escape als **Klick auf den
Hintergrund** aus. Damit greift der ``@mousedown.self``-Zuhörer, den der Dialog
ohnehin hat, und die Entscheidung bleibt beim Dialog: Wer auf Klick daneben
nicht schließt (ungespeicherte Eingabe), schließt auch auf Escape nicht. Die
Regel kann so nicht von den Dialogen wegdriften — sie liest ihre Antwort aus
ihnen ab, statt sie zu wiederholen.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests.i18n_text import ohne_kommentare

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "frontend" / "src"
MODUL = SRC / "composables" / "useEscapeSchicht.ts"


def _programm(pfad: Path) -> str:
    return ohne_kommentare(pfad.read_text(encoding="utf-8"))


def test_der_fallback_ist_verdrahtet():
    """Ein Modul, das niemand **aufruft**, ist ein Knopf ohne Wirkung (#1805).

    Geprüft wird der Aufruf, nicht der Import. Die erste Fassung dieses Tests
    suchte nur den Namen — und blieb grün, als ich den Aufruf für die
    Gegenprobe entfernte, weil die Import-Zeile stehen blieb. Das ist #1830
    wörtlich: ein Zuhörer ohne Funktion, und nichts schlägt fehl.
    """
    app = _programm(SRC / "App.vue")
    assert "useEscapeSchicht" in app, "Import fehlt"
    assert re.search(r"escapeSchichtVerdrahten\s*\(\s*\)", app), (
        "escapeSchichtVerdrahten wird importiert, aber nicht aufgerufen")
    # und zwar beim Start, nicht irgendwo
    assert "onMounted" in app


def test_der_zuhoerer_haengt_an_window_nicht_an_document():
    """Die Reihenfolge ist die ganze Sicherheit.

    Der Weg eines Tastendrucks läuft ``… → document → window``. Ein Dialog, der
    selbst zuhört, hängt an ``document`` — hinge der Fallback dort auch, wäre
    nicht entschieden, wer zuerst kommt, und zwei Zuhörer schlössen zwei
    Schichten auf einen Tastendruck.
    """
    programm = _programm(MODUL)
    assert "window.addEventListener('keydown'" in programm
    assert "document.addEventListener" not in programm


def test_ein_bereits_behandeltes_ereignis_wird_uebergangen():
    programm = _programm(MODUL)
    assert "defaultPrevented" in programm
    assert "rahmenOffen.anzahl > 0" in programm


def test_modalrahmen_zaehlt_sich_mit():
    """Solange ein ``ModalRahmen`` offen ist, gehört Escape ihm.

    Er kennt seine Ebene und schließt nur die oberste (#1849); der Fallback
    kann das nicht wissen und hält sich heraus.
    """
    programm = _programm(SRC / "components" / "shared" / "ModalRahmen.vue")
    assert "rahmenOffen.anzahl += 1" in programm
    assert "rahmenOffen.anzahl - 1" in programm


def test_die_eigene_schicht_des_rahmens_ist_ausgenommen():
    """Doppelter Boden: Auch ohne den Zähler darf der Fallback die Schicht des
    Rahmens nicht anfassen. Der Klassenname muss zu der Schicht passen, die
    ``ModalRahmen`` wirklich rendert — eine erfundene Klasse wäre eine
    Ausnahme, die nichts ausnimmt."""
    programm = _programm(MODUL)
    assert "'mr-overlay'" in programm
    rahmen = (SRC / "components" / "shared" / "ModalRahmen.vue").read_text(
        encoding="utf-8")
    assert 'class="mr-overlay"' in rahmen


def test_kein_eigener_schliess_befehl_im_fallback():
    """Der Fallback entscheidet nicht, **ob** geschlossen wird.

    Täte er es (eigene Liste von Schließ-Funktionen), wäre er die zweite
    Wahrheit neben dem Dialog — und ein Dialog mit ungespeicherter Eingabe
    verlöre sie auf Escape, obwohl ein Klick daneben sie behält.
    """
    programm = _programm(MODUL)
    for verboten in ("emit(", "router.", "store.", "close()"):
        assert verboten not in programm, verboten
    assert "dispatchEvent(new MouseEvent" in programm


def test_beide_schreibweisen_werden_bedient():
    """Im Haus kommen ``@mousedown.self`` und ``@click.self`` vor."""
    programm = _programm(MODUL)
    assert "'mousedown'" in programm and "'click'" in programm


def test_kein_dialog_baut_den_fallback_nach():
    """Ein zweiter window-weiter Escape-Zuhörer wäre die Spiegel-Liste.

    Erlaubt bleibt ein **eigener** Zuhörer an ``document`` (so macht es
    ``ModalRahmen``); verboten ist ein zweiter globaler Fallback, der die
    oberste Schicht sucht.
    """
    treffer: list[str] = []
    for pfad in sorted(SRC.rglob("*.vue")) + sorted(SRC.rglob("*.ts")):
        if pfad == MODUL:
            continue
        programm = _programm(pfad)
        if re.search(r"window\.addEventListener\(\s*'keydown'", programm):
            treffer.append(str(pfad.relative_to(SRC)))
    assert not treffer, f"zweiter globaler Escape-Zuhörer: {treffer}"
