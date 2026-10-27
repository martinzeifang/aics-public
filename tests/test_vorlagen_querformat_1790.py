"""Breite Tabellen stehen im Querformat, der Rest hoch (#1790).

Eine Auflistung mit sechs Spalten — ID, Kapitel, Anforderung, Fundstelle,
Bewertung, Kommentar — hat im Hochformat je Spalte knapp drei Zentimeter. Die
Tabelle wird damit zur Buchstabensäule, und ein Bericht, den niemand liest,
belegt nichts. Word löst das über Abschnitte: Die Ausrichtung gehört nicht dem
Dokument, sondern dem Abschnitt.

Geprüft wird hier nicht, dass der Mechanismus funktioniert (das zeigt die
erzeugte Datei), sondern dass die **Regel eingehalten** ist: ab fünf Spalten
quer, bis drei Spalten hoch. Ein neuer Bauplan, der eine breite Tabelle ins
Hochformat setzt, lässt diesen Test rot werden — vor dem Einspielen beim
Kunden, nicht danach.

Der Rohling dieses Tests wird gebaut, nicht geladen: Das Briefpapier eines
Hauses liegt nicht im Repository. Er trägt dieselben zwei Eigenheiten, an denen
sich die Sache entscheidet — einen rechten Tabulator als absolute Position und
ein Seitenzahlfeld in der Fußzeile.
"""
from __future__ import annotations

import pytest
from docx import Document
from docx.enum.section import WD_HEADER_FOOTER
from docx.oxml.ns import qn
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.shared import Twips

from tools.vorlagen import cyberwoks_bausteine as b
from tools.vorlagen.cyberwoks_plaene import PLAENE

#: Textbreite des Rohlings im Hochformat (A4 abzüglich 2 cm Rand je Seite).
_TEXTBREITE_HOCH = 9638
_TEXTBREITE_QUER = 14570


def _feldlauf(absatz, feld: str):
    """Ein Lauf mit Feldcode, wie ihn Word für „Seite x von y" schreibt."""
    lauf = absatz.add_run()
    for tag, wert in (("w:fldChar", "begin"), ("w:instrText", None),
                      ("w:fldChar", "end")):
        el = lauf._element.makeelement(qn(tag), {})
        if tag == "w:fldChar":
            el.set(qn("w:fldCharType"), wert)
        else:
            el.text = feld
        lauf._element.append(el)
    return lauf


@pytest.fixture()
def rohling(tmp_path):
    doc = Document()
    abschnitt = doc.sections[0]
    abschnitt.page_width, abschnitt.page_height = Twips(11906), Twips(16838)
    abschnitt.left_margin = abschnitt.right_margin = Twips(1134)
    abschnitt.different_first_page_header_footer = True

    kopf = abschnitt.header.paragraphs[0]
    kopf.paragraph_format.tab_stops.add_tab_stop(
        Twips(_TEXTBREITE_HOCH), WD_TAB_ALIGNMENT.RIGHT)
    kopf.add_run("CYBERWOKS")
    kopf.add_run("\tCRA-Readiness-Bericht · aus dem Rohling")

    fuss = abschnitt.footer.paragraphs[0]
    fuss.paragraph_format.tab_stops.add_tab_stop(
        Twips(_TEXTBREITE_HOCH), WD_TAB_ALIGNMENT.RIGHT)
    fuss.add_run("Vertraulich · aus dem Rohling")
    fuss.add_run("\tSeite ")
    _feldlauf(fuss, "PAGE")
    fuss.add_run(" von ")
    _feldlauf(fuss, "NUMPAGES")

    pfad = tmp_path / "rohling.docx"
    doc.save(str(pfad))
    return pfad


def _tabellen_mit_abschnitt(doc: Document) -> list[tuple[int, int]]:
    """Je Tabelle: (Spaltenzahl, Nummer des Abschnitts, in dem sie steht).

    Ein Abschnitt endet an dem Absatz, der ein ``w:sectPr`` trägt; der letzte
    steht am Ende des Textkörpers. Die Reihenfolge im Körper ist also die
    Reihenfolge der Abschnitte.
    """
    treffer: list[tuple[int, int]] = []
    nummer = 0
    for kind in doc.element.body:
        if kind.tag == qn("w:tbl"):
            treffer.append((len(kind.findall(qn("w:tblGrid") + "/" + qn("w:gridCol"))),
                            nummer))
        elif kind.tag == qn("w:p") and kind.findall(
                qn("w:pPr") + "/" + qn("w:sectPr")):
            nummer += 1
    return treffer


def _ist_quer(abschnitt) -> bool:
    return abschnitt.page_width > abschnitt.page_height


