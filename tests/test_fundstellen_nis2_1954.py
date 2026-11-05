"""Die Melde-Fundstellen der NIS-2-Richtlinie stimmen (#1954).

DER BEFUND, DER DAS NÖTIG MACHT
Der 1-Monats-**Abschlussbericht** war an zwölf Stellen als ``Art. 23 Abs. 4
lit. c`` zitiert. Lit. c ist der **Zwischenbericht auf Verlangen**; der
Abschlussbericht ist **lit. d**. Gefunden hat es ein Übersetzer-Agent beim
Nachschlagen der amtlichen englischen Fassung — nicht ein Prüfer.

Art. 23 Abs. 4 der Richtlinie (EU) 2022/2555:

===== ==================================================================
 lit.  Meldung
===== ==================================================================
 a     Frühwarnung — unverzüglich, jedenfalls binnen **24 Stunden**
 b     Meldung des Sicherheitsvorfalls — binnen **72 Stunden**
 c     Zwischenbericht — **auf Verlangen** der Behörde oder des CSIRT
 d     Abschlussbericht — spätestens **einen Monat** nach der Meldung
       nach lit. b
 e     Fortschrittsbericht — bei noch laufendem Vorfall
===== ==================================================================

Die Suite modelliert bewusst die drei **Pflicht**stufen 24h/72h/1 Monat
(``shared/deadlines.py``, STAGE_SETS ``nis2_art23``) und lässt den optionalen
Zwischenbericht weg. Der Stufenbau war richtig, nur der Buchstabe der
dritten Stufe war um eins verrutscht.

WARUM EIN PRÜFER UND NICHT SORGFALT
Die Angabe steht in Prosa, in Prompts, in Hilfetexten und in zwei
Sprachkatalogen — zwölf Stellen, die niemand gemeinsam liest. Sie wird in
die Meldung an Behörde und CSIRT gedruckt. Dieselbe Fehlerklasse wie
#1763/#1792: Eine falsche Fundstelle in einer Nachweisakte sieht aus wie
eine Feststellung.

WAS HIER **NICHT** GEPRÜFT WIRD
Nicht jede Fundstelle der Anwendung — das wäre eine zweite Fassung des
Rechtstextes im Testcode, und die könnte selbst falsch sein. Geprüft wird
genau der Zusammenhang, der hier falsch war: **Steht neben einer
Abschluss-/Final-Meldung ein anderer Buchstabe als d?**
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]

#: Wo überhaupt gesucht wird. `.sync-exclude`-Themen sind unerheblich — die
#: Fundstelle gehört ins Produkt, nicht in die Dokumentation allein.
VERZEICHNISSE = ("nis2", "server", "shared", "frontend/src")
ENDUNGEN = (".py", ".json", ".vue", ".ts")

#: Die Meldung, um die es geht. „Zwischenbericht" bewusst **nicht** — der ist
#: lit. c und damit richtig zitiert, wo er vorkommt.
ABSCHLUSS = re.compile(
    r"abschluss(?:bericht|meldung)|final[- ]?report|1-?Monats-?Abschluss",
    re.I)

#: `Art. 23 Abs. 4 lit. x` und `Art. 23(4) point (x)`.
FUNDSTELLE = re.compile(
    r"Art\.?\s*23\s*(?:Abs\.?\s*4|\(4\))\s*(?:lit\.?\s*([a-e])"
    r"|point\s*\(([a-e])\))", re.I)


def _dateien() -> list[Path]:
    out: list[Path] = []
    for v in VERZEICHNISSE:
        basis = WURZEL / v
        if not basis.exists():
            continue
        for p in basis.rglob("*"):
            if p.is_file() and p.suffix in ENDUNGEN \
                    and "node_modules" not in p.parts:
                out.append(p)
    return sorted(out)


def test_der_abschlussbericht_ist_lit_d():
    """Steht die Abschlussmeldung neben einem anderen Buchstaben als d?

    Geprüft wird **zeilenweise**: Nur wenn Meldung und Fundstelle in
    derselben Zeile stehen, gehören sie zusammen. Ein Fenster über mehrere
    Zeilen würde den Zwischenbericht einer Nachbarzeile mitfangen und
    Fehlalarme erzeugen — ein Prüfer, dessen Ausgabe man nicht mehr liest,
    prüft nichts (#1805/#1834).
    """
    verstoesse: list[str] = []
    for p in _dateien():
        try:
            inhalt = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "23" not in inhalt:
            continue
        for nr, zeile in enumerate(inhalt.splitlines(), 1):
            if not ABSCHLUSS.search(zeile):
                continue
            for m in FUNDSTELLE.finditer(zeile):
                buchstabe = (m.group(1) or m.group(2) or "").lower()
                if buchstabe and buchstabe != "d":
                    verstoesse.append(
                        f"{p.relative_to(WURZEL)}:{nr}: lit. {buchstabe} "
                        f"neben der Abschlussmeldung — {zeile.strip()[:72]}")
    assert not verstoesse, (
        "Der 1-Monats-Abschlussbericht ist Art. 23 Abs. 4 **lit. d** "
        "(lit. c ist der Zwischenbericht auf Verlangen):\n  "
        + "\n  ".join(verstoesse))


def test_die_drei_pflichtstufen_bleiben_drei():
    """24h, 72h, 1 Monat — der optionale Zwischenbericht gehört nicht dazu.

    Der Buchstabe war verrutscht, der **Stufenbau** war richtig. Dieser Test
    hält ihn fest, damit die Korrektur nicht zur Einladung wird, lit. c als
    vierte Pflichtstufe nachzutragen: Art. 23 Abs. 4 lit. c greift nur **auf
    Verlangen** der Behörde oder des CSIRT und ist keine Frist, die von
    selbst läuft.
    """
    from shared import deadlines

    stufen = deadlines.STAGE_SETS.get("nis2_art23")
    assert stufen, "STAGE_SETS[nis2_art23] fehlt"
    assert len(stufen) == 3, (
        f"nis2_art23 hat {len(stufen)} Stufen, erwartet sind die drei "
        f"Pflichtstufen 24h/72h/1 Monat: {stufen}")
