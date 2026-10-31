"""Kein Name, den es nicht gibt (#1896).

**Der Befund.** Im Tab „✅ Konformität" kam ein interner Serverfehler:
`server/api/cra_konformitaet.py` rief `_require_projekt(projekt_name)` auf,
importiert hatte es `require_projekt` — ohne Unterstrich. Die beiden Zeilen
waren nach dem Muster von `server/api/cra/__init__.py` geschrieben, wo es
einen modul-lokalen Helfer dieses Namens gibt; in diesem Modul gibt es ihn
nicht. Zwei Endpunkte gaben damit HTTP 500, seit v8.2.3 live.

**Warum es keiner gemerkt hat.** Python löst einen unbekannten Namen erst
**zur Laufzeit** auf. Kein Importfehler, keine Warnung, grüner Build — die
Datei importiert sauber, der Fehler entsteht, wenn jemand die Zeile erreicht.
Dieselbe Klasse wie #1830 (unbekannter Bezeichner im Template) und #1854
(durchgereichter Name ohne Bindung), nur im Backend. Das Frontend hat seit
#1858 einen Typprüfer; das Backend hatte für diese Klasse **nichts**, denn
`mypy` läuft in der CI bewusst auf einer kleinen, saubergehaltenen Teilmenge
und non-blocking — `server/api/` steckt nicht darin.

**Bewusst eng.** Geprüft werden ausschließlich die drei Befunde, aus denen
zur Laufzeit ein `NameError` wird: `UndefinedName`, `UndefinedLocal`,
`UndefinedExport`. Derselbe Lauf meldet über den ganzen Baum rund 350 weitere
Dinge (ungenutzte Importe, ungenutzte Variablen, f-Strings ohne Platzhalter).
Die mitzunehmen hieße, eine Ausnahmeliste zu führen, und eine Ausnahmeliste
wird zum Teppich — ein Prüfer, dessen Ausgabe man nicht mehr liest, prüft
nichts (die Lehre aus #1805 und #1834).

**Als Test und nicht als CI-Job**, damit er in den schon verbindlichen
`test-shard`-Checks wirkt: Ein neuer Job-Name müsste erst in der
Branch-Protection als Pflicht eingetragen werden und wäre bis dahin folgenlos
(die Lehre aus #1858).

Was der erste Lauf gefunden hat, steht in #1896 — darunter ein zweiter
ungemeldeter HTTP 500 (`server/api/nis2.py`, fehlendes `import json`), zwei
lautlos falsche Lesarten und 21 Tkinter-Fehlerdialoge, die nie erscheinen
konnten.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Zur Laufzeit ein NameError — und nur diese drei.
_UNDEFINIERT = ("UndefinedName", "UndefinedLocal", "UndefinedExport")


def _python_dateien() -> list[Path]:
    """Die versionierten Python-Dateien — nicht der Arbeitsbaum.

    `git ls-files` lässt `data/`, Build-Reste und fremde Bäume (`node_modules`,
    heruntergeladene Archive) außen vor. Ein Prüfer, der fremden Code
    beanstandet, wird abgeschaltet.
    """
    roh = subprocess.run(
        ["git", "ls-files", "-z", "*.py"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    return [REPO / p for p in roh.split("\0") if p]


def _kurz(datei: Path) -> str:
    """Repo-relativ, wenn möglich — die Testdateien liegen in tmp_path."""
    try:
        return str(datei.relative_to(REPO))
    except ValueError:
        return str(datei)


def _befunde(dateien: list[Path]) -> list[str]:
    from pyflakes import checker, messages

    erwartet = tuple(getattr(messages, n) for n in _UNDEFINIERT)
    treffer: list[str] = []
    for datei in dateien:
        quelle = datei.read_text(encoding="utf-8", errors="replace")
        try:
            baum = ast.parse(quelle, filename=str(datei))
        except SyntaxError as e:
            # Eine nicht parsebare Datei ist der härtere Fall: sie fliegt beim
            # Import. Deshalb gemeldet und nicht übersprungen.
            treffer.append(f"{_kurz(datei)}:{e.lineno}: Syntaxfehler — {e.msg}")
            continue
        for m in checker.Checker(baum, filename=str(datei)).messages:
            if isinstance(m, erwartet):
                treffer.append(
                    f"{_kurz(datei)}:{m.lineno}: "
                    f"{m.message % m.message_args}"
                )
    return sorted(treffer)


@pytest.fixture(scope="module")
def dateien() -> list[Path]:
    gefunden = _python_dateien()
    assert len(gefunden) > 300, (
        f"nur {len(gefunden)} Python-Dateien gefunden — läuft der Test außerhalb "
        "des Repositorys? Ein Prüfer über eine leere Liste ist immer grün."
    )
    return gefunden


def test_pyflakes_ist_installiert():
    """Ohne den Prüfer ist dieser Test ein leeres Versprechen.

    Deshalb rot und nicht `skip`: Ein übersprungener Wächter wacht nicht, und
    in der CI (`pip install -r requirements-dev.txt`) ist er da.
    """
    try:
        import pyflakes  # noqa: F401
    except ImportError:  # pragma: no cover
        pytest.fail(
            "pyflakes fehlt. Es steht in requirements-dev.txt — "
            f"`{sys.executable} -m pip install -r requirements-dev.txt`."
        )


def test_kein_name_den_es_nicht_gibt(dateien):
    """Der eigentliche Wächter."""
    treffer = _befunde(dateien)
    assert not treffer, (
        "Namen, die zur Laufzeit nicht existieren — daraus wird ein NameError, "
        "und im Webserver ein HTTP 500 (#1896):\n  " + "\n  ".join(treffer)
    )


def test_der_waechter_wird_wirklich_rot(tmp_path):
    """Der Prüfer muss anschlagen — sonst prüft er nichts.

    Zweimal in diesem Haus ist ein Wächter grün geblieben, weil er die
    Erzählung statt das Programm gelesen hat (#1834, #1867). Hier wird der
    gemeldete Fehler nachgebaut und muss gefunden werden.
    """
    datei = tmp_path / "nachbau.py"
    datei.write_text(
        "from server.api._common import require_projekt\n"
        "\n"
        "def doc_vorschlag(projekt_name):\n"
        "    _p, err = _require_projekt(projekt_name)\n"
        "    return err\n",
        encoding="utf-8",
    )
    treffer = _befunde([datei])
    assert any("_require_projekt" in t for t in treffer), treffer


def test_der_waechter_bleibt_eng(tmp_path):
    """Ein ungenutzter Import ist kein Fund dieses Tests.

    Sonst wäre die Ausnahmeliste länger als der Nutzen, und der Teppich liegt
    schon nach dem ersten Sweep.
    """
    datei = tmp_path / "ungenutzt.py"
    datei.write_text("import json\n\n\ndef f():\n    return 1\n", encoding="utf-8")
    assert _befunde([datei]) == []
