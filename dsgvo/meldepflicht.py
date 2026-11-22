"""Die Meldepflicht nach Art. 33/34 rechnen statt ankreuzen (#1891).

DER BEFUND
----------
``dsgvo_datenpannen.meldung_aufsicht_pflicht`` und
``meldung_betroffene_pflicht`` sind ``INTEGER NOT NULL DEFAULT 0`` und kamen
**aus dem Browser** — nachgeprüft: Keine Stelle im Produktionscode leitete sie
ab. ``DatenpannenPanel.vue`` schickte ``aufsichtPflicht ? 1 : 0``,
``dsgvo/db.py`` schrieb ``int(bool(...))``.

Die Verordnung nennt die Bedingung ausdrücklich, und die Grundlage liegt in
derselben Zeile (``risikoeinschaetzung``):

* **Art. 33 Abs. 1** — Meldung an die Aufsichtsbehörde binnen 72 Stunden,
  *„es sei denn, dass die Verletzung … voraussichtlich nicht zu einem Risiko
  für die Rechte und Freiheiten natürlicher Personen führt"*.
* **Art. 34 Abs. 1** — Benachrichtigung der betroffenen Personen bei
  *„hohem Risiko"*.

Ein Häkchen, das eine Rechtspflicht behauptet, während die Grundlage daneben
liegt, ist die Fehlerklasse aus #1814 — nur hier mit Meldefristen daran.

DIE RICHTUNG IST FAIL-**SAFE**, NICHT FAIL-CLOSED
-------------------------------------------------
Bei unklarer Lage wird die Meldepflicht **vorgeschlagen** und nicht
unterdrückt. Eine Anwendung, die eine Meldepflicht wegrechnet, nimmt dem
Verantwortlichen eine Entscheidung, deren Folgen er trägt. Deshalb:

* ``gering`` ist die **einzige** Einschätzung, die die Meldung an die Aufsicht
  entfallen lässt — und auch dann bleibt sie ein Vorschlag.
* Besondere Kategorien nach Art. 9 heben die Einschätzung an, nie ab.
* Eine **abweichende Entscheidung** des Verantwortlichen ist zulässig. Sie
  wird nicht überschrieben, sondern als Widerspruch **ausgewiesen** — mit
  Begründungsbedarf, wie die Risikoakzeptanz in #1608/#1613.

WAS HIER NICHT ANGEFASST WIRD
-----------------------------
Die **72-h-Frist**. Sie läuft über die zentrale Engine
(:mod:`dsgvo.datenpannen_frist`, STAGE_SET ``dsgvo_art33``, #1193) und ist
status-aware. Zwei Rechenwege für dieselbe Frist wären zwei Wahrheiten
(#1726/#1727).
"""
from __future__ import annotations

import re
from typing import Any

from shared import formular_pruefung as fp

#: Einschätzungen, bei denen Art. 33 greift. ``gering`` ist die Ausnahme des
#: Abs. 1 — und sie ist eine **Einschätzung**, kein Rechenergebnis.
AUFSICHT_AB = ("mittel", "hoch")

#: Art. 34 Abs. 1 verlangt „hohes Risiko".
BETROFFENE_AB = ("hoch",)

#: Datenkategorien, die auf besondere Kategorien nach Art. 9 hindeuten. Sie
#: **heben** die Einschätzung an und senken sie nie — und sie entscheiden
#: nicht, sondern begründen einen Hinweis. Eine Wortliste ist keine
#: Rechtsanwendung; sie macht nur sichtbar, was in der Zeile steht.
ART9_WOERTER: tuple[str, ...] = (
    "gesundheit", "patient", "diagnose", "medizin", "biometri", "genetisch",
    "religio", "weltanschau", "gewerkschaft", "politisch", "ethnisch",
    "herkunft", "sexual", "sexuell", "strafrecht", "vorstraf",
)

RECHTSGRUNDLAGE_AUFSICHT = "Art. 33 Abs. 1 DSGVO (Meldung binnen 72 Stunden)"
RECHTSGRUNDLAGE_BETROFFENE = "Art. 34 Abs. 1 DSGVO (Benachrichtigung)"


