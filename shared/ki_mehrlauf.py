"""Zwei Läufe, und die Abweichung ist das Signal (#1863).

DER BEFUND
Die automatische Massenbewertung (#1573) läuft je Objekt einen Stream und
speichert sofort. Für 130 Anforderungen heißt das: 130 Entwürfe, und der Mensch
muss 130 lesen. Die Arbeit ist dieselbe wie vorher, nur in anderer Reihenfolge.

WARUM ZWEI UND NICHT DREI
Drei Läufe und „zwei gegen einen“ wäre ein **Mehrheitsentscheid der Maschine** —
genau das, was die Leitplanke aus #1773 ausschließt: Die KI schreibt Entwürfe,
sie entscheidet nicht. Zwei Läufe reichen für das, was hier gebraucht wird:
festzustellen, dass die Antwort **nicht stabil** ist. Was dann richtig ist,
entscheidet ein Mensch — er bekommt nur den Grund, hinzusehen.

Dazu ein praktischer Grund: on-prem ist die Rechenzeit die Grenze, nicht das
Geld. 257 Prüffragen × ~30 s sind schon einfach rund zwei Stunden; verdreifacht
würde der Lauf nicht mehr gestartet.

WAS VERGLICHEN WIRD
Der **Wert**, nicht der Text. Zwei Formulierungen derselben Bewertung sind keine
Abweichung — würde man die Prosa vergleichen, wäre jeder Lauf uneinig und der
Hinweis wertlos (die Regel aus #1774: Wer bei allem anschlägt, wird
abgeschaltet). Welcher Wert das ist, weiß nur der Aufrufer: Score 0–5,
BSI-Antwortmodell, Risikostufe. Deshalb ein Callback und keine Fallunterscheidung
hier.

DER ERSTE LAUF IST MASSGEBLICH
Nicht der „beste“ — welcher besser ist, kann die Anwendung nicht wissen, und eine
Auswahl zu behaupten wäre erfunden. Der zweite Lauf ist ein **Kontrolllauf**: Er
erzeugt keinen Inhalt am Fachobjekt und trägt deshalb auch keinen
Herkunftsvermerk (#1765); vermerkt wird, was gespeichert wird.
"""
from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from shared.ki_engine import OHNE_OBJEKT, KiAuftrag, KiErgebnis, ki_lauf


@dataclass
class Mehrlaufergebnis:
    """Der maßgebliche Entwurf plus das, was die Kontrollläufe dazu sagen."""

    ergebnis: KiErgebnis
    #: Die Kontrollläufe (ohne den ersten).
    kontrollen: list[KiErgebnis] = field(default_factory=list)
    #: ``None`` = es gab nur einen Lauf; das ist **kein** Befund.
    einig: bool | None = None
    #: Die verglichenen Werte in Laufreihenfolge — für die Anzeige („4/5 vs. 2/5“).
    werte: list[str] = field(default_factory=list)

    @property
    def abweichung(self) -> str:
        """„4/5 vs. 2/5“ — leer, wenn einig oder nur ein Lauf."""
        if self.einig is not False:
            return ""
        return " vs. ".join(self.werte)


def kontrolllauf(a: KiAuftrag, *, wert: Callable[[Any], str],
                 erster: KiErgebnis | None = None,
                 n: int = 2) -> Mehrlaufergebnis:
    """Führt den Auftrag mehrfach aus und vergleicht die Werte.

    Args:
      a: der Auftrag. Für jeden Lauf wird eine **eigene Lauf-Kennung** erzeugt,
        sonst wären die Einträge im Revisionspfad nicht auseinanderzuhalten
        (``lauf_id`` ist am Auftrag eine ``default_factory`` — ein
        wiederverwendeter Auftrag behielte seine).
      wert: ``parsed -> str``; liefert den Vergleichswert aus der geparsten
        Antwort. Gibt es keinen (unparsebar), liefert der Aufrufer "".
      erster: ein **schon gelaufenes** Ergebnis, das als maßgeblich gilt. So
        kann der Live-Stream der Lauf 1 sein und hier nur noch kontrolliert
        werden — ohne den Anwender zweimal Text lesen zu lassen.
      n: Gesamtzahl der Läufe einschließlich ``erster``.

    Fehler in den Kontrollläufen sind **kein** Befund über die Fachlichkeit:
    Ein Provider-Fehler im zweiten Lauf macht den ersten nicht falsch. Er
    liefert dann ``einig=None`` — „nicht geprüft“, nicht „uneinig“. Eine
    Abweichung zu behaupten, wo nur die Technik versagt hat, wäre ein
    Fehlalarm, und wer Fehlalarme sammelt, verliert den Prüfer (#1805).
    """
    haupt = erster
    laeufe: list[KiErgebnis] = []
    gebraucht = max(0, int(n) - (1 if erster is not None else 0))

    for i in range(gebraucht):
        # Der Kontrolllauf erzeugt keinen Inhalt am Objekt: keine Herkunft.
        # Eigene Lauf-Kennung je Anfrage.
        auftrag = dataclasses.replace(
            a,
            herkunft=OHNE_OBJEKT if (erster is not None or i > 0) else a.herkunft,
            lauf_id=uuid.uuid4().hex[:12],
            kontext=(a.kontext or a.aufgabe) + f" (Lauf {i + 2 if erster else i + 1})",
        )
        erg = ki_lauf(auftrag)
        if haupt is None:
            haupt = erg
        else:
            laeufe.append(erg)

    if haupt is None:  # pragma: no cover — n<1 ist ein Programmierfehler
        raise ValueError("kontrolllauf braucht mindestens einen Lauf")

    werte = [_wert_sicher(wert, haupt)]
    einig: bool | None = None
    for erg in laeufe:
        if not erg.ok:
            continue  # Technikfehler ist kein fachlicher Befund (s. Docstring)
        w = _wert_sicher(wert, erg)
        werte.append(w)
        if not w or not werte[0]:
            continue  # ohne Wert kein Vergleich
        einig = (einig is not False) and (w == werte[0])

    return Mehrlaufergebnis(ergebnis=haupt, kontrollen=laeufe, einig=einig,
                            werte=werte)


def kontrolle_gewuenscht() -> bool:
    """Hat der Aufrufer im Request einen Kontrolllauf verlangt (``kontrolle``)?

    Die Entscheidung kommt aus der Maske — der Massenlauf setzt sie, die
    Einzelbewertung nicht. Gelesen wird sie **hier**, nicht in den Endpunkten:
    Sechs Bewertungs-Streams, die den Schalter einzeln durchreichen, wären die
    Spiegel-Liste aus #1731/#1735, und beim siebten fehlte er wieder, ohne dass
    etwas fehlschlägt. Dasselbe Muster wie ``_egress_bestaetigt`` in der Engine
    und ``prompt_zusatz.aus_request``.
    """
    try:
        from flask import has_request_context, request
        if not has_request_context():
            return False
        body = request.get_json(silent=True)
        if isinstance(body, dict) and body.get("kontrolle"):
            return True
        return bool(request.args.get("kontrolle"))
    except Exception:  # noqa: BLE001
        return False


def _wert_sicher(wert: Callable[[Any], str], erg: KiErgebnis) -> str:
    if not erg.ok:
        return ""
    try:
        return str(wert(erg.parsed) or "")
    except Exception:  # noqa: BLE001 — ein Parserfehler ist kein Befund
        return ""


__all__ = ["Mehrlaufergebnis", "kontrolllauf", "kontrolle_gewuenscht"]
