"""Breite Tabellen laufen nicht über den Rand (#2062).

DER BEFUND
----------
``globals.css`` setzt ``table { width: 100% }`` und kannte **kein** einziges
``overflow`` — es gab also kein Auffangnetz. Von 23 Tabellen mit mindestens
sieben Spalten hatte **eine** einen Rahmen: die, die mit #1782 einzeln
repariert wurde.

Und die #1782-Diagnose sagt wörtlich, warum ``width: 100%`` nicht genügt: Es
„verkleinert nichts, was nicht umbrechen darf" — Auswahlfelder wachsen mit
ihrer längsten Option, Badges brechen nicht, lange Titel wollen Platz.

Der wahrscheinlichste Fall ist die CRA-Schwachstellentabelle: Sie bringt
genau die Bestandteile mit, an denen #1782 gerissen ist (ein ``<select>``,
eine eingebettete ``IssueVerknuepfung`` in ``darstellung="zeile"``, lange
CVE-Titel) — und sie ist bei der Kuppelwerk-Demo mit 184 SBOM-Komponenten und
10 Pentest-Findings gefüllt.

WAS HIER **NICHT** PASSIERT
---------------------------
Kein ``display: block; overflow-x: auto`` global auf ``table``. Das lässt die
Tabelle scrollen, nimmt ``width: 100%`` aber die Wirkung (die innere anonyme
Tabelle schrumpft auf ihren Inhalt) — und hätte damit das Aussehen **jeder**
Tabelle der Anwendung verändert, ungemessen und ohne Browser.

Stattdessen **eine** Regel (``.tabelle-scroll`` in ``globals.css``) und ein
Rahmen je breiter Tabelle. 22 ``scoped``-Kopien derselben CSS-Zeile wären die
Spiegel-Liste aus #1731/#1735, und bei der 23. Tabelle fehlte sie wieder —
genau das war der Befund.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "frontend" / "src"
GLOBALS = SRC / "styles" / "globals.css"

#: Ab wie vielen Spalten eine Tabelle als breit gilt. Die Zahl ist unsere —
#: gemessen ist nur, dass die eine reparierte Tabelle sieben hatte.
BREIT_AB = 7


def _tabellen(zeilen: list[str]):
    """Alle Tabellen der Datei: (Zeilennummer, Spalten, auf oberster Ebene?).

    Die Tiefe wird mitgezählt. Eine Tabelle **in** einer Tabelle braucht
    keinen eigenen Rahmen — der der äußeren genügt, und ein zweiter
    Scrollbalken darin wäre eine Zumutung. Beim ersten Anlauf fehlte diese
    Zählung: Das Skript nahm das **erste** ``</table>`` und setzte den
    Rahmenschluss der äußeren Tabelle mitten in die innere. ``vue-tsc`` hat
    das nicht beanstandet, ``npm run build`` schon.
    """
    for i, z in enumerate(zeilen):
        if "<table" not in z:
            continue
        tiefe = sum(x.count("<table") - x.count("</table>")
                    for x in zeilen[:i])
        # Der Kopf steht bis ``</thead>`` — nicht in drei Zeilen. Die erste
        # Fassung nahm ein Fenster von drei Zeilen und fand deshalb nur 10 der
        # 23 Tabellen: Der Wächter hätte eine ungeschützte Tabelle übersehen,
        # weil er sie nicht als breit erkannte.
        kopf: list[str] = []
        for z2 in zeilen[i:i + 20]:
            kopf.append(z2)
            if "</thead>" in z2 or "</tr>" in z2:
                break
        spalten = len(re.findall(r"<th\b", "\n".join(kopf)))
        yield i + 1, spalten, tiefe == 0


def test_es_gibt_genau_eine_regel():
    css = GLOBALS.read_text(encoding="utf-8")
    assert ".tabelle-scroll" in css
    assert "overflow-x: auto" in css
    # Nicht global auf ``table`` — siehe Dateikopf.
    tabellen_regel = re.search(r"(?m)^table \{[^}]*\}", css)
    assert tabellen_regel
    assert "overflow" not in tabellen_regel.group(0)
    assert "display: block" not in tabellen_regel.group(0)


def test_jede_breite_tabelle_hat_einen_rahmen():
    ohne: list[str] = []
    gezaehlt = 0
    for pfad in sorted(SRC.rglob("*.vue")):
        quelle = pfad.read_text(encoding="utf-8")
        zeilen = quelle.split("\n")
        for nr, spalten, oberste in _tabellen(zeilen):
            if spalten < BREIT_AB or not oberste:
                continue
            gezaehlt += 1
            vor = "\n".join(zeilen[max(0, nr - 4):nr - 1])
            if "tabelle-scroll" in vor:
                continue
            # Eine eigene Klasse mit ``overflow-x`` zählt auch — so hat
            # #1782 es gelöst, und das soll nicht rückgebaut werden müssen.
            eigen = False
            for klassen in re.findall(r'class="([^"]*)"', vor):
                for name in klassen.split():
                    if re.search(rf"\.{re.escape(name)}\b[^{{]*\{{[^}}]*overflow-x",
                                 quelle):
                        eigen = True
            if not eigen:
                ohne.append(f"{pfad.relative_to(SRC)}:{nr} ({spalten} Spalten)")
    assert gezaehlt >= 20, f"nur {gezaehlt} breite Tabellen gefunden — prüfen"
    assert not ohne, (
        "breite Tabelle ohne Überlaufschutz (``<div class=\"tabelle-scroll\">`` "
        f"davor): {ohne}")


def test_der_rahmen_tr_gt_die_bedingung_der_tabelle():
    """``v-if`` muss an den Rahmen, nicht an die Tabelle.

    Sonst trennt das ``</div>`` die Tabelle von ihrem ``v-else``-Nachbarn, und
    der Build scheitert mit „v-else has no adjacent v-if". Genau das ist beim
    ersten Anlauf in 17 Dateien passiert — und **``vue-tsc`` beanstandet es
    nicht**, nur ``npm run build``.
    """
    fehler: list[str] = []
    for pfad in sorted(SRC.rglob("*.vue")):
        zeilen = pfad.read_text(encoding="utf-8").split("\n")
        for i, z in enumerate(zeilen):
            if "tabelle-scroll" not in z:
                continue
            j = i + 1
            while j < len(zeilen) and "<table" not in zeilen[j]:
                j += 1
            if j < len(zeilen) and re.search(r"\sv-(if|else)", zeilen[j]):
                fehler.append(f"{pfad.relative_to(SRC)}:{j+1}")
    assert not fehler, f"Bedingung an der Tabelle statt am Rahmen: {fehler}"
