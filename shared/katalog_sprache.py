"""Rechtskataloge in der Sprache des Mandanten (#1954).

WAS HIER AUFGELÖST WIRD
Die Anforderungskataloge der Module (CRA, NIS2, DSGVO, AI Act) sind Listen
von Einträgen mit ``id``, ``kapitel``, ``ref``, ``titel``, ``beschreibung``.
Übersetzt werden **nur** ``titel``, ``beschreibung`` und ``hinweise``; die
englische Fassung steht additiv als ``titel_en`` usw. im selben Eintrag.

WAS UNBERÜHRT BLEIBT, UND WARUM
* ``id`` und ``kapitel`` sind Bezeichner. Eine übersetzte ID bricht jede
  Verknüpfung — Issue-Links (``object_id``), Bewertungen, Evidence-Mappings,
  das Release-Gate. Dieselbe Klasse wie der Fehlercode im Sprachkatalog.
* ``ref`` ist die **Fundstelle**. Sie wird in den Nachweis gedruckt; eine
  falsche Fundstelle sieht dort aus wie eine Feststellung (#1763/#1792). Sie
  wird deshalb im Katalog selbst gepflegt, nicht hier umgeformt.
* ``gewichtung`` und alles Gerechnete: Eine Übersetzung darf keine Zahl
  verändern.

**Selbst angelegte Anforderungen bleiben, wie der Anwender sie getippt hat.**
Sie tragen kein ``titel_en``, also greift der Rückfall. Das ist die
wichtigste Entscheidung hier: Den eigenen Text eines Mandanten maschinell zu
übersetzen hieße, seine Formulierung durch eine wahrscheinliche zu ersetzen —
in einer Nachweisakte das Gegenteil von hilfreich. Wer seine Anforderung
zweisprachig braucht, legt ``titel_en`` selbst an.

FEHLT DIE ÜBERSETZUNG, GILT DER DEUTSCHE TEXT
Nicht die leere Zeichenkette: Eine Anforderung ohne Titel wäre eine Zeile
ohne Namen, und eine halb übersetzte Liste ist schlechter als eine deutsche.
Dieselbe Zusage wie ``shared/reports/texte.macher``.
"""
from __future__ import annotations

from typing import Any, Iterable

#: Die Felder, die eine englische Fassung haben dürfen. Positivliste: Was
#: nicht darin steht, wird nie ersetzt — ein neues Feld wandert nicht
#: versehentlich in die Übersetzung (die Lehre aus #1871/#1879, wo eine
#: Positivliste nicht mitwuchs, hier in der schützenden Richtung).
#: ``referenz`` ist wie ``ref`` eine **Fundstelle**: Sie darf eine
#: englische Fassung haben (``Annex I Part II``), aber ihre Ziffern
#: müssen dieselben bleiben — das prüft
#: ``tests/test_katalog_sprache_1954.py``.
UEBERSETZBAR: tuple[str, ...] = ("titel", "untertitel", "beschreibung",
                                 "hinweise", "label", "kurzlabel",
                                 "title", "description", "hinweis",
                                 "evidence_hint", "ref", "referenz",
                                 # #1954: Der Dokumenten-Katalog
                                 # (`shared/documents/catalog`) führt
                                 # diese vier zusätzlich. Ohne sie
                                 # fielen 91 seiner 165 englischen
                                 # Felder still durch — eine
                                 # Positivliste, die nicht mitwächst
                                 # (#1871/#1879).
                                 "erklaerung", "kategorie",
                                 "rechtsgrundlage", "rechtsbezug",
                                 "guidance", "evidence", "rubric")

#: Felder, deren Wert keine einfache Zeichenkette ist. ``evidence`` ist eine
#: **Liste** von Stichworten, ``rubric`` ein **Dict**, dessen Schlüssel die
#: Bewertungsstufe bezeichnen (``"0"``/``"3"``/``"5"``) und dessen Werte Text
#: sind. Die Schlüssel bleiben; getauscht werden nur die Werte — ein
#: übersetzter Stufenschlüssel wäre kein Schlüssel mehr.
STRUKTUR: dict[str, str] = {"evidence": "liste", "rubric": "dict_werte"}


def uebersetze(eintrag: dict[str, Any], sprache: str) -> dict[str, Any]:
    """Einen Katalog-Eintrag in der gewünschten Sprache.

    Liefert eine **Kopie**; der Katalog im Modul bleibt unangetastet. Er ist
    ein Modul-Literal und wird von mehreren Anfragen gleichzeitig gelesen —
    ihn an Ort und Stelle zu ändern wäre ein Datenrennen, das sich als
    sprunghaft falsche Sprache zeigt.
    """
    if not sprache or sprache == "de":
        return eintrag
    out = dict(eintrag)
    for feld in UEBERSETZBAR:
        wert = eintrag.get(f"{feld}_{sprache}")
        art = STRUKTUR.get(feld)
        if art == "liste":
            # Gleiche Länge verlangt: Eine kürzere Liste ließe Stichworte
            # verschwinden, eine längere erfände welche.
            if (isinstance(wert, list)
                    and len(wert) == len(eintrag.get(feld) or [])
                    and all(isinstance(x, str) and x.strip() for x in wert)):
                out[feld] = list(wert)
        elif art == "dict_werte":
            # Schlüssel bleiben; nur vorhandene Stufen werden getauscht.
            if isinstance(wert, dict):
                alt_d = eintrag.get(feld) or {}
                neu_d = dict(alt_d)
                for k, v in wert.items():
                    if k in alt_d and isinstance(v, str) and v.strip():
                        neu_d[k] = v
                out[feld] = neu_d
        elif isinstance(wert, str) and wert.strip():
            out[feld] = wert
    return out


def uebersetze_viele(eintraege: Iterable[dict[str, Any]],
                     sprache: str) -> list[dict[str, Any]]:
    """Wie :func:`uebersetze`, für eine Liste."""
    if not sprache or sprache == "de":
        return list(eintraege)
    return [uebersetze(e, sprache) for e in eintraege]


def fehlende(eintraege: Iterable[dict[str, Any]], sprache: str,
             *, nur_standard: bool = True) -> list[str]:
    """Welche Einträge haben für ``sprache`` keinen Titel?

    Für den Wächter und für die Administration: Eine Lücke im Katalog soll
    **benannt** werden, nicht als deutscher Titel in einer englischen Liste
    untergehen. ``nur_standard`` lässt die selbst angelegten Anforderungen
    außen vor — dort ist das Fehlen der Normalfall und kein Befund.
    """
    if not sprache or sprache == "de":
        return []
    out: list[str] = []
    for e in eintraege:
        if nur_standard and e.get("_quelle") in ("custom", "override"):
            continue
        titel = e.get(f"titel_{sprache}") or e.get(f"title_{sprache}")
        if not (isinstance(titel, str) and titel.strip()):
            out.append(str(e.get("id") or "?"))
    return out
