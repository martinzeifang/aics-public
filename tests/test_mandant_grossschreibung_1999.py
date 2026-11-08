"""Der Mandant wird auch bei Großschreibung aufgelöst (#1999).

DER BEFUND
``shared.firmen_link.firma_des_projekts`` ging den Rückweg ID → Firma über
``firmen_name_to_id`` und ``load_firma``. Die Abbildung liefert
``name.casefold()`` als Schlüssel (so steht es in ihrem Docstring),
``load_firma`` sucht über ``WHERE name = ?`` — also genau. Aufgelöst wurde damit
**nur**, wessen Firmenname schon durchgehend kleingeschrieben war.

Gemessen auf aics-test, bevor das behoben war::

    projekt_firmen_id(cra.sqlite, "AI Compliance Suite")  → 3
    firmen_name_to_id(firmen.sqlite)                      → {'firma cyberwoks': 3}
    load_firma(firmen.sqlite, 'firma cyberwoks')          → None
    load_firma(firmen.sqlite, 'Firma Cyberwoks')          → Datensatz

WAS DADURCH NICHT WIRKTE
Die Herstellerangaben der EU-Konformitätserklärung nach Anhang V Nr. 2 (#1887)
und der Briefkopf der Dokument-Vorlagen (#1997). Beides blieb leer und sah aus
wie „beim Mandanten nicht erfasst" — die Klasse aus #1805/#1870: Nichts schlägt
fehl, es wird nur das Falsche gelesen.

WARUM DER BESTEHENDE RUNDLAUF ES NICHT FAND
``tests/test_firmen_anschrift_1892.py`` ist genau dafür geschrieben und war
grün — seine Testfirma hieß ``pytest-anschrift-1892``, also durchgehend klein.
Der Test prüfte den Pfad, auf dem der Fehler nicht liegt. Die Namen dort tragen
jetzt Großbuchstaben; **ohne diese Änderung ist dieser Defekt nicht haltbar**.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from firmen import db as fdb

#: Großbuchstaben **und** ein Leerzeichen — beides kommt in echten Firmennamen
#: vor, und ``casefold`` trifft nur das erste. Dass „Firma Cyberwoks" auf
#: Produktiv genau so heißt, ist der Grund, warum es dort aufgefallen ist.
FIRMA = "Pytest Mandant GROSS 1999"
PROJEKT = "pytest-mandant-1999-cra"
CRA_DB = Path("data/db/cra.sqlite")


@pytest.fixture
def firma(pg):
    fdb.ensure_db(fdb.DEFAULT_DB_PATH)
    fdb.hard_delete_firma(fdb.DEFAULT_DB_PATH, FIRMA)
    fdb.save_firma(fdb.DEFAULT_DB_PATH, FIRMA,
                   unternehmen="Pytest Mandant GmbH", rechtsform="GmbH",
                   anschrift="Beispielweg 7", plz="12345", ort="Musterstadt",
                   land="Deutschland", vertreter_name="B. Person",
                   vertreter_funktion="Geschäftsführung")
    yield FIRMA
    fdb.hard_delete_firma(fdb.DEFAULT_DB_PATH, FIRMA)


@pytest.fixture
def projekt(firma):
    from cra import db as cdb

    cdb.ensure_db(CRA_DB)
    cdb.delete_projekt(CRA_DB, PROJEKT)
    cdb.save_projekt(CRA_DB, PROJEKT, unternehmen=FIRMA, produkt="Testprodukt")
    yield PROJEKT
    cdb.delete_projekt(CRA_DB, PROJEKT)


# ── Die Grundfunktion ───────────────────────────────────────────────────────

def test_load_firma_by_id_findet_die_firma(firma):
    """Über den Primärschlüssel gibt es keine Schreibweise, die danebengeht."""
    kennung = fdb.firmen_zeilen(fdb.DEFAULT_DB_PATH, q=FIRMA)
    treffer = [z for z in kennung if z.get("name") == FIRMA]
    assert treffer, "die Testfirma wurde nicht angelegt"
    fid = treffer[0]["id"]

    rec = fdb.load_firma_by_id(fdb.DEFAULT_DB_PATH, fid)
    assert rec is not None and rec["name"] == FIRMA
    assert rec["ort"] == "Musterstadt"
    # Aufbereitet wie bei `load_firma` — eine zweite Aufbereitung desselben
    # Datensatzes wäre die zweite Wahrheit über seine Form.
    assert isinstance(rec.get("meta"), dict)
    assert isinstance(rec.get("frameworks"), list)


def test_load_firma_by_id_vertraegt_unsinn(firma):
    assert fdb.load_firma_by_id(fdb.DEFAULT_DB_PATH, None) is None
    assert fdb.load_firma_by_id(fdb.DEFAULT_DB_PATH, "keine zahl") is None
    assert fdb.load_firma_by_id(fdb.DEFAULT_DB_PATH, 99999999) is None


# ── DER RUNDLAUF, um den es geht ────────────────────────────────────────────

def test_der_mandant_wird_bei_grossschreibung_aufgeloest(projekt):
    """**Der Kern.** Derselbe Aufruf, der auf aics-test leer zurückkam."""
    from shared.firmen_link import firma_des_projekts

    f = firma_des_projekts(CRA_DB, PROJEKT)
    assert f, "der Mandant wurde nicht aufgelöst"
    assert f["name"] == FIRMA
    assert f["ort"] == "Musterstadt"
    assert f["vertreter_name"] == "B. Person"


def test_die_erklaerung_bekommt_die_herstellerangaben(projekt):
    """Strecke 1 — EU-Konformitätserklärung, Anhang V Nr. 2 (#1887)."""
    from cra.doc_vorschlag import vorschlag

    v = vorschlag(CRA_DB, PROJEKT, "")
    assert v.get("firma") == FIRMA
    assert v["felder"].get("hersteller_adresse"), "die Anschrift kam nicht an"
    assert "Musterstadt" in v["felder"]["hersteller_adresse"]["wert"]
    assert v["felder"]["unterzeichner_name"]["wert"] == "B. Person"
    assert v["felder"]["ort"]["wert"] == "Musterstadt"


def test_die_dokumentvorlage_bekommt_den_briefkopf(projekt):
    """Strecke 2 — Word-Vorlagen der Modul-Dokumente (#1997).

    Gemeldet hatte sich das als leere Kopfzeile am Dokument
    „Benutzerinformationen/-anleitung (Annex II)" auf aics-test, obwohl der
    Mandant Firmierung und Anschrift trug.
    """
    from shared.documents import vorlage as dv

    doc = {"titel": "Benutzerinformationen", "doc_type": "benutzeranleitung_annex_ii",
           "status": "entwurf", "version": 1, "content_html": "<p>Text.</p>", "meta": {}}
    ctx = dv.kontext("cra", PROJEKT, doc, module_db=CRA_DB)

    assert ctx["firma"]["unternehmen"] == "Pytest Mandant GmbH"
    assert ctx["firma"]["rechtsform"] == "GmbH"
    assert ctx["firma"]["ort"] == "Musterstadt"
    # Der Briefkopf ist die Zeile, die im Dokument steht.
    assert "Pytest Mandant GmbH" in ctx["firma"]["anschrift_text"]
    assert "12345 Musterstadt" in ctx["firma"]["anschrift_text"]
    assert ctx["firma"]["vertreter_funktion"] == "Geschäftsführung"


# ── Wächter ─────────────────────────────────────────────────────────────────

def test_die_aufloesung_geht_nicht_mehr_ueber_kleingeschriebene_schluessel():
    """``firmen_name_to_id`` liefert ``casefold``-Schlüssel.

    Sie taugen zum Nachschlagen Name → ID (dort wird der Name selbst
    kleingeschrieben verglichen), **nicht** für den Rückweg ID → Firma. Geprüft
    wird das Programm über den Syntaxbaum, nicht die Erzählung (#1834).
    """
    import ast

    quelle = Path("shared/firmen_link.py").read_text(encoding="utf-8")
    fn = next(k for k in ast.walk(ast.parse(quelle))
              if isinstance(k, ast.FunctionDef) and k.name == "firma_des_projekts")
    # **Den Docstring abschneiden.** `ast.unparse` nimmt ihn mit, und er
    # erklärt den alten Weg — der Wächter schlug beim ersten Anlauf auf seine
    # eigene Begründung an. Genau die Falle, die er zitiert (#1834/#1867/#1878):
    # das Programm prüfen, nicht die Erzählung.
    if (fn.body and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)
            and isinstance(fn.body[0].value.value, str)):
        fn.body = fn.body[1:]
    code = ast.unparse(fn)
    assert "firmen_name_to_id" not in code, (
        "firma_des_projekts löst wieder über die casefold-Schlüssel auf (#1999)")
    assert "load_firma_by_id" in code


def test_der_bestandstest_nutzt_einen_namen_mit_grossbuchstaben():
    """Ohne das prüft #1892 den Pfad, auf dem der Fehler nicht liegt.

    Das ist die eigentliche Lehre dieses Defekts: Der Rundlauf war da, war grün
    und traf die Verwechslung nicht — weil sein Testwert sie nicht auslöst.
    """
    quelle = Path("tests/test_firmen_anschrift_1892.py").read_text(encoding="utf-8")
    zeile = next(z for z in quelle.splitlines() if z.startswith("FIRMA = "))
    wert = zeile.split("=", 1)[1].strip().strip('"')
    assert wert != wert.casefold(), (
        f"FIRMA = {wert!r} ist durchgehend klein — damit kann der Rundlauf den "
        f"casefold-Fehler nicht finden (#1999).")
