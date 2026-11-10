"""Der Erschließungsstand steht in der Nachweisliste (#1984).

DER BEFUND
„Der Extrahieren-Button tut nichts." Er tat etwas: vier Klicks, vier Mal
HTTP 200, Volltext und Abschnitte wurden geschrieben (7 Abschnitte, 9 405
Zeichen). Gemeldet wurde es nur über ``successMsg`` am **Seitenkopf**, über dem
Reitergitter — die Nachweistabelle steht rund tausend Bildpunkte darunter. Kein
Besetztzustand, keine Veränderung in der Zeile, keine Verfallszeit.

Das ist die **dritte Richtung** derselben Fehlerklasse: #1805 ein Ereignis ohne
Zuhörer, #1830 ein Zuhörer ohne Funktion, hier eine **Wirkung, die niemand
sieht**. Keine der drei schlägt fehl.

Fachlich fehlte dabei die Angabe, die an dieser Stelle zählt: Ohne lesbaren
Text gibt es keine zitierbaren Fundstellen, also keine Erschließung (#1861) und
keinen Nachweis-Block in der KI-Bewertung (#1485). „Welche Nachweise sind
bereit?" war aus der Liste nicht zu beantworten.
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
VIEW = WURZEL / "frontend" / "src" / "views" / "firmen" / "FirmenView.vue"


def test_erschliessungsstand_zaehlt_in_einer_abfrage(tmp_path):
    """Eine Abfrage für die ganze Liste, nicht eine je Zeile (#1703/S6)."""
    from evidence.db import (add_document, erschliessungsstand,
                             replace_chunks, upsert_extracted_text)

    db = tmp_path / "evidence.sqlite"
    quelle = tmp_path / "doku.md"
    quelle.write_text("# Netzdokumentation\n", encoding="utf-8")

    mit = add_document(db, quelle, store_dir=tmp_path / "s", firmen_id="F")
    ohne = add_document(db, quelle, store_dir=tmp_path / "s", firmen_id="F")
    upsert_extracted_text(db, mit.id, "x" * 1234)
    replace_chunks(db, mit.id, [(1, "erster"), (2, "zweiter")])

    stand = erschliessungsstand(db, [mit.id, ohne.id, "gibt-es-nicht"])
    assert stand[mit.id] == {"abschnitte": 2, "zeichen": 1234}
    # Ein Dokument ohne Text ist kein Fehler, sondern ein eigener Zustand — er
    # muss als Null erscheinen und nicht fehlen, sonst steht in der Spalte
    # „undefined".
    assert stand[ohne.id] == {"abschnitte": 0, "zeichen": 0}
    assert stand["gibt-es-nicht"] == {"abschnitte": 0, "zeichen": 0}
    assert erschliessungsstand(db, []) == {}


def test_die_liste_liefert_den_stand_mit():
    """Der Endpunkt muss die Felder führen, sonst zeigt die Spalte nichts."""
    quelle = (WURZEL / "server" / "api" / "firmen.py").read_text(encoding="utf-8")
    liste = quelle.split("def list_evidence", 1)[1].split("\n@firmen_bp", 1)[0]
    for feld in ("'abschnitte':", "'zeichen':"):
        assert feld in liste, (
            f"list_evidence liefert {feld} nicht — ohne das bleibt die Spalte "
            f"„Lesbarer Text\" leer (#1984).")
    assert "erschliessungsstand" in liste, (
        "Der Stand wird nicht in einer Abfrage geholt — je Zeile wären es bei "
        "16 Nachweisen 17 Roundtrips (#1703/S6).")


def test_die_zeile_zeigt_die_wirkung_des_knopfes():
    """Spalte, Besetztzustand und Nachladen — die drei sichtbaren Teile."""
    quelle = VIEW.read_text(encoding="utf-8")
    vorlage = quelle.split("<script setup", 1)[0]

    assert "ev.abschnitte" in vorlage, (
        "Die Nachweiszeile zeigt den Erschließungsstand nicht. Ohne ihn sieht "
        "sie nach dem Extrahieren genauso aus wie davor (#1984).")
    assert "evidenceBusy === ev.id" in vorlage, (
        "Kein Besetztzustand am Knopf — bei einem Lauf von mehreren Sekunden "
        "ist das von einem Hänger nicht zu unterscheiden (#1944).")

    programm = quelle.split("<script setup", 1)[1]
    rumpf = programm.split("const onExtractEvidence", 1)[1].split("\nconst ", 1)[0]
    assert "fetchEvidence" in rumpf, (
        "Nach dem Extrahieren wird die Liste nicht neu geladen — die neue "
        "Spalte zeigt dann weiter den alten Stand.")
    assert "evidenceBusy.value = ''" in rumpf, (
        "Der Besetztzustand wird nicht zurückgesetzt; ein Fehlschlag würde die "
        "Zeile dauerhaft sperren. Dafür ist das `finally` da.")


def test_die_rueckmeldung_haengt_nicht_am_seitenkopf():
    """``successMsg`` war die einzige Rückmeldung — und stand außer Sicht.

    Geprüft wird, dass das Extrahieren den **schließbaren** Kanal benutzt
    (`meldung`, #1781) und nicht mehr den Kopf-Kasten ohne Verfallszeit.
    """
    programm = VIEW.read_text(encoding="utf-8").split("<script setup", 1)[1]
    rumpf = programm.split("const onExtractEvidence", 1)[1].split("\nconst ", 1)[0]
    assert "meldung.value" in rumpf
    assert "successMsg" not in rumpf, (
        "Das Extrahieren meldet wieder über den Kasten am Seitenkopf — er "
        "steht über dem Reitergitter und damit außerhalb des Bereichs, in dem "
        "die Nachweistabelle sichtbar ist (#1984).")


def test_der_fall_ohne_text_wird_benannt():
    """Ein Scan ohne Texterkennung liefert nichts — das ist kein Fehler.

    Aber es muss dastehen: Sonst klickt der Anwender den Knopf wieder, und die
    Erschließung scheitert später an einer Ursache, die er nicht kennt.
    """
    quelle = VIEW.read_text(encoding="utf-8")
    assert re.search(r"keinTextExtrahiert|kein Text", quelle), (
        "Die Spalte unterscheidet „kein Text\" nicht von „noch nicht "
        "versucht\".")
    assert "ausDieserDateiLiessSichKeinTextLesen" in quelle
