"""„Nicht geprüft" ist nicht „erfüllt" — #2074/#2080/#2091.

Die ``None``-Semantik ist in ``cra/konformitaet_gate.evaluate`` **durchgängig**
richtig: SBOM, Fremdkomponenten, Upstream-Meldung, Support, Meldefristen,
Marktaufsicht, Update-Zusagen, Kaufhinweis und Bewertungsweg setzen im Ausfall
``None``, und ``release_bericht`` druckt daraus „nicht geprüft". Dieser Vorgang
schließt die Ausnahmen.

Warum das in diesem Produkt besonders zählt: Ein grüner Haken auf einer nicht
gelesenen Quelle ist von einem echten Nachweis nicht unterscheidbar — und er
steht in dem Dokument, das ein Prüfer behält. #1751 hat für dieselbe Stelle
schon einmal die **Ampel** repariert; die **Ausgabe** blieb bei ``0``.
"""

from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

import pytest

PROJ = "pytest-ungeprueft-2074"
VERSION = "3.1.0"
DB = Path("data/db/cra.sqlite")


# ══════════════════════════════════════════════════════════════════════════════
# #2074 — eine Ursache, zwei grüne Haken
# ══════════════════════════════════════════════════════════════════════════════

def test_aus_zahl_druckt_none_als_nicht_geprueft():
    """Die Leseseite war immer richtig — es kam nur nie ein ``None`` an."""
    from cra.release_bericht import _aus_zahl

    erg, _text = _aus_zahl(None, sp="x", ok="ok", fehl="fehl")
    assert erg == "ungeprueft"
    erg, _text = _aus_zahl(0, sp="x", ok="ok", fehl="fehl")
    assert erg == "erfuellt"


def test_gate_meldet_schwachstellen_als_ungeprueft(monkeypatch):
    """Fällt ``list_vuln`` aus, darf der flache Befund nicht ``0`` sein.

    Aus ``0`` machte der Vorgangsbericht „erfüllt — keine offenen kritischen
    oder hohen Befunde" in grüner Zelle, während zwei Abschnitte weiter unter
    „Offene Punkte" stand, dass die Schwachstellen nicht geprüft werden
    konnten.
    """
    from cra import konformitaet_gate as gate
    from cra.db import save_projekt

    save_projekt(DB, PROJ, unternehmen="Pytest AG", produkt="Prüfling")

    def _kaputt(*_a, **_k):
        raise RuntimeError("Schwachstellentabelle nicht lesbar")

    # `list_vuln` wird im Gate **lokal** importiert — gepatcht wird deshalb die
    # Quelle, nicht das Modul (sonst prüft der Test an der Reparatur vorbei).
    monkeypatch.setattr("cra.db.list_vuln", _kaputt)
    erg = gate.evaluate(PROJ)
    assert erg["offene_kritische_schwachstellen"] is None, (
        "ungeprüft muss None sein, nicht 0")
    # Die Ampel bleibt, wie #1751 sie entschieden hat.
    assert erg["ampel"] != "gruen"
    # Und der offene Punkt steht weiterhin da.
    assert any(p.get("ungeprueft") for p in erg["offene_punkte"])


def test_komponenten_befunde_trennen_die_beiden_quellen():
    """``ohne_komponentenliste`` und ``ohne_vulnliste`` sind zwei Zustände.

    Bis v8.6.3 gab es nur den ersten — bei einer ausgefallenen
    Schwachstellenliste trug der Bericht deshalb **zwei** grüne Haken für
    **eine** Ursache.
    """
    from cra.komponenten_befunde import befund_fuer_release

    b = befund_fuer_release(DB, "pytest-ohne-sbom-2074", version="1.0.0")
    assert b["ohne_komponentenliste"] is True
    assert b["ohne_vulnliste"] is False, (
        "ohne Komponentenliste ist die Schwachstellenliste nicht die Ursache")


