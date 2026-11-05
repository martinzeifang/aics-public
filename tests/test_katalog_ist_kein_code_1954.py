"""Ein Katalogwert ist Anzeige, niemals Daten (#1954).

DER BEFUND, DER DAS NÖTIG MACHT
Beim Verlegen der Oberflächentexte in den Sprachkatalog sind vier **technische**
Werte mitgewandert, weil sie in der Quelle aussahen wie Beschriftungen::

    method: uebersetze('gutachten.gerichtsgutachtenView.dELETE')   # 'DELETE'
    method: t('common.pOST')                                       # 'POST'
    kapitel: uebersetze('cra.cRAView.iMPL')                        # 'IMPL'
    c.id.replace($t('cra.cRAView.oWASPPC'), '')                    # 'OWASP-PC-'

Wer `dELETE` als „Delete" übersetzt, bricht das Löschen eines
Verfahrensereignisses. Wer `oWASPPC` übersetzt, bricht die Anzeige der
Control-Kennungen. **Nichts davon schlägt fehl:** Der Build bleibt grün, der
Typprüfer auch — `t()` liefert eine Zeichenkette, und eine Zeichenkette passt
überall. Gefunden hat es ein Mensch beim Lesen, nicht ein Prüfer.

Dieselbe Fehlerklasse wie #1805/#1820/#1870: Es wird das Falsche gelesen, und
es sieht aus wie eine Aussage.

WAS HIER GEPRÜFT WIRD
Die Stellen, an denen eine Zeichenkette **Daten** ist und nicht Anzeige:
HTTP-Methode, Vergleich, Speicherschlüssel, Ereignisname, Argument einer
Zeichenketten-Operation, Routen- und Feldname. Steht dort ein `t(…)`, ist das
ein Defekt — unabhängig davon, wie der Wert heute lautet.
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SRC = WURZEL / "frontend" / "src"

#: Stellen, an denen eine Zeichenkette **Daten** ist. Je Muster ein Grund —
#: ohne Begründung wäre die Liste nicht nachprüfbar.
DATENSTELLEN: dict[str, str] = {
    r"\bmethod\s*:\s*\$?t\(":
        "HTTP-Methode: übersetzt wird aus DELETE ein ungültiges Verb, und die "
        "Anfrage läuft ins Leere.",
    r"[=!]==?\s*\$?t\(":
        "Vergleich: die eine Seite käme aus dem Katalog, die andere aus den "
        "Daten — der Vergleich wäre sprachabhängig.",
    r"\.(?:replace|split|startsWith|endsWith|includes|indexOf)\(\s*\$?t\(":
        "Zeichenketten-Operation auf einem Bezeichner: der Katalog bestimmt "
        "dann, ob ein Präfix erkannt wird.",
    r"\b(?:getItem|setItem|removeItem)\(\s*\$?t\(":
        "Speicherschlüssel: nach einem Sprachwechsel wäre der alte Wert weg.",
    r"\$?emit\(\s*\$?t\(":
        "Ereignisname: der Zuhörer hört auf den deutschen Namen weiter (#1805).",
    r"\bname\s*:\s*\$?t\(.*\}\s*\)":
        "Routenname in router.push({ name }) — übersetzt gibt es die Route nicht.",
    r"\b(?:querySelector|querySelectorAll|getElementById)\(\s*\$?t\(":
        "CSS-/DOM-Selektor: Übersetzt findet er das Element nicht mehr, und "
        "der Zweig läuft still ins Leere.",
    r"\b(?:addEventListener|removeEventListener)\(\s*\$?t\(":
        "DOM-Ereignisname: Übersetzt wird nichts mehr abgehört, ohne Fehler.",
    r"\bheaders\s*\[\s*\$?t\(":
        "Kopfzeilenname: `Accept-Language` übersetzt wäre keine Kopfzeile mehr.",
}

#: Ausnahmen — je mit Grund. Noch keine; die Liste gibt es, damit eine
#: begründete Ausnahme nicht als stiller Kommentar endet.
ERLAUBT: dict[str, str] = {}


def _ohne_kommentare(text: str) -> str:
    """Kommentare abziehen — das Programm prüfen, nicht die Erzählung.

    Die Lehre aus #1834 und inzwischen sechs Wiederholungen: Dieser Dateikopf
    **zitiert** `method: uebersetze('…dELETE')`, um den Befund zu erklären.
    Ohne diesen Schritt würde der Wächter an seiner eigenen Begründung rot.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return "\n".join(z for z in text.split("\n")
                     if not z.lstrip().startswith(("//", "*", "#")))


def _dateien() -> list[Path]:
    return sorted(list(SRC.rglob("*.vue")) + list(SRC.rglob("*.ts")))


def test_kein_katalogwert_steht_an_einer_datenstelle():
    verstoesse: list[str] = []
    for p in _dateien():
        rel = str(p.relative_to(SRC))
        inhalt = _ohne_kommentare(p.read_text(encoding="utf-8"))
        for zeile_nr, zeile in enumerate(inhalt.splitlines(), 1):
            for muster, grund in DATENSTELLEN.items():
                if not re.search(muster, zeile):
                    continue
                if f"{rel}:{zeile_nr}" in ERLAUBT:
                    continue
                verstoesse.append(
                    f"{rel}:{zeile_nr}: {zeile.strip()[:80]}\n      → {grund}")
    assert not verstoesse, (
        "Ein Katalogwert steht an einer Stelle, an der er **Daten** ist:\n  "
        + "\n  ".join(verstoesse))


def test_die_ausnahmen_tragen_eine_begruendung():
    """Eine Ausnahme ohne Grund ist ein Teppich, kein Befund (#1851)."""
    for stelle, grund in ERLAUBT.items():
        assert len(grund) >= 40, f"{stelle}: Grund zu knapp — {grund!r}"


def test_jede_datenstelle_traegt_eine_begruendung():
    """Auch die Regeln selbst. Ein Muster ohne Grund ist nicht nachprüfbar."""
    for muster, grund in DATENSTELLEN.items():
        assert len(grund) >= 40, f"{muster}: Grund zu knapp — {grund!r}"
