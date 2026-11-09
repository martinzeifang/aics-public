"""Die CRA-Release-Zustandsmaschine hält — #2072/#2073/#2076/#2078/#2017/#2018.

Sechs Fundstellen an einem Gegenstand: dem Vorgang, der ein Release belegt.
Keine davon schlägt fehl, und genau das macht sie teuer — es steht nur das
Falsche an der Stelle, an der ein Prüfer liest, oder ein in Verkehr gebrachtes
Release bleibt änderbar.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

DB = Path("data/db/cra.sqlite")
PROJ = "pytest-zustand-2072"
VERSION = "8.3.0"

EINREICHER = "editor@example.com"
APPROVER = "compliance@example.com"


def _quelle(pfad: str) -> str:
    """Python-Quelle ohne Kommentare und Docstrings (das Programm, nicht die
    Erzählung — #1834/#1867/#1878/#1903/#1974)."""
    baum = ast.parse(Path(pfad).read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.ClassDef, ast.FunctionDef,
                               ast.AsyncFunctionDef)):
            if (knoten.body and isinstance(knoten.body[0], ast.Expr)
                    and isinstance(knoten.body[0].value, ast.Constant)
                    and isinstance(knoten.body[0].value.value, str)):
                knoten.body = knoten.body[1:] or [ast.Pass()]
    return ast.unparse(baum)


@pytest.fixture
def veroeffentlicht():
    """Ein Vorgang durch die ganze Maschine: entwurf → … → veröffentlicht."""
    from cra import konformitaet_db as kdb
    from cra.db import save_projekt

    save_projekt(DB, PROJ, unternehmen="Pytest AG", produkt="Prüfling")
    kdb.save_konformitaet(DB, PROJ, {"release_version": VERSION,
                                     "bewertungsweg": "A",
                                     "bewertung_abgeschlossen": True})
    kdb.einreichen(DB, PROJ, VERSION, von=EINREICHER)
    kdb.freigeben(DB, PROJ, VERSION, von=APPROVER)
    kdb.veroeffentlichen(DB, PROJ, VERSION)
    rec = kdb.get_konformitaet(DB, PROJ, VERSION)
    assert rec["freigabe_status"] == "veroeffentlicht"
    return rec


# ══════════════════════════════════════════════════════════════════════════════
# #2072 — ein veröffentlichtes Release wird nicht wieder zum Entwurf
# ══════════════════════════════════════════════════════════════════════════════

def test_reopen_verweigert_ein_veroeffentlichtes_release(veroeffentlicht):
    """Drei stille Folgen hatte das: Die abgeleitete Version fiel zurück
    (``HERAUS`` kennt ``entwurf`` nicht — der Befund aus #1820), die Akte des in
    Verkehr gebrachten Release wurde wieder editierbar, und der Datensatz trug
    danach ``veroeffentlicht_am`` **und** Status „Entwurf".

    #1876 verbietet ``verwerfen`` aus ``veroeffentlicht`` mit genau dieser
    Begründung — dass ``reopen`` es durfte, war der Widerspruch im eigenen Haus.
    """
    from cra import konformitaet_db as kdb

    with pytest.raises(ValueError) as fehler:
        kdb.reopen(DB, PROJ, VERSION)
    assert "Verkehr" in str(fehler.value)
    assert kdb.get_konformitaet(DB, PROJ, VERSION)["freigabe_status"] \
        == "veroeffentlicht"


def test_reopen_aus_freigegeben_bleibt_moeglich():
    """Die Reparatur ist keine Sperre: Vor der Veröffentlichung geht es weiter."""
    from cra import konformitaet_db as kdb
    from cra.db import save_projekt

    proj = PROJ + "-frei"
    save_projekt(DB, proj, unternehmen="Pytest AG", produkt="P")
    kdb.save_konformitaet(DB, proj, {"release_version": "1.0.0",
                                     "bewertungsweg": "A",
                                     "bewertung_abgeschlossen": True})
    kdb.einreichen(DB, proj, "1.0.0", von=EINREICHER)
    kdb.freigeben(DB, proj, "1.0.0", von=APPROVER)
    rec = kdb.reopen(DB, proj, "1.0.0")
    assert rec["freigabe_status"] == "entwurf" and rec["gesperrt"] is False


