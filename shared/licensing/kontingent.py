"""Benutzer-Kontingent: Sockel plus Zuschlag je Mandant (#1819).

Gegenstück zu ``server/services/kontingent.py`` im Lizenzserver. Die Regel
reist als **Formel** im Token (``usr`` = Sockel, ``usrm`` = Zuschlag je aktivem
Mandanten) und wird hier ausgerechnet:

    erlaubt = usr + usrm × aktive Mandanten

**Warum der Client rechnet und nicht der Server.** Die Mandantenzahl ändert
sich hier — in dem Moment, in dem jemand eine Firma anlegt. Käme die fertige
Zahl vom Lizenzserver, hinge sie bis zum nächsten Heartbeat (Vorgabe 6 h) dem
Bestand hinterher: Der Kunde legt den zwölften Mandanten an und bekommt für den
Rest des Tages eine Überschreitung gemeldet, die er gerade bezahlt hat. Morgen
ist sie weg, ohne dass jemand etwas getan hat — ein Fehlerbild, das niemand
reproduzieren kann. Und die Anzeige hinge an der Erreichbarkeit des
Lizenzservers (die Lehre aus #1510).

**Durchgesetzt wird nichts.** Wie beim Mandanten-Kontingent (#1713) ist der
Überhang eine kaufmännische Aussage: Er steht im Fuß der Anwendung und geht an
den Lizenzserver — er sperrt nicht. Wer Benutzer braucht, legt sie an.
"""

from __future__ import annotations


def erlaubte_benutzer(sockel: int, je_mandant: int, aktive_mandanten: int) -> int:
    """Erlaubte Named-User für diesen Bestand. ``0`` heißt unbegrenzt.

    Der Sockel entscheidet über die Unbegrenztheit: Ist er 0, bleibt die Lizenz
    unbegrenzt, egal was je Mandant vereinbart ist. Ein Zuschlag auf
    „unbegrenzt" ergäbe sonst eine endliche Zahl — aus einer Lizenz ohne Grenze
    würde stillschweigend eine mit.
    """
    basis = int(sockel or 0)
    if basis <= 0:
        return 0
    return basis + max(0, int(je_mandant or 0)) * max(0, int(aktive_mandanten or 0))


def ueberhang(user_count: int, sockel: int, je_mandant: int,
              aktive_mandanten: int) -> int:
    """Benutzer über der Grenze. ``0`` = kein Überhang oder unbegrenzt."""
    grenze = erlaubte_benutzer(sockel, je_mandant, aktive_mandanten)
    if grenze <= 0:
        return 0
    return max(0, int(user_count or 0) - grenze)