def test_fuer_projekt_verschluckt_nur_wenn_es_darf(monkeypatch):
    """Für die Komponentenspalte ist Verschlucken richtig, für einen gerechneten
    Prüfpunkt nicht — deshalb ``strikt``."""
    import cra.db as cradb
    from cra.komponenten_befunde import fuer_projekt

    def _kaputt(*_a, **_k):
        raise RuntimeError("nicht lesbar")

    monkeypatch.setattr(cradb, "list_vuln", _kaputt)
    komp = [{"name": "requests", "version": "2.0", "bewertung": "geprueft"}]
    assert fuer_projekt(DB, PROJ, komp) == {}          # Oberfläche: leer
    with pytest.raises(RuntimeError):                   # Prüfpunkt: durchlassen
        fuer_projekt(DB, PROJ, komp, strikt=True)


# ══════════════════════════════════════════════════════════════════════════════
# #2080 — die übrigen Ausnahmen
# ══════════════════════════════════════════════════════════════════════════════

def test_ohne_erklaerte_art_wird_nicht_abgeglichen():
    """``widersprueche('')`` gibt ``[]`` — das darf nicht „passt zur Akte"
    heißen. Betroffen war jeder Bestandsvorgang vor #1793."""
    from cra.release_art import widersprueche

    # Die reine Funktion bleibt, wie sie ist (sie sagt „nichts zu vergleichen").
    assert widersprueche("", wesentliche_aenderung="",
                         neue_komponenten=3, behobene_schwachstellen=5) == []

    # Der Gate-Befund muss None sein — das ist die Reparatur.
    from cra import konformitaet_gate as gate
    befunde: dict = {}
    gate._check_release_art(PROJ, VERSION, befunde, [])
    assert befunde["release_art_widersprueche"] is None


def test_aus_liste_druckt_none_als_nicht_geprueft():
    from cra.release_bericht import _aus_liste

    assert _aus_liste(None, sp="x", ok="ok", fehl="fehl")[0] == "ungeprueft"
    assert _aus_liste([], sp="x", ok="ok", fehl="fehl")[0] == "erfuellt"


def test_fristen_sind_erst_bestimmbar_wenn_alle_bestimmbar_sind():
    """Der Katalogtext verspricht Plural, gerechnet wurde ein ``any``.

    Wer nur ``eol_datum`` einträgt, hatte einen grünen Prüfpunkt und keinen
    offenen Punkt — obwohl drei der vier Fristen aus Art. 13 unbekannt waren.
    """
    from cra.fristenuhr import aufbewahrungsfristen

    nur_eol = aufbewahrungsfristen({"eol_datum": "2031-05-01"})
    assert nur_eol["unbestimmbar"], "drei Fristen sind hier unbekannt"
    assert nur_eol["berechenbar"] is False

    vollstaendig = aufbewahrungsfristen({
        "markteintritt_datum": "2026-01-01", "eol_datum": "2036-01-01",
        "update_verfuegbarkeit_bis": "2036-01-01",
        "doku_aufbewahrung_bis": "2036-01-01",
        "doc_aufbewahrung_bis": "2036-01-01"})
    if not vollstaendig["unbestimmbar"]:
        assert vollstaendig["berechenbar"] is True


def test_annex_baustein_traegt_seine_pflicht():
    """``pflicht`` fiel in ``als_baustein()`` weg und wurde nie gelesen."""
    from cra.annex_vii import PUNKTE, bausteine

    bs = bausteine()
    assert all("pflicht" in b for b in bs)
    nicht_pflicht = {p.baustein_key or p.key for p in PUNKTE if not p.pflicht}
    assert nicht_pflicht, "der Katalog hat mindestens einen optionalen Punkt"
    assert {b["key"] for b in bs if not b["pflicht"]} == nicht_pflicht


