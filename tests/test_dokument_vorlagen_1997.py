"""Word-Vorlagen für die Modul-Dokumente (#1997).

DER BEFUND
In CRA → 📄 Dokumente ließ sich jedes Pflichtdokument als Word und PDF
herausgeben, aber **keine Vorlage** hinterlegen — anders als an jeder anderen
Stelle der Suite, an der ein Dokument entsteht (Berichts-Center #1735/#1777,
EU-Konformitätserklärung #1753/#1889, Nachweis #1776, Gutachten #957). Getroffen
hat es genau die Dokumente, die das Haus **herausgibt**.

DIE ZWEI ZUSAGEN, AN DENEN ALLES HÄNGT
1. **Der modulweite Berichts-Standard greift hier nicht.** Er ist für den
   Berichts-Kontext gebaut; würde er für Dokumente gelten, renderte
   ``{{ reifegrad }}`` dank ``ChainableUndefined`` leer und ein
   Compliance-Dokument sähe fertig aus, in dem eine Zahl fehlt. Das ist #1777
   wörtlich — dort hat ein Haus-Standard für „den CRA-Bericht" lautlos ein
   Rechtsdokument ersetzt.
2. **Die Prosa trägt die Formatvorlagen der Vorlage** und steht an der Stelle,
   die die Vorlage bestimmt. Eine Vorlage ohne diese Stelle wird abgewiesen:
   Sie erzeugt ein Dokument ohne seinen Inhalt, und das ist die schlimmste Form
   des Fehlschlags, weil das Ergebnis fertig aussieht (#1805/#1870).

Die DB-abhängigen Tests hängen am ``pg``-Fixture (tests/conftest.py).
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest
from docx import Document

from shared.documents import vorlage as dv

WURZEL = Path(__file__).resolve().parents[1]
PROJ = "ZZ-DokVorlage-1997"


# ──────────────────────────────────────────────────────────────────────────────
# Hilfsmittel
# ──────────────────────────────────────────────────────────────────────────────
def _haus_vorlage(pfad: Path) -> Path:
    """Die mitgelieferte Haus-Vorlage — über ihren Generator, nicht nachgebaut."""
    import sys
    sys.path.insert(0, str(WURZEL))
    from tools.vorlagen.dokument_vorlage import baue
    return baue(pfad)


def _eintrag(tid: int, *, typ: str, firma: int | None = None,
            default: bool = True) -> dict:
    """Ein Listeneintrag, wie ``dv.vorlagen`` ihn liefert."""
    return {"id": tid, "name": f"v{tid}", "version": 1, "ist_default": default,
            "bericht_typ": typ, "doc_type": dv.doc_type_aus_scope(typ),
            "firmen_id": firma}


def _doc(**kw) -> dict:
    basis = {
        "titel": "SBOM-Begleitdokument", "doc_type": "sbom_begleitdoc",
        "status": "entwurf", "version": 2, "sha256": "f" * 64,
        "updated_at": "2026-11-06 15:40:00", "updated_by": "pytest",
        "meta": {}, "content_html": "<h1>Zweck</h1><p>Text.</p>",
    }
    basis.update(kw)
    return basis


# ──────────────────────────────────────────────────────────────────────────────
# 1 · Der Geltungsbereich — die Zusage, die #1777 gelernt hat
# ──────────────────────────────────────────────────────────────────────────────
def test_ein_modulweiter_berichtsstandard_gilt_fuer_dokumente_nicht():
    """**Der Kern.** Leerer ``bericht_typ`` heißt „alle Berichte des Moduls".

    Für Dokumente darf das nicht gelten: Diese Vorlage bekommt den
    Berichts-Kontext, ein Dokument liefert einen anderen. Würde sie greifen,
    stünde eine leere Zahl in einem Dokument, das das Haus herausgibt.
    """
    assert dv.ist_dokument_scope("") is False
    assert dv.ist_dokument_scope(None) is False
    assert dv.ist_dokument_scope("gesamt") is False
    assert dv.ist_dokument_scope("konformitaetsnachweis") is False
    assert dv.gilt_fuer("", "sbom_begleitdoc") is False
    assert dv.gilt_fuer("gesamt", "sbom_begleitdoc") is False

    assert dv.ist_dokument_scope("dokument") is True
    assert dv.ist_dokument_scope("dokument:sbom_begleitdoc") is True


def test_modulweit_und_typgenau():
    assert dv.scope() == "dokument"
    assert dv.scope("sbom_begleitdoc") == "dokument:sbom_begleitdoc"
    # modulweit gilt für jedes Dokument
    assert dv.gilt_fuer("dokument", "sbom_begleitdoc")
    assert dv.gilt_fuer("dokument", "update_policy")
    # typgenau nur für seinen Typ
    assert dv.gilt_fuer("dokument:update_policy", "update_policy")
    assert not dv.gilt_fuer("dokument:update_policy", "sbom_begleitdoc")


def test_die_geltungsbereiche_kommen_aus_dem_rechtskanon():
    """Keine zweite Liste der Dokumenttypen (#1731)."""
    from shared.documents import catalog as dcat

    for modul in ("cra", "nis2", "ai_act", "dsgvo", "wiba"):
        aus = dv.scopes_fuer_modul(modul)
        assert aus[0]["key"] == "dokument", modul
        katalog = {str(s["doc_type"]) for s in dcat.get_catalog(modul)}
        gemeldet = {dv.doc_type_aus_scope(s["key"]) for s in aus[1:]}
        assert gemeldet == katalog, (
            f"{modul}: Geltungsbereiche weichen vom Rechts-Kanon ab")


# ──────────────────────────────────────────────────────────────────────────────
# 2 · Vorauswahl — die Rangfolge rechnet der Server
# ──────────────────────────────────────────────────────────────────────────────
def test_rangfolge_der_vorauswahl():
    typgenau_haus = _eintrag(1, typ="dokument:sbom_begleitdoc")
    typgenau_kunde = _eintrag(2, typ="dokument:sbom_begleitdoc", firma=7)
    modulweit_haus = _eintrag(3, typ="dokument")
    modulweit_kunde = _eintrag(4, typ="dokument", firma=7)
    alle = [modulweit_haus, typgenau_haus, modulweit_kunde, typgenau_kunde]

    # Mandanten-Vorlage für genau diesen Typ gewinnt
    assert dv.vorauswahl("cra", "sbom_begleitdoc", firmen_id=7, alle=alle) == 2
    # Ohne Mandant: Haus-Vorlage für genau diesen Typ
    assert dv.vorauswahl("cra", "sbom_begleitdoc", alle=alle) == 1
    # Anderer Dokumenttyp: nur die modulweiten kommen in Frage
    assert dv.vorauswahl("cra", "update_policy", firmen_id=7, alle=alle) == 4
    assert dv.vorauswahl("cra", "update_policy", alle=alle) == 3


def test_vorauswahl_nimmt_keine_berichtsvorlage():
    """Auch wenn sie Standard ist und das Modul stimmt."""
    alle = [_eintrag(9, typ=""), _eintrag(10, typ="gesamt")]
    assert dv.vorauswahl("cra", "sbom_begleitdoc", alle=alle) == 0


def test_ohne_standard_keine_vorauswahl():
    alle = [_eintrag(1, typ="dokument", default=False)]
    assert dv.vorauswahl("cra", "sbom_begleitdoc", alle=alle) == 0


# ──────────────────────────────────────────────────────────────────────────────
# 3 · Der Kontext
# ──────────────────────────────────────────────────────────────────────────────
def test_der_kontext_ist_nicht_der_modulkontext():
    ctx = dv.kontext("cra", PROJ, _doc())
    assert set(ctx) == {"dokument", "firma", "projekt", "inhalt"}
    # Die Berichts-Variablen gibt es hier ausdrücklich nicht.
    for fremd in ("meta", "reifegrad", "anforderungen", "risiken", "bewertungen"):
        assert fremd not in ctx


def test_die_pruefsumme_erscheint_nur_am_freigegebenen_dokument():
    """Eine Prüfsumme am Entwurf wäre eine Zusage, die nicht gilt.

    ``set_status`` berechnet sie erst bei der Freigabe; ein Altwert am Entwurf
    würde im Dokument stehen, als sei dieser Text gesichert.
    """
    assert dv.kontext("cra", PROJ, _doc(status="entwurf"))["dokument"]["sha256"] == ""
    assert dv.kontext("cra", PROJ, _doc(status="final"))["dokument"]["sha256"] == ""
    frei = dv.kontext("cra", PROJ, _doc(status="freigegeben"))
    assert frei["dokument"]["sha256"] == "f" * 64


def test_der_kontext_erfindet_keinen_platzhalter():
    """Leere Angaben bleiben leer (#1892) — kein ``[FEHLT]``, kein ``—``."""
    ctx = dv.kontext("cra", PROJ, _doc(titel="", updated_by=""), firma={})
    assert ctx["firma"]["anschrift_text"] == ""
    assert ctx["firma"]["ort"] == ""
    assert ctx["dokument"]["geaendert_von"] == ""
    # Der Titel fällt auf die Bezeichnung des Dokumenttyps zurück — die ist
    # belegt (Rechts-Kanon) und keine Erfindung.
    assert ctx["dokument"]["titel"] == "SBOM-Begleitdokument"


def test_die_rechtsgrundlage_kommt_aus_dem_kanon():
    ctx = dv.kontext("cra", PROJ, _doc())
    assert "Annex I Teil II Nr. 1" in ctx["dokument"]["rechtsgrundlage"]


def test_meta_als_json_zeichenkette_wird_gelesen():
    """``meta_json`` kommt je Weg als Dict oder als Text — beides muss gehen.

    Dieselbe Rückgabeform-Falle wie #1985/#1993: Die Annahme „ist ein Dict"
    stimmt nur auf einem der Wege.
    """
    ctx = dv.kontext("cra", PROJ, _doc(meta='{"vertraulich": true}'))
    assert ctx["dokument"]["vertraulich"] is True
    assert dv.kontext("cra", PROJ, _doc(meta="kein json"))["dokument"]["vertraulich"] is False


# ──────────────────────────────────────────────────────────────────────────────
# 4 · Die Variablen-Prüfung aus #1741 kennt den Dokument-Kontext
# ──────────────────────────────────────────────────────────────────────────────
def test_die_pruefung_vergleicht_gegen_den_dokumentkontext(tmp_path):
    from shared.templates import validate

    pfad = _haus_vorlage(tmp_path / "haus.docx")
    erg = validate.pruefe_variablen("cra", pfad, bericht_typ="dokument")
    assert erg.ok, erg.meldung
    assert erg.dokument_scope is True


def test_eine_berichtsvorlage_als_dokumentvorlage_wird_benannt(tmp_path):
    """Der häufigste Anwenderfehler — und die Meldung muss ihn erklären."""
    from shared.templates import validate

    d = Document()
    d.add_paragraph("{{ meta.reifegrad_pct }} %")
    d.add_paragraph("{{ inhalt }}")
    pfad = tmp_path / "bericht.docx"
    d.save(str(pfad))

    erg = validate.pruefe_variablen("cra", pfad, bericht_typ="dokument")
    assert not erg.ok
    assert "Berichts-Kontext" in erg.meldung
    assert "dokument.*" in erg.meldung


def test_der_genaue_vergleich_faengt_die_gemeinsame_wurzel(tmp_path):
    """``projekt`` ist in **beiden** Kontexten eine Wurzel.

    Ein Wurzel-Vergleich allein ließe ``projekt.produkt`` durchgehen — das gibt
    es nur im Bericht. Deshalb wird im Dokument-Bereich gegen die vollen Pfade
    geprüft, sobald die Vorlagendatei vorliegt.
    """
    from shared.templates import validate

    d = Document()
    d.add_paragraph("{{ projekt.produkt }}")
    d.add_paragraph("{{ inhalt }}")
    pfad = tmp_path / "halbrichtig.docx"
    d.save(str(pfad))

    erg = validate.pruefe_variablen("cra", pfad, bericht_typ="dokument")
    assert not erg.ok, "projekt.produkt gibt es im Dokument-Kontext nicht"
    assert any(u["name"] == "projekt.produkt" for u in erg.unbekannt)
    # Und die Gegenrichtung: projekt.name gibt es.
    d2 = Document()
    d2.add_paragraph("{{ projekt.name }}")
    d2.add_paragraph("{{ inhalt }}")
    pfad2 = tmp_path / "richtig.docx"
    d2.save(str(pfad2))
    assert validate.pruefe_variablen("cra", pfad2, bericht_typ="dokument").ok


def test_der_berichtsweg_bleibt_unveraendert(tmp_path):
    """Ohne Geltungsbereich gilt weiter das Modul-Schema — Regressionsschutz."""
    from shared.templates import validate

    d = Document()
    d.add_paragraph("{{ meta.reifegrad_pct }}")
    pfad = tmp_path / "b.docx"
    d.save(str(pfad))
    assert validate.pruefe_variablen("cra", pfad).ok
    assert validate.pruefe_variablen("cra", pfad).dokument_scope is False


# ──────────────────────────────────────────────────────────────────────────────
# 5 · Eine Vorlage ohne Platz für die Prosa
# ──────────────────────────────────────────────────────────────────────────────
def test_vorlage_ohne_inhalt_wird_abgewiesen(tmp_path):
    d = Document()
    d.add_paragraph("{{ dokument.titel }}")
    pfad = tmp_path / "ohne.docx"
    d.save(str(pfad))

    with pytest.raises(dv.VorlageUngeeignet) as exc:
        dv.pruefe_datei(pfad)
    assert "{{ inhalt }}" in str(exc.value), "Die Meldung muss sagen, was fehlt"

    # Gegenprobe: mit der Variable geht sie durch.
    d.add_paragraph("{{ inhalt }}")
    mit = tmp_path / "mit.docx"
    d.save(str(mit))
    dv.pruefe_datei(mit)


def test_eine_unlesbare_datei_ist_keine_vorlage(tmp_path):
    pfad = tmp_path / "kaputt.docx"
    pfad.write_bytes(b"kein DOCX")
    with pytest.raises(dv.VorlageUngeeignet):
        dv.pruefe_datei(pfad)


# ──────────────────────────────────────────────────────────────────────────────
# 6 · DER RUNDLAUF — daran hängt die ganze Erweiterung
# ──────────────────────────────────────────────────────────────────────────────
def _rendere(tmp_path, doc: dict, firma: dict | None = None):
    """Wie ``dv.render_docx``, nur ohne Registry (Vorlage direkt vom Pfad).

    Die Einsetzlogik wird **aufgerufen** (``dv.prosa_einsetzen``), nicht
    nachgebaut. Der erste Anlauf dieses Helfers hatte sie kopiert — damit prüfte
    der Test seinen eigenen Doppelgänger und übersah genau den Fehler, den er
    finden sollte (der ``id()``-Vergleich auf lxml-Proxys). Ein Testhelfer, der
    Produktionslogik nachbaut, prüft nichts.
    """
    from shared.templates import engine

    pfad = _haus_vorlage(tmp_path / f"{uuid.uuid4().hex}.docx")
    ctx = dv.kontext("cra", PROJ, doc, firma=firma or {})
    g = Document(io.BytesIO(engine.render_docx_from_path(pfad, ctx, modul="cra")))
    dv.prosa_einsetzen(g, doc.get("content_html") or "")
    aus = tmp_path / "ergebnis.docx"
    g.save(str(aus))
    return Document(str(aus))


def _folge(docx_doc) -> list[tuple[str, str]]:
    """Körper-Elemente in Dokumentreihenfolge: (Art, Text/Stil)."""
    from docx.text.paragraph import Paragraph

    aus: list[tuple[str, str]] = []
    for el in docx_doc.element.body:
        tag = el.tag.split("}")[-1]
        if tag == "p":
            p = Paragraph(el, docx_doc)
            if (p.text or "").strip():
                aus.append((p.style.name, p.text))
        elif tag == "tbl":
            aus.append(("tbl", ""))
        else:
            aus.append((tag, ""))
    return aus


def test_rundlauf_die_prosa_steht_an_der_stelle_der_marke(tmp_path):
    doc = _doc(content_html=(
        "<h1>Zweck</h1><p>Begleitet die <strong>SBOM</strong>.</p>"
        "<h2>Umfang</h2><ul><li>Anwendung</li><li>Webserver</li></ul>"
        "<table><tr><th>Artefakt</th><th>Format</th></tr>"
        "<tr><td>aics</td><td>SPDX 2.3</td></tr></table>"
        "<p>Schlusssatz.</p>"))
    erg = _rendere(tmp_path, doc, {"unternehmen": "Nordlicht Systeme",
                                   "rechtsform": "GmbH", "plz": "24103",
                                   "ort": "Kiel", "anschrift": "Hafenstr. 1"})
    folge = _folge(erg)
    texte = [t for _, t in folge]

    # Die Marke ist weg — sonst stünde sie im herausgegebenen Dokument.
    assert dv.INHALT_MARKE not in "\n".join(texte)

    # Der Rahmen der Vorlage steht VOR der Prosa, in seiner Reihenfolge.
    i_titel = next(i for i, (_, t) in enumerate(folge) if t == "SBOM-Begleitdokument")
    i_herausgeber = next(i for i, (_, t) in enumerate(folge) if t == "Herausgeber")
    i_zweck = next(i for i, (_, t) in enumerate(folge) if t == "Zweck")
    i_schluss = next(i for i, (_, t) in enumerate(folge) if t == "Schlusssatz.")
    assert i_titel < i_herausgeber < i_zweck < i_schluss

    # Die Prosa behält ihre eigene Reihenfolge.
    i_umfang = next(i for i, (_, t) in enumerate(folge) if t == "Umfang")
    i_anwendung = next(i for i, (_, t) in enumerate(folge) if t == "Anwendung")
    assert i_zweck < i_umfang < i_anwendung < i_schluss

    # Und sie trägt die Formatvorlagen der VORLAGE, nicht nur Text.
    stile = dict((t, s) for s, t in folge if t)
    assert stile["Zweck"] == "Heading 1"
    assert stile["Umfang"] == "Heading 2"
    assert stile["Anwendung"] == "List Bullet"

    # Die Tabelle aus der Prosa ist eine Tabelle, keine Textzeile.
    assert sum(1 for a, _ in folge if a == "tbl") == 2, (
        "Erwartet: Angaben-Tabelle der Vorlage + Tabelle aus der Prosa")


def test_die_abschnittseigenschaften_bleiben_am_ende(tmp_path):
    """Die Falle, in die der erste Entwurf gelaufen ist.

    ``add_paragraph`` hängt **vor** ``w:sectPr`` an, nicht ans Ende des Körpers.
    Ein Index-Schnitt (``list(koerper)[vorher:]``) übersprang deshalb das erste
    neue Element und nahm ``sectPr`` mit — Seiteneinrichtung samt Kopf- und
    Fußzeile wanderten vor den Text. **Word zeigt das trotzdem an**, also wäre
    es nicht aufgefallen; der Test schaut auf die Baumstruktur statt auf die
    Anzeige.
    """
    erg = _rendere(tmp_path, _doc())
    folge = _folge(erg)
    assert folge[-1][0] == "sectPr", (
        f"sectPr muss zuletzt stehen, steht aber an {[a for a, _ in folge].index('sectPr')}")
    assert sum(1 for a, _ in folge if a == "sectPr") == 1


def test_das_einsetzen_entscheidet_nicht_ueber_objektkennungen():
    """Wächter gegen den Fehler, den ein Verhaltenstest hier **nicht** fängt.

    Der erste Entwurf bestimmte die neuen Elemente über ``id(el)``. lxml legt
    seine Element-Proxys bei jedem Zugriff neu an; hält man keine Referenz,
    werden sie freigegeben und ihre Kennungen neu vergeben — neue Absätze
    erschienen dann als „schon vorhanden". Der Fehler trat **nicht zuverlässig**
    auf: Derselbe Code lief in der Handprobe richtig und im Test falsch.

    Genau deshalb steht hier ein Wächter und kein Rundlauf: Eine Zusage, die nur
    manchmal reißt, ist mit einem Verhaltenstest nicht haltbar — der wäre
    gelegentlich grün und hieße „in Ordnung".

    Geprüft wird das **Programm**, nicht die Erzählung: über den Syntaxbaum, und
    Kommentare und Docstring sind daher außen vor (die Lehre aus #1834).
    """
    import ast

    quelle = (WURZEL / "shared" / "documents" / "vorlage.py").read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    fn = next((k for k in ast.walk(baum)
               if isinstance(k, ast.FunctionDef) and k.name == "prosa_einsetzen"), None)
    assert fn is not None, "prosa_einsetzen gibt es nicht mehr — Wächter anpassen"

    aufrufe = {k.func.id for k in ast.walk(fn)
               if isinstance(k, ast.Call) and isinstance(k.func, ast.Name)}
    assert "id" not in aufrufe, (
        "prosa_einsetzen bestimmt die neuen Elemente wieder über id() — "
        "lxml-Proxy-Kennungen werden neu vergeben (#1997).")
    # Positiv: Der feste Punkt ist sectPr.
    assert "w:sectPr" in ast.unparse(fn), (
        "Die neuen Elemente müssen an sectPr abgelesen werden.")


def test_die_reihenfolge_bleibt_ueber_viele_absaetze_erhalten(tmp_path):
    """Jedes Element der Prosa landet vor der Marke, in seiner Reihenfolge.

    Mit vielen Elementen, weil ein einzelnes übersprungenes am Ende steht und
    bei drei Absätzen leicht übersehen wird.
    """
    teile = [f"<p>Absatz {i:02d}</p>" for i in range(40)]
    erg = _rendere(tmp_path, _doc(content_html="".join(teile)))
    folge = _folge(erg)
    texte = [t for _, t in folge]
    erwartet = [f"Absatz {i:02d}" for i in range(40)]
    assert [x for x in texte if x.startswith("Absatz ")] == erwartet
    # Nichts davon steht hinter den Abschnittseigenschaften.
    i_sect = [a for a, _ in folge].index("sectPr")
    assert i_sect == len(folge) - 1
    letzter = max(i for i, (_, x) in enumerate(folge) if x.startswith("Absatz "))
    assert letzter < i_sect


def test_kopf_und_fusszeile_der_vorlage_wirken(tmp_path):
    erg = _rendere(tmp_path, _doc(), {"unternehmen": "Nordlicht Systeme",
                                      "rechtsform": "GmbH"})
    kopf = erg.sections[0].header.paragraphs[0].text
    fuss = erg.sections[0].footer.paragraphs[0].text
    assert "Nordlicht Systeme GmbH" in kopf
    assert PROJ in fuss and "Fassung 2" in fuss


def test_die_vertraulichkeit_erscheint_nur_wenn_gekennzeichnet(tmp_path):
    ohne = "\n".join(t for _, t in _folge(_rendere(tmp_path, _doc())))
    assert "VERTRAULICH" not in ohne
    mit = "\n".join(t for _, t in _folge(
        _rendere(tmp_path, _doc(meta={"vertraulich": True}))))
    assert "VERTRAULICH" in mit


def test_ohne_marke_bricht_der_lauf_ab_statt_den_text_zu_verlieren(tmp_path, pg):
    """Ein Dokument ohne seinen Inhalt sieht fertig aus — das ist der Grund."""
    from shared.templates import db as tdb
    from shared.templates import storage

    d = Document()
    d.add_paragraph("{{ dokument.titel }}")
    pfad = tmp_path / "ohne_marke.docx"
    d.save(str(pfad))
    rec = storage.upload_template(pfad, modul="cra",
                                  name=f"pytest-1997-{uuid.uuid4().hex[:8]}",
                                  db_path=tdb.DEFAULT_DB_PATH,
                                  bericht_typ="dokument")
    with pytest.raises(dv.VorlageUngeeignet):
        dv.render_docx("cra", PROJ, _doc(), int(rec["id"]))


# ──────────────────────────────────────────────────────────────────────────────
# 7 · Der Generator liefert eine brauchbare Vorlage
# ──────────────────────────────────────────────────────────────────────────────
def test_die_mitgelieferte_hausvorlage_besteht_die_eigene_pruefung(tmp_path):
    pfad = _haus_vorlage(tmp_path / "haus.docx")
    dv.pruefe_datei(pfad)          # wirft nicht
    assert pfad.stat().st_size > 10_000


def test_die_hausvorlage_nennt_die_belegenden_angaben(tmp_path):
    """Was ein herausgegebenes Dokument belegbar macht, steht fest drin.

    Gestaltung gehört dem Haus — diese Angaben nicht: Ohne Herausgeber,
    Rechtsgrundlage, Fassung und Stand ist das Dokument als Nachweis wertlos.
    """
    from shared.templates.validate import vorlage_inhalt

    tokens, text = vorlage_inhalt(_haus_vorlage(tmp_path / "haus.docx"))
    for pflicht in ("inhalt", "dokument.titel", "dokument.rechtsgrundlage",
                    "dokument.version", "dokument.stand", "dokument.status_label",
                    "firma.anschrift_text", "projekt.name"):
        assert pflicht in tokens, f"{pflicht} fehlt in der Haus-Vorlage"
    assert "Herausgeber" in text


# ──────────────────────────────────────────────────────────────────────────────
# 8 · Verdrahtung — jedes Dokumenten-Modul, nicht nur CRA (#1731)
# ──────────────────────────────────────────────────────────────────────────────
def test_jedes_dokumenten_modul_ist_verdrahtet():
    """Fünf Module führen Dokumente. Nur CRA zu versorgen wäre die Spiegel-Liste."""
    from server.api.documents import DOCUMENT_MODULES
    from shared.templates import schema

    for db_modul, url_modul, *_ in DOCUMENT_MODULES:
        # Der Rechts-Kanon kennt das Modul …
        assert dv.scopes_fuer_modul(db_modul), f"{db_modul}: keine Geltungsbereiche"
        # … und die Vorlagen-Engine auch (sonst 404/403, die Falle aus #1731).
        em = dv.engine_modul(db_modul)
        assert em in schema.MODULE, f"{db_modul} → {em} fehlt in schema.MODULE"
        assert em in schema.MODULE_DB, f"{em} fehlt in schema.MODULE_DB"


def test_der_ai_act_schluesselwechsel_stimmt_in_beide_richtungen():
    """``ai_act`` (Dokumente, Rechts-Kanon) ↔ ``aiact`` (Vorlagen-Engine).

    Die beiden Schlüsselräume laufen im Haus auseinander (#1735). Ein Dreher
    hier heißt: AI Act findet seine eigenen Vorlagen nicht.
    """
    from server.api.templates import _dok_modul

    assert dv.engine_modul("ai_act") == "aiact"
    assert _dok_modul("aiact") == "ai_act"
    assert _dok_modul("cra") == "cra"
    assert dv.scopes_fuer_modul("ai_act")[1:], "AI Act hat Dokumenttypen"


# ──────────────────────────────────────────────────────────────────────────────
# 9 · Über die Schnittstelle
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def rest(pg, request):
    return request.getfixturevalue("client"), request.getfixturevalue("auth_headers")


def _lade_hoch(client, headers, tmp_path, *, typ: str, modul: str = "cra"):
    pfad = _haus_vorlage(tmp_path / f"{uuid.uuid4().hex}.docx")
    res = client.post("/api/templates", data={
        "file": (io.BytesIO(pfad.read_bytes()), "v.docx"),
        "modul": modul, "name": f"pytest-1997-{uuid.uuid4().hex[:8]}",
        "bericht_typ": typ},
        content_type="multipart/form-data", headers=headers)
    return res


def test_geltungsbereiche_kommen_ueber_die_schnittstelle(rest):
    client, headers = rest
    res = client.get("/api/templates/berichte/cra", headers=headers)
    assert res.status_code == 200
    body = res.get_json()
    keys = {d["key"] for d in body["dokumente"]}
    assert "dokument" in keys and "dokument:sbom_begleitdoc" in keys
    # Die beiden Schlüsselräume bleiben getrennt.
    assert not any(b["key"].startswith("dokument") for b in body["berichte"])
    assert body["dokument_variablen"], "Das Admin-UI braucht die Variablenliste"


def test_upload_mit_dokument_geltungsbereich(rest, tmp_path):
    client, headers = rest
    res = _lade_hoch(client, headers, tmp_path, typ="dokument:sbom_begleitdoc")
    assert res.status_code == 201, res.get_data(as_text=True)
    body = res.get_json()
    assert body["bericht_typ"] == "dokument:sbom_begleitdoc"
    assert body["pruefung"]["ok"] is True, body["pruefung"]["meldung"]
    assert body["pruefung"]["dokument_scope"] is True


def test_upload_eines_unbekannten_dokumenttyps_wird_abgewiesen(rest, tmp_path):
    client, headers = rest
    res = _lade_hoch(client, headers, tmp_path, typ="dokument:gibt-es-nicht")
    assert res.status_code == 400
    assert "gibt-es-nicht" in res.get_json()["error"]


def test_upload_ohne_inhalt_wird_abgewiesen(rest, tmp_path):
    client, headers = rest
    d = Document()
    d.add_paragraph("{{ dokument.titel }}")
    pfad = tmp_path / "ohne.docx"
    d.save(str(pfad))
    res = client.post("/api/templates", data={
        "file": (io.BytesIO(pfad.read_bytes()), "v.docx"),
        "modul": "cra", "name": f"pytest-1997-{uuid.uuid4().hex[:8]}",
        "bericht_typ": "dokument"},
        content_type="multipart/form-data", headers=headers)
    assert res.status_code == 400
    assert "{{ inhalt }}" in res.get_json()["error"]


def test_export_durch_die_vorlage(rest, tmp_path):
    client, headers = rest
    tid = _lade_hoch(client, headers, tmp_path,
                     typ="dokument:vuln_disclosure_policy").get_json()["id"]

    basis = "/api/cra-dokumente"
    neu = client.post(f"{basis}/{PROJ}", json={
        "doc_type": "vuln_disclosure_policy",
        "content_html": "<h1>CVD</h1><p>Melden an die PSIRT-Adresse.</p>",
        "source": "manuell"}, headers=headers)
    assert neu.status_code == 201, neu.get_data(as_text=True)
    did = neu.get_json()["id"]
    try:
        # Ohne Vorlage: unverändertes Verhalten.
        ohne = client.post(f"{basis}/{PROJ}/{did}/export?format=docx", headers=headers)
        assert ohne.status_code == 200 and ohne.data[:2] == b"PK"

        mit = client.post(f"{basis}/{PROJ}/{did}/export?format=docx&template_id={tid}",
                          headers=headers)
        assert mit.status_code == 200, mit.get_data(as_text=True)
        assert mit.data[:2] == b"PK"
        # Die Vorlage wirkt wirklich: ihr Rahmen steht im Ergebnis.
        texte = [p.text for p in Document(io.BytesIO(mit.data)).paragraphs]
        assert any("Herausgeber" in t for t in texte), (
            "Der Rahmen der Vorlage fehlt — die Vorlage hat nicht gewirkt")
        assert any("CVD" in t for t in texte), "Die Prosa fehlt"
        assert dv.INHALT_MARKE not in "\n".join(texte)
    finally:
        client.delete(f"{basis}/{PROJ}/{did}", headers=headers)


def test_eine_berichtsvorlage_laesst_sich_am_dokument_nicht_waehlen(rest, tmp_path):
    """422 mit Klartext, nicht 500 — der Anwender kann es beheben."""
    client, headers = rest
    d = Document()
    d.add_paragraph("{{ meta.reifegrad_pct }}")
    pfad = tmp_path / "bericht.docx"
    d.save(str(pfad))
    res = client.post("/api/templates", data={
        "file": (io.BytesIO(pfad.read_bytes()), "v.docx"),
        "modul": "cra", "name": f"pytest-1997-{uuid.uuid4().hex[:8]}",
        "bericht_typ": "gesamt"},
        content_type="multipart/form-data", headers=headers)
    assert res.status_code == 201
    tid = res.get_json()["id"]

    basis = "/api/cra-dokumente"
    did = client.post(f"{basis}/{PROJ}", json={
        "doc_type": "update_policy", "content_html": "<p>x</p>",
        "source": "manuell"}, headers=headers).get_json()["id"]
    try:
        aus = client.post(f"{basis}/{PROJ}/{did}/export?format=docx&template_id={tid}",
                          headers=headers)
        assert aus.status_code == 422, aus.get_data(as_text=True)
        assert "keine Dokument-Vorlage" in aus.get_json()["error"]
    finally:
        client.delete(f"{basis}/{PROJ}/{did}", headers=headers)


def test_die_auswahl_nennt_die_vorauswahl_je_dokumenttyp(rest, tmp_path):
    client, headers = rest
    res = client.get(f"/api/cra-dokumente/{PROJ}/vorlagen", headers=headers)
    assert res.status_code == 200, res.get_data(as_text=True)
    body = res.get_json()
    assert "sbom_begleitdoc" in body["je_doc_type"]
    for dt, eintrag in body["je_doc_type"].items():
        assert "vorlagen" in eintrag and "vorlage_id" in eintrag, dt
        # Jede angebotene Vorlage gilt für diesen Dokumenttyp.
        for v in eintrag["vorlagen"]:
            assert dv.gilt_fuer(v["bericht_typ"], dt)


def test_eine_unsinnige_template_id_ist_kein_serverfehler(rest):
    client, headers = rest
    basis = "/api/cra-dokumente"
    did = client.post(f"{basis}/{PROJ}", json={
        "doc_type": "update_policy", "content_html": "<p>x</p>",
        "source": "manuell"}, headers=headers).get_json()["id"]
    try:
        assert client.post(f"{basis}/{PROJ}/{did}/export?format=docx&template_id=abc",
                           headers=headers).status_code == 400
        assert client.post(f"{basis}/{PROJ}/{did}/export?format=docx&template_id=999999",
                           headers=headers).status_code == 422
    finally:
        client.delete(f"{basis}/{PROJ}/{did}", headers=headers)
