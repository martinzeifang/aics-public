"""Ein Nachweis ohne Datei wird benannt, nicht gezählt (#1974).

DER BEFUND
Beim Nachverschlüsseln der Nachweisdateien (#1966) auf **Produktiv** gemessen:
69 Zeilen in ``evidence.evidence_documents``, 34 davon mit ``stored_path`` —
und bei **31** von diesen 34 gibt es die Datei nicht. Darunter
``sbom.cdx.json``, ``cra-evidence-pack.zip`` und ein
Administratorhandbuch. Wer im Nachweis-Store nachsah, zählte 34 Nachweise;
vorlegen ließen sich 3.

Nichts schlug dabei fehl. Es stand nur eine falsche Zahl an der Stelle, an der
ein Prüfer sie liest — dieselbe Klasse wie #1805, #1820 und #1870. Und eine
Ebene schlimmer als #1862 („Erfüllung behauptet ohne Beleg"): Hier *gibt* es
den Beleg in der Liste, nur nicht auf der Platte, und ``shared/evidence_context``
reiht ihn in den Prompt jeder KI-Bewertung (#1483), wo ein Titel ohne Datei
aussieht wie ein Nachweis.

Vermutete Ursache: #1808 — die Übernahme eines Archivs brachte die Dateien
**erst nachträglich** mit (``_dateien_ergaenzen``, als Ergänzung eingeführt).

WAS HIER GEPRÜFT WIRD UND WARUM SO
Tragend ist der **Rundlauf**: Dokument mit Datei → zählt; Datei entfernen →
gilt als fehlend, erscheint im Prompt **gekennzeichnet**, und **die Zeile
bleibt in der Akte**. Die Behauptung „die Markierung kommt an" lässt sich nicht
aus dem Quelltext ablesen (die Lehre aus #1785 und #1870), deshalb geht der
Test durch ``build_context`` und liest den gerenderten Block — nicht die
Teilfunktionen einzeln.

Der zweite Schwerpunkt ist die **Gegenrichtung**: „Datei fehlt" an einer Datei,
die sehr wohl da ist, wäre der schlimmere Fehler. Deshalb ist die Definition
von „vorhanden" dieselbe wie die des Downloads (``Path(stored).is_file()``,
``.enc`` inbegriffen), und genau das steht hier unter Prüfung.
"""
from __future__ import annotations


from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]


# ── Die eine Stelle, die entscheidet ────────────────────────────────────────

@pytest.fixture()
def akte(tmp_path):
    """Eine Firma mit drei Nachweisen: mit Datei, ohne Datei, nur URL."""
    from evidence import db as edb

    db = tmp_path / "evidence.sqlite"
    store = tmp_path / "store"
    quelle = tmp_path / "TOM-Nachweis.md"
    quelle.write_text("# Netzdokumentation\nVLANs je Zweck.\n", encoding="utf-8")

    da = edb.add_document(db, quelle, store_dir=store, doc_type="architektur",
                          firmen_id="Firma Cyberwoks", filename="netzdoku.md")
    weg = edb.add_document(db, quelle, store_dir=store, doc_type="sbom",
                           firmen_id="Firma Cyberwoks", filename="sbom.cdx.json")
    netz = edb.add_web_document(db, "https://example.invalid/policy",
                                "Update-Politik", "Updates erscheinen monatlich.",
                                firmen_id="Firma Cyberwoks")

    # Beide Dokumente haben Volltext — der ist ein eigenes Artefakt und bleibt,
    # wenn die Datei verschwindet. Genau das macht den Fall aus.
    edb.upsert_extracted_text(db, da.id, "Das Netz ist in VLANs je Zweck getrennt.")
    edb.upsert_extracted_text(db, weg.id, "184 Komponenten, Format CycloneDX.")

    # Und so entsteht der gemeldete Zustand: die Zeile bleibt, die Datei geht.
    Path(weg.stored_path).unlink()

    return {"db": db, "store": store, "da": da, "weg": weg, "netz": netz}