def test_vollstaendig_liest_die_pflicht():
    """Ein Projekt ohne den optionalen Baustein kann grün werden."""
    from cra.annex_vii import PUNKTE
    from cra.traceability_db import annex_vii_status

    st = annex_vii_status(DB, "pytest-annex-pflicht-2080")
    assert "pflicht_count" in st and "pflicht_offen" in st
    optional = {p.baustein_key or p.key for p in PUNKTE if not p.pflicht}
    assert optional.isdisjoint(set(st["pflicht_offen"])), (
        "ein als nicht pflichtig erklärter Baustein darf die Ampel nicht "
        "blockieren")


def test_zehn_jahre_sind_zehn_kalenderjahre():
    """Art. 13 Abs. 13 verlangt zehn Jahre — nicht 3650 Tage.

    Zehn Kalenderjahre ab 2026-01-01 enthalten zwei Schalttage; die Frist endete
    deshalb am 2035-12-30, zwei Tage zu früh.
    """
    from cra.db import _plus_jahre

    assert _plus_jahre(datetime.fromisoformat("2026-01-01"), 10).isoformat() \
        == "2036-01-01"
    assert _plus_jahre(datetime.fromisoformat("2024-02-29"), 5).isoformat() \
        == "2029-02-28", "der 29.02. wandert zurück, nie vor"


def test_keine_365_tage_rechnung_mehr_in_den_fristen():
    """Wächter gegen den Rückfall — **kommentarfrei** geprüft.

    Die erste Fassung dieses Tests schlug auf die eigene Kommentarzeile an
    („Vorher stand hier ``timedelta(days=jahre * 365)``") und auf den Docstring,
    der den Fehler erklärt. Das ist die Lehre aus #1834/#1867/#1878/#1903 am
    eigenen Werkzeug: das Programm prüfen, nicht die Erzählung. ``ast.unparse``
    über den Syntaxbaum sieht weder Kommentare noch Docstrings.
    """
    baum = ast.parse(Path("cra/db.py").read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module,
                               ast.ClassDef)):
            # Docstrings aus dem Vergleich nehmen.
            if (knoten.body and isinstance(knoten.body[0], ast.Expr)
                    and isinstance(knoten.body[0].value, ast.Constant)
                    and isinstance(knoten.body[0].value.value, str)):
                knoten.body = knoten.body[1:] or [ast.Pass()]
    code = ast.unparse(baum)
    verdaechtig = [z.strip() for z in code.splitlines()
                   if "365" in z and "timedelta" in z]
    assert not verdaechtig, f"365-Tage-Jahr zurück: {verdaechtig}"


def test_reassess_wird_nicht_geleert():
    """Teil-Update wie ``artefakt`` (#1771), ``meta_json`` (#1540)."""
    from cra.release_db import get_release, save_release

    save_release(DB, PROJ, {"aktuelle_version": "1.0", "reassess": {"a": True}})
    vorher = get_release(DB, PROJ)
    assert (vorher.get("reassess") or {}).get("a") is True

    save_release(DB, PROJ, {"aktuelle_version": "1.1"})   # nennt reassess nicht
    nachher = get_release(DB, PROJ)
    assert (nachher.get("reassess") or {}).get("a") is True, (
        "ein Speichern ohne das Feld hat den Stand geleert")


# ══════════════════════════════════════════════════════════════════════════════
# #2091 — Programmierfehler werden nicht verschluckt
# ══════════════════════════════════════════════════════════════════════════════

ALLE_SICHER_WRAPPER = [
    "cra/doc_pruefung.py",
    "cra/doc_vorschlag.py",
    "ai_act/doc_vorschlag.py",
    "ai_act/doc_pruefung.py",
]


