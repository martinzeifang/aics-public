"""Eine freigegebene Zuordnung schließt die Anforderung ab (#1991).

DER WUNSCH AUS DEM BETRIEB
„Ich will beim Einlesen die Möglichkeit haben, das Thema abschließend zu
machen. Sonst bringt das ja alles nichts. Hinweise sind ok, aber wenn ich
übernehmen klicke, dann erwarte ich, dass die Frage beantwortet ist. Ich habe
das ja gelesen und geprüft." — und auf Rückfrage: **für alle Module.**

DER STAND VORHER
Die Freigabe legte einen Beleg ab, der *irgendwann* in einem KI-Lauf wirken
würde. Auf Produktiv hatte der Anwender **65 Prüffragen** belegt und brauchte
dafür 65 KI-Läufe, um sie beantwortet zu bekommen — der Sammel-Prompt trägt den
Nachweis-Block bewusst nicht (#1989). Die Arbeit lag damit auf dem einen Weg,
den man bei 65 Fragen nicht geht.

WARUM DAS #1526 NICHT BRICHT
Dort darf der **Abgleich** nicht bewerten, weil keine Maschine ein Mensch ist.
Hier liest der Bearbeiter die belegte Aussage, prüft sie gegen das Dokument und
klickt — das **ist** die fachliche Prüfung (die Linie aus #1773 und #1868).
Dieser Test hält die vier Bedingungen fest, unter denen das vertretbar ist.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
MODAL = (WURZEL / "frontend" / "src" / "components" / "firmen"
         / "NachweisErschliessungModal.vue")


def test_jeder_erschliessbare_katalog_kann_abschliessen():
    """Die Spiegel-Liste: Wer erschlossen werden kann, muss abschließen können.

    Sonst ist die Freigabe in genau diesem Modul wieder schreib-nur — und das
    fällt niemandem auf, weil nichts fehlschlägt.
    """
    from evidence.erschliessung import MODULE as KATALOGE
    from shared.nachweis_abschluss import MODULE as ABSCHLUSS

    fehlt = set(KATALOGE) - set(ABSCHLUSS)
    assert not fehlt, (
        "Diese Kataloge lassen sich erschließen, aber nicht abschließen: "
        f"{sorted(fehlt)} — die Freigabe bliebe dort wirkungslos (#1991).")
    zuviel = set(ABSCHLUSS) - set(KATALOGE)
    assert not zuviel, f"Abschluss ohne Katalog: {sorted(zuviel)}"


def test_die_antwort_wird_nicht_geraten():
    """``antwort`` hat keine Vorgabe in der Funktion — nur in der Maske.

    Eine belegte Aussage ist meist ein „ja“ bzw. „überwiegend umgesetzt“. Aber
    nicht immer: Dokument 15 des Mandanten heißt „Offene Punkte und begründete
    Abweichungen", und ein Beleg daraus stützt ein **nein**. Eine Vorgabe in
    der Schreibfunktion wäre eine geratene Aussage in einer Nachweisakte.
    """
    import inspect

    from shared.nachweis_abschluss import abschliessen

    sig = inspect.signature(abschliessen)
    assert sig.parameters["antwort"].default is inspect.Parameter.empty, (
        "`antwort` hat eine Vorgabe bekommen — damit kann ein Aufrufer sie "
        "weglassen und die Anwendung entscheidet (#1991).")


def test_leere_antwort_schreibt_nichts(tmp_path, monkeypatch):
    """„nur Beleg“ muss bleiben: Nicht jeder Beleg ist ein Urteil."""
    from shared import nachweis_abschluss as na

    erg = na.abschliessen("wiba", projekt="P", objekt_id="netze-1",
                          antwort="", claim="belegt")
    assert erg["antwort"] == "" and erg["ersetzt"] is False
    assert "" in na.antworten("wiba") and "" in na.antworten("cra"), (
        "Der Weg „nur Beleg“ ist der Zustand vor #1991 und darf nicht "
        "wegfallen.")


def test_eine_unzulaessige_antwort_wird_abgewiesen():
    from shared.nachweis_abschluss import AbschlussFehler, abschliessen

    with pytest.raises(AbschlussFehler):
        abschliessen("wiba", projekt="P", objekt_id="x", antwort="vielleicht",
                     claim="belegt")
    with pytest.raises(AbschlussFehler):
        # 0 ist „nicht bewertet“ — das ist kein Abschluss, sondern sein
        # Gegenteil, und steht deshalb nicht in der Liste.
        abschliessen("cra", projekt="P", objekt_id="x", antwort="0",
                     claim="belegt")
    with pytest.raises(AbschlussFehler):
        abschliessen("gibtesnicht", projekt="P", objekt_id="x", antwort="ja",
                     claim="belegt")


def test_ohne_belegte_aussage_kein_abschluss():
    """Die Aussage ist die Grundlage — ohne sie wäre es eine Behauptung."""
    from shared.nachweis_abschluss import AbschlussFehler, abschliessen

    with pytest.raises(AbschlussFehler):
        abschliessen("wiba", projekt="P", objekt_id="netze-1", antwort="ja",
                     claim="   ")


def test_die_vorgabe_der_score_module_ist_die_schwelle_des_gates():
    """4, nicht 5 — und das ist die Zahl aus ``_ERFUELLT_AB``.

    4 heißt „Überwiegend umgesetzt“ und ist die Schwelle, ab der das Gate eine
    Anforderung als erfüllt zählt. **Ein** belegter Satz trägt das; die
    Vollständigkeit bleibt eine eigene, ausdrückliche Entscheidung.
    """
    from cra.konformitaet_gate import _ERFUELLT_AB
    from shared.nachweis_abschluss import MODULE

    for schluessel, eintrag in MODULE.items():
        if eintrag.art == "score":
            assert eintrag.vorgabe == str(_ERFUELLT_AB), (
                f"{schluessel}: Vorgabe {eintrag.vorgabe} weicht von der "
                f"Erfüllt-Schwelle {_ERFUELLT_AB} ab (#1991).")


def test_der_rundlauf_setzt_eine_wiba_antwort(tmp_path, monkeypatch):
    """Der Beweis, dass es ankommt — nicht die Behauptung (#1785)."""
    from shared import nachweis_abschluss as na
    import wiba.db as wdb

    db = tmp_path / "wiba.sqlite"
    wdb.ensure_db(db)
    wdb.save_projekt(db, name="P", unternehmen="Firma Cyberwoks")
    monkeypatch.setitem(na.MODULE, "wiba",
                        na.Abschluss(str(db), "status", "ja", "Prüffrage"))

    erg = na.abschliessen("wiba", projekt="P", objekt_id="netze-18",
                          antwort="ja",
                          claim="Die WLAN-Kommunikation ist verschlüsselt.",
                          dokumente=["TOM-Nachweis-02.md"], doc_ids=["d1"],
                          person="pruefer-1", datum="06.11.2026")

    assert erg["antwort"] == "ja" and erg["vorher"] == "offen"
    gespeichert = wdb.load_antworten(db, "P")["netze-18"]
    assert gespeichert["status"] == "ja"
    assert na.MARKER in gespeichert["notiz"]
    for teil in ("TOM-Nachweis-02.md", "verschlüsselt", "pruefer-1",
                 "06.11.2026"):
        assert teil in gespeichert["notiz"], (
            f"{teil!r} fehlt in der Spur — eine Bewertung ohne nachlesbare "
            f"Grundlage ist in einer Nachweisakte keine.")
    assert "d1" in gespeichert["evidence_doc_ids"]


def test_ein_bestehender_stand_wird_benannt_und_nicht_verschluckt(tmp_path,
                                                                  monkeypatch):
    """Die Lehre aus #1988: 50 von 179 Freigaben ersetzten lautlos."""
    from shared import nachweis_abschluss as na
    import wiba.db as wdb

    db = tmp_path / "wiba.sqlite"
    wdb.ensure_db(db)
    wdb.save_projekt(db, name="P", unternehmen="F")
    wdb.save_antwort(db, "P", "netze-18", status="nein",
                     notiz="Von Hand geprüft: fehlt noch.")
    monkeypatch.setitem(na.MODULE, "wiba",
                        na.Abschluss(str(db), "status", "ja", "Prüffrage"))

    erg = na.abschliessen("wiba", projekt="P", objekt_id="netze-18",
                          antwort="ja", claim="belegt", person="p",
                          datum="06.11.2026")
    assert erg["vorher"] == "nein" and erg["ersetzt"] is True
    notiz = wdb.load_antworten(db, "P")["netze-18"]["notiz"]
    assert "Von Hand geprüft: fehlt noch." in notiz, (
        "Die vorige Notiz ist die Aussage eines Menschen und darf nicht "
        "verschwinden, weil eine neue dazukommt (#1988).")


def test_zwei_abschluesse_stapeln_den_kommentar_nicht(tmp_path, monkeypatch):
    """Sonst wächst der Kommentar bei jedem Beleg um einen Block."""
    from shared import nachweis_abschluss as na
    import wiba.db as wdb

    db = tmp_path / "wiba.sqlite"
    wdb.ensure_db(db)
    wdb.save_projekt(db, name="P", unternehmen="F")
    monkeypatch.setitem(na.MODULE, "wiba",
                        na.Abschluss(str(db), "status", "ja", "Prüffrage"))
    for i in range(3):
        na.abschliessen("wiba", projekt="P", objekt_id="netze-18",
                        antwort="ja", claim=f"belegt {i}", person="p",
                        datum="06.11.2026")
    notiz = wdb.load_antworten(db, "P")["netze-18"]["notiz"]
    assert notiz.count(na.MARKER) == 1


def test_der_rundlauf_setzt_eine_score_bewertung(tmp_path, monkeypatch):
    from shared import nachweis_abschluss as na
    import cra.db as cdb

    db = tmp_path / "cra.sqlite"
    cdb.ensure_db(db)
    cdb.save_projekt(db, "Produkt", unternehmen="Firma Cyberwoks")
    monkeypatch.setitem(na.MODULE, "cra",
                        na.Abschluss(str(db), "score", "4", "Anforderung"))

    erg = na.abschliessen("cra", projekt="Produkt", objekt_id="CRA-C1-03",
                          antwort="4", claim="Die SBOM liegt je Release vor.",
                          dokumente=["sbom.cdx.json"], person="p",
                          datum="06.11.2026")
    assert erg["antwort"] == "4"
    b = cdb.load_bewertungen(db, "Produkt")["CRA-C1-03"]
    assert int(b["bewertung"]) == 4
    assert na.MARKER in b["kommentar"] and "SBOM" in b["kommentar"]


def test_der_endpunkt_raet_das_projekt_nicht():
    """Zwei Projekte einer Firma sind zwei Akten."""
    quelle = (WURZEL / "server" / "api" / "firmen.py").read_text(encoding="utf-8")
    rumpf = quelle.split("def _antwort_aus_freigabe", 1)[1].split("\n@firmen_bp", 1)[0]
    assert "len(projekte) > 1" in rumpf, (
        "Bei mehreren Projekten muss gewählt werden — eine Bewertung in der "
        "falschen Akte ist ein stiller Fehler (#1991).")
    assert "aus_nachweis" in quelle and "audit_event" in rumpf
    assert "sync_for_wiba_projekt" in rumpf, (
        "Die WiBA-Antwort speist den TOM-Status (#1575) — ohne den Nachzug "
        "bleibt die DSGVO-Seite auf dem alten Stand.")


def test_die_maske_zeigt_die_wahl_und_den_server_als_quelle():
    quelle = MODAL.read_text(encoding="utf-8")
    vorlage = quelle.split("<script setup", 1)[0]
    assert "option.antworten" in vorlage, (
        "Die Antwortmöglichkeiten kommen nicht vom Server — im Frontend "
        "nachgebaut wären sie die zweite Wahrheit (#1703/S9).")
    assert "abschlussProjekt" in vorlage
    programm = quelle.split("<script setup", 1)[1]
    assert "abschlussOptionen" in programm
    # Die Vorgabe kommt aus der Server-Antwort, nicht als Literal in der Maske.
    assert not re.search(r"\?\?\s*'ja'", programm), (
        "Die Vorgabe steht als Literal in der Maske — sie gehört zum Modul "
        "und kommt mit den Optionen (#1991).")


# ── #1993: Die Projektlisten haben zwei Formen ──────────────────────────────

def test_jedes_modul_loest_seine_projekte_wirklich_auf(tmp_path, monkeypatch):
    """Der Lauf über **alle** Module — nicht die Behauptung.

    DER BEFUND: ``list_projekte`` liefert in CRA, NIS2, AI Act und DSGVO
    ``list[str]`` (nur Namen), in **WiBA** aber ``list[dict]`` (ganze Zeilen).
    Meine Schleife nahm Namen an und übergab WiBA ein Dict an
    ``load_projekt`` — unter PostgreSQL ``cannot adapt type 'dict'``.

    Gefunden hat das der Lauf gegen die **echte Testinstanz**, nicht dieser
    Test: Die vier Score-Module lieferten brav ihre Listen, und bei WiBA brach
    es ab. Dieselbe Klasse wie #1986 (``list_firmen_rows`` liefert ein Tupel)
    und #1985 (Dataclass als Dict gelesen) — eine Rückgabeform, die anderswo
    festgelegt ist, und eine Annahme darüber.

    Dieser Test geht deshalb **durch** die Funktion, für jedes Modul, mit einer
    angelegten Firma und einem angelegten Projekt. Ein neues Modul mit einer
    dritten Form wird hier rot, nicht erst auf der Instanz.
    """
    import importlib

    from shared import nachweis_abschluss as na

    for schluessel, eintrag in na.MODULE.items():
        paket, feld = na._PAKET[schluessel]
        mod = importlib.import_module(paket)
        db = tmp_path / f"{schluessel}.sqlite"
        mod.ensure_db(db)
        # Auch `save_projekt` ist nicht einheitlich: In AI Act und WiBA ist
        # `name` **keyword-only**, in CRA, NIS2 und DSGVO positionell. Der
        # Test sieht das nach statt es anzunehmen — sonst prüft er die
        # Signatur und nicht die Auflösung (und mein erster Anlauf tat genau
        # das und wurde rot).
        import inspect
        kind = inspect.signature(mod.save_projekt).parameters["name"].kind
        if kind is inspect.Parameter.KEYWORD_ONLY:
            mod.save_projekt(db, name="P", **{feld: "Firma Cyberwoks"})
        else:
            mod.save_projekt(db, "P", **{feld: "Firma Cyberwoks"})
        monkeypatch.setitem(na.MODULE, schluessel,
                            na.Abschluss(str(db), eintrag.art, eintrag.vorgabe,
                                         eintrag.objekt))

        treffer = na.projekte_der_firma(schluessel, "Firma Cyberwoks")
        assert treffer == ["P"], (
            f"{schluessel}: projekte_der_firma liefert {treffer!r} statt "
            f"['P'] — die Rückgabeform von {paket}.list_projekte passt nicht "
            f"zur Annahme der Schleife (#1993).")
        assert all(isinstance(t, str) for t in treffer), (
            f"{schluessel}: Es müssen Projekt**namen** herauskommen.")
        # Eine fremde Firma darf nichts treffen — sonst landete eine Bewertung
        # in der Akte eines anderen Mandanten.
        assert na.projekte_der_firma(schluessel, "Fremde GmbH") == []