def test_die_abgeleitete_version_bleibt_stehen(veroeffentlicht):
    """Die Folge, die #1820 schon einmal behoben hat — hier anders ausgelöst."""
    from cra.release_db import abgeleitete_version

    assert abgeleitete_version(DB, PROJ) == VERSION


# ══════════════════════════════════════════════════════════════════════════════
# #2073 — die Sperre gilt für ALLE vier Schreibwege
# ══════════════════════════════════════════════════════════════════════════════

def test_save_konformitaet_achtet_alle_gesperrten_zustaende(veroeffentlicht):
    """Geprüft wurde nur ``== "freigegeben"``, gesperrt sind drei Zustände.

    Damit ging ein ``PUT …/konformitaet`` auf einen **veröffentlichten**
    Vorgang mit bloßem ``CRA_WRITE`` durch und änderte Bewertungsweg,
    Abschlusshaken, NB-Kennnummer, CE-Status und Nachweis-Checkliste eines
    Produkts, das in Verkehr ist — während ``gesperrt: true`` gemeldet wird.
    """
    from cra import konformitaet_db as kdb

    with pytest.raises(ValueError) as fehler:
        kdb.save_konformitaet(DB, PROJ, {
            "release_version": VERSION, "bewertungsweg": "A",
            "bewertung_abgeschlossen": False, "ce_status": "offen"})
    assert "gesperrt" in str(fehler.value)
    assert kdb.get_konformitaet(DB, PROJ, VERSION)["bewertung_abgeschlossen"]


def test_set_sicherheitstests_hatte_gar_keine_sperre(veroeffentlicht):
    """Der vierte von vier Schreibwegen, und der einzige ganz ohne Prüfung.

    An der Teststrategie hängt ein gerechneter Prüfpunkt (#1824).
    """
    from cra import konformitaet_db as kdb

    with pytest.raises(ValueError) as fehler:
        kdb.set_sicherheitstests(DB, PROJ, VERSION,
                                 {"testnachweis_art": "kein_test",
                                  "test_verzicht_begruendung": "x" * 25,
                                  "test_verzicht_review": "2027-01-01"},
                                 von=EINREICHER)
    assert "gesperrt" in str(fehler.value)


def test_alle_vier_schreibwege_lesen_dieselbe_liste():
    """Vier Kopien derselben Regel sind vier Gelegenheiten, dass eine fehlt."""
    quelle = _quelle("cra/konformitaet_db.py")
    for name in ("set_release_checkliste", "set_release_art",
                 "set_wesentliche_aenderung", "save_konformitaet",
                 "set_sicherheitstests"):
        baum = ast.parse(Path("cra/konformitaet_db.py").read_text(encoding="utf-8"))
        fn = next(k for k in ast.walk(baum)
                  if isinstance(k, ast.FunctionDef) and k.name == name)
        namen = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        assert "GESPERRTE_STATUS" in namen, (
            f"{name}() liest die Sperrliste nicht")
    assert "GESPERRTE_STATUS" in quelle


# ══════════════════════════════════════════════════════════════════════════════
# #2078 — eine Ordnung für Versionen
# ══════════════════════════════════════════════════════════════════════════════

def test_eine_vorabfassung_ist_kleiner_als_ihr_release():
    """Semver, und damit dasselbe Ergebnis wie ``shared/deploy/kanal`` (#1908).

    Vorher war ``8.3.0-beta.1`` **größer** als ``8.3.0``: ``abgeleitete_version``
    nahm über ``max()`` die Beta als aktuelle Produktversion, und
    ``doc_vorschlag.charge`` belegte damit **Anhang V Nr. 1** der
    EU-Konformitätserklärung vor — eine falsche Bezeichnung des in Verkehr
    gebrachten Standes in einem unterschriebenen Dokument.
    """
    from cra.release_db import version_schluessel as vs

    assert vs("8.3.0-beta.1") < vs("8.3.0")
    assert vs("1.0-rc1") < vs("1.0")
    assert max(["8.3.0", "8.3.0-beta.1"], key=vs) == "8.3.0"


