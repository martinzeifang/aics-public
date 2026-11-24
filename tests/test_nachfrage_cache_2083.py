"""``ensure_db`` bleibt wiederholbar — gecacht wird nur die Nachfrage (#2083).

DER BEFUND
----------
Die DDL in ``ensure_db`` ist seit #1396 prozessweit gecacht. Zwei Stellen
machen darin trotzdem **echte** Abfragen, die der DDL-Cache nicht erfasst:

* ``cra.db._constraint_vorhanden`` liest ``pg_constraint`` (21 Leser im Modul),
* ``evidence/db.py`` vier Mal ``information_schema.columns`` (19 Leser).

Gemessen am 09.11.2026: 25 Durchläufe ``cra.ensure_db`` + ``evidence.ensure_db``
brauchten **0,139 s** ohne und **0,018 s** mit dem Cache — Faktor 7,7, und das
auf *localhost*; über ein Netz ist der Abstand größer.

DER ERSTE ANLAUF WAR DAS FALSCHE WERKZEUG — UND DIESER TEST HÄLT IHN FEST
-------------------------------------------------------------------------
Er legte einen ``@nur_einmal``-Decorator über **55** ``ensure_*``-Funktionen.
Das spart mehr Verbindungen und macht aus einer dokumentierten Invariante eine
Reihenfolgefrage:

* ``ensure_db`` ist der **Träger der Migrationen** (CLAUDE.md: „neue Spalten in
  das Inline-``SCHEMA`` *und* in ``_COLUMN_MIGRATIONS``"). Wird der zweite
  Aufruf übersprungen, fehlt die Spalte — und der Insert dagegen ist ein
  Laufzeitfehler, kein Startfehler.
* ``server/auth/users_db`` hat seinen **eigenen** Cache mit ausdrücklichem
  Bust-Haken (``_ENSURED_PATHS``); ein zweiter Cache darüber macht den Haken
  wirkungslos.
* ``shared/backup`` legt beim **Einspielen** Schemata im selben Prozess neu an
  („erst die Anwendung legt ihr Schema an"). Ein Cache, der das überspringt,
  schreibt in ein Schema, das gerade gedroppt wurde.

Zwei Wächter sind sofort rot geworden (``test_migration_wiederholbar_1771``,
``test_users_db``). Die Stellen **ohne** Wächter wären still geblieben — und
genau das ist die Fehlerklasse, von der dieses Repo lebt: Nichts schlägt fehl,
es wird nur das Falsche gelesen (#1805/#1870/#1984).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.i18n_text import python_programm

REPO = Path(__file__).resolve().parents[1]


def test_kein_decorator_ueber_ensure_funktionen():
    """Der Rückbau bleibt zurückgebaut.

    Geprüft wird das **Programm**, nicht die Erzählung (``python_programm``
    entfernt Kommentare und Docstrings) — sonst genügte dieser Dateikopf, um
    den Wächter zu befriedigen oder zu brechen (#1834/#1867/#1974).
    """
    treffer: list[str] = []
    for pfad in sorted(REPO.glob("*/db.py")) + sorted(REPO.glob("*/*_db.py")):
        if "node_modules" in pfad.parts or pfad.parts[-2] == "tests":
            continue
        try:
            programm = python_programm(pfad)
        except SyntaxError:
            continue
        if "nur_einmal" in programm:
            treffer.append(str(pfad.relative_to(REPO)))
    assert not treffer, (
        "ensure_db ist der Träger der Migrationen und darf nicht pauschal "
        f"gecacht werden: {treffer}")


def test_die_entwertung_haengt_an_denselben_haken_wie_der_ddl_cache():
    """Ein Cache mit eigenem Lebenszyklus ist eine zweite Invariante.

    Entscheidend ist nicht eine Namensliste, sondern die **Kopplung**: Wo der
    DDL-Cache entwertet wird, muss auch der Nachfrage-Cache entwertet werden.
    Beide beantworten dieselbe Frage („steht die Struktur schon?"), also
    dürfen sie nicht verschieden lange gelten.

    Dass es ``reset_pool`` und ``drop_stale_test_schemas`` sind und **nicht**
    ``drop_test_schemas``, ist kein Versehen: Letzteres **truncatet** nur
    (#1396) — die Tabellen bleiben stehen, und genau deshalb bleibt der
    Cache gültig. Beim Schreiben dieses Tests habe ich das Gegenteil
    angenommen und ihn dafür rot gesehen; die Vermutung stand im Docstring,
    nicht im Programm.
    """
    quelle = python_programm(REPO / "shared/db.py")
    baum = ast.parse(quelle)
    gefunden: set[str] = set()
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.FunctionDef):
            continue
        rumpf = ast.unparse(knoten)
        if "_ensured_ddl.clear()" in rumpf:
            assert "_ensured_nachfrage.clear()" in rumpf, (
                f"{knoten.name} entwertet den DDL-Cache, aber nicht den "
                "Nachfrage-Cache")
            gefunden.add(knoten.name)
    assert gefunden >= {"reset_pool", "drop_stale_test_schemas"}, gefunden


def test_bei_einem_fehlschlag_wird_nichts_vermerkt():
    """Sonst gälte eine Migration als gelaufen, die abgebrochen ist."""
    from shared import db as sdb

    quelle = python_programm(REPO / "cra/db.py")
    baum = ast.parse(quelle)
    fn = next(k for k in ast.walk(baum)
              if isinstance(k, ast.FunctionDef) and k.name == "_vermerken")
    # ``_vermerken`` wird im ``try`` **nach** dem erfolgreichen ALTER gerufen
    # und im ``except`` nicht.
    migr = next(k for k in ast.walk(baum)
                if isinstance(k, ast.FunctionDef)
                and k.name == "_migrate_sbom_unique")
    for versuch in [k for k in ast.walk(migr) if isinstance(k, ast.Try)]:
        for handler in versuch.handlers:
            assert "_vermerken(" not in ast.unparse(handler), (
                "_vermerken im except — ein Fehlschlag darf nicht als "
                "erledigt gelten")
    assert fn is not None
    assert hasattr(sdb, "nachfrage_vermerken")


@pytest.mark.parametrize("modul,marke", [
    ("cra/db.py", "cra.sbom_unique"),
    ("evidence/db.py", "evidence.kunden_id_umbenannt"),
])
def test_die_teure_nachfrage_ist_gecacht(modul, marke):
    """Die beiden Stellen, die der DDL-Cache nicht erfasst."""
    programm = python_programm(REPO / modul)
    assert "nachfrage_erledigt" in programm, modul
    assert marke in programm, modul


def test_ensure_db_legt_nach_einem_drop_wieder_an(tmp_path):
    """Der Rundlauf, nicht die Behauptung (die Lehre aus #1785).

    Der Cache darf eine gedroppte Struktur nicht als vorhanden ausweisen.
    """
    pytest.importorskip("psycopg")
    from shared import db as sdb
    import cra.db as cdb

    db = tmp_path / "cra_nachfrage_2083.sqlite"
    cdb.ensure_db(db)
    assert sdb.nachfrage_erledigt(db, "cra.sbom_unique")
    # Der Haken, der die Struktur wirklich wegnimmt (``drop_test_schemas``
    # truncatet nur) — danach muss ``ensure_db`` sie wieder anlegen.
    with sdb._ensured_lock:
        sdb._ensured_nachfrage.clear()
        sdb._ensured_ddl.clear()
        sdb._ensured_scripts.clear()
    assert not sdb.nachfrage_erledigt(db, "cra.sbom_unique")
    sdb.drop_schema(db)
    cdb.ensure_db(db)
    con = sdb.connect(db)
    try:
        zeile = con.execute(
            "SELECT 1 FROM pg_constraint WHERE conname = "
            "'cra_sbom_projekt_release_format_artefakt_key'").fetchone()
    finally:
        con.close()
    assert zeile, "Die Eindeutigkeit fehlt nach dem erneuten ensure_db"
