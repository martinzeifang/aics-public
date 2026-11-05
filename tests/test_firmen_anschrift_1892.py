"""Die Anschrift gehört dem Mandanten (#1892).

``firmen`` führte Name, Unternehmen, Beschreibung und Berater — **keine
Anschrift**. Gebraucht wird sie überall: CRA Anhang V Nr. 2, KI-VO Anhang V,
DSGVO Art. 30 Abs. 1 lit. a, jeder Briefkopf. Getippt wurde sie je Modul und
je Projekt erneut, und beim vierten Produkt steht dann eine andere da.

#1887 hat sie notdürftig unter ``firmen.meta.hersteller`` abgelegt — richtige
Ebene, falscher Ort: ``meta_json`` erscheint in keiner Firmenmaske, und der
nächste, der die Anschrift braucht, legt eine zweite Kopie an. Das ist die
Spiegel-Liste aus #1731/#1735, nur in den Stammdaten.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from firmen import db as fdb

FIRMA = "pytest-anschrift-1892"
FIRMA_ALT = "pytest-anschrift-1892-alt"
FRONTEND = Path(__file__).resolve().parents[1] / "frontend/src"


@pytest.fixture
def firma():
    fdb.ensure_db(fdb.DEFAULT_DB_PATH)
    for name in (FIRMA, FIRMA_ALT):
        fdb.hard_delete_firma(fdb.DEFAULT_DB_PATH, name)
    fdb.save_firma(fdb.DEFAULT_DB_PATH, FIRMA, unternehmen="Beispiel AG")
    yield FIRMA
    for name in (FIRMA, FIRMA_ALT):
        fdb.hard_delete_firma(fdb.DEFAULT_DB_PATH, name)


# ── Die Spalten gibt es ─────────────────────────────────────────────────────

@pytest.mark.parametrize("feld", fdb.ANSCHRIFT_FELDER)
def test_jedes_anschriftsfeld_ist_speicherbar(firma, feld):
    fdb.save_firma(fdb.DEFAULT_DB_PATH, firma, **{feld: "Wert"})
    assert (fdb.load_firma(fdb.DEFAULT_DB_PATH, firma) or {}).get(feld) == "Wert"


def test_die_felder_stehen_in_der_erlaubten_liste():
    """``save_firma`` filtert gegen ``_ALLOWED_FIELDS``; ein Feld, das dort
    fehlt, wird **still** verworfen — das Speichern meldet Erfolg und bewirkt
    nichts (die Form aus #1805)."""
    assert set(fdb.ANSCHRIFT_FELDER) <= fdb._ALLOWED_FIELDS


def test_teil_update_leert_die_uebrigen_angaben_nicht(firma):
    """Die Falle aus #1540/#1771/#1805 — der Schutz gehört in die
    Speicherfunktion, nicht in jeden Aufrufer."""
    fdb.save_firma(fdb.DEFAULT_DB_PATH, firma, anschrift="Weg 1", ort="Ort",
                   vertreter_name="A. Person")
    fdb.save_firma(fdb.DEFAULT_DB_PATH, firma, ort="Anderer Ort")
    d = fdb.load_firma(fdb.DEFAULT_DB_PATH, firma) or {}
    assert d.get("anschrift") == "Weg 1"
    assert d.get("vertreter_name") == "A. Person"
    assert d.get("ort") == "Anderer Ort"


# ── Eine Stelle für die Formatierung ────────────────────────────────────────

def test_der_briefkopf_entsteht_an_einer_stelle():
    assert fdb.anschrift_text({
        "unternehmen": "Beispiel AG", "rechtsform": "GmbH",
        "anschrift": "Weg 1", "plz": "00000", "ort": "Ort",
        "land": "Deutschland",
    }) == "Beispiel AG GmbH\nWeg 1\n00000 Ort\nDeutschland"


def test_leere_teile_entfallen_ohne_platzhalter():
    """Eine halbe Anschrift ist eine halbe Angabe und soll als solche
    erkennbar sein — nicht als „[fehlt]" im Briefkopf."""
    text = fdb.anschrift_text({"unternehmen": "Beispiel AG", "ort": "Ort"})
    assert text == "Beispiel AG\nOrt"
    assert "[" not in text


def test_ohne_angaben_ein_leerer_text():
    assert fdb.anschrift_text({}) == ""
    assert fdb.anschrift_text(None) == ""


# ── Der Umzug aus meta.hersteller ───────────────────────────────────────────

def _umzug():
    """Den Umzug anstoßen, ohne den Prozess-Cache zu treffen.

    ``ensure_db`` ruft ihn **je Prozess einmal** — es läuft pro Request und
    pro Test, und ein ``SELECT`` über alle Firmen bei jedem Aufruf wäre ein
    Dauerzuschlag für eine Migration, die genau einmal etwas zu tun hat
    (#1396). Für den Test ist genau dieser Cache im Weg: Er würde beim zweiten
    Aufruf im selben Prozess nichts mehr sehen.
    """
    con = fdb._connect(fdb.DEFAULT_DB_PATH)
    try:
        fdb._migriere_hersteller_jetzt(con)
        con.commit()
    finally:
        con.close()


def test_ensure_db_stoesst_den_umzug_an():
    """Die Verdrahtung selbst — sonst wäre der Umzug eine Funktion, die
    niemand ruft."""
    import inspect

    assert "_migrate_hersteller_meta" in inspect.getsource(fdb.ensure_db)


def test_der_umzug_holt_die_alten_angaben_in_die_spalten(firma):
    """#1887 legte sie in ``meta`` ab; der Umzug holt sie idempotent."""
    fdb.save_firma(fdb.DEFAULT_DB_PATH, firma, meta={"hersteller": {
        "anschrift": "Altweg 9", "ort": "Altort",
        "unterzeichner_name": "B. Person",
        "unterzeichner_funktion": "Geschäftsführung"}})
    _umzug()
    d = fdb.load_firma(fdb.DEFAULT_DB_PATH, firma) or {}
    assert d.get("anschrift") == "Altweg 9"
    assert d.get("ort") == "Altort"
    assert d.get("vertreter_name") == "B. Person"
    assert d.get("vertreter_funktion") == "Geschäftsführung"


def test_der_umzug_ueberschreibt_keinen_gesetzten_wert(firma):
    fdb.save_firma(fdb.DEFAULT_DB_PATH, firma, anschrift="Neuweg 1",
                   meta={"hersteller": {"anschrift": "Altweg 9"}})
    _umzug()
    assert (fdb.load_firma(fdb.DEFAULT_DB_PATH, firma) or {}).get("anschrift") == "Neuweg 1"


def test_der_umzug_laesst_meta_stehen(firma):
    """Eine Installation, die zwischen zwei Versionen springt, soll die
    Angaben noch finden; gelesen werden sie nur noch als Rückfall."""
    fdb.save_firma(fdb.DEFAULT_DB_PATH, firma,
                   meta={"hersteller": {"anschrift": "Altweg 9"}})
    _umzug()
    d = fdb.load_firma(fdb.DEFAULT_DB_PATH, firma) or {}
    assert (d.get("meta") or {}).get("hersteller", {}).get("anschrift") == "Altweg 9"


def test_der_umzug_ist_idempotent(firma):
    fdb.save_firma(fdb.DEFAULT_DB_PATH, firma,
                   meta={"hersteller": {"ort": "Altort"}})
    _umzug()
    _umzug()
    assert (fdb.load_firma(fdb.DEFAULT_DB_PATH, firma) or {}).get("ort") == "Altort"


# ── CRA liest die Spalten, meta bleibt Rückfall ─────────────────────────────

def test_cra_liest_die_spalten(firma):
    from cra.doc_vorschlag import hersteller_stammdaten

    fdb.save_firma(fdb.DEFAULT_DB_PATH, firma, anschrift="Weg 1", plz="00000",
                   ort="Ort", land="Deutschland", vertreter_name="A. Person",
                   vertreter_funktion="Geschäftsführung")
    stamm = hersteller_stammdaten(fdb.load_firma(fdb.DEFAULT_DB_PATH, firma))
    assert "Weg 1" in stamm["anschrift"] and "00000 Ort" in stamm["anschrift"]
    assert stamm["unterzeichner_name"] == "A. Person"
    assert stamm["unterzeichner_funktion"] == "Geschäftsführung"


def test_cra_faellt_auf_meta_zurueck():
    """Ohne Spaltenwerte gilt der Bestand aus #1887."""
    from cra.doc_vorschlag import hersteller_stammdaten

    stamm = hersteller_stammdaten({
        "meta": {"hersteller": {"anschrift": "Altweg 9", "ort": "Altort"}}})
    assert stamm["anschrift"] == "Altweg 9"
    assert stamm["ort"] == "Altort"


def test_die_spalte_hat_vorrang_vor_meta():
    from cra.doc_vorschlag import hersteller_stammdaten

    stamm = hersteller_stammdaten({
        "ort": "Neuort",
        "meta": {"hersteller": {"ort": "Altort"}}})
    assert stamm["ort"] == "Neuort"


def test_der_hersteller_endpunkt_schreibt_keine_meta_mehr():
    """Wächter: Zwei Orte für dieselbe Angabe wären die Doppelpflege, die
    #1892 beendet."""
    quelle = (Path(__file__).resolve().parents[1]
              / "server/api/cra_konformitaet.py").read_text(encoding="utf-8")
    block = quelle.split("def put_hersteller", 1)[1].split("@cra_konformitaet_bp", 1)[0]
    assert 'meta["hersteller"]' not in block
    assert "save_firma" in block


# ── Oberfläche ──────────────────────────────────────────────────────────────

def test_die_firmenmaske_zeigt_die_anschrift():
    """Der Grund, warum ``meta_json`` der falsche Ort war: Es erschien in
    keiner Maske."""
    view = (FRONTEND / "views/firmen/FirmenView.vue").read_text(encoding="utf-8")
    for feld in ("anschrift", "plz", "ort", "land", "rechtsform",
                 "vertreter_name", "vertreter_funktion"):
        assert f'v-model="form.{feld}"' in view, feld


def test_der_endpunkt_gibt_die_anschrift_heraus():
    """Eine Positivliste gibt die Rohspalte nicht von selbst heraus — der
    Fehler aus #1858 (``meta_json`` bei AI Act)."""
    api = (Path(__file__).resolve().parents[1]
           / "server/api/firmen.py").read_text(encoding="utf-8")
    assert "ANSCHRIFT_FELDER" in api
    assert "anschrift_text" in api


def test_der_formatierer_wird_nicht_nachgebaut():
    """Zeilenumbrüche je Modul wären verschiedene Briefköpfe desselben
    Mandanten."""
    treffer = []
    for datei in FRONTEND.rglob("*.vue"):
        text = datei.read_text(encoding="utf-8")
        if "plz" in text and "land" in text and "join" in text.lower() \
                and datei.name != "FirmenView.vue":
            treffer.append(str(datei.relative_to(FRONTEND)))
    assert treffer == [], f"eigene Anschrift-Formatierung in {treffer}"


# ── Der Rundlauf, der den verschluckten Fehler gefunden hat ─────────────────

def test_der_vorschlag_loest_den_mandanten_wirklich_auf(firma):
    """**Der Fehler, den dieser Test gefunden hat.**

    ``cra/doc_vorschlag._firma_des_projekts`` importierte
    ``firmen.db.DB_PATH`` — das Modul heißt dort ``DEFAULT_DB_PATH``. Der
    ``_sicher``-Wrapper fing den ``ImportError`` mit, also wurde der Mandant
    **nie** aufgelöst: Die Herstellerangaben blieben leer, und nichts schlug
    fehl. Genau die Fehlerklasse aus #1805/#1870 — es wird das Falsche
    gelesen, und es sieht aus wie „nichts erfasst".

    Ein Test über ``hersteller_stammdaten`` allein hätte es nicht gefunden:
    Die Funktion ist richtig, nur bekam sie nie eine Firma. Deshalb der
    **Rundlauf** über ``vorschlag()`` (die Lehre aus #1785).
    """
    from cra import db as cdb
    from cra.doc_vorschlag import vorschlag

    CRA_DB = Path("data/db/cra.sqlite")
    projekt = "pytest-anschrift-1892-cra"
    cdb.ensure_db(CRA_DB)
    cdb.delete_projekt(CRA_DB, projekt)
    try:
        fdb.save_firma(fdb.DEFAULT_DB_PATH, firma, anschrift="Weg 1",
                       plz="00000", ort="Ort", vertreter_name="A. Person",
                       vertreter_funktion="Geschäftsführung")
        cdb.save_projekt(CRA_DB, projekt, unternehmen=firma,
                         produkt="Testprodukt")
        v = vorschlag(CRA_DB, projekt, "")
        assert v.get("firma") == firma, "der Mandant wurde nicht aufgelöst"
        assert v["felder"].get("hersteller_adresse"), "die Anschrift kam nicht an"
        assert v["felder"]["unterzeichner_name"]["wert"] == "A. Person"
        assert v["felder"]["ort"]["wert"] == "Ort"
    finally:
        cdb.delete_projekt(CRA_DB, projekt)


def test_ein_programmierfehler_wird_nicht_verschluckt():
    """Die Gegenrichtung: ``_sicher`` lässt ``ImportError`` und
    ``AttributeError`` durch, weil sie keine Datenzustände sind."""
    from cra import doc_vorschlag as dv

    quelle = __import__("inspect").getsource(dv.vorschlag)
    assert "except (ImportError, AttributeError):" in quelle
