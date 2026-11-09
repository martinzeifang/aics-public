"""Wiederverwenden, was zu **einem** Vorgang gehört (#2081–#2087).

DIE GEMEINSAME HALTUNG
----------------------
Alle Vorgänge dieses Blocks sparen Verbindungen und Daten, und keiner tut es
mit einem Cache, der über seinen Vorgang hinaus gilt. Das ist die Grenze, die
sie vertretbar macht: Ein Prozess-Cache wäre die Fehlerklasse, die dieses Repo
durchzieht — gespeichert wird etwas, der nächste Lauf liest den alten Stand,
und nichts schlägt fehl (#1805/#1820/#1870).

* **#2084** ``cra.gate_cache.lauf()`` — ein ``ContextVar``, der mit
  ``evaluate()`` endet. Gemessen 92 → 70 Verbindungen, Ergebnis bitidentisch.
* **#2086** ``shared.nachweis_lauf`` — nur Anfragen mit derselben **erklärten**
  Lauf-Kennung teilen den Nachweis-Aufbau. Ohne Kennung ändert sich nichts.
* **#2081** ``risikobewertung.db.projekt_statistik`` — die zwei Zahlen der
  Seitenleiste in **einer** Abfrage statt aus einem 727-KB-Vollabzug.
* **#2087/2** ``list_documents(mit_inhalt=False)`` — die Spaltenliste wird aus
  dem Schema **abgeleitet**, nicht abgetippt.
"""
from __future__ import annotations

import ast
import contextlib
from pathlib import Path

import pytest

from tests.i18n_text import python_programm

REPO = Path(__file__).resolve().parents[1]


# ── #2084: der Merkzettel endet mit dem Lauf ───────────────────────────────

def test_der_merkzettel_ueberlebt_den_lauf_nicht():
    from cra import gate_cache as gc

    n = {"c": 0}

    def holen():
        n["c"] += 1
        return "x"

    assert not gc.im_lauf()
    assert gc.merke("a", holen) == "x" and n["c"] == 1
    assert gc.merke("a", holen) == "x" and n["c"] == 2, (
        "ohne Lauf darf nichts gemerkt werden")
    with gc.lauf():
        assert gc.im_lauf()
        gc.merke("b", holen)
        gc.merke("b", holen)
    assert not gc.im_lauf()
    vorher = n["c"]
    with gc.lauf():
        gc.merke("b", holen)
    assert n["c"] == vorher + 1, "ein neuer Lauf holt neu"


def test_none_wird_mitgemerkt():
    """„Es gibt diese Zeile nicht" ist ein Ergebnis.

    Würde ``None`` nicht gemerkt, kostete die Abwesenheit einer Zeile in jeder
    Prüfung erneut eine Verbindung — und das ist der häufigste Fall bei einem
    frischen Projekt.
    """
    from cra import gate_cache as gc

    n = {"c": 0}

    def holen():
        n["c"] += 1
        return None

    with gc.lauf():
        assert gc.merke("leer", holen) is None
        assert gc.merke("leer", holen) is None
    assert n["c"] == 1


def test_verschachtelte_laeufe_legen_keinen_zweiten_zettel_an():
    from cra import gate_cache as gc

    n = {"c": 0}

    def holen():
        n["c"] += 1
        return 1

    with gc.lauf():
        gc.merke("x", holen)
        with gc.lauf():
            gc.merke("x", holen)
    assert n["c"] == 1


def test_evaluate_spannt_den_lauf_auf():
    """Sonst wirkt der Merkzettel nirgends."""
    programm = python_programm(REPO / "cra/konformitaet_gate.py")
    baum = ast.parse(programm)
    fn = next(k for k in ast.walk(baum)
              if isinstance(k, ast.FunctionDef) and k.name == "evaluate")
    rumpf = ast.unparse(fn)
    assert "_gc.lauf()" in rumpf, "evaluate läuft ohne Merkzettel"


def test_die_schluessel_tragen_den_db_pfad():
    """Ein Schlüssel ohne DB-Pfad teilte Zeilen über Datenbanken hinweg.

    ``annex_evidence`` und ``sicherheitstests`` bekommen ihren Pfad als
    Argument; stimmte er nicht mit dem des Gates überein, wäre eine geteilte
    Antwort eine **falsche** — und die sieht aus wie eine Aussage.
    """
    for datei in ("cra/konformitaet_gate.py", "cra/sicherheitstests.py",
                  "cra/annex_evidence.py"):
        programm = python_programm(REPO / datei)
        for zeile in programm.split("\n"):
            if "_gc.merke(" not in zeile:
                continue
            assert ("{CRA_DB}" in zeile or "{db_path}" in zeile
                    or "{RB_DB}" in zeile), f"{datei}: {zeile.strip()[:70]}"