def test_der_dateistand_unterscheidet_drei_zustaende(akte):
    """``vorhanden`` · ``fehlt`` · ``ohne_datei`` — und das dritte ist kein Mangel.

    Ein Nachweis der Art ``web`` hatte nie eine Datei. Auf Produktiv sind das
    35 von 69 Zeilen; sie als „fehlt" zu melden wäre ein Befund, der die Hälfte
    des Bestands trifft — und ein Befund, der bei allen anschlägt, wird
    abgeschaltet statt beachtet (#1774/#1877).
    """
    from evidence.db import (DATEI_FEHLT, DATEI_VORHANDEN, OHNE_DATEI,
                             dateistand, list_documents)

    docs = list_documents(akte["db"], firmen_id="Firma Cyberwoks")
    stand = dateistand(docs)

    assert stand[akte["da"].id] == DATEI_VORHANDEN
    assert stand[akte["weg"].id] == DATEI_FEHLT
    assert stand[akte["netz"].id] == OHNE_DATEI, (
        "Ein Nachweis per URL hat keine Datei und hatte nie eine — er darf "
        "nicht als Mangel erscheinen (#1974).")


def test_die_zeile_bleibt_in_der_akte(akte):
    """Aufräumen ist eine fachliche Entscheidung, keine technische.

    Eine Zeile zu löschen nimmt der Akte den Hinweis, dass dieses Dokument
    einmal da war — das wäre Datenverlust mit Erfolgsmeldung.
    """
    from evidence.db import get_document, list_documents

    docs = list_documents(akte["db"], firmen_id="Firma Cyberwoks")
    assert akte["weg"].id in {d.id for d in docs}
    zeile = get_document(akte["db"], akte["weg"].id)
    assert zeile is not None
    assert zeile.filename == "sbom.cdx.json"
    assert zeile.stored_path, (
        "Der Pfad bleibt stehen — er ist der Hinweis darauf, welche Datei "
        "fehlt. Ihn zu leeren wäre dieselbe Klasse wie das Teil-Update-Problem "
        "aus #1540/#1771/#1805.")


def test_eine_verschluesselte_datei_gilt_als_vorhanden(tmp_path, monkeypatch):
    """Der schlimmere Fehler wäre „fehlt" für eine Datei, die da ist.

    Bei eingeschalteter At-Rest-Verschlüsselung liegt die Datei als ``.enc`` —
    und ``stored_path`` trägt diese Endung mit (``add_document`` schreibt sie
    so, ``scripts/ops/nachweise_verschluesseln.py`` stellt sie beim
    Nachverschlüsseln um). Wer hier die Endung abschneidet oder sie ignoriert,
    meldet 34 von 34 Dateien als fehlend.
    """
    from evidence import db as edb

    monkeypatch.setenv("AICS_AT_REST_KEY", "0" * 64)
    monkeypatch.setattr(edb, "_load_suite_config", lambda *a, **k: {
        "security": {"at_rest_encryption": {
            "enabled": True, "encrypt_evidence": True,
            "key_env": "AICS_AT_REST_KEY"}}})

    db = tmp_path / "evidence.sqlite"
    quelle = tmp_path / "bericht.md"
    quelle.write_text("Pentest-Bericht\n", encoding="utf-8")
    doc = edb.add_document(db, quelle, store_dir=tmp_path / "store",
                           firmen_id="F", filename="bericht.md")

    assert doc.stored_path.endswith(".enc"), (
        "Vorbedingung dieses Tests: Die Verschlüsselung steht im stored_path.")
    assert edb.datei_vorhanden(doc.stored_path) is True
    assert edb.dateistand([doc])[doc.id] == edb.DATEI_VORHANDEN


