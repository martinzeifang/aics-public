"""Eine leere Liste ist eine Antwort, kein Fehler (#1995).

DER BEFUND
Meldung aus dem Betrieb (aics-test): „Antwort enthält keine Liste
‚vorschlaege'." Im Zugriffslog zweimal **HTTP 409** auf
``POST …/evidence/<doc>/erschliessen``.

Die Ursache stand in einer Zeile:

    liste = daten.get("vorschlaege") or daten.get("suggestions")

Eine **leere Liste ist falsy**. Aus ``{"vorschlaege": []}`` wurde damit
``None``, und daraus ein Fehler — und genau diese Antwort **verlangt der
Prompt**:

    Gibt es keinen Beleg: {"vorschlaege": []}

Das Modell hat also getan, was dasteht, und der Code hat es als unlesbar
abgewiesen. Verschärfend läuft die Erschließung **in Scheiben** über den
Katalog (bei WiBA drei): Fand die erste Scheibe nichts, brach der **ganze**
Lauf ab — für ein Dokument, das schlicht nichts aus diesem Katalogteil belegt.

DIE ZWEITE FUNDSTELLE WAR DIE LEISERE UND IN EINER AKTE DIE SCHLIMMERE
``cra/aktenpruefung.parse_antwort`` hatte dasselbe ``or`` — dort aber mit
``return []`` als Rückfall. Eine **unlesbare** Antwort war damit von „nichts zu
beanstanden" nicht zu unterscheiden, und die Maske sagt dazu „Keine Befunde".
Ein Prüfbericht, der aus einer kaputten Antwort ein reines Ergebnis macht, ist
schlimmer als einer, der abbricht.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]


# ── Erschließung: der laute Fall ────────────────────────────────────────────

def test_eine_leere_vorschlagsliste_ist_kein_fehler():
    """Die Antwort, die der Prompt verlangt, muss durchgehen."""
    from evidence.erschliessung import parse_antwort

    ok, verworfen = parse_antwort({"vorschlaege": []}, erlaubte_ids={"x"},
                                  erlaubte_zitate={("d", 1)})
    assert ok == [] and verworfen == []
    # Auch der englische Schlüssel und die nackte Liste.
    assert parse_antwort({"suggestions": []}, erlaubte_ids=set(),
                         erlaubte_zitate=set()) == ([], [])
    assert parse_antwort([], erlaubte_ids=set(), erlaubte_zitate=set()) == ([], [])


def test_eine_wirklich_unlesbare_antwort_bleibt_ein_fehler():
    """Der Riegel bleibt — er war nur zu scharf, nicht falsch."""
    from evidence.erschliessung import ErschliessungFehler, parse_antwort

    for roh in ({}, {"irgendwas": 1}, {"vorschlaege": "keine"},
                {"vorschlaege": {"a": 1}}, 42):
        with pytest.raises(ErschliessungFehler):
            parse_antwort(roh, erlaubte_ids=set(), erlaubte_zitate=set())


def test_der_prompt_und_der_parser_sagen_dasselbe():
    """Spiegel-Liste: Was der Prompt zusagt, muss der Parser annehmen.

    Der Prompt nennt die Form für „kein Beleg" wörtlich. Stünde dort etwas
    anderes als der Parser akzeptiert, wäre das genau dieser Defekt wieder —
    nur an der anderen Seite.
    """
    from evidence import erschliessung as er

    treffer = re.search(r'\{"vorschlaege":\s*\[\]\}', er._FORMAT)
    assert treffer, (
        "Der Prompt nennt die Form für „kein Beleg\" nicht mehr — dann weiß "
        "das Modell nicht, was es antworten soll (#1995).")
    # Und der Parser nimmt genau sie an.
    assert er.parse_antwort({"vorschlaege": []}, erlaubte_ids=set(),
                            erlaubte_zitate=set()) == ([], [])


def test_eine_leere_scheibe_bricht_den_lauf_nicht_ab(monkeypatch):
    """**Der Rundlauf** — daran ist es gescheitert.

    Der Lauf geht in Scheiben über den Katalog. Fand die erste nichts, war
    vorher der ganze Lauf verloren; die zweite Scheibe mit echten Belegen kam
    nie zum Zug.
    """
    from evidence import erschliessung as er

    eintraege = [er.Katalogeintrag(f"ID-{i}", f"Titel {i}", "x" * 400)
                 for i in range(80)]
    monkeypatch.setattr(er, "katalog", lambda modul: eintraege)
    monkeypatch.setattr(er, "MAX_KATALOG_ZEICHEN", 4000)

    antworten = [
        {"vorschlaege": []},                       # erste Scheibe: nichts
        {"vorschlaege": [{"requirement_id": "ID-50", "claim": "belegt",
                          "citations": [{"doc_id": "d1", "chunk": 1}],
                          "confidence": 0.9}]},
    ]
    laeufe = {"n": 0}

    class _Erg:
        ok = True
        provider = "probe"
        fehler = ""

        def __init__(self, parsed):
            self.parsed = parsed

    def _lauf(auftrag):
        i = laeufe["n"]
        laeufe["n"] += 1
        return _Erg(antworten[i] if i < len(antworten) else {"vorschlaege": []})

    import shared.ki_engine as ke
    monkeypatch.setattr(ke, "ki_lauf", _lauf)

    erg = er.erschliesse(doc_id="d1", dokument_name="doku.md", modul="wiba",
                         chunks=[{"doc_id": "d1", "chunk_idx": 1,
                                  "text": "Inhalt des Dokuments."}])
    assert erg["laeufe"] > 1, "Der Lauf muss über mehrere Scheiben gehen."
    assert len(erg["vorschlaege"]) == 1, (
        "Die leere erste Scheibe hat den Lauf abgebrochen — genau der "
        "gemeldete Befund (#1995).")
    assert erg["vorschlaege"][0]["requirement_id"] == "ID-50"


# ── Aktenprüfung: der leise Fall ───────────────────────────────────────────

def test_keine_befunde_und_unlesbar_sind_zwei_verschiedene_ausgaenge():
    """In einer Nachweisakte ist das der Punkt.

    ``{"befunde": []}`` heißt „nichts zu beanstanden" und ist ein Ergebnis.
    Eine unlesbare Antwort heißt „wir wissen es nicht" — und darf nicht als
    reines Ergebnis erscheinen.
    """
    from cra.aktenpruefung import AktenpruefungFehler, parse_antwort

    assert parse_antwort({"befunde": []}) == []
    assert parse_antwort({"findings": []}) == []
    assert parse_antwort([]) == []

    for roh in ({}, {"ampel": "gruen"}, {"befunde": "keine"}, 7):
        with pytest.raises(AktenpruefungFehler):
            parse_antwort(roh)


def test_der_prompt_der_aktenpruefung_nennt_die_leere_form():
    from cra import aktenpruefung as ap

    quelle = Path(ap.__file__).read_text(encoding="utf-8")
    assert re.search(r'\{"befunde":\s*\[\]\}', quelle), (
        "Der Prompt nennt die Form für „nichts zu beanstanden\" nicht mehr.")


def test_der_import_endpunkt_meldet_400_statt_eines_reinen_ergebnisses():
    """Eine unlesbare eingefügte Antwort ist ein 400, kein „keine Befunde"."""
    quelle = (WURZEL / "server" / "api" / "cra_konformitaet.py").read_text(
        encoding="utf-8")
    rumpf = quelle.split("def aktenpruefung_import", 1)[1].split("\n@cra", 1)[0]
    assert "AktenpruefungFehler" in rumpf and "400" in rumpf, (
        "Der Import-Endpunkt unterscheidet „unlesbar\" nicht von „keine "
        "Befunde\" (#1995).")