@pytest.mark.parametrize("version", ["", "1.0"])
def test_das_gate_rechnet_mit_und_ohne_merkzettel_dasselbe(version, monkeypatch):
    """Die Probe aufs Exempel: Ein Cache, der das Ergebnis verändert, ist ein
    Defekt und keine Optimierung."""
    pytest.importorskip("psycopg")
    from pathlib import Path as P

    import cra.db as cdb
    import cra.gate_cache as gc
    import cra.konformitaet_gate as g

    db = P("data/db/cra.sqlite")
    pn = "pytest-gate-2084"
    cdb.save_projekt(db, pn, "PyTest", "X", "default")
    try:
        mit = g.evaluate(pn, version=version or None)
        monkeypatch.setattr(gc, "lauf", contextlib.nullcontext)
        ohne = g.evaluate(pn, version=version or None)
        assert mit == ohne
    finally:
        cdb.delete_projekt(db, pn)


# ── #2086: nur ein **erklärter** Lauf teilt ────────────────────────────────

def test_ohne_lauf_kennung_wird_nichts_geteilt():
    from shared.nachweis_lauf import cache_fuer, leeren

    leeren()
    assert cache_fuer("", "cra", "P") is None
    assert cache_fuer(None, "cra", "P") is None


def test_eine_unerlaubte_kennung_wird_abgewiesen():
    """Sie kommt aus dem Request und dient als Schlüssel — Positivliste."""
    from shared.nachweis_lauf import cache_fuer

    for boese in ("a/../b", "a\x00b", "x" * 200, "a b"):
        assert cache_fuer(boese, "cra", "P") is None, boese


def test_der_mandant_geht_in_den_schluessel():
    """Zwei Läufe verschiedener Projekte mit derselben Kennung dürfen sich
    keine Nachweise teilen — die Trennung aus #1703/S4 bleibt fail-closed."""
    from shared.nachweis_lauf import cache_fuer, leeren

    leeren()
    a = cache_fuer("lauf1", "cra", "Mandant A")
    b = cache_fuer("lauf1", "cra", "Mandant B")
    c = cache_fuer("lauf1", "nis2", "Mandant A")
    assert a is not None and a is not b and a is not c
    assert cache_fuer("lauf1", "cra", "Mandant A") is a


def test_jeder_einzel_stream_loest_die_lauf_kennung_auf():
    """Fünf Module, fünf Streams — und ein Weg, der sie alle bedient.

    Fehlt der Aufruf in einem, ist dort der Nachweis-Aufbau weiter je Objekt
    neu; und auffallen würde das nur an der Laufzeit (#1731/#1735).
    """
    for datei in ("server/api/cra/__init__.py", "server/api/nis2.py",
                  "server/api/dsgvo.py", "server/api/aiact.py",
                  "server/api/wiba/__init__.py"):
        programm = python_programm(REPO / datei)
        assert "_lauf_cache" in programm, datei
        assert "nachweis_lauf" in programm, datei


def test_die_massenbewertung_schickt_eine_lauf_kennung():
    from tests.i18n_text import ohne_kommentare

    quelle = ohne_kommentare(
        (REPO / "frontend/src/components/shared/AutoMassBewertungModal.vue")
        .read_text(encoding="utf-8"))
    assert "lauf_id" in quelle


# ── #2081: zwei Zahlen aus einer Abfrage ───────────────────────────────────

def test_die_seitenleiste_laedt_keinen_vollabzug_mehr():
    from tests.i18n_text import ohne_kommentare

    quelle = ohne_kommentare(
        (REPO / "frontend/src/components/sidebars/RisikobewertungSidebar.vue")
        .read_text(encoding="utf-8"))
    assert "fetchRisiken" not in quelle, (
        "GET /risikobewertung ist der Vollabzug aller Risiken aller Mandanten")
    assert "fetchProjekte" in quelle


def test_die_kennzahlen_rechnet_der_server():
    """Im Frontland nachgebaut wäre es die zweite Wahrheit (#1703/S9)."""
    programm = python_programm(REPO / "server/api/risikobewertung.py")
    assert "projekt_statistik" in programm
    assert "load_projekte_rows" in programm
    # ``len(load_risiken(...))`` war ein ``SELECT *``, um Zeilen zu zählen.
    assert "len(load_risiken(DB_PATH, name))" not in programm


def test_der_marker_kommt_als_parameter():
    """Eine zweite Kopie der Zeichenkette hätte den leisen Ausgang aus #1870:
    Der Zähler findet nichts mehr, und das sieht aus wie „nichts markiert"."""
    programm = python_programm(REPO / "risikobewertung/db.py")
    assert "Neubewertung erforderlich" not in programm
    assert "def projekt_statistik" in programm


# ── #2087/2: die Spaltenliste ist abgeleitet ───────────────────────────────