def test_ein_relativer_pfad_wird_wie_beim_download_aufgeloest(tmp_path,
                                                              monkeypatch):
    """``add_document`` schreibt ``data/evidence/…`` — also **relativ**.

    Der Download löst das gegen das Arbeitsverzeichnis auf
    (``Path(stored).is_file()``), und diese Prüfung muss es genauso tun. Eine
    eigene Wurzel (etwa ``AICS_DATA_DIR``) wäre eine zweite Wahrheit über
    denselben Pfad — und sie würde hier „fehlt" an Zeilen schreiben, deren
    Datei der Download klaglos ausliefert.
    """
    from evidence.db import datei_vorhanden

    (tmp_path / "data" / "evidence").mkdir(parents=True)
    (tmp_path / "data" / "evidence" / "x_bericht.pdf").write_bytes(b"%PDF-1.4")
    monkeypatch.chdir(tmp_path)

    assert datei_vorhanden("data/evidence/x_bericht.pdf") is True
    assert datei_vorhanden("data/evidence/gibt-es-nicht.pdf") is False
    assert datei_vorhanden("") is False
    assert datei_vorhanden(None) is False


def test_die_definition_ist_die_des_downloads():
    """Zwei Definitionen von „vorhanden" wären zwei Wahrheiten.

    Geprüft wird das Verhalten, nicht der Wortlaut: Derselbe Pfad muss für den
    Downloadweg (``is_file``) und für ``datei_vorhanden`` dasselbe ergeben —
    auch im Grenzfall „Verzeichnis statt Datei", an dem ein ``exists()`` die
    falsche Antwort gäbe.
    """
    import tempfile

    from evidence.db import datei_vorhanden

    with tempfile.TemporaryDirectory() as d:
        ordner = Path(d) / "ein_ordner"
        ordner.mkdir()
        datei = Path(d) / "eine_datei.pdf"
        datei.write_bytes(b"x")
        for p in (str(ordner), str(datei), str(Path(d) / "weg.pdf")):
            assert datei_vorhanden(p) is Path(p).is_file(), (
                f"{p}: weicht von der Prüfung des Downloads ab (#1974)")


def test_der_dateistand_kostet_eine_abfrage_nicht_n(akte, monkeypatch):
    """Die Liste darf keine Abfrage je Zeile auslösen (#1703/S6, #1984).

    ``dateistand`` nimmt die Zeilen, die der Aufrufer **schon hat** — es gibt
    hier gar keinen Datenbankzugriff. Gemessen wurde das Übrige: ein ``stat``
    je Zeile, 34 Zeilen in einem Ablageordner mit 2 000 Dateien = 0,20 ms.
    """
    from evidence import db as edb

    def keine_verbindung(*a, **k):
        raise AssertionError("dateistand fragt die Datenbank (#1974)")

    monkeypatch.setattr(edb, "_connect", keine_verbindung)
    docs = [akte["da"], akte["weg"], akte["netz"]]
    assert len(edb.dateistand(docs)) == 3


# ── Punkt 2: die Evidenz-Auswahl kennzeichnet ──────────────────────────────

@pytest.fixture()
def kontext(akte, monkeypatch):
    """``evidence_context`` auf die Test-Akte zeigen lassen."""
    from shared import evidence_context as ec

    monkeypatch.setattr(ec, "_EVIDENCE_DB", akte["db"])
    monkeypatch.setattr(ec, "_FIRMEN_DB", akte["db"].parent / "firmen.sqlite")
    return akte


