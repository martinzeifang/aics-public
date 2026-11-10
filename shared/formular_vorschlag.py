"""Formularfelder aus den Quellen vorschlagen — modulübergreifend (#1893).

WARUM DIESE DATEI EXISTIERT
---------------------------
#1884–#1887 haben den Mechanismus für die CRA-Konformitätserklärung gebaut:
Feldklassen, Vorschläge mit Fundstelle, „nur leere Felder füllen", und die
Grenze gegen die KI. Dasselbe braucht die AI-Act-Erklärung (#1889), das
DSGVO-VVT (#1890) und die Datenpanne (#1891).

Je Modul nachgebaut wären das vier Kopien — und beim fünften fehlt eine, ohne
dass etwas fehlschlägt. Das ist die Fehlerklasse aus #1731/#1735, und sie hat
hier einen besonders teuren Ausgang: Die Regel „die KI darf gerechnete Felder
nicht setzen" existierte dann in vier Fassungen, und in einer fehlt sie.

DIE VIER KLASSEN
----------------
Jedes Feld eines rechtlich vorgeschriebenen Formulars fällt in genau eine:

* :data:`KLASSE_GERECHNET` — die Akte weiß die Antwort (Version, Fristen,
  abgeleitete Angaben).
* :data:`KLASSE_UEBERNOMMEN` — die Angabe steht an anderer Stelle in der Suite
  (Mandant, Projekt, ein anderes Register).
* :data:`KLASSE_AUSWAHL` — das Gesetz nennt eine geschlossene Menge; ein
  Freitextfeld ist dort schon die falsche Bauform.
* :data:`KLASSE_KI` — Prosa, die sonst ein Mensch formuliert.

Die Klasse entscheidet, welcher Knopf neben dem Feld steht — und ob ein
Sprachmodell es anfassen darf.

WAS HIER **NICHT** STEHT
------------------------
Modulwissen. Keine Feldnamen, keine Rechtsbezüge, keine Datenbankzugriffe. Die
Funktionen nehmen alles als Argument; welche Quelle ein Feld hat, sagt der
Adapter des Moduls (``<modul>/doc_vorschlag.py`` bzw.
``<modul>/formular_adapter.py``).
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

KLASSE_GERECHNET = "gerechnet"
KLASSE_UEBERNOMMEN = "uebernommen"
KLASSE_AUSWAHL = "auswahl"
KLASSE_KI = "ki"

KLASSEN: tuple[str, ...] = (KLASSE_GERECHNET, KLASSE_UEBERNOMMEN,
                            KLASSE_AUSWAHL, KLASSE_KI)


def _s(wert: Any) -> str:
    return "" if wert is None else str(wert).strip()


def ist_gefuellt(wert: Any) -> bool:
    """Trägt das Feld eine Angabe?

    Listen gelten als gefüllt, sobald ein Eintrag darin steht; ``False`` und
    ``0`` gelten als **nicht** gefüllt, weil ein Schalter in diesen Formularen
    „nicht entschieden" und „nein" nicht auseinanderhält (die Lehre aus #1805:
    ``INTEGER NOT NULL DEFAULT 0`` ist als Verneinung nicht lesbar).
    """
    if isinstance(wert, (list, tuple, set)):
        return any(_s(w) for w in wert)
    if isinstance(wert, bool):
        return wert
    return bool(_s(wert))


class Sammler:
    """Baut die Vorschlagsliste eines Moduls auf.

    Ein Eintrag entsteht **nur mit Wert und Quelle**: Ein leerer Vorschlag mit
    Quellenangabe wäre ein Angebot, das ins Nichts führt, und eine Quelle ohne
    Wert sagt dem Anwender nichts, was er nicht schon sieht.

    ``klassen`` ist die Zuordnung des Moduls (Feld → Klasse). Ein Feld ohne
    Eintrag gilt als :data:`KLASSE_UEBERNOMMEN` — das ist die mildere Annahme:
    Es bekommt einen Füll-Knopf, aber die KI darf es nicht setzen (dafür muss
    es ausdrücklich in der KI-Liste stehen).
    """

    def __init__(self, klassen: Mapping[str, str] | None = None) -> None:
        self._klassen = dict(klassen or {})
        self._out: dict[str, dict[str, Any]] = {}

    def setze(self, feld: str, wert: Any, quelle: str) -> "Sammler":
        if not ist_gefuellt(wert) or not _s(quelle):
            return self
        self._out[feld] = {
            "wert": list(wert) if isinstance(wert, (list, tuple)) else _s(wert),
            "quelle": _s(quelle),
            "klasse": self._klassen.get(feld, KLASSE_UEBERNOMMEN),
        }
        return self

    def ergebnis(self) -> dict[str, dict[str, Any]]:
        return dict(self._out)


def nur_leere(vorschlaege: Mapping[str, Any],
              werte: Mapping[str, Any]) -> list[str]:
    """Welche Felder ein „alles füllen" anfassen darf.

    **Nur leere.** Ein gefülltes Feld ist die Aussage eines Menschen; es beim
    Öffnen der Maske oder auf Sammelklick stillschweigend zu ersetzen ist
    derselbe Fehler wie der Verzeichnis-Scan in #1769 und die
    Gruppenübernahme ohne ``nur_offene`` in #1773.
    """
    return sorted(f for f in vorschlaege if not ist_gefuellt(werte.get(f)))


def filter_ki(felder: Mapping[str, Any] | None,
              ki_felder: Iterable[str]) -> tuple[dict[str, Any], list[str]]:
    """Was eine KI-Antwort setzen darf — und was verworfen wird.

    **Die wichtigste Funktion dieser Datei.** Sie zieht die Grenze
    serverseitig, nicht im Browser: Eine Grenze, die der Client zieht, ist
    keine. Ein Modell, das eine plausible Version oder einen plausiblen
    Digest einsetzt, erzeugt eine Falschaussage, die wie eine Feststellung
    aussieht (der Befund aus #1885).

    Verworfene Felder werden **benannt** — ein stilles Weglassen sähe aus, als
    hätte das Modell sie nicht geliefert.
    """
    erlaubt = {str(f) for f in ki_felder}
    uebernommen: dict[str, Any] = {}
    verworfen: list[str] = []
    for feld, wert in (felder or {}).items():
        if not ist_gefuellt(wert):
            continue
        if str(feld) in erlaubt:
            uebernommen[str(feld)] = _s(wert)
        else:
            verworfen.append(str(feld))
    return uebernommen, sorted(verworfen)


def verworfen_satz(verworfen: Iterable[str]) -> str:
    """Der Satz, mit dem die Maske das Verworfene nennt."""
    namen = sorted({str(f) for f in verworfen if _s(f)})
    if not namen:
        return ""
    return ("Nicht übernommen, weil diese Angaben aus der Akte stammen und "
            "nicht aus einem Entwurf: " + ", ".join(namen) + ".")


__all__ = ["KLASSE_GERECHNET", "KLASSE_UEBERNOMMEN", "KLASSE_AUSWAHL",
           "KLASSE_KI", "KLASSEN", "Sammler", "ist_gefuellt", "nur_leere",
           "filter_ki", "verworfen_satz"]
