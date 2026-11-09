"""Berichtstexte in der Sprache des Mandanten (#1954).

WARUM DIE TEXTE BEI IHREM RENDERER BLEIBEN
Jeder Berichts-Renderer führt seinen eigenen ``TEXTE``-Katalog
(``{"de": {...}, "en": {...}}``) — nicht ein zentraler Katalog für alle. Ein
Berichtstext ist Teil des Dokuments, das er erzeugt: Wer den Renderer
ändert, ändert den Text im selben Atemzug und sieht ihn dabei. Ein zentraler
Katalog wäre die Spiegel-Liste aus #1731/#1735, nur mit Prosa — und eine
Überschrift, die nicht mehr zu ihrem Abschnitt passt, fällt dort niemandem
auf.

Geteilt ist deshalb nur die **Mechanik**: Auflösen, Rückfall und die Frage,
welche Sprache für dieses Dokument gilt. 24 Kopien von sechs Zeilen wären
24 Gelegenheiten, den Rückfall unterschiedlich falsch zu machen.

WELCHE SPRACHE GILT
Nicht die des Bedieners. Ein Bericht geht an den Mandanten, und
``firmen.sprache`` sagt, in welcher Sprache er ihn bekommt
(Entscheidung „Nur Inhalte + KI": Die Menüsprache bleibt dem Bediener, die
**Inhalte** folgen dem Mandanten). Ein ausdrücklich übergebener Wert hat
Vorrang — ein Anwender, der einmal eine englische Fassung braucht, soll sie
bekommen, ohne die Stammdaten zu ändern.

FAIL-OPEN, UND ZWAR ABSICHTLICH
Lässt sich der Mandant nicht auflösen, gilt die Standardsprache. Ein nicht
erzeugter Bericht ist der teurere Ausgang als ein Bericht in der falschen
Sprache — er lässt sich noch einmal erzeugen, aber nicht nachholen, wenn der
Prüfer im Raum sitzt. Dasselbe Muster wie ``shared/firmen_link``.
"""
from __future__ import annotations

from typing import Any

#: Die Sprache, in der ein Bericht erscheint, wenn nichts anderes bekannt ist.
STANDARD = "de"


def aufloesen(modul: str, projekt_name: str | None,
              sprache: str | None = None) -> str:
    """Welche Sprache gilt für dieses Dokument?

    ``sprache`` übersteuert; sonst entscheidet der Mandant des Projekts.
    """
    from shared import sprache as _sp

    if sprache:
        return _sp.oder_standard(sprache)
    if not projekt_name:
        return _sp.oder_standard(None)
    return _sp.inhalt_fuer_projekt(modul, projekt_name)


def macher(texte: dict[str, dict[str, str]]):
    """Liefert ein ``t(sprache, schluessel, **werte)`` für diesen Katalog.

    Fehlt eine Übersetzung, gilt der deutsche Text. Das ist kein Versehen,
    sondern die Zusage: Ein neuer Abschnitt erscheint sofort in jedem
    Bericht — auf Deutsch, bis ihn jemand übersetzt. Würde er fehlen, wäre
    eine halbe Übersetzung ein **unvollständiges Dokument**, und das ist in
    einer Nachweisakte schlimmer als ein deutscher Satz darin.

    Ein unbekannter Schlüssel liefert den Schlüssel selbst zurück, nicht die
    leere Zeichenkette (Muster ``shared.meldungen.m``): Eine leere
    Überschrift sieht aus wie Absicht, ein sichtbarer Schlüssel nicht.
    """
    def t(sprache: str, schluessel: str, **werte: Any) -> str:
        katalog = texte.get(sprache) or texte.get(STANDARD, {})
        muster = katalog.get(schluessel)
        if muster is None:
            muster = texte.get(STANDARD, {}).get(schluessel)
        if muster is None:
            return schluessel
        return muster.format(**werte) if werte else muster

    return t