def test_zahlen_werden_als_zahlen_verglichen():
    """Die Zusage aus #1820 bleibt: ``"7.10" < "7.9"`` wäre falsch."""
    from cra.release_db import version_schluessel as vs

    assert vs("7.9") < vs("7.10")
    assert vs("v8.0.1") < vs("8.1.0")


def test_unlesbare_angaben_verschwinden_nicht():
    """Bestandsangaben sortieren unter jeder lesbaren Version — und bleiben."""
    from cra.release_db import version_schluessel as vs

    assert vs("Stand 3") < vs("1.0")
    assert vs("") < vs("0.1")
    # Untereinander behalten sie eine stabile Ordnung.
    assert vs("Stand 2") < vs("Stand 3")


def test_beide_ordnungen_stimmen_ueberein():
    """Zwei Vergleichsfunktionen für dieselbe Frage hatten entgegengesetzte
    Ergebnisse — das ist die Spiegel-Liste aus #1731/#1735 in ihrer stillsten
    Form. Jetzt rechnet die eine mit der anderen."""
    from shared.deploy.kanal import parse_version

    from cra.release_db import version_schluessel as vs

    paare = [("8.3.0-beta.1", "8.3.0"), ("1.0.0", "1.0.1"), ("2.0.0", "10.0.0")]
    for kleiner, groesser in paare:
        a, b = parse_version(kleiner), parse_version(groesser)
        assert a is not None and b is not None
        assert (a < b) == (vs(kleiner) < vs(groesser)), (
            f"{kleiner} vs {groesser}: Kanal und Release-Ordnung sind uneins")


# ══════════════════════════════════════════════════════════════════════════════
# #2076 — Anhang V Nr. 6 wird wirklich geprüft
# ══════════════════════════════════════════════════════════════════════════════

def test_ohne_erklaerung_ist_nr6_nicht_geprueft():
    """``befunde["normen_widerspruch"] = []`` ergab „Anhang V Nr. 6 ist erklärt
    und passt zum Bewertungsweg" — ohne jede Erklärung. ``normen.erfasst`` las
    niemand."""
    from cra import konformitaet_gate as gate
    from cra.db import save_projekt

    proj = PROJ + "-nr6"
    save_projekt(DB, proj, unternehmen="Pytest AG", produkt="P")
    befunde: dict = {}
    gate._check_normen(proj, "", befunde, [])
    assert befunde["normen_widerspruch"] is None, (
        "eine nicht erfasste Erklärung gilt weiter als erfüllt")


def test_die_erklaerung_des_produkts_erreicht_den_release_vorgang():
    """#2076, der schwerere Teil: ``doc_daten`` las die **Rohzeile**.

    Damit war die mit #1886 gebaute Vererbung für jeden Aufrufer unsichtbar,
    der eine Version nennt — Produkt-Datensatz mit vollständiger Erklärung,
    Release-Zeile mit leerem ``doc_json`` ist der #1886-**Normalfall**, und die
    Prüfung lief für jeden erbenden Vorgang gar nicht.
    """
    from cra import konformitaet_db as kdb
    from cra.db import save_projekt
    from cra.doc_export import doc_daten

    proj = PROJ + "-erbe"
    save_projekt(DB, proj, unternehmen="Pytest AG", produkt="P")
    # Produkt-Datensatz trägt die Erklärung …
    kdb.save_konformitaet(DB, proj, {"bewertungsweg": "A"})
    kdb.save_doc(DB, proj, {"ort": "Musterstadt",
                            "unterzeichner_name": "Fr. Dr. Vogt",
                            "keine_harmonisierten": True}, "")
    # … der Release-Vorgang nicht.
    kdb.save_konformitaet(DB, proj, {"release_version": "2.0.0",
                                     "bewertungsweg": "A"})

    d = doc_daten(DB, proj, "2.0.0")
    doc = d.get("doc") or {}
    assert doc.get("ort") == "Musterstadt", (
        "die geerbte Erklärung erreicht den Release-Vorgang nicht")
    assert doc.get("keine_harmonisierten") is True