def _s(wert: Any) -> str:
    return "" if wert is None else str(wert).strip()


def art9_treffer(panne: dict[str, Any]) -> list[str]:
    """Hinweise auf besondere Kategorien in den erfassten Datenkategorien."""
    text = " ".join((_s(panne.get("datenkategorien")),
                     _s(panne.get("beschreibung")))).lower()
    return sorted({w for w in ART9_WOERTER if w in text})


def _stufe(panne: dict[str, Any]) -> tuple[str, list[str]]:
    """Die maßgebliche Einschätzung und was sie angehoben hat.

    Angehoben wird nur von ``gering`` auf ``mittel``: Aus einer Wortliste auf
    „hohes Risiko" zu schließen wäre eine Rechtsanwendung, die diese Anwendung
    nicht leisten kann — und Art. 34 hängt daran.
    """
    stufe = _s(panne.get("risikoeinschaetzung")).lower() or "gering"
    gruende: list[str] = []
    treffer = art9_treffer(panne)
    if treffer and stufe == "gering":
        stufe = "mittel"
        gruende.append(
            "Die erfassten Datenkategorien deuten auf besondere Kategorien "
            f"nach Art. 9 hin ({', '.join(treffer)})")
    return stufe, gruende


def befund(panne: dict[str, Any]) -> dict[str, Any]:
    """Was die Verordnung zu dieser Panne sagt — als **Vorschlag**.

    Liefert je Pflicht ``{pflicht, grund, rechtsgrundlage}`` und dazu die
    Widersprüche zur erfassten Angabe. Geschrieben wird nichts.
    """
    panne = dict(panne or {})
    stufe, gruende = _stufe(panne)
    anzahl = int(panne.get("betroffene_anzahl") or 0)

    aufsicht = stufe in AUFSICHT_AB
    betroffene = stufe in BETROFFENE_AB

    grund_aufsicht = (
        f"Risikoeinschätzung „{stufe}“ — Art. 33 Abs. 1 nimmt nur Fälle aus, "
        "in denen die Verletzung voraussichtlich **nicht** zu einem Risiko "
        "führt." if aufsicht else
        f"Risikoeinschätzung „{stufe}“ — die Ausnahme des Art. 33 Abs. 1 "
        "greift. Das bleibt eine Einschätzung des Verantwortlichen.")
    grund_betroffene = (
        f"Risikoeinschätzung „{stufe}“ — Art. 34 Abs. 1 verlangt die "
        "Benachrichtigung bei hohem Risiko." if betroffene else
        f"Risikoeinschätzung „{stufe}“ — Art. 34 Abs. 1 greift erst bei hohem "
        "Risiko.")
    if gruende:
        grund_aufsicht += " " + "; ".join(gruende) + "."

    erfasst_aufsicht = bool(panne.get("meldung_aufsicht_pflicht"))
    erfasst_betroffene = bool(panne.get("meldung_betroffene_pflicht"))

    widersprueche: list[dict[str, Any]] = []
    if aufsicht and not erfasst_aufsicht:
        widersprueche.append(fp.befund(
            "aufsicht_nicht_vermerkt", feld="meldung_aufsicht_pflicht",
            art="widerspruch", wirkung=fp.WIRKUNG_HINWEIS,
            text="Die Einschätzung spricht für eine Meldung an die "
                 "Aufsichtsbehörde; im Datensatz ist sie nicht vermerkt.",
            hinweis=RECHTSGRUNDLAGE_AUFSICHT + " — " + grund_aufsicht))
    if betroffene and not erfasst_betroffene:
        widersprueche.append(fp.befund(
            "betroffene_nicht_vermerkt", feld="meldung_betroffene_pflicht",
            art="widerspruch", wirkung=fp.WIRKUNG_HINWEIS,
            text="Bei hohem Risiko verlangt Art. 34 Abs. 1 die "
                 "Benachrichtigung der betroffenen Personen; im Datensatz ist "
                 "sie nicht vermerkt.",
            hinweis=RECHTSGRUNDLAGE_BETROFFENE + " — " + grund_betroffene))
    # Die Gegenrichtung ist **kein** Widerspruch: Wer meldet, obwohl er nicht
    # müsste, tut nichts Falsches. Sie hier zu beanstanden hieße, von einer
    # Meldung abzuraten.

    # Eine erfasste Meldepflicht ohne Datum ist die Lücke, die der Prüfer
    # findet — die Frist dazu rechnet `datenpannen_frist` (#1193).
    if erfasst_aufsicht and not _s(panne.get("meldung_aufsicht_datum")):
        widersprueche.append(fp.befund(
            "aufsicht_ohne_datum", feld="meldung_aufsicht_datum",
            art="unbestaetigt", wirkung=fp.WIRKUNG_HINWEIS,
            text="Die Meldung an die Aufsichtsbehörde ist als pflichtig "
                 "vermerkt, ein Meldedatum fehlt.",
            hinweis="Ohne Datum lässt sich die 72-Stunden-Frist des Art. 33 "
                    "Abs. 1 nicht belegen."))
    if erfasst_betroffene and not _s(panne.get("meldung_betroffene_datum")):
        widersprueche.append(fp.befund(
            "betroffene_ohne_datum", feld="meldung_betroffene_datum",
            art="unbestaetigt", wirkung=fp.WIRKUNG_HINWEIS,
            text="Die Benachrichtigung der Betroffenen ist als pflichtig "
                 "vermerkt, ein Datum fehlt.",
            hinweis="Art. 34 Abs. 1 verlangt die Benachrichtigung "
                    "„unverzüglich“."))

    return {
        "stufe": stufe,
        "angehoben": gruende,
        "art9_treffer": art9_treffer(panne),
        "betroffene_anzahl": anzahl,
        "aufsicht": {"pflicht": aufsicht, "erfasst": erfasst_aufsicht,
                     "grund": grund_aufsicht,
                     "rechtsgrundlage": RECHTSGRUNDLAGE_AUFSICHT},
        "betroffene": {"pflicht": betroffene, "erfasst": erfasst_betroffene,
                       "grund": grund_betroffene,
                       "rechtsgrundlage": RECHTSGRUNDLAGE_BETROFFENE},
        "widersprueche": widersprueche,
        # Der Vorschlag für das Formular — **nur** für leere Felder, nie als
        # Ersatz einer getroffenen Entscheidung (#1769/#1773).
        "vorschlag": {"meldung_aufsicht_pflicht": aufsicht,
                      "meldung_betroffene_pflicht": betroffene},
    }