def test_die_schmale_spaltenliste_stimmt_mit_dem_schema():
    """Eine abgetippte Liste wäre die Spiegel-Liste: Eine neue Spalte fehlte
    darin, und die Liste gäbe sie stillschweigend nicht mehr heraus — ein Feld,
    das im Browser zu ``undefined`` wird (#1830)."""
    import re

    from shared.documents.db import OHNE_INHALT, _schema, _spalten_ohne_inhalt

    # Weggelassen wird **nur** der Volltext. Ohne diese Zeile ist der
    # Vergleich darunter tautologisch: Er zieht ``OHNE_INHALT`` auf beiden
    # Seiten ab, und ein zusätzlicher Eintrag ließe die Prüfung grün —
    # genau das zeigte die Gegenprobe (``sha256`` ergänzt → grün).
    assert OHNE_INHALT == ("content_html",), (
        "Nur der Volltext darf fehlen. Jedes weitere weggelassene Feld wird "
        "im Browser still zu ``undefined`` (#1830) — ``sha256`` belegt die "
        "Freigabe, ``created_at``/``updated_at`` stehen in der Liste als "
        "Stand.")
    quelle = _schema("x")
    alle = set(re.findall(r"(?m)^\s{8}([a-z_][a-z0-9_]*)\s+[A-Z]", quelle))
    schmal = set(_spalten_ohne_inhalt().split(", "))
    assert schmal == alle - set(OHNE_INHALT), (
        f"fehlen: {sorted(alle - set(OHNE_INHALT) - schmal)} · "
        f"zu viel: {sorted(schmal - alle)}")
    assert "content_html" not in schmal
    # Die sieben Felder, die der erste Parse-Anlauf verloren hat: ``created_at``
    # fiel durch ``"CREATED_AT".startswith("CREATE")``, ``sha256`` durch einen
    # Namens-Regex ohne Ziffern.
    for pflicht in ("sha256", "created_at", "updated_at", "deleted_at",
                    "created_by", "updated_by", "deleted_by"):
        assert pflicht in schmal, pflicht


def test_catalog_und_liste_laden_den_volltext_nicht():
    programm = python_programm(REPO / "server/api/documents/__init__.py")
    assert programm.count("mit_inhalt=False") >= 2


# ── #2085: der Firmenbericht rechnet die Übersicht einmal ──────────────────

def test_die_firmen_uebersicht_wird_je_anfrage_einmal_gerechnet():
    """Der Gesamtbericht rief sie **zweimal** — ``summary_context`` und
    ``render`` —, und sie kostet gerechnet ≈ 437 Verbindungen je Lauf."""
    import firmen.uebersicht as fu

    n = {"c": 0}
    echt = fu._build_uebersicht

    def gezaehlt(firma):
        n["c"] += 1
        return {"firma": firma}

    fu._build_uebersicht = gezaehlt
    try:
        # Ohne Request-Kontext wird **immer** gerechnet: Zeitplan, CLI, Tests
        # dürfen keinen Stand von vorher sehen.
        fu.build_uebersicht("A")
        fu.build_uebersicht("A")
        assert n["c"] == 2

        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context("/"):
            n["c"] = 0
            fu.build_uebersicht("A")
            fu.build_uebersicht("A")
            fu.build_uebersicht("B")
            assert n["c"] == 2, "A einmal, B einmal"
        with app.test_request_context("/"):
            n["c"] = 0
            fu.build_uebersicht("A")
            assert n["c"] == 1, "eine neue Anfrage rechnet neu"

        # **Der Fall, den die erste Fassung dieses Tests nicht ausgelöst hat.**
        # Zwei ``test_request_context``-Blöcke schieben *zwei* App-Kontexte,
        # und ``g`` ist damit ohnehin leer — die Prüfung lief am Problem
        # vorbei (die Lehre aus #1999: Ein Testwert, der die geprüfte
        # Unterscheidung nicht auslöst, macht den Test zur Behauptung).
        #
        # So sah der echte Fehlschlag aus: **ein** App-Kontext, darin zwei
        # Requests. ``flask.g`` hängt am App-Kontext, überlebte also den
        # ersten Request — ``test_firmen_uebersicht_v7`` bekam nach dem
        # Speichern einer Bewertung den alten Stand (0.0 statt 3.5).
        with app.app_context():
            n["c"] = 0
            with app.test_request_context("/"):
                fu.build_uebersicht("A")
            with app.test_request_context("/"):
                fu.build_uebersicht("A")
            assert n["c"] == 2, (
                "Der Merkzettel hat den Request überlebt — g hängt am "
                "App-Kontext, nicht am Request")
    finally:
        fu._build_uebersicht = echt


def test_ein_fehler_rechnet_nicht_zweimal():
    """Läge die Rechnung im ``try`` um den ``g``-Zugriff, würde ein Fehler
    darin die ganze Übersicht ein zweites Mal rechnen, bevor er nach außen
    kommt — doppelte Last **und** ein verzögerter Fehler."""
    import firmen.uebersicht as fu

    n = {"c": 0}
    echt = fu._build_uebersicht

    def kaputt(firma):
        n["c"] += 1
        raise LookupError("Firma nicht gefunden")

    fu._build_uebersicht = kaputt
    try:
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context("/"):
            with pytest.raises(LookupError):
                fu.build_uebersicht("gibt-es-nicht")
        assert n["c"] == 1
    finally:
        fu._build_uebersicht = echt