def test_der_prompt_kennzeichnet_den_nachweis_ohne_datei(kontext):
    """Der Rundlauf — und die Entscheidung zu Punkt 2 des Issues.

    **Gekennzeichnet, nicht weggelassen.** Der Volltext ist ein eigenes
    Artefakt (extrahiert, als die Datei da war) und war Grundlage früherer
    Bewertungen; ihn lautlos aus dem Prompt zu nehmen, würde die Bewertung
    verändern, ohne dass jemand erfährt warum. Dass ein Dokument *verzeichnet*
    ist, kann selbst eine Aussage sein — das ist etwas anderes als „es gibt
    keinen Nachweis".

    Was der Prompt braucht, ist nicht Verschweigen, sondern Nachprüfbarkeit.
    """
    from shared import evidence_context as ec

    erg = ec.build_context("cra", {"unternehmen": "Firma Cyberwoks"},
                           {"id": "ART13-05"}, include_risks=False)
    block = erg["rendered_block"]

    assert "sbom.cdx.json" in block, (
        "Der verzeichnete Nachweis fehlt im Block — weggelassen wäre die "
        "andere Hälfte desselben Fehlers.")
    assert ec.OHNE_DATEI_VERMERK.strip("[ ]")[:30] in block, (
        "Der Nachweis ohne Datei steht unmarkiert im Prompt. Genau so sieht "
        "ein Titel ohne Datei aus wie ein Nachweis (#1974).")
    assert "Datei fehlt" in block, (
        "Auch die Quelle muss es sagen — `rank_and_truncate` kann den Text "
        "kürzen, die Quelle bleibt.")

    # Die Gegenprobe: Der Nachweis **mit** Datei trägt den Vermerk nicht.
    zeile_da = next(i for i in erg["items"] if i.ref.endswith(kontext["da"].id))
    assert ec.OHNE_DATEI_VERMERK not in zeile_da.text
    assert zeile_da.quelle.startswith("Hochgeladener Nachweis")
    assert zeile_da.relevance == 1.2


def test_ohne_datei_verliert_bei_knappem_budget(kontext):
    """Die Relevanz ist der wirksame Teil der Kennzeichnung.

    Wird das Zeichenbudget knapp, fällt zuerst der Nachweis heraus, den
    niemand vorlegen kann — nicht der, den man auf den Tisch legen könnte.
    """
    from shared import evidence_context as ec

    items = ec.firm_upload_items("Firma Cyberwoks")
    nach_ref = {i.ref.split(":", 1)[1]: i for i in items}
    assert nach_ref[kontext["weg"].id].relevance == ec.RELEVANZ_OHNE_DATEI
    assert (nach_ref[kontext["weg"].id].relevance
            < nach_ref[kontext["da"].id].relevance)

    # Budget für genau einen Eintrag: Der nicht vorlegbare darf es nicht sein.
    einer = ec.rank_and_truncate(items, max_chars=10)
    assert len(einer) == 1
    assert not einer[0].ref.endswith(kontext["weg"].id), (
        "Bei knappem Budget bleibt der Nachweis übrig, den niemand vorlegen "
        "kann — die Kennzeichnung wirkt dann nur noch als Text (#1974).")
    # Und er steht in der Rangfolge hinter allen anderen.
    geordnet = ec.rank_and_truncate(items, max_chars=100_000)
    assert geordnet[-1].ref.endswith(kontext["weg"].id)


def test_ein_nachweis_per_url_wird_nicht_gekennzeichnet(kontext):
    """Ein Vermerk an jeder zweiten Zeile ist keiner mehr."""
    from shared import evidence_context as ec

    items = ec.firm_upload_items("Firma Cyberwoks", limit=10)
    netz = next(i for i in items if i.ref.endswith(kontext["netz"].id))
    assert ec.OHNE_DATEI_VERMERK not in netz.text
    assert netz.relevance == 1.2


def test_ein_unlesbarer_dateistand_laesst_die_bewertung_laufen(kontext,
                                                               monkeypatch):
    """Fail-open bei Lesefehlern — aber nie eine Lücke als Erfüllung.

    Scheitert die Dateiprüfung selbst, bleibt der Prompt wie vor #1974 (also
    ohne Vermerk). Eine Bewertung an einer nicht lesbaren Platte scheitern zu
    lassen wäre die teurere Richtung; weggelassen wird deswegen nichts.
    """
    from evidence import db as edb
    from shared import evidence_context as ec

    def kaputt(*a, **k):
        raise OSError("Platte nicht lesbar")

    monkeypatch.setattr(edb, "dateistand", kaputt)
    items = ec.firm_upload_items("Firma Cyberwoks", limit=10)
    assert len(items) == 3
    assert all(ec.OHNE_DATEI_VERMERK not in i.text for i in items)