@pytest.mark.parametrize("pfad", ALLE_SICHER_WRAPPER)
def test_jeder_sicher_wrapper_laesst_programmierfehler_durch(pfad):
    """Alle fünf Geschwister, eine Regel.

    ``cra/doc_pruefung`` war der einzige ohne die Ausnahme — und der Ausgang
    wäre dort am teuersten: An dieser Prüfung hängt die **Sperre** der
    EU-Konformitätserklärung. Ein verschluckter Tippfehler im Importnamen hieße,
    dass eine blockierende Prüfung stillschweigend nichts mehr prüft.
    """
    baum = ast.parse(Path(pfad).read_text(encoding="utf-8"))
    wrapper = [k for k in ast.walk(baum)
               if isinstance(k, ast.FunctionDef) and k.name == "_sicher"]
    assert wrapper, f"{pfad} hat keinen _sicher-Wrapper (mehr)"
    for fn in wrapper:
        typen: set[str] = set()
        for handler in (h for k in ast.walk(fn) if isinstance(k, ast.Try)
                        for h in k.handlers):
            if isinstance(handler.type, ast.Tuple):
                typen |= {e.id for e in handler.type.elts
                          if isinstance(e, ast.Name)}
            elif isinstance(handler.type, ast.Name):
                typen.add(handler.type.id)
        assert {"ImportError", "AttributeError"} <= typen, (
            f"{pfad}: _sicher fängt Programmierfehler mit — {sorted(typen)}")


def test_doc_pruefung_laesst_attributeerror_durch(monkeypatch):
    """Behaviour, nicht nur Struktur: Ein falscher Attributname muss knallen."""
    import cra.doc_pruefung as dp

    def _kaputt(*_a, **_k):
        raise AttributeError("module 'firmen.db' has no attribute 'DB_PATH'")

    monkeypatch.setattr("cra.doc_export.doc_daten", _kaputt)
    with pytest.raises(AttributeError):
        dp.befunde(DB, PROJ, release_version=VERSION)


# ══════════════════════════════════════════════════════════════════════════════
# #2037 / #2038 / #2064 — dieselbe Richtung in der Oberfläche
#
# Dort ist der Ausgang noch unangenehmer als im Bericht: Nicht nur fehlt ein
# Hinweis, es steht die **gegenteilige** Aussage — und zwar auf dem ersten Tab
# von sechs Modulen bzw. in den beiden Registern, die die zehnjährige
# Aufbewahrung tragen.
#
# Geprüft wird **kommentarfrei** (``tests.i18n_text.ohne_kommentare``): Ein
# Kommentar, der den alten Zustand zitiert, darf keinen Wächter erfüllen und
# keinen rot machen.
# ══════════════════════════════════════════════════════════════════════════════

def _quelle(pfad: str) -> str:
    from tests.i18n_text import ohne_kommentare

    return ohne_kommentare(Path(pfad).read_text(encoding="utf-8"))


def test_dashboard_meldet_den_ausfall_statt_risikofreiheit():
    """#2037: ``catch { risiko.value = { gesamt: 0 } }`` machte aus einem 500er
    eine grüne Kachel mit „Keine offenen Risiken"."""
    quelle = _quelle("frontend/src/composables/useModuleDashboard.ts")
    assert "fehler: true" in quelle, (
        "der Fehlerfall setzt keinen eigenen Zustand — eine grüne Null ist von "
        "echter Risikofreiheit nicht unterscheidbar")


def test_risikokachel_hat_drei_zustaende():
    """Im Fehlerfall **keine** Ampelfarbe."""
    quelle = _quelle("frontend/src/components/shared/ModuleDashboard.vue")
    assert "risiko.fehler" in quelle
    assert "risikoStandNichtAbrufbar" in quelle
    # Die Ampel darf nicht mehr allein an `risiko.gesamt` hängen.
    assert "risiko.fehler ? 'unbekannt'" in quelle, (
        "die Kachel färbt im Fehlerfall weiter nach der Zahl")
    assert "kpi-value.unbekannt" in quelle, (
        "ein Zustand ohne sichtbaren Unterschied ist keine Reparatur")


def test_der_dritte_zustand_steht_in_beiden_sprachen():
    from tests.i18n_text import nachricht

    for sprache in ("de", "en"):
        for schluessel in ("geteilt.moduleDashboard.risikoStandNichtAbrufbar",
                           "geteilt.moduleDashboard.risikoStandNichtAbrufbarHinweis",
                           "cra.releasesPanel.archivNichtAbrufbar",
                           "cra.releasesPanel.archivLeer",
                           "aiact.konformitaetserklaerungForm.archivNichtAbrufbar",
                           "aiact.konformitaetserklaerungForm.archivLeer"):
            assert nachricht(schluessel, sprache), f"{schluessel} fehlt in {sprache}"


