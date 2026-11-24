"""Enddatum, Markteintritt und Dauer müssen zueinander passen (#1914).

**Der Befund aus dem Betrieb:** In der Akte des eigenen Produkts stand
Markteintritt 23.10.2026, Dauer fünf Jahre — und als Enddatum 28.04.2031. Der
Wert war aus dem Anlagedatum des Quellverzeichnisses abgeleitet und beim
Eintragen des Markteintritts nicht nachgezogen worden; er lag **sechs Monate zu
früh** und unterschritt damit die fünf Jahre des Art. 13 Abs. 8.

Aufgefallen ist es keinem Prüfpfad, weil ``pruefe_support_period`` die *Anzahl
der Jahre* ansah (fünf, also zulässig) und nie den Zusammenhang der drei
Angaben. Dieselbe Fehlerklasse wie #1805 und #1820.

Diese Zahl geht nach Art. 13 Abs. 19 in Angebot und Vertrag — sie ist die
einzige Angabe des Unterstützungszeitraums, die ein Kunde **vor** dem Kauf
sieht.
"""
from __future__ import annotations

import pytest

from cra.db import EOL_TOLERANZ_TAGE, pruefe_support_period


def _datensatz(**felder):
    basis = {
        "markteintritt_datum": "2026-10-23",
        "support_jahre": 5,
        "eol_datum": "2031-10-23",
        "rationale": "Fünf Jahre ab Inverkehrbringen, Art. 13 Abs. 8.",
    }
    basis.update(felder)
    return basis


def test_der_gemeldete_fall_wird_abgewiesen():
    """Genau die Zahlen, die auf Produktiv standen."""
    with pytest.raises(ValueError) as fehler:
        pruefe_support_period(_datensatz(eol_datum="2031-04-28"))
    text = str(fehler.value)
    assert "2031-04-28" in text and "2026-10-23" in text, (
        "Die Meldung muss beide Anker nennen — sonst weiß der Bearbeiter "
        "nicht, welche der drei Angaben er ansehen soll")
    assert "zu früh" in text
    assert "Art. 13 Abs. 19" in text, (
        "Die Meldung soll sagen, warum die Zahl zählt: Sie geht in Angebot "
        "und Vertrag")


def test_ein_zu_spaetes_enddatum_faellt_auch_auf():
    """Beide Richtungen sind Falschangaben.

    Ein zu spätes Enddatum verspricht mehr, als die Dauer deckt. Welche der
    beiden Richtungen schlimmer ist, entscheidet nicht die Anwendung — eine
    Prüfung, die nur die eine Richtung kennt, lädt zur anderen ein.
    """
    with pytest.raises(ValueError) as fehler:
        pruefe_support_period(_datensatz(eol_datum="2033-10-23"))
    assert "zu spät" in str(fehler.value)


def test_stimmige_angaben_gehen_durch():
    assert pruefe_support_period(_datensatz()) == 5


def test_schalttage_sind_kein_fehler():
    """Ein um Tage abweichendes Enddatum wird nicht beanstandet.

    Die Toleranz stand hier ursprünglich mit einer anderen Begründung:
    ``save_support_period`` rechnete mit ``jahre * 365`` und verlor dabei die
    Schalttage, also hätte eine Gleichheitsprüfung jede von der Anwendung
    selbst erzeugte Zeile beanstandet. **Diese Begründung ist mit #2080
    entfallen** — beide Seiten rechnen jetzt in Kalenderjahren.

    Der Test bleibt, weil die Toleranz einen zweiten, fortbestehenden Grund
    hat: Der Anwender darf ein gerundetes Datum eintragen, und Art. 13 Abs. 19
    verlangt ohnehin nur Monat und Jahr.
    """
    # 2026-10-23 + 5 Kalenderjahre = 2031-10-23; ein Tag daneben bleibt gültig.
    assert pruefe_support_period(_datensatz(eol_datum="2031-10-22")) == 5
    assert pruefe_support_period(_datensatz(eol_datum="2031-10-24")) == 5


def test_die_toleranz_ist_grosszuegig_aber_endlich():
    """Monatsgenau, nicht kalendergenau — Art. 13 Abs. 19 will Monat und Jahr.

    #2080: Der Anker wird mit **derselben** Funktion gerechnet wie im
    Produktionscode (``_plus_jahre``). Vorher stand hier ``timedelta(days=5 *
    365)`` — zwei verschiedene Jahresbegriffe auf den zwei Seiten desselben
    Vergleichs, und die 45-Tage-Toleranz hat den Unterschied verdeckt. Genau so
    prüft ein Test irgendwann die falsche Wahrheit.
    """
    from datetime import date, datetime, timedelta

    from cra.db import _plus_jahre

    anker = _plus_jahre(datetime(2026, 10, 23), 5)
    assert anker == date(2031, 10, 23)      # Kalenderjahre, nicht 1825 Tage
    knapp_drin = (anker + timedelta(days=EOL_TOLERANZ_TAGE)).isoformat()
    knapp_draussen = (anker + timedelta(days=EOL_TOLERANZ_TAGE + 1)).isoformat()
    assert pruefe_support_period(_datensatz(eol_datum=knapp_drin)) == 5
    with pytest.raises(ValueError):
        pruefe_support_period(_datensatz(eol_datum=knapp_draussen))


