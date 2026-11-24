"""Die Kundenfassung spricht die Sprache des Mandanten — und der Riegel wirkt (#1954).

WAS HIER SCHIEFLAG
``cra/kundenfassung.VERBOTENE_BEGRIFFE`` war eine Liste mit zehn **deutschen**
Wörtern, und gesucht wurden sie ausschließlich in Tests. Beides war in dem
Moment falsch, in dem das Dokument auch englisch entstehen kann:

1. Eine englische Kundenfassung passierte die deutsche Liste **grün** — nicht
   weil nichts drin war, sondern weil nichts gesucht wurde, was drin sein
   könnte. Der Riegel gegen Informationsabfluss wäre genau in dem Fall aus
   gewesen, für den es ihn gibt, und zwar lautlos: Ein Prüfer, der nichts
   findet, sieht aus wie einer, der nichts zu finden hatte. Dieselbe
   Fehlerklasse wie #1870, wo „Was ist überholt?" immer leer war und das als
   Erfolg meldete.
2. Eine Prüfung, die nur im Test läuft, prüft den **Fixture-Datensatz** und
   nicht das Dokument, das ein Mandant herunterlädt.

Diese Datei prüft deshalb drei Dinge, und der dritte ist der, der im Betrieb
zählt: dass die Begriffe je Sprache vorliegen, dass unsere **eigene** Prosa
keinen davon trägt (sonst hielte der Riegel jedes Dokument auf), und dass das
fertige Dokument zur Laufzeit geprüft wird und bei einem Treffer **nicht**
herausgeht.

Ohne Datenbank: Der Renderer bekommt seinen Datensatz gestellt. Das ist hier
nicht die billige Variante, sondern die richtige — geprüft werden soll die
Prosa des Renderers, und die hängt nicht an der Datenbank.
"""
from __future__ import annotations

import copy
import io
import re

import pytest

from cra import ce_mark
from cra import kundenfassung as kf
from cra import requirements as rq
from cra import sicherheitstests as st
from shared import sprache as sp

PLATZHALTER = re.compile(r"\{(\w+)\}")

#: Ein vollständiger Datensatz — jeder Zweig des Renderers wird betreten.
#: Nur so prüft der Rundlauf die ganze Prosa und nicht die Hälfte.
DATEN: dict = {
    "erstellt_am": "2026-11-04",
    "projekt_name": "Testprodukt",
    "produkt": {"name": "Testprodukt", "hersteller": "Test GmbH",
                "beschreibung": "Ein Gerät", "klasse_label": ""},
    "konformitaet": {"bewertungsweg": "B+C", "nb_name": "Teststelle",
                     "nb_kennnummer": "0123", "doc_ausgestellt": True,
                     "doc_ausgestellt_am": "2026-10-01", "doc_version": 3,
                     "release_version": "1.0"},
    "_record": {"ce_angebracht_am": "2026-10-02", "ce_status": "ce_angebracht",
                "ce_ort": "https://example.test/ce"},
    "erklaerung_archiv": [{"version": "3", "am": "2026-10-01", "sha256": "a" * 64}],
    "support": {"markteintritt": "2026-01-01", "jahre": 5, "eol": "2031-01-01",
                "update_kanal": "https://example.test/updates",
                "kostenlos": True, "getrennt": True,
                "sicherheitsupdate_kanal": "security.example.test",
                "funktionsupdate_kanal": "release.example.test",
                "zusagen_nachweis": "https://example.test/zusagen",
                "kaufhinweis_url": "https://example.test/eol"},
    "meldestelle": {"policy_url": "https://example.test/vdp", "security_md": "",
                    "kontakt": "psirt@example.test"},
    "advisories": [{"id": "CVE-2026-1000", "behoben_in": "1.1.0",
                    "url": "https://example.test/adv/1"}],
    "sbom": {"vorhanden": True, "format": "SPDX", "stand": "2026-10-20",
             "version": "1.0"},
    "tests": {"art": "pentest_extern", "art_label": "", "juengster": "2026-09-01",
              "anzahl": 1, "verzicht": False, "verzicht_begruendung": "",
              "verzicht_review": ""},
    "risikomanagement": {"gefuehrt": True, "methode": "STRIDE",
                         "stand": "2026-10-15"},
}


def _daten(sprache: str) -> dict:
    d = copy.deepcopy(DATEN)
    d["produkt"]["klasse_label"] = rq.klasse_label("important_ii", sprache=sprache)
    d["tests"]["art_label"] = st.art_label("pentest_extern", sprache=sprache)
    return d