ARCHIV_REGISTER = [
    ("frontend/src/views/cra/ReleasesPanel.vue", 'v-if="archiv.length"'),
    ("frontend/src/components/aiact/KonformitaetserklaerungForm.vue",
     'v-if="archiv.length"'),
]


@pytest.mark.parametrize("pfad,altes_muster", ARCHIV_REGISTER)
def test_archiv_verschwindet_nicht_mehr_samt_ueberschrift(pfad, altes_muster):
    """#2038: ``v-if`` nahm bei einem gescheiterten Abruf den ganzen Abschnitt
    aus der Seite — was der Anwender las, war identisch mit „noch nie einen
    Nachweis archiviert". Daran hängt eine Aufbewahrungspflicht (Art. 13 Abs. 9
    und 13 CRA · Art. 47 Abs. 2 KI-VO)."""
    quelle = _quelle(pfad)
    assert altes_muster not in quelle, (
        "der Abschnitt hängt weiter an der Listenlänge")
    assert "archivFehler" in quelle, "kein dritter Zustand"
    # Beide Verschluck-Stellen: das `catch` UND `?.… || []`.
    assert "archiv.value = []\n    archivFehler.value = true" in quelle \
        or "archivFehler.value = true" in quelle


ALTE_VERSCHLUCKER = [
    ("frontend/src/views/cra/ReleasesPanel.vue", "data?.eintraege || []"),
    ("frontend/src/components/aiact/KonformitaetserklaerungForm.vue",
     "data?.archiv || []"),
]


@pytest.mark.parametrize("pfad,altes_muster", ALTE_VERSCHLUCKER)
def test_eine_antwort_ohne_den_schluessel_gilt_als_ausfall(pfad, altes_muster):
    """``?.eintraege || []`` verwandelte auch eine Antwort **ohne** den Schlüssel
    in eine leere Liste — das war die zweite Verschluck-Stelle neben dem
    ``catch``.

    Die erste Fassung dieses Tests prüfte nur ``"Array.isArray" in quelle`` und
    blieb beim Rückbau **grün**: Die Zeichenkette steht in beiden Dateien schon
    anderswo. Ein Wächter, der ein Vorkommen zählt, prüft nichts (#1834/#2001) —
    jetzt wird das alte Muster ausgeschlossen, und das ist nachweislich rot.
    """
    quelle = _quelle(pfad)
    assert altes_muster.replace(" ", "") not in quelle.replace(" ", ""), (
        f"{altes_muster} verschluckt weiter eine Antwort ohne die Liste")


def test_reifegrad_ausserhalb_des_bereichs_wird_sichtbar():
    """#2064: Begrenzt war nur der **Bogen**, nicht die gedruckte Zahl — ein
    voller Bogen neben „112 %" hätte den Rechenfehler verborgen statt ihn zu
    zeigen. Eine Anzeige soll einen unmöglichen Wert sichtbar machen."""
    for pfad in ("frontend/src/components/shared/MaturityGauge.vue",
                 "frontend/src/components/shared/ChapterCard.vue"):
        quelle = _quelle(pfad)
        assert "ungueltig" in quelle, f"{pfad}: kein Hinweis auf einen unmöglichen Wert"
        assert "Number.isFinite" in quelle, f"{pfad}: NaN bleibt unbemerkt"


def test_die_balkenbreite_bleibt_gueltiges_css():
    """Eine negative Breite ist ungültiges CSS und blieb leer — der Balken log
    damit in beide Richtungen."""
    quelle = _quelle("frontend/src/components/shared/ChapterCard.vue")
    assert "balkenBreite" in quelle
    assert "width: percent + '%'" not in quelle
