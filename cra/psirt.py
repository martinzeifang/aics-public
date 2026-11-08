"""Meldestelle für Schwachstellen — eine Lesart der Kontaktangaben (#1796).

DER BEFUND, DER ZU DIESEM MODUL GEFÜHRT HAT
Der gerechnete Prüfpunkt ``vuln_handling`` verlangte einen PSIRT-Kontakt und
las dafür ``cra_psirt.psirt_contacts``. Dieses Feld hatte in der Oberfläche
keine Eingabestelle: Die C2-Maske führt den **Intake-Kanal**, und genau dort
trägt jeder die Meldeadresse ein. Der Prüfpunkt las also an einer Angabe
vorbei, die direkt daneben stand, und war durch Bedienung nicht erfüllbar —
eine Liste, die sich nicht abhaken lässt, ist als Nachweis genauso wertlos wie
eine, die sich von selbst abhakt.

WARUM DER INTAKE-KANAL MITZÄHLT
Anhang I Teil II Nr. 6 verlangt eine **Kontaktadresse für die Meldung von
Schwachstellen**. Ob die Adresse im Feld „Intake-Kanal" oder in der Liste
„Kontakte" steht, ist eine Eigenheit unserer Maske, kein fachlicher
Unterschied: Beide beantworten dieselbe Frage — wohin melden Dritte eine
Schwachstelle? Dieselbe Entscheidung wie bei Disclosure-Policy und SECURITY.md
im Gate, wo auch eines von beidem genügt.

Die Reihenfolge ist dabei nicht beliebig: Ein ausdrücklich gepflegter Kontakt
steht vor dem Intake-Kanal, weil er die gezieltere Angabe ist.

WARUM DIE NORMALISIERUNG HIER LIEGT UND NICHT BEI DEN AUFRUFERN
``psirt_contacts`` trägt in Bestandsinstallationen **beides**: eine JSON-Liste
(so legt die Spalte es an) und einen einzelnen String (so hat es die
Kundenfassung gesehen und so steht es in deren Test seit #1758). Jeder
Aufrufer, der das selbst auseinandernimmt, ist eine weitere Stelle, an der ein
``str(['a@b'])`` im Kundendokument landet — genau der Defekt aus #1796. Darum
gibt es hier **eine** Lesart, und die Druckfunktionen rufen sie auf.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

#: Trennzeichen in einer von Hand getippten Liste. Semikolon und Zeilenumbruch
#: gehören dazu, weil beides vorkommt, wenn jemand Adressen untereinander
#: schreibt oder aus einer Tabelle kopiert.
_TRENNER = re.compile(r"[,;\n\r]+")


def normalisiere(wert: Any) -> list[str]:
    """Beliebige Altform → Liste getrimmter Adressen, ohne Dubletten.

    Nimmt eine Liste, einen String mit Trennzeichen, ``None`` — und gibt immer
    eine Liste. Dubletten werden ohne Rücksicht auf Groß-/Kleinschreibung
    entfernt (``Security@…`` und ``security@…`` sind dieselbe Stelle), die
    Reihenfolge bleibt erhalten: Sie ist die Entscheidung des Pflegenden.
    """
    if wert is None:
        roh: list[Any] = []
    elif isinstance(wert, (list, tuple, set)):
        roh = list(wert)
    else:
        roh = _TRENNER.split(str(wert))

    ergebnis: list[str] = []
    gesehen: set[str] = set()
    for eintrag in roh:
        text = str(eintrag or "").strip()
        if not text or text.lower() in gesehen:
            continue
        gesehen.add(text.lower())
        ergebnis.append(text)
    return ergebnis


def kontakte(psirt: Mapping[str, Any] | None) -> list[str]:
    """Alle Meldeadressen des Projekts — Kontakte **und** Intake-Kanal.

    Das ist die Zahl, die der Prüfpunkt meint. Ein Projekt, das nur den
    Intake-Kanal gepflegt hat, hat seine Meldestelle benannt; ihm einen
    fehlenden Kontakt vorzuhalten, wäre eine Falschaussage über die eigene
    Akte.
    """
    p = psirt or {}
    werte = normalisiere(p.get("psirt_contacts"))
    for kanal in normalisiere(p.get("intake_kanal")):
        if kanal.lower() not in {w.lower() for w in werte}:
            werte.append(kanal)
    return werte


def als_text(psirt: Mapping[str, Any] | None, *, trenner: str = ", ") -> str:
    """Die Meldeadressen als druckbare Zeile — für Dokumente und Berichte."""
    return trenner.join(kontakte(psirt))