def test_ohne_beide_anker_wird_nicht_geprueft():
    """Ein Bestandsdatensatz ohne Markteintritt darf nicht unspeicherbar werden.

    Die Lehre aus #1905: Ein Rückbau — und eine neue Prüfung ist einer —
    braucht den Blick auf den Bestand. Hier ist er leicht: Ohne beide Anker
    gibt es nichts zu vergleichen, also wird nicht beanstandet.
    """
    assert pruefe_support_period(_datensatz(markteintritt_datum="")) == 5
    assert pruefe_support_period(_datensatz(eol_datum="")) == 5


def test_unlesbares_datum_ist_nicht_gegenstand_dieser_pruefung():
    """Ein kaputtes Datum ist ein anderer Fehler.

    Hier abzubrechen würde die Meldung auf die falsche Spur setzen — der
    Bearbeiter suchte nach einem Widerspruch, wo eine Eingabe unlesbar ist.
    """
    assert pruefe_support_period(_datensatz(eol_datum="31.10.2031")) == 5


def test_ein_widerspruechlicher_bestand_muss_einmal_berichtigt_werden():
    """Die Kehrseite dieser Prüfung, ausdrücklich benannt.

    Eine neue Prüfung **auf dem Schreibweg** kann Bestandsdaten unspeicherbar
    machen — das ist die Falle aus #1779 (unbekannte Rolle) und #1905
    (``soc_operator``). Hier tritt sie ein: Wer eine widersprüchliche Zeile im
    Bestand hat, kann das Formular erst speichern, nachdem er sie berichtigt
    hat.

    **Das ist hier vertretbar, und zwar aus einem Grund:** Das C-Panel zeigt
    alle drei Angaben — Markteintritt, Dauer, Enddatum — in derselben Maske,
    und die Fehlermeldung nennt alle drei mit Werten. Der Bearbeiter sieht
    also, was nicht zusammenpasst, und kann es an der Stelle richten. Bei
    #1779 war das anders: Dort war der störende Wert (eine Rolle, die es nicht
    mehr gab) in der Maske überhaupt nicht sichtbar, und die Meldung nannte
    ihn nicht — deshalb brauchte es dort eine Bereinigung beim Start.

    Zwei Bestandstests mussten dafür angefasst werden
    (``test_release_gate_1745``): Sie legten absichtlich widersprüchliche
    Zeilen an, um einen abgelaufenen Unterstützungszeitraum zu bauen. Beide
    drücken denselben Sachverhalt jetzt stimmig aus — und sind damit
    realistischer als vorher.
    """
    with pytest.raises(ValueError) as fehler:
        pruefe_support_period({
            "markteintritt_datum": "2015-01-01", "support_jahre": 5,
            "eol_datum": "2026-10-03"})
    text = str(fehler.value)
    for wert in ("2015-01-01", "2026-10-03", "5 Jahre"):
        assert wert in text, (
            f"Die Meldung nennt {wert!r} nicht — ohne alle drei Werte weiß der "
            "Bearbeiter nicht, welche Angabe er ansehen soll, und die Prüfung "
            "wird zur Sackgasse")


def test_die_autoerkennung_erzeugt_stimmige_daten():
    """Der Pfad, der den Fehler ursprünglich gelegt hat, muss selbst durchgehen.

    ``detect_support_period`` rechnet das Enddatum aus demselben Datum, das es
    als Markteintritt einträgt — die Zeile ist in sich stimmig. Der Fehler
    entstand erst, als der Markteintritt von Hand berichtigt wurde, ohne das
    Enddatum nachzuziehen. Wäre die Autoerkennung selbst widersprüchlich,
    wäre diese Prüfung bei jedem Autofill im Weg.
    """
    from datetime import datetime, timedelta
    mt = "2026-04-29"
    eol = (datetime.fromisoformat(mt) + timedelta(days=5 * 365)).date().isoformat()
    assert pruefe_support_period(
        {"markteintritt_datum": mt, "support_jahre": 5, "eol_datum": eol}) == 5
