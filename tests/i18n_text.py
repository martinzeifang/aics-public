"""Den sichtbaren Text einer ``.vue``-Datei mit aufgelösten i18n-Schlüsseln (#1954).

**Warum es diesen Helfer gibt.** Rund ein Dutzend Wächter prüfen, dass ein
Knopf, ein Hinweis oder eine Fundstelle in der Oberfläche *steht* — und sie
taten das, indem sie die deutsche Zeichenkette in der ``.vue``-Datei suchten.
Mit der Umschaltung auf Englisch (#1954) stehen dort ``$t('…')``-Schlüssel, und
alle wurden rot. Nicht, weil der Knopf fehlt, sondern weil der Text umgezogen
ist.

Die drei naheliegenden Wege sind alle falsch:

* **Den Wächter löschen** — er prüft genau das, was in #1805/#1830 zweimal
  kaputt war: einen Knopf, den es nicht gibt.
* **Auf den Schlüssel prüfen** (``'cra.form.ausstellen' in quelle``) — dann
  beschreibt der Test die Benennung und nicht mehr die Oberfläche. Ein
  umbenannter Schlüssel mit demselben Text wäre rot, ein geleerter Text grün.
* **Je Wächter den Katalog nachlesen** — das wäre ein Dutzend Fassungen
  derselben Auflösung, also die Spiegel-Liste aus #1731/#1735.

Deshalb **eine** Stelle: ``vue_text(pfad)`` liefert die Datei, in der jeder
``$t('…')``-Aufruf durch seine **deutsche** Nachricht ersetzt ist. Die Wächter
suchen danach weiter nach Wörtern, und sie prüfen weiter die Oberfläche.

``sprache="en"`` prüft die englische Fassung — nützlich dort, wo ein Wächter
sicherstellen soll, dass eine Zusage in *beiden* Sprachen steht.

**Ein fehlender Schlüssel bleibt stehen** (als ``$t('…')``), er wird nicht zu
``""``. Ein Wächter, der auf ein Wort prüft, wird dadurch rot — und das ist
richtig: Ein Schlüssel ohne Nachricht zeigt in der Oberfläche seinen eigenen
Namen (``strictTemplates`` ist aus, #1858, also fällt das sonst **nie** auf).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
KATALOG_VERZEICHNIS = WURZEL / "frontend" / "src" / "i18n"

#: Der **Anfang** eines Aufrufs: ``$t('k'`` oder ``t('k'``. Wo er endet,
#: entscheidet ein Klammerzähler und kein Regex — ein Aufruf kann Parameter
#: tragen (``$t('k', { v0: x })``), und an dessen geschweifter Klammer bricht
#: jedes ``[^}]*`` ab. Daran ist die erste Fassung dieses Helfers gescheitert,
#: und zwar **stillschweigend**: Der Schlüssel blieb stehen, der Wächter wurde
#: rot, und es sah nach einem fehlenden Text aus statt nach einem fehlerhaften
#: Prüfer.
_ANFANG = re.compile(r"\$?t\(\s*(['\"])([\w.]+)\1")


@lru_cache(maxsize=4)
def _katalog(sprache: str) -> dict:
    """Alle Katalogdateien einer Sprache als ``{erstes_segment: inhalt}``.

    Der Dateiname ist das erste Segment des Schlüssels: ``cra.form.x`` steht in
    ``de/cra.json`` unter ``["form"]["x"]``.
    """
    verzeichnis = KATALOG_VERZEICHNIS / sprache
    katalog: dict = {}
    for datei in sorted(verzeichnis.glob("*.json")):
        katalog[datei.stem] = json.loads(datei.read_text(encoding="utf-8"))
    return katalog


def nachricht(schluessel: str, sprache: str = "de") -> str | None:
    """Die Nachricht zu einem Schlüssel, oder ``None``, wenn es keine gibt."""
    teile = schluessel.split(".")
    if len(teile) < 2:
        return None
    knoten = _katalog(sprache).get(teile[0])
    for teil in teile[1:]:
        if not isinstance(knoten, dict):
            return None
        knoten = knoten.get(teil)
    return knoten if isinstance(knoten, str) else None


def _ende_des_aufrufs(quelle: str, start: int) -> int:
    """Die Position **nach** der schließenden Klammer des Aufrufs ab ``start``.

    Gezählt werden runde und geschweifte Klammern; Zeichenketten werden
    übersprungen, damit ein ``)`` in einem Parameter-Text nicht zu früh
    schließt. Ohne schließende Klammer: ``-1``.
    """
    tiefe = 0
    i = start
    while i < len(quelle):
        z = quelle[i]
        if z in "'\"`":
            i += 1
            while i < len(quelle) and quelle[i] != z:
                i += 2 if quelle[i] == "\\" else 1
        elif z in "({":
            tiefe += 1
        elif z in ")}":
            tiefe -= 1
            if tiefe == 0:
                return i + 1
        i += 1
    return -1


def vue_text(pfad: Path | str, sprache: str = "de") -> str:
    """Die Datei mit aufgelösten ``$t('…')``-Aufrufen.

    Ersetzt wird der **ganze** Aufruf, bei ``{{ … }}`` samt den Klammern: Der
    Text soll dort stehen, wo er angezeigt wird, denn Wächter zählen
    ``<button …>Text</button>``.

    Platzhalter bleiben als ``{v0}`` im Text stehen. Das ist ehrlicher als ein
    erfundener Wert und genügt jedem Wächter, der auf Wörter prüft.
    """
    quelle = Path(pfad).read_text(encoding="utf-8")
    teile: list[str] = []
    pos = 0
    for m in _ANFANG.finditer(quelle):
        if m.start() < pos:
            continue  # liegt in einem schon ersetzten Aufruf
        ende = _ende_des_aufrufs(quelle, quelle.index("(", m.start()))
        if ende < 0:
            continue
        text = nachricht(m.group(2), sprache)
        if text is None:
            continue  # unbekannter Schlüssel bleibt stehen — siehe Dateikopf
        anfang, schluss = m.start(), ende
        # ``{{ `` davor und `` }}`` danach mitnehmen, wenn es eine
        # Mustache-Einbettung ist — sonst bliebe ``{{ Text }}`` im Markup.
        vor = quelle.rfind("{{", 0, anfang)
        if vor != -1 and quelle[vor + 2:anfang].strip() == "" and quelle[schluss:].lstrip().startswith("}}"):
            anfang = vor
            schluss = quelle.index("}}", schluss) + 2
        teile.append(quelle[pos:anfang])
        teile.append(text)
        pos = schluss
    teile.append(quelle[pos:])
    return "".join(teile)


def ohne_kommentare(text: str) -> str:
    """HTML- und JS-Kommentare heraus — das Programm prüfen, nicht die Erzählung.

    Die Lehre aus #1834/#1867/#1878/#1903, dort viermal zugeschlagen: Ein
    Wächter wird rot, weil ein Kommentar den alten Zustand *zitiert*.
    """
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)

def python_programm(pfad: Path | str) -> str:
    """Python-Quelltext **ohne Kommentare und ohne Docstrings**.

    ``ohne_kommentare`` kennt HTML und JS, nicht Pythons ``#``. In dieser
    Sitzung hat derselbe Fehler **achtmal** zugeschlagen: Ein Wächter wird rot
    (oder, schlimmer, grün), weil ein Kommentar den alten Zustand *zitiert* —
    oft genau der Kommentar, der die Reparatur erklärt. Siehe #1834, #1867,
    #1878, #1903, #1974, #2069, #2026, #2058.

    ``ast.unparse`` entfernt Kommentare von sich aus; Docstrings sind
    Ausdrücke und bleiben stehen, deshalb werden sie eigens entfernt.

    **Für neue Wächter über Python-Quellen gilt: diese Funktion, nicht
    ``read_text``.**
    """
    import ast

    baum = ast.parse(Path(pfad).read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.ClassDef, ast.FunctionDef,
                               ast.AsyncFunctionDef)):
            if (knoten.body and isinstance(knoten.body[0], ast.Expr)
                    and isinstance(knoten.body[0].value, ast.Constant)
                    and isinstance(knoten.body[0].value.value, str)):
                knoten.body = knoten.body[1:] or [ast.Pass()]
    return ast.unparse(baum)