@pytest.mark.parametrize("schluessel", sorted(PLAENE), ids=lambda k: f"{k[0]}-{k[1]}")
def test_breite_tabellen_stehen_quer(rohling, schluessel):
    dokumentart, titel, zeile, untertitel, inhalt = PLAENE[schluessel]
    doc = b.oeffne_rohling(rohling)
    inhalt(doc)

    abschnitte = doc.sections
    for spalten, nummer in _tabellen_mit_abschnitt(doc):
        quer = _ist_quer(abschnitte[nummer])
        if spalten >= 5:
            assert quer, (f"{schluessel}: Tabelle mit {spalten} Spalten steht im "
                          "Hochformat — je Spalte bleiben keine zwei Zentimeter")
        elif spalten <= 3:
            assert not quer, (f"{schluessel}: Tabelle mit {spalten} Spalten steht "
                              "im Querformat — das kostet nur Papier")


@pytest.mark.parametrize("schluessel", sorted(PLAENE), ids=lambda k: f"{k[0]}-{k[1]}")
def test_kein_abschnitt_faengt_mit_der_titelseite_an(rohling, schluessel):
    """``w:titlePg`` gilt **je Abschnitt**.

    Bliebe die Einstellung des Rohlings in den neuen Abschnitten stehen, bekäme
    die erste Seite jedes Abschnitts die Kopf- und Fußzeile der Titelseite —
    beim Cyberwoks-Rohling also einen leeren Kopf und die Hausanschrift im Fuß,
    mitten im Bericht.
    """
    doc = b.oeffne_rohling(rohling)
    PLAENE[schluessel][4](doc)
    for i, abschnitt in enumerate(doc.sections[1:], start=1):
        assert not abschnitt.different_first_page_header_footer, (
            f"{schluessel}: Abschnitt {i} führt noch die Titelseiten-Einstellung")


def test_querformat_bekommt_eigene_kopfzeile_mit_passendem_tabulator(rohling):
    """Der Tabulator steht absolut; im Querformat ist die Seite breiter.

    Ohne eigene Kopf- und Fußzeile stünde die rechte Hälfte — darunter
    „Seite x von y" — acht Zentimeter vor dem Rand mitten auf der Seite.
    """
    doc = b.oeffne_rohling(rohling)
    b.kapitel(doc, 1, "Schmal")
    with b.querformat(doc):
        b.kapitel(doc, 2, "Breit")
        b.datentabelle(doc, schleife="for x in liste",
                       spalten=[(f"S{i}", "{{ x.a }}") for i in range(6)])
    b.kapitel(doc, 3, "Wieder schmal")

    hoch, quer = doc.sections[0], doc.sections[1]
    assert _ist_quer(quer) and not _ist_quer(hoch)
    assert not _ist_quer(doc.sections[2]), "nach der Tabelle gehört es zurück"

    def _tabs(abschnitt) -> set[int]:
        return {int(t.get(qn("w:pos")))
                for teil in (abschnitt.header, abschnitt.footer)
                for t in teil._element.iter(qn("w:tab"))
                if t.get(qn("w:val")) == "right"}

    assert _tabs(hoch) == {_TEXTBREITE_HOCH}
    assert _tabs(quer) == {_TEXTBREITE_QUER}
    assert _tabs(doc.sections[2]) == {_TEXTBREITE_HOCH}, (
        "der Abschnitt nach dem Querformat erbt sonst die breite Fassung")

    sectPr = quer._sectPr
    assert (sectPr.get_headerReference(WD_HEADER_FOOTER.PRIMARY).rId
            != doc.sections[0]._sectPr.get_headerReference(
                WD_HEADER_FOOTER.PRIMARY).rId)


def test_seitenzahl_und_dokumentart_ueberstehen_das_umschreiben(rohling):
    """Zwei Fehler, die erst beim Nachrechnen der fertigen Datei auffielen.

    Der Tabulator steht im Rohling als Zeichen, nicht als ``w:tab``-Element.
    Wer nur nach dem Element sucht, findet keinen — und schreibt dann den
    ganzen Absatz als linke Hälfte um: Die Dokumentart in der Kopfzeile blieb
    die des Rohlings, und ``run.text = ""`` nahm die Feldzeichen der Seitenzahl
    mit (#1007).
    """
    doc = b.oeffne_rohling(rohling)
    b.kapitel(doc, 1, "Schmal")
    with b.querformat(doc):
        b.datentabelle(doc, schleife="for x in liste",
                       spalten=[(f"S{i}", "{{ x.a }}") for i in range(6)])
    b.kopf_und_fuss(doc, dokumentart="WiBA-Nachweisbericht",
                    titel_ausdruck="{{ projekt.name }}", fuss_mitte="Fuß dieses Dokuments")

    for abschnitt in doc.sections:
        kopf = "".join(p.text for p in abschnitt.header.paragraphs)
        assert "WiBA-Nachweisbericht · {{ projekt.name }}" in kopf
        assert "Rohling" not in kopf, "die Dokumentart des Rohlings steht noch da"

        fuss_el = abschnitt.footer._element
        assert fuss_el.findall(".//" + qn("w:instrText")), (
            "„Seite x von y“ ist beim Umschreiben verloren gegangen")
        assert "Fuß dieses Dokuments" in "".join(
            p.text for p in abschnitt.footer.paragraphs)