# ── Punkt 1: benannt, wo gezählt wird ──────────────────────────────────────

def _programm(pfad: Path) -> str:
    """Python ohne Kommentare — das Programm prüfen, nicht die Erzählung.

    Dieselbe Vorsichtsmaßnahme wie ``i18n_text.ohne_kommentare`` für die
    ``.vue``-Dateien: Die Kommentare dieses Vorgangs zitieren „Datei fehlt" und
    „len(docs)", und ein Wächter, der darauf anspringt, prüft nichts
    (#1834/#1867/#1903).
    """
    import re as _re
    text = pfad.read_text(encoding="utf-8")
    return _re.sub(r"(?m)(^|\s)#.*$", "", text)


def test_die_nachweisliste_liefert_den_dateistand_mit():
    """Ohne das Feld zeigt die Zeile nichts — und die Liste zählt weiter 34."""
    quelle = _programm(WURZEL / "server" / "api" / "firmen.py")
    liste = quelle.split("def list_evidence", 1)[1].split("\n@firmen_bp", 1)[0]
    assert "'datei':" in liste, (
        "list_evidence liefert den Dateistand nicht mit (#1974).")
    assert "dateistand(docs)" in liste, (
        "Der Stand wird nicht aus den schon geladenen Zeilen gerechnet — eine "
        "zweite Abfrage dafür ist der Anfang von #1703/S6.")


def test_die_zeile_und_die_zahl_nennen_den_mangel():
    """Die Oberfläche muss es sagen, nicht nur die Antwort des Servers.

    Geprüft wird der **kommentarfreie** Text. Beim ersten Anlauf hat dieser
    Test genau die Falle getreten, vor der er warnt: Entfernt man den Badge aus
    der Zeile, blieb er grün — weil der CSS-Kommentar darunter „Datei fehlt"
    *zitiert*. Das Programm prüfen, nicht die Erzählung (#1834/#1867/#1903).
    """
    from tests.i18n_text import ohne_kommentare, vue_text

    ansicht = ohne_kommentare(vue_text(
        WURZEL / "frontend" / "src" / "views" / "firmen" / "FirmenView.vue"))
    assert "Datei fehlt" in ansicht, (
        "Die Nachweiszeile zeigt nicht, dass die Datei fehlt — dann sieht sie "
        "aus wie ein vorlegbarer Nachweis (#1974).")
    assert "ev.datei === 'fehlt'" in ansicht, (
        "Der Hinweis hängt nicht am Stand der Zeile; er stünde dann an jeder "
        "oder an keiner.")
    assert "von {v1} Nachweisen fehlt die hinterlegte Datei" in ansicht, (
        "Die Zahl gehört dorthin, wo gezählt wird: in den Nachweis-Store.")

    kachel = ohne_kommentare(vue_text(
        WURZEL / "frontend" / "src" / "views" / "firmen" / "FirmaDashboard.vue"))
    assert "ohne Datei" in kachel, (
        "Die Kennzahl „Nachweise\" im Firmen-Dashboard nennt den Mangel "
        "nicht — dort zählt der Anwender zuerst (#1974).")
    assert "daten.nachweise_ohne_datei" in kachel


def test_die_gesamtzahl_bleibt_die_gesamtzahl():
    """Zwei Zahlen für denselben Bestand wären zwei Wahrheiten (#1726/#1727).

    ``nachweise`` zählt weiter alle Zeilen; der Mangel steht als eigene Zahl
    daneben. Würde die Kachel kürzen und die Liste nicht, müsste der Anwender
    raten, welche der beiden stimmt.
    """
    quelle = _programm(WURZEL / "firmen" / "uebersicht.py")
    assert "'nachweise_ohne_datei'" in quelle
    rumpf = quelle.split("def _nachweise", 1)[1].split("nachweis_stand =", 1)[0]
    assert "len(docs)" in rumpf, (
        "Die Gesamtzahl wird gekürzt statt ergänzt — damit weichen Kachel und "
        "Nachweisliste voneinander ab (#1974).")