@pytest.fixture
def rendere(monkeypatch):
    """Rendert die Kundenfassung mit gestelltem Datensatz."""
    def _rendere(sprache: str, daten: dict | None = None) -> bytes:
        monkeypatch.setattr(kf, "sammle",
                            lambda name, **kw: daten or _daten(sprache))
        monkeypatch.setattr(kf, "_sprache_fuer", lambda name, s: sprache)
        return kf.build_docx("Testprodukt", sprache=sprache)
    return _rendere


def _absaetze(blob: bytes) -> str:
    from docx import Document
    d = Document(io.BytesIO(blob))
    return "\n".join(p.text for p in d.paragraphs)


def _dokumentsprache(blob: bytes) -> str | None:
    from docx import Document
    xml = Document(io.BytesIO(blob)).styles["Normal"].element.xml
    m = re.search(r'w:lang [^/]*w:val="([^"]+)"', xml)
    return m.group(1) if m else None


# ── Die Begriffslisten ───────────────────────────────────────────────────────

def test_jede_sprache_hat_eigene_verbotene_begriffe():
    """Das ist der gemeldete Mangel: Es gab nur die deutsche Liste."""
    assert set(kf.VERBOTENE) == set(sp.SPRACHEN), (
        "für jede unterstützte Sprache braucht es eine Liste — sonst passiert "
        "ein Dokument in dieser Sprache die Prüfung zwangsläufig grün")
    for code, begriffe in kf.VERBOTENE.items():
        assert len(begriffe) >= 8, f"{code}: zu wenige Begriffe"


def test_die_listen_sind_nicht_dieselbe_liste():
    """Eine kopierte deutsche Liste unter dem Schlüssel ``en`` wäre keine Prüfung."""
    de = {b.lower() for b in kf.VERBOTENE["de"]}
    en = {b.lower() for b in kf.VERBOTENE["en"]}
    assert not (de & en), f"gemeinsame Begriffe: {de & en}"


def test_alle_verbotenen_ist_die_vereinigung():
    union = {b.lower() for b in kf.alle_verbotenen()}
    for begriffe in kf.VERBOTENE.values():
        assert {b.lower() for b in begriffe} <= union
    assert len(kf.alle_verbotenen()) == len(set(kf.alle_verbotenen())), "Dubletten"


def test_verbotene_begriffe_faellt_auf_deutsch_zurueck():
    assert kf.verbotene_begriffe("en") == kf.VERBOTENE["en"]
    assert kf.verbotene_begriffe("klingonisch") == kf.VERBOTENE["de"]
    assert kf.verbotene_begriffe(None) == kf.VERBOTENE["de"]


# ── Der Selbsttest: unsere eigene Prosa ──────────────────────────────────────

def test_keine_eigene_prosa_traegt_einen_verbotenen_begriff():
    """Der wichtigste Test dieser Datei.

    Der Riegel ist **blockierend**. Stünde in einem unserer Textbausteine ein
    verbotener Begriff, käme für diesen Mandanten gar keine Kundenfassung mehr
    heraus — und zwar erst im Betrieb. Dieselbe Falle wie in #1885, wo der
    Prüfer auf ein Feld ansprang, das die Anwendung selbst gefüllt hatte.
    """
    quellen: dict[str, list[str]] = {
        "kundenfassung.TEXTE/de": list(kf.TEXTE["de"].values()),
        "kundenfassung.TEXTE/en": list(kf.TEXTE["en"].values()),
        "ce_mark.TEXTE/de": list(ce_mark.TEXTE["de"].values()),
        "ce_mark.TEXTE/en": list(ce_mark.TEXTE["en"].values()),
        "ART_LABEL/de": list(st.ART_LABEL.values()),
        "ART_LABEL/en": list(st.ART_LABEL_EN.values()),
    }
    for code in sp.SPRACHEN:
        quellen[f"klasse_label/{code}"] = [
            rq.klasse_label(k, sprache=code)
            for k in ("default", "important_i", "important_ii", "critical")]
    schlecht = {name: kf.treffer("\n".join(werte))
                for name, werte in quellen.items() if kf.treffer("\n".join(werte))}
    assert not schlecht, f"eigene Prosa mit internen Begriffen: {schlecht}"


# ── Textkatalog ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("katalog,name", [
    (kf.TEXTE, "cra.kundenfassung.TEXTE"),
    (ce_mark.TEXTE, "cra.ce_mark.TEXTE"),
])
def test_textkatalog_ist_paritaetisch(katalog, name):
    assert set(katalog) == set(sp.SPRACHEN), name
    schluessel = {code: set(texte) for code, texte in katalog.items()}
    erste = schluessel[sp.STANDARD]
    for code, menge in schluessel.items():
        assert menge == erste, f"{name}/{code} weicht ab: {menge ^ erste}"