def enrich_panne(panne: dict[str, Any]) -> dict[str, Any]:
    """Reichert einen Datensatz um ``meldepflicht`` an.

    Dieselbe Bauform wie ``datenpannen_frist.enrich_panne`` — damit beide
    Anreicherungen nebeneinander laufen können, ohne sich zu kennen.
    """
    d = dict(panne)
    d["meldepflicht"] = befund(d)
    return d


def offene_widersprueche(pannen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die Widersprüche über alle Pannen — für das DSMS-Cockpit.

    Eine Liste, die bei jeder Panne anschlägt, wird abgeschaltet
    (#1774/#1877): Gemeldet werden deshalb nur **offene** Vorgänge.
    """
    out: list[dict[str, Any]] = []
    for p in pannen or []:
        if _s(p.get("status")) in ("gemeldet", "abgeschlossen"):
            continue
        b = p.get("meldepflicht") or befund(p)
        for w in b.get("widersprueche") or []:
            out.append({**w, "panne_id": p.get("panne_id") or p.get("id"),
                        "titel": _s(p.get("titel"))})
    return out


__all__ = ["AUFSICHT_AB", "BETROFFENE_AB", "ART9_WOERTER",
           "RECHTSGRUNDLAGE_AUFSICHT", "RECHTSGRUNDLAGE_BETROFFENE",
           "art9_treffer", "befund", "enrich_panne", "offene_widersprueche"]