# ── Die Fehlerklasse als Ganzes ────────────────────────────────────────────

def test_kein_parser_entscheidet_mehr_per_or_ueber_eine_liste():
    """Der Wächter gegen die nächste Fundstelle.

    ``a.get(x) or a.get(y)`` ist für **Listen** falsch, weil eine leere Liste
    falsy ist. Bei Zeichenketten ist dasselbe Muster harmlos und verbreitet
    (``str(v.get("a") or v.get("b") or "")``) — deshalb prüft dieser Wächter
    nur die Stellen, die eine **Liste** erwarten, und die erkennt man daran,
    dass das Ergebnis gegen ``isinstance(..., list)`` geprüft wird.
    """
    verdaechtig: list[str] = []
    for pfad in (WURZEL / "evidence" / "erschliessung.py",
                 WURZEL / "cra" / "aktenpruefung.py"):
        text = pfad.read_text(encoding="utf-8")
        # Kommentare weg — sie zitieren den alten Zustand (die Falle aus
        # #1834/#1867/#1878/#1903).
        programm = re.sub(r"(?m)^\s*#.*$", "", text)
        programm = re.sub(r'""".*?"""', "", programm, flags=re.S)
        for zeile in programm.splitlines():
            if re.search(r"liste\s*=\s*\w+\.get\([^)]*\)\s*or\s", zeile):
                verdaechtig.append(f"{pfad.name}: {zeile.strip()}")
    assert not verdaechtig, (
        "Diese Zeilen entscheiden per `or` über eine Liste — eine leere Liste "
        "ist falsy und wird dadurch zu „fehlt\" (#1995):\n  "
        + "\n  ".join(verdaechtig))