@pytest.mark.parametrize("katalog,name", [
    (kf.TEXTE, "cra.kundenfassung.TEXTE"),
    (ce_mark.TEXTE, "cra.ce_mark.TEXTE"),
])
def test_platzhalter_sind_in_jeder_sprache_dieselben(katalog, name):
    """Ein fehlender Platzhalter wirft ``KeyError`` — und zwar erst beim Export."""
    for schluessel in katalog[sp.STANDARD]:
        mengen = {code: set(PLATZHALTER.findall(texte[schluessel]))
                  for code, texte in katalog.items()}
        erste = mengen[sp.STANDARD]
        for code, menge in mengen.items():
            assert menge == erste, f"{name}/{code}/{schluessel}: {menge ^ erste}"


def test_keine_leeren_texte():
    for code, texte in kf.TEXTE.items():
        for schluessel, wert in texte.items():
            assert wert.strip(), f"{code}/{schluessel} ist leer"


def test_art_label_und_klassen_sind_uebersetzt():
    assert set(st.ART_LABEL) == set(st.ART_LABEL_EN)
    for art in st.ART_LABEL:
        assert st.art_label(art) != st.art_label(art, sprache="en") or not art
    # Eine unbekannte Art liefert den Schlüssel, nicht die leere Zeichenkette:
    # „nichts" liest sich im Dokument wie „nicht geprüft".
    assert st.art_label("erfunden", sprache="en") == "erfunden"
    assert rq.klasse_label("critical", sprache="en") != rq.klasse_label("critical")


# ── Der Riegel ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,erwartet", [
    ("Das Restrisiko wurde akzeptiert.", {"Restrisiko", "akzeptiert"}),
    ("The residual risk was accepted.", {"residual risk", "accepted"}),
    ("Reifegrad 4/5 — Ampel gelb", {"Reifegrad", "Ampel"}),
    ("Sign-off by the approver, reviewed by QA",
     {"sign-off", "approver", "reviewed by"}),
    ("Eine saubere Kundenfassung.", set()),
])
def test_treffer_findet_in_jeder_sprache(text, erwartet):
    assert set(kf.treffer(text)) == erwartet


def test_angaben_des_mandanten_loesen_keinen_fehlalarm_aus():
    """Ohne diese Unterscheidung wäre die Liste für einen blockierenden Prüfer
    zu weit — „verantwortlich" steht in echten Update-Kanälen und Adressen."""
    eigen = "https://kunde.example/verantwortlich-portal"
    assert kf.treffer(f"Bezug der Updates: {eigen}", eigene=[eigen]) == []
    # Die Prosa daneben bleibt geprüft.
    assert kf.treffer(f"Bezug: {eigen}\nFreigeber: Frau M.",
                      eigene=[eigen]) == ["Freigeber"]


def test_ausblenden_schiebt_keine_bruchstuecke_zusammen():
    """Ersetzt würde durch ``""``, entstünde aus „Restri"+„siko" ein Treffer,
    den niemand im Dokument wiederfindet."""
    assert kf.treffer("RestriXXXXsiko", eigene=["XXXX"]) == []


def test_kurze_angaben_werden_nicht_ausgeblendet():
    """Unter drei Zeichen nähme das Ausblenden reihenweise Buchstaben weg."""
    assert kf.treffer("Der Freigeber", eigene=["e", "ab"]) == ["Freigeber"]


def test_pruefe_nennt_den_begriff():
    with pytest.raises(kf.InternasImDokument) as e:
        kf.pruefe("Offene Punkte: 3 · Zieldatum 2027-01-01")
    assert "offene Punkte" in str(e.value)
    assert "Zieldatum" in str(e.value)


def test_internas_im_dokument_ist_ein_runtimeerror():
    """Muster ``vcs.errors.IssueBackendFehlt`` (#1815) — ein bestehendes
    ``except RuntimeError`` fängt den Fall weiter."""
    assert issubclass(kf.InternasImDokument, RuntimeError)


def test_mandantendaten_lassen_unsere_labels_drin():
    d = _daten("de")
    gesammelt = kf._mandantendaten(d)
    assert d["produkt"]["name"] in gesammelt
    assert d["support"]["update_kanal"] in gesammelt
    assert d["tests"]["art_label"] not in gesammelt, (
        "unsere Katalogbezeichnung muss geprüft werden, nicht ausgeblendet")
    assert d["produkt"]["klasse_label"] not in gesammelt