def test_der_fehlende_beleg_wird_in_der_matrix_nicht_unterschlagen(akte,
                                                                   monkeypatch):
    """Ein Beleg ohne Datei darf in der Annex-VII-Matrix nicht wie einer aussehen.

    Im **Label**, nicht nur in einem Datenfeld: Diese Matrix wird gelesen, und
    ein Mangel, den nur ein Programm sieht, ist für den Anwender keiner
    (#1805/#1830). Die **Zählung bleibt unverändert** — den Eintrag weglassen
    würde den Vollständigkeitsstand verändern, und das ist eine fachliche
    Entscheidung über die Akte, kein Nebenbefund dieses Vorgangs.

    Geprüft wird das Verhalten, nicht der Quelltext.
    """
    from cra import annex_evidence as ae
    from evidence.db import list_documents

    # Vorbedingung, ausdrücklich: ``auto_nachweise`` ist best effort und
    # verschluckt jeden Fehler je Quelle. Ist der Nachweis-Store gerade nicht
    # lesbar, fällt die ganze Stufe 2 lautlos aus — und dieser Test meldete
    # dann „der Beleg fehlt in der Matrix", obwohl der Code stimmt. Der
    # häufigste Grund ist ein **gleichzeitiger** pytest-Lauf: Der Schemaname
    # wird aus dem SQLite-Stem abgeleitet, ist also geteilt, und die
    # autouse-Fixture ``_pg_isolate`` droppt ihn vor jedem Test (#1760).
    assert len(list_documents(akte["db"], firmen_id="Firma Cyberwoks")) == 3, (
        "Vorbedingung verletzt: Der Nachweis-Store ist nicht lesbar. Das ist "
        "kein Befund an diesem Code — es lief wahrscheinlich ein zweiter "
        "pytest-Prozess (#1760).")

    monkeypatch.setattr(ae, "EVIDENCE_DB", akte["db"])
    monkeypatch.setattr(ae, "RB_DB", akte["db"].parent / "rb.sqlite")
    monkeypatch.setattr("cra.db.load_projekt",
                        lambda *a, **k: {"firmen_id": "Firma Cyberwoks"})

    out = ae.auto_nachweise(akte["db"].parent / "cra.sqlite", "Produkt A")
    sbom = [e for e in out.get("sbom", []) if "sbom.cdx.json" in e["label"]]
    assert len(sbom) == 1, "Der Beleg fehlt in der Matrix — er soll bleiben."
    assert sbom[0].get("datei_fehlt") is True
    assert "Datei fehlt" in sbom[0]["label"]

    design = [e for e in out.get("design", []) if "netzdoku.md" in e["label"]]
    assert len(design) == 1
    assert "datei_fehlt" not in design[0], (
        "Der Beleg **mit** Datei trägt den Mangel — ein Befund, der alle "
        "trifft, trifft keinen (#1774/#1877).")


def test_niemand_raeumt_beim_start_auf():
    """Die Zeilen beim Start stillschweigend zu entfernen war ausdrücklich
    nicht vorgeschlagen — das wäre Datenverlust mit Erfolgsmeldung.

    Geprüft wird, dass dieser Vorgang **kein** Löschen eingeführt hat: Weder
    ``ensure_db`` noch die neue Prüfung fassen Zeilen an.
    """
    quelle = _programm(WURZEL / "evidence" / "db.py")
    ensure = quelle.split("def ensure_db", 1)[1].split("\ndef ", 1)[0]
    assert "DELETE" not in ensure.upper()
    for name in ("def datei_vorhanden", "def dateistand"):
        rumpf = quelle.split(name, 1)[1].split("\ndef ", 1)[0]
        assert "DELETE" not in rumpf.upper()
        assert "unlink" not in rumpf
        assert "os.remove" not in rumpf
