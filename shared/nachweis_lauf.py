"""Nachweis-Lookups eines erklärten Massenlaufs wiederverwenden (#2086).

DER BEFUND
----------
``shared/evidence_context.build_context`` nimmt seit #1483/Q1 ein
``cache``-Dict, damit firmenweite Lookups **je Lauf** nur einmal aufgelöst
werden. Übergeben wird es von allen vier ``mass-prompt``-Endpunkten — und von
**keinem** der Einzel-Streams.

Das ist genau der Weg, den die Oberfläche als Vorgabe anbietet: Seit #1573
fährt „🤖 Automatische Massenbewertung" **je Objekt einen eigenen SSE-Stream**
(der synchrone Sammel-Request lief in den Browser-Timeout). Jeder Stream ist
eine eigene Anfrage, also ein eigener Prozessaufruf — ein Cache, der nur
innerhalb einer Anfrage lebt, hilft dort nicht.

Gerechnet für 130 Anforderungen, 6 verwaltete Dokumente à 100 kB: rund 880
Verbindungen und ≈ 86 MB aus der Datenbank, davon ``list_documents`` mit
``SELECT *`` inklusive ``content_html`` 260-mal.

WARUM EIN **ERKLÄRTER** LAUF UND KEIN ZEIT-CACHE
------------------------------------------------
Der naheliegende Weg wäre ein Prozess-Cache je ``(modul, projekt)`` mit
Verfallszeit. Das wäre falsch: Der Nachweis-Block ist die Grundlage, über die
die KI urteilt. Ein frisch hochgeladenes Dokument würde für die Dauer der
Verfallszeit **nicht** erscheinen, und niemand könnte erklären, warum zwei
Läufe hintereinander verschieden bewerten. Dieselbe Haltung wie bei
``prompt_hinweise`` (#1835): nicht heimlich wiederverwenden, sondern nur, was
der Aufrufer ausdrücklich zusammenfasst.

Deshalb trägt jede Anfrage eines Laufs dieselbe **Lauf-Kennung**
(``lauf_id``), und nur Anfragen mit derselben Kennung teilen den Cache. Ohne
Kennung ändert sich **nichts** — ein Einzellauf löst wie bisher frisch auf.
Das ist dieselbe Zusage wie bei ``evidence_section`` und ``prompt_zusatz``:
ohne das neue Feld byte-identisches Verhalten.

DIE GRENZEN
-----------
* **Kurzlebig** (``LEBENSDAUER_S``). Ein Lauf über 257 WiBA-Prüffragen
  dauert Minuten; ein Cache, der Stunden hält, wäre der Zeit-Cache von oben
  durch die Hintertür.
* **Je Prozess.** Mit mehreren gunicorn-Workern landen die Anfragen eines
  Laufs auf verschiedenen Prozessen und treffen dort auf einen kalten Cache.
  Das ist richtig so: Ein geteilter Cache über Prozessgrenzen wäre ein
  zweiter Datenbestand mit eigener Lebensdauer.
* **Die Kennung kommt vom Client** und ist nur ein Cache-Schlüssel — sie
  entscheidet nichts über Rechte. Zur Sicherheit geht der **Mandant** in den
  Schlüssel ein: Zwei Läufe verschiedener Projekte mit derselben Kennung
  dürfen sich keine Nachweise teilen (die Trennung aus #1703/S4 bleibt
  fail-closed).
"""
from __future__ import annotations

import re
import threading
import time
from typing import Any

#: Wie lange ein Lauf-Cache lebt. Lang genug für einen Lauf über 257
#: Prüffragen, kurz genug, dass er kein Zeit-Cache ist.
LEBENSDAUER_S = 900

#: Erlaubte Form einer Lauf-Kennung. Positivliste, weil sie aus dem Request
#: kommt und als Schlüssel dient — was nicht ausdrücklich erlaubt ist, fällt
#: durch (dieselbe Richtung wie ``_backup_pfad`` in #1784).
_KENNUNG = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")

_speicher: dict[str, tuple[float, dict[str, Any]]] = {}
_sperre = threading.Lock()


def _aufraeumen(jetzt: float) -> None:
    for k in [k for k, (t, _) in _speicher.items() if jetzt - t > LEBENSDAUER_S]:
        _speicher.pop(k, None)


def cache_fuer(lauf_id: Any, modul: str, projekt_name: str) -> dict[str, Any] | None:
    """Der gemeinsame Cache dieses Laufs — oder ``None`` ohne Kennung.

    ``None`` heißt „kein Lauf erklärt": Der Aufrufer löst dann frisch auf, wie
    vor #2086.
    """
    kennung = str(lauf_id or "").strip()
    if not kennung or not _KENNUNG.match(kennung):
        return None
    schluessel = f"{modul}\x00{projekt_name}\x00{kennung}"
    jetzt = time.time()
    with _sperre:
        _aufraeumen(jetzt)
        eintrag = _speicher.get(schluessel)
        if eintrag is None:
            cache: dict[str, Any] = {}
            _speicher[schluessel] = (jetzt, cache)
            return cache
        # Zeitstempel **nicht** erneuern: Die Lebensdauer gilt ab dem ersten
        # Zugriff. Sonst hielte ein langer Lauf den Cache unbegrenzt am Leben
        # und wäre wieder der Zeit-Cache, der hier abgelehnt wird.
        return eintrag[1]


def leeren() -> None:
    """Alles verwerfen (Tests, und nach dem Einspielen einer Sicherung)."""
    with _sperre:
        _speicher.clear()


__all__ = ["LEBENSDAUER_S", "cache_fuer", "leeren"]