# ── Rundlauf ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sprache,lang", [("de", "de-DE"), ("en", "en-GB")])
def test_dokument_entsteht_in_beiden_sprachen(rendere, sprache, lang):
    text = _absaetze(rendere(sprache))
    assert kf.TEXTE[sprache]["titel"] in text
    assert kf.TEXTE[sprache]["h_sbom"] in text
    # Der Titel der anderen Sprache darf nicht mitkommen.
    andere = "en" if sprache == "de" else "de"
    assert kf.TEXTE[andere]["titel"] not in text


@pytest.mark.parametrize("sprache,lang", [("de", "de-DE"), ("en", "en-GB")])
def test_dokumentsprache_steht_im_docx(rendere, sprache, lang):
    """Ohne ``w:lang`` unterstreicht Word in einem englischen Bericht jedes Wort."""
    assert _dokumentsprache(rendere(sprache)) == lang


@pytest.mark.parametrize("sprache", list(sp.SPRACHEN))
def test_das_fertige_dokument_traegt_keine_internas(rendere, sprache):
    text = _absaetze(rendere(sprache))
    assert kf.treffer(text, eigene=kf._mandantendaten(_daten(sprache))) == []


@pytest.mark.parametrize("sprache,gift", [
    ("de", " Das Restrisiko wurde vom Freigeber akzeptiert."),
    ("en", " Residual risk accepted by the approver."),
])
def test_ein_vergifteter_textbaustein_haelt_das_dokument_auf(rendere, sprache, gift):
    """Die Rotprobe. Ohne sie wäre „der Riegel wirkt" eine Behauptung.

    Geprüft wird über ``build_docx`` und nicht an ``pruefe`` vorbei: Die Frage
    ist nicht, ob die Funktion erkennt, sondern ob das Dokument **nicht
    herausgeht** (die Lehre aus #1785 — der Rundlauf, nicht die Behauptung).
    """
    echt = kf.TEXTE[sprache]["einleitung"]
    kf.TEXTE[sprache]["einleitung"] = echt + gift
    try:
        with pytest.raises(kf.InternasImDokument):
            rendere(sprache)
    finally:
        kf.TEXTE[sprache]["einleitung"] = echt


def test_eine_eigene_angabe_des_mandanten_haelt_das_dokument_nicht_auf(rendere):
    """Die Gegenrichtung: Was der Mandant selbst eingetragen hat, gehört ihm."""
    daten = _daten("de")
    daten["support"]["update_kanal"] = "https://kunde.example/verantwortlich"
    text = _absaetze(rendere("de", daten))
    assert "verantwortlich" in text


# ── Durchreichen ─────────────────────────────────────────────────────────────

def test_build_und_build_pdf_reichen_die_sprache_durch(monkeypatch):
    """Sonst wäre die Sprache im DOCX wirksam und im PDF nicht."""
    gesehen: list[str | None] = []

    def falle(projekt_name, *, db_path=None, version=None, sprache=None):
        gesehen.append(sprache)
        return b"PK"

    monkeypatch.setattr(kf, "build_docx", falle)
    monkeypatch.setattr("shared.reports.docx_pdf.docx_bytes_to_pdf",
                        lambda blob, **kw: blob)
    kf.build("P", fmt="docx", sprache="en")
    kf.build("P", fmt="pdf", sprache="en")
    assert gesehen == ["en", "en"], gesehen


def test_apply_base_font_ueberschreibt_eine_gesetzte_sprache_nicht():
    """Die Falle aus #1771.

    ``_normalize_docx_bytes`` ruft ``apply_base_font`` ein zweites Mal über
    jedes fertige Dokument, bevor es ins PDF geht. Mit einem Vorgabewert würde
    dieser Durchlauf jedes englische Dokument wieder auf Deutsch stellen — und
    zwar nur im PDF, also genau dort, wo niemand es sucht.
    """
    from docx import Document

    from shared.reports.docx_pdf import apply_base_font, set_doc_lang

    doc = Document()
    set_doc_lang(doc, "en")
    apply_base_font(doc)                      # ohne `sprache`
    assert 'w:val="en-GB"' in doc.styles["Normal"].element.xml


def test_set_doc_lang_haelt_genau_eine_angabe():
    """Zweimal gesetzt heißt nicht zwei ``w:lang``-Elemente — Word nimmt sonst
    das erste, und das wäre das alte."""
    from docx import Document

    from shared.reports.docx_pdf import set_doc_lang

    doc = Document()
    set_doc_lang(doc, "de")
    set_doc_lang(doc, "en")
    xml = doc.styles["Normal"].element.xml
    assert xml.count("<w:lang") == 1, xml
    assert 'w:val="en-GB"' in xml
