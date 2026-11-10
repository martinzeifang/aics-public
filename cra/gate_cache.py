"""Dieselbe Zeile nicht achtmal laden — für **einen** Gate-Lauf (#2084).

DER BEFUND
----------
``cra.konformitaet_gate.evaluate`` plus die 17 Prüfungen aus
``_RELEASE_CHECKS`` brauchen zusammen **113 Verbindungen**, gezählt über den
Call-Graph. Darin: dasselbe Projekt **achtmal**, derselbe
Konformitätsdatensatz sechsmal, dieselbe Schwachstellenliste sechsmal.

Das ist keine Nachlässigkeit der Prüfungen, sondern ihr Aufbau: Jede ist für
sich lesbar und holt sich, was sie braucht. Genau das soll so bleiben — eine
Prüfung, die auf Daten angewiesen ist, die eine andere vorher geholt hat,
wäre reihenfolgeabhängig (``_check_release_art`` ist die einzige, die das
ausdrücklich ist, und das steht dort als Kommentar).

WAS HIER PASSIERT
-----------------
Ein Merkzettel, der **nur während eines Gate-Laufs** existiert
(``contextvars.ContextVar``). Außerhalb ist er nicht gesetzt, und dann
reichen die Helfer unverändert durch — ``evaluate`` ohne ``lauf()`` verhält
sich wie vor #2084.

WARUM EIN CONTEXTVAR UND KEIN MODUL-DICT
----------------------------------------
Weil es **nicht** über den Lauf hinaus gelten darf. Ein Prozess-Cache wäre die
Fehlerklasse, die dieses Repo durchzieht: Eine Bewertung wird gespeichert, das
Gate läuft erneut und liest den alten Stand — die Ampel zeigt dann die Lage von
vorher, und nichts schlägt fehl (#1805/#1820/#1870). Ein ``ContextVar`` ist
zudem je Thread/Task eigen; mit 24 gunicorn-Threads je Worker teilen sich zwei
gleichzeitige Läufe nichts.

Dieselbe Haltung wie ``shared/nachweis_lauf`` (#2086): wiederverwendet wird
nur, was der Aufrufer ausdrücklich als **einen** Vorgang erklärt.
"""
from __future__ import annotations

import contextlib
import contextvars
from typing import Any, Callable, TypeVar

_merker: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "cra_gate_merker", default=None)

T = TypeVar("T")


@contextlib.contextmanager
def lauf():
    """Ein Gate-Lauf: Innerhalb wird jede Zeile höchstens einmal geholt.

    Verschachtelung ist erlaubt und legt **keinen** zweiten Merkzettel an —
    ``_check_*`` darf ``evaluate`` nicht rufen, aber ein Aufrufer, der schon in
    einem Lauf steht, soll nicht raten müssen.
    """
    if _merker.get() is not None:
        yield
        return
    marke = _merker.set({})
    try:
        yield
    finally:
        _merker.reset(marke)


def merke(schluessel: str, holen: Callable[[], T]) -> T:
    """``holen()`` einmal je Lauf und Schlüssel.

    Ohne laufenden Gate-Lauf wird **immer** geholt. ``None`` wird mitgemerkt:
    „es gibt diese Zeile nicht" ist ein Ergebnis, und es ein zweites Mal zu
    erfragen kostet dieselbe Verbindung.
    """
    zettel = _merker.get()
    if zettel is None:
        return holen()
    if schluessel in zettel:
        return zettel[schluessel]
    wert = holen()
    zettel[schluessel] = wert
    return wert


def im_lauf() -> bool:
    """Für Tests und Wächter: Läuft gerade ein Gate-Lauf?"""
    return _merker.get() is not None


__all__ = ["lauf", "merke", "im_lauf"]
