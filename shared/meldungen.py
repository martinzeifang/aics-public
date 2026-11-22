"""Die Meldungen des Servers in der Sprache des Bearbeiters (#1954).

DER BEFUND
In `server/api/` standen **663 Fundstellen** mit **232 verschiedenen** deutschen
Fehlertexten. Davon waren allein **343** die Form „<Objekt> nicht gefunden" —
226-mal „Projekt nicht gefunden". In einer englischen Oberfläche kam aus dem
Server weiter Deutsch zurück, und zwar an der Stelle, an der der Anwender am
dringendsten versteht, was er lesen muss.

WELCHE SPRACHE GILT
Die des **Bearbeiters**, nicht die des Mandanten. Das ist die Trennung aus
#1954: Berichte, Dokumente und KI-Antworten folgen `firmen.sprache` (sie
gehören dem Mandanten), die Oberfläche folgt der Wahl des Anwenders. Eine
Fehlermeldung ist Oberfläche — sie sagt *dem Bearbeiter*, was er tun soll.

Aufgelöst wird über :func:`shared.sprache.anzeige_sprache`, also über
`Accept-Language`, das der Client seit #1954 mitschickt. **Fail-open**: Ohne
Request-Kontext und bei jedem Fehler gilt Deutsch — also das bisherige
Verhalten.

WARUM JSON UND NICHT EIN DICT IM CODE
Damit ein Wächtertest die Kataloge lesen und die Deckungsgleichheit prüfen kann,
und damit eine Übersetzung ohne Python-Kenntnis möglich ist. Dieselbe
Überlegung wie bei `frontend/src/i18n` (siehe dort den Dateikopf).

WAS HIER **NICHT** HINEINGEHÖRT
Fachliche Texte, die in ein Dokument gedruckt werden. Die folgen dem Mandanten
und stehen in ihrem Fachmodul (`cra/kundenfassung.TEXTE` zum Beispiel). Eine
Meldung ist, was der Server auf einen Request antwortet.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

VERZEICHNIS = Path(__file__).resolve().parent / "meldungen"


def _lade(sprache: str) -> dict[str, str]:
    datei = VERZEICHNIS / f"{sprache}.json"
    try:
        return json.loads(datei.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — eine fehlende Übersetzung ist kein Ausfall
        log.debug("Meldungskatalog %s nicht lesbar", datei, exc_info=True)
        return {}


_KATALOGE: dict[str, dict[str, str]] = {}


def katalog(sprache: str) -> dict[str, str]:
    if sprache not in _KATALOGE:
        _KATALOGE[sprache] = _lade(sprache)
    return _KATALOGE[sprache]


def _sprache() -> str:
    from shared import sprache as _sp

    try:
        return _sp.anzeige_sprache()
    except Exception:  # noqa: BLE001
        log.debug("Anzeigesprache nicht bestimmbar", exc_info=True)
        return "de"


def m(schluessel: str, *, sprache: str | None = None, **werte: Any) -> str:
    """Eine Meldung in der Sprache des Bearbeiters.

    Fehlt der Schlüssel in der gewählten Sprache, gilt die deutsche Fassung;
    fehlt er auch dort, kommt der **Schlüssel** zurück. Das ist Absicht: Eine
    Meldung, die ihren eigenen Schlüssel zeigt, fällt auf — eine leere
    Zeichenkette an derselben Stelle nicht, und sie sieht aus wie „alles in
    Ordnung" (die Lehre aus #1805).
    """
    from shared import sprache as _sp

    code = _sp.oder_standard(sprache) if sprache else _sprache()
    muster = katalog(code).get(schluessel) or katalog("de").get(schluessel)
    if muster is None:
        log.warning("Meldung %r fehlt in allen Katalogen", schluessel)
        return schluessel
    try:
        return muster.format(**werte) if werte else muster
    except (KeyError, IndexError):
        log.warning("Meldung %r: Platzhalter passen nicht zu %r",
                    schluessel, sorted(werte))
        return muster


def nicht_gefunden(objekt: str, *, sprache: str | None = None) -> str:
    """„Projekt nicht gefunden" / „Project not found".

    Die häufigste Meldung der ganzen Anwendung (343 von 663 Fundstellen). Das
    **Objekt** kommt aus dem Katalog (`objekt.projekt`), der Satzbau aus
    `nicht_gefunden` — dann heißt es in beiden Sprachen überall gleich, und eine
    neue Objektart braucht einen Eintrag statt eines neuen Satzes.
    """
    return m("nicht_gefunden", sprache=sprache,
             was=m(f"objekt.{objekt}", sprache=sprache))


def fehlt(objekt: str, *, sprache: str | None = None) -> str:
    """„Projekt fehlt" — die Pflichtangabe, nicht der Datensatz."""
    return m("fehlt", sprache=sprache,
             was=m(f"objekt.{objekt}", sprache=sprache))