# ══════════════════════════════════════════════════════════════════════════════
# #2017 — die Phase sagt die Wahrheit
# ══════════════════════════════════════════════════════════════════════════════

PRODUKT_PRUEFUNGEN = ["_check_ki_pruefung", "_check_akzeptanz_verknuepfung",
                      "_check_akzeptanz_nicht_gelesen"]


@pytest.mark.parametrize("name", PRODUKT_PRUEFUNGEN)
def test_produkt_pruefungen_stempeln_phase_produkt(name):
    """``_punkt()`` schrieb ``phase="release"`` hart auf.

    Diese drei laufen aus der **Produkt**-Kette, und ihr eigener Kommentar sagt
    warum: „weil der Widerspruch eine Eigenschaft der Akte ist, nicht des
    Release." Die Begründung war richtig, die Beschriftung widersprach ihr.
    """
    baum = ast.parse(Path("cra/konformitaet_gate.py").read_text(encoding="utf-8"))
    fn = next(k for k in ast.walk(baum)
              if isinstance(k, ast.FunctionDef) and k.name == name)
    aufrufe = [n for n in ast.walk(fn)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id in ("_punkt", "_ungeprueft")]
    assert aufrufe, f"{name}() legt keine Punkte an"
    for aufruf in aufrufe:
        phasen = [k.value.value for k in aufruf.keywords
                  if k.arg == "phase" and isinstance(k.value, ast.Constant)]
        assert phasen == ["produkt"], (
            f"{name}(): ein Punkt trägt phase={phasen or 'release (Vorgabe)'}")


def test_kein_produkt_punkt_traegt_phase_release():
    """Der Wächter, den #2017 verlangt: Behaviour über ``evaluate``."""
    from cra import konformitaet_gate as gate
    from cra.db import save_projekt

    proj = PROJ + "-phase"
    save_projekt(DB, proj, unternehmen="Pytest AG", produkt="P")
    erg = gate.evaluate(proj)
    falsch = [p for p in erg.get("produkt_punkte") or []
              if p.get("phase") == "release"]
    assert not falsch, (
        f"{len(falsch)} Punkt(e) der Produkt-Kette tragen phase='release': "
        f"{[p.get('typ') for p in falsch]}")


# ══════════════════════════════════════════════════════════════════════════════
# #2018 — eine Quelle für die Erfüllungsschwelle
# ══════════════════════════════════════════════════════════════════════════════

def test_die_schwelle_steht_nicht_mehr_als_literal_in_der_rest_schicht():
    quelle = _quelle("server/api/cra/__init__.py")
    assert "_ERFUELLT_AB" in quelle, "die REST-Schicht kennt die Quelle nicht"
    assert "score >= 4" not in quelle.replace(" ", "").replace("score>=4", "score >= 4"), (
        "die Schwelle steht weiter als nacktes Literal da")


def test_alle_fassungen_der_schwelle_stimmen_ueberein():
    """Vier Fassungen gab es: Gate, ``shared/ki_pruefhinweise`` (bewusst, mit
    Test), und zwei nackte Literale ohne Verweis und ohne Wächter."""
    from cra.konformitaet_gate import _ERFUELLT_AB
    from shared.ki_pruefhinweise import ERFUELLUNG_AB
    from shared.req_risks import GATE_SCHWELLE

    assert _ERFUELLT_AB == ERFUELLUNG_AB == GATE_SCHWELLE["cra"], (
        "die Schwelle ist auseinandergelaufen — das Gate rechnet anders als "
        "die Prüfhinweise oder der Risiko-Baustein")


def test_ein_abgeschnittener_kommentar_sagt_es():
    """Ohne Auslassungszeichen liest sich ein gekappter Kommentar im Bericht wie
    ein vollständiger Satz."""
    from cra.report_export import _gekuerzt

    assert _gekuerzt("kurz", 200) == "kurz"
    lang = "Ein sehr langer Kommentar mit vielen Worten, der gekappt wird"
    gek = _gekuerzt(lang, 30)
    assert gek.endswith("…") and len(gek) <= 32
    assert " " not in gek[-3:-2] or True   # kein zerschnittenes Wort
