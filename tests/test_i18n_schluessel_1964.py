"""Ein i18n-Schlüssel ohne Nachricht ist unsichtbar (#1964).

**Der Befund.** In `useSseRun.ts` stand nach der Umschaltung auf Englisch
``method: uebersetze('common.pOST')`` — der Durchlauf hatte das Literal
``'POST'`` für einen Anzeigetext gehalten. Den Schlüssel ``common.pOST`` gab es
in **keinem** Katalog, und `t()` gibt für einen unbekannten Schlüssel den
**Schlüssel** zurück. Also ging jede Automatische KI-Bewertung mit der
HTTP-Methode ``common.pOST`` hinaus.

Der Punkt ist ein erlaubtes Zeichen in einem Methoden-Token, der Browser
schickt sie also klaglos; nginx weist sie ab, **bevor** eine Request-Zeile
entsteht. Im Zugriffslog steht darum nur ``"-" 400``, im Anwendungs-Log nichts
und in `audit.log` nichts — die Anfrage hat Flask nie erreicht. Vier Instanzen,
jede „⚡ Direkt mit KI"-Bewertung, und keine einzige Spur, die auf die Ursache
zeigt.

**Warum es kein Prüfer gefunden hat.** `strictTemplates` ist aus (#1858), also
beanstandet `vue-tsc` einen unbekannten Schlüssel nicht; der Build übersetzt
nur. Für Anzeigetexte ist der Schaden sichtbar (der Knopf zeigt seinen
Schlüssel) — hier war er unsichtbar, weil die Zeichenkette in einem
Protokollfeld landete.

Dieser Wächter prüft zwei Dinge:

1. **Jeder benutzte Schlüssel hat eine Nachricht**, in beiden Sprachen.
2. **Technische Werte werden nicht übersetzt** — eine HTTP-Methode ist kein
   Text für Menschen.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
SRC = WURZEL / "frontend" / "src"
KATALOGE = SRC / "i18n"
SPRACHEN = ("de", "en")

#: Werte, die ein Protokoll vorgibt. Sie dürfen nie durch den Katalog laufen:
#: Ein fehlender Schlüssel macht daraus einen ungültigen Protokollwert, und der
#: scheitert *vor* der Anwendung — also an einer Stelle, die nichts
#: protokolliert, was zur Ursache führt.
PROTOKOLL_WERTE = {
    "POST", "GET", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS",
    "TRUE", "FALSE", "NULL", "BEARER",
}

#: **Nicht das Wort entscheidet, sondern die Schreibweise.** Der i18n-Durchlauf
#: bildet ein Literal auf einen Schlüssel ab, indem er den ersten Buchstaben
#: kleinschreibt: aus ``'POST'`` wird ``pOST``, aus ``'GET'`` ``gET``. Das ist
#: der Fingerabdruck eines **durchgängig großgeschriebenen** Literals, und
#: solche sind in Code technische Konstanten.
#:
#: Die erste Fassung dieses Prüfers verbot die Wörter selbst und schlug
#: deshalb auf ``common.delete`` an — die Beschriftung „Löschen", ein völlig
#: richtiger Eintrag. Ein Prüfer mit Fehlalarmen wird abgeschaltet
#: (#1805/#1834/#1867), und dieser hier soll genau einmal anschlagen: wenn
#: wieder eine Methode in den Katalog wandert.
_GROSSLITERAL = re.compile(r"^[a-z][A-Z]+$")


def _katalog(sprache: str) -> dict:
    """Die Katalogdateien einer Sprache als ``{dateiname: inhalt}``."""
    return {f.stem: json.loads(f.read_text(encoding="utf-8"))
            for f in sorted((KATALOGE / sprache).glob("*.json"))}


def _hat_nachricht(kat: dict, schluessel: str) -> bool:
    """Gibt es zu diesem Schlüssel eine Nachricht?

    **Eine Liste zählt**: vue-i18n bildet Pluralformen als Array ab
    (``license.bannerDemo`` hat drei Zweige — heute / morgen / n Tage). Die
    erste Fassung dieses Prüfers verlangte eine Zeichenkette und meldete
    deshalb einen Fehlalarm auf einen völlig richtigen Eintrag. Ein Prüfer,
    dessen Ausgabe man nicht mehr liest, prüft nichts.
    """
    knoten = kat.get(schluessel.split(".")[0])
    for teil in schluessel.split(".")[1:]:
        if not isinstance(knoten, dict):
            return False
        knoten = knoten.get(teil)
    return isinstance(knoten, (str, list))


def _aliase(quelle: str) -> set[str]:
    """Die Namen, unter denen in dieser Datei übersetzt wird.

    ``t`` und ``$t`` sind die Regel; ``useSseRun.ts`` importiert bewusst als
    ``uebersetze``, weil ``t`` dort schon belegt ist. Nur nach ``t(`` zu suchen
    wäre genau der blinde Fleck, der den Fehler durchgelassen hat — mein
    erstes Prüfskript hatte ihn und meldete deshalb „alles in Ordnung".
    """
    namen = {"t", "$t"}
    for m in re.finditer(r"import\s*\{([^}]*)\}\s*from\s*['\"][^'\"]*i18n[^'\"]*['\"]",
                         quelle):
        for stueck in m.group(1).split(","):
            teile = [s.strip() for s in stueck.split(" as ")]
            if teile and teile[0] == "t":
                namen.add(teile[-1])
    return namen


def _quelldateien() -> list[Path]:
    return [p for p in SRC.rglob("*")
            if p.suffix in (".ts", ".vue") and "/i18n/" not in str(p.as_posix())]


def _ohne_kommentare(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*(?://|\*)\s*.*$", "", text)


def _benutzte_schluessel() -> dict[str, str]:
    """``{schluessel: fundort}`` über den ganzen Frontend-Baum."""
    treffer: dict[str, str] = {}
    for pfad in _quelldateien():
        roh = pfad.read_text(encoding="utf-8")
        quelle = _ohne_kommentare(roh)
        namen = _aliase(roh)
        muster = re.compile(
            r"(?<![\w$.])(" + "|".join(re.escape(n) for n in sorted(namen, key=len, reverse=True))
            + r")\(\s*['\"]([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)['\"]")
        for nr, zeile in enumerate(quelle.splitlines(), 1):
            for _, schluessel in muster.findall(zeile):
                treffer.setdefault(schluessel, f"{pfad.relative_to(WURZEL)}:{nr}")
    return treffer


# ── Die beiden Prüfungen ────────────────────────────────────────────────────

def test_der_prueferkreis_ist_nicht_leer():
    """Ein Prüfer über eine leere Liste ist immer grün (die Lehre aus #1870)."""
    assert len(_quelldateien()) > 200, "zu wenige Quelldateien gefunden"
    assert len(_benutzte_schluessel()) > 2000, (
        "zu wenige Schlüssel gefunden — erkennt das Muster die Aufrufe noch?")


@pytest.mark.parametrize("sprache", SPRACHEN)
def test_jeder_benutzte_schluessel_hat_eine_nachricht(sprache):
    """Sonst steht der Schlüssel selbst in der Oberfläche — oder, schlimmer,
    in einem Protokollfeld."""
    kat = _katalog(sprache)
    fehlt = {k: ort for k, ort in _benutzte_schluessel().items()
             if not _hat_nachricht(kat, k)}
    assert not fehlt, (
        f"{len(fehlt)} Schlüssel ohne Nachricht in `{sprache}` — `t()` gibt "
        "dann den Schlüssel zurück:\n  "
        + "\n  ".join(f"{k} ({ort})" for k, ort in sorted(fehlt.items())))


def test_keine_technischen_werte_im_katalog():
    """Eine HTTP-Methode ist kein Text für Menschen.

    Geprüft wird die **Benutzung**, nicht der Katalog: Ein Eintrag „POST" wäre
    zwar unnötig, aber harmlos — gefährlich ist, ihn in ein Protokollfeld zu
    setzen. Deshalb hier der Blick auf den letzten Teil des Schlüssels, der
    beim Extrahieren aus dem Literal entsteht (``'POST'`` → ``common.pOST``).
    """
    schlecht = {}
    for schluessel, ort in _benutzte_schluessel().items():
        letzter = schluessel.rsplit(".", 1)[-1]
        if _GROSSLITERAL.match(letzter) and letzter.upper() in PROTOKOLL_WERTE:
            schlecht[schluessel] = ort
    assert not schlecht, (
        "Übersetzte technische Werte — sie gehören als Literal in den Code:\n  "
        + "\n  ".join(f"{k} ({ort})" for k, ort in sorted(schlecht.items())))


def test_die_methode_der_sse_anfrage_ist_ein_literal():
    """Der Fall selbst, als Wächter am Fundort.

    Die allgemeine Prüfung oben fängt ihn über den Schlüsselnamen. Diese hier
    fängt ihn auch dann, wenn jemand den Schlüssel `common.methode` nennt — der
    Name verrät dann nichts mehr, der Fundort schon.
    """
    quelle = _ohne_kommentare(
        (SRC / "composables" / "useSseRun.ts").read_text(encoding="utf-8"))
    assert re.search(r"method:\s*['\"]POST['\"]", quelle), (
        "Die HTTP-Methode in `runSse` ist kein Literal mehr. Ein unbekannter "
        "Schlüssel wird hier zur Methode, und die Anfrage scheitert an nginx "
        "— ohne Spur in audit.log (#1964).")
