"""``ensure_db`` muss wiederholbar sein (#1771, endgültig).

DER BEFUND
----------
``cra/db._migrate_sbom_unique`` setzte eine Eindeutigkeitsregel mit
``ALTER TABLE … ADD CONSTRAINT``. Das kennt kein ``IF NOT EXISTS``; steht die
Regel schon, schlägt es fehl. Der Fehler **wurde gefangen** — aber in
PostgreSQL ist die Transaktion danach abgebrochen, und mit ihr fiel alles weg,
was ``_migrate_columns`` vorher in derselben Transaktion getan hatte.

**Seit #1771 wurde jede neue Spalte von ``cra_sbom`` angelegt und sofort
wieder verworfen.** Still und dauerhaft — aufgefallen ist es erst, als #1884
mit ``image_digest`` die erste neue Spalte seit damals brachte.

WARUM DIESE TESTS SO AUSSEHEN
-----------------------------
Ein Test, der nur ``image_digest`` prüft, hätte den Fall gefunden und die
**Klasse** nicht. Die Klasse ist: *Der zweite Aufruf von ``ensure_db`` macht
etwas kaputt.* Deshalb prüfen die Tests unten für **alle** Module, dass der
Schemastand nach dem zweiten und dritten Aufruf derselbe ist wie nach dem
ersten — und zwar genau dann, wenn der erste Aufruf die Migrationen
tatsächlich ausgeführt hat.

Dazu ein Wächter gegen das Muster selbst: DDL, das einen Fehler als Normalfall
einplant, braucht einen Savepoint. Das Backup-Modul macht es seit #1785
richtig (``with conn.transaction()``); ``_migrate_sbom_unique`` war die eine
Stelle, die die Lehre nicht hatte.
"""
from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import pytest

import shared.db as sdb

REPO = Path(__file__).resolve().parents[1]

#: (Modulpfad für ``ensure_db``, DB-Pfad, Schemaname). Wächst mit jedem Modul,
#: das eigene Spaltenmigrationen führt.
MODULE: tuple[tuple[str, str, str], ...] = (
    ("cra.db", "data/db/cra.sqlite", "cra"),
    ("firmen.db", "data/db/firmen.sqlite", "firmen"),
    ("ai_act.db", "data/db/ai_act.sqlite", "ai_act"),
    ("dsgvo.db", "data/db/dsgvo.sqlite", "dsgvo"),
    ("nis2.db", "data/db/nis2.sqlite", "nis2"),
    ("wiba.db", "data/db/wiba.sqlite", "wiba"),
)


def _schemastand(db_pfad: str, schema: str) -> dict[str, set[str]]:
    """Tabelle → Spalten, wie der Katalog sie sieht."""
    con = sdb.connect(db_pfad)
    try:
        rows = con.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = ? ORDER BY table_name, column_name",
            (schema,)).fetchall()
    finally:
        con.close()
    out: dict[str, set[str]] = {}
    for r in rows:
        out.setdefault(str(r[0]), set()).add(str(r[1]))
    return out


def _ensure(modulpfad: str, db_pfad: str) -> None:
    """``ensure_db`` wie beim **Prozessstart** — ohne DDL-Cache.

    Ohne das Leeren prüfte dieser Test den Cache statt die Migration: #1396
    vermerkt jede idempotente DDL-Anweisung je Prozess und überspringt sie beim
    zweiten Aufruf. Der Originaldefekt aus #1771 blieb damit unentdeckt — die
    Spalten überlebten, weil der zweite Lauf gar nichts tat.

    Eine Installation startet den Prozess neu; genau das wird hier
    nachgebildet.
    """
    import importlib

    sdb._ensured_ddl.clear()
    sdb._ensured_scripts.clear()
    modul = importlib.import_module(modulpfad)
    modul.ensure_db(Path(db_pfad))


@pytest.mark.parametrize("modulpfad,db_pfad,schema", MODULE,
                         ids=[m[0] for m in MODULE])
def test_ensure_db_ist_wiederholbar(modulpfad, db_pfad, schema):
    """**Der Kern.** Dreimal rufen, und der Stand muss derselbe bleiben.

    Der dritte Aufruf ist nicht Zierde: Beim zweiten steht die
    Eindeutigkeitsregel erstmals schon, und genau dann schlug ``ADD
    CONSTRAINT`` fehl.

    **Was dieser Test nicht findet:** den Defekt aus #1771 selbst. Dort fehlten
    die Spalten nach **jedem** Lauf, also war der Stand gleich — und „gleich"
    ist genau, was hier geprüft wird. Nachgewiesen (Defekt eingebaut, Test
    blieb grün). Dafür ist
    :func:`test_jede_erklaerte_migrationsspalte_existiert` da, das gegen
    ``_COLUMN_MIGRATIONS`` prüft statt gegen den Vorlauf. Beide braucht es:
    Dieser hier fängt die andere Richtung — ein Lauf, der etwas **verwirft**,
    was der vorige angelegt hat.
    """
    _ensure(modulpfad, db_pfad)
    nach_erst = _schemastand(db_pfad, schema)
    assert nach_erst, f"{schema}: keine Tabellen angelegt"

    _ensure(modulpfad, db_pfad)
    nach_zweit = _schemastand(db_pfad, schema)
    _ensure(modulpfad, db_pfad)
    nach_dritt = _schemastand(db_pfad, schema)

    for tabelle, spalten in nach_erst.items():
        fehlend = spalten - nach_zweit.get(tabelle, set())
        assert not fehlend, (
            f"{schema}.{tabelle}: der zweite ensure_db-Lauf hat "
            f"{sorted(fehlend)} verworfen")
        fehlend = spalten - nach_dritt.get(tabelle, set())
        assert not fehlend, (
            f"{schema}.{tabelle}: der dritte ensure_db-Lauf hat "
            f"{sorted(fehlend)} verworfen")


def test_die_migrationsspalten_ueberleben_einen_frischen_lauf():
    """Die Gegenprobe zum Befund: Spalte löschen, ``ensure_db`` rufen, da.

    Das ist der Ablauf, der auf einer Bestandsinstallation stattfindet — und
    der, bei dem die Spalte bis v8.2.3 sofort wieder verschwand.
    """
    import cra.db as cdb

    pfad = "data/db/cra.sqlite"
    cdb.ensure_db(Path(pfad))
    con = sdb.connect(pfad)
    try:
        for spalte in ("image_digest", "digest_geholt_am"):
            con.execute(f"ALTER TABLE cra_sbom DROP COLUMN IF EXISTS {spalte}")
        con.commit()
    finally:
        con.close()

    # Der DDL-Prozess-Cache (#1396) muss weg: Er hat die ALTER-Anweisungen
    # beim ersten Lauf vermerkt und würde sie jetzt überspringen. In einer
    # Installation ist das richtig (der Prozess startet neu); hier simuliert
    # der Test genau diesen Neustart, und ohne das Leeren prüfte er den
    # Cache statt die Migration.
    sdb._ensured_ddl.clear()
    cdb.ensure_db(Path(pfad))
    spalten = _schemastand(pfad, "cra").get("cra_sbom", set())
    assert {"image_digest", "digest_geholt_am"} <= spalten


@pytest.mark.parametrize("tabelle,spalten", [
    (t, [n for n, _ in cols])
    for t, cols in __import__("cra.db", fromlist=["_COLUMN_MIGRATIONS"])
    ._COLUMN_MIGRATIONS.items()
])
def test_jede_erklaerte_migrationsspalte_existiert(tabelle, spalten):
    """Was in ``_COLUMN_MIGRATIONS`` steht, muss nach ``ensure_db`` da sein.

    Eine Migrationsliste, die nicht wirkt, ist schlimmer als keine: Der Code
    verlässt sich auf die Spalte, und der Insert scheitert erst im Betrieb.
    """
    import cra.db as cdb

    cdb.ensure_db(Path("data/db/cra.sqlite"))
    vorhanden = _schemastand("data/db/cra.sqlite", "cra").get(tabelle, set())
    assert vorhanden, f"Tabelle {tabelle} fehlt"
    fehlend = set(spalten) - vorhanden
    assert not fehlend, f"{tabelle}: {sorted(fehlend)} nicht angelegt"


def test_die_eindeutigkeit_wird_nachgesehen_statt_erzwungen():
    """Endgültig behoben ist es ohne die Ausnahme.

    Ein Savepoint fängt die Folgen auf; der Fehler entsteht trotzdem, und ein
    Code, der ihn als Normalfall einplant, lädt zum Weglassen des Savepoints
    ein. ``_constraint_vorhanden`` sieht vorher nach.
    """
    import cra.db as cdb

    cdb.ensure_db(Path("data/db/cra.sqlite"))
    con = sdb.connect("data/db/cra.sqlite")
    try:
        assert cdb._constraint_vorhanden(
            con, "cra_sbom", "cra_sbom_projekt_release_format_artefakt_key")
        assert not cdb._constraint_vorhanden(con, "cra_sbom", "gibt_es_nicht")
    finally:
        con.close()


# ── Der Wächter gegen das Muster selbst ─────────────────────────────────────

def _ohne_kommentare(text: str) -> str:
    """Nur die **Kommentare** weg — das Programm prüfen, nicht die Erzählung
    (#1834/#1867/#1878).

    Zeichenketten bleiben: In ihnen steht die SQL-Anweisung, und genau die ist
    hier der Gegenstand.

    ``untokenize`` statt ``" ".join(...)``: Der erste Anlauf fügte zwischen
    allen Tokens ein Leerzeichen ein, und damit war aus
    ``conn.transaction()`` ``conn . transaction ( )`` geworden — der Wächter
    fand die Absicherung nicht und beanstandete ``shared/backup/datenbank.py``,
    das sie seit #1785 hat. Ein Fehlalarm auf eine korrekte Stelle macht einen
    Wächter unglaubwürdig (die Lehre aus dem ersten Anlauf von #1805).
    """
    behalten = [tok for tok in tokenize.generate_tokens(io.StringIO(text).readline)
                if tok.type != tokenize.COMMENT]
    try:
        return tokenize.untokenize(behalten)
    except Exception:  # noqa: BLE001 — dann lieber der Rohtext als nichts
        return text


def _python_dateien() -> list[Path]:
    aus = ("tests", "node_modules", ".git", "frontend", "build", "dist",
           "scratchpad", ".venv")
    return [p for p in REPO.rglob("*.py")
            if not any(teil in aus for teil in p.relative_to(REPO).parts)]


def test_kein_gefangenes_ddl_ohne_savepoint():
    """DDL, dessen Fehlschlag eingeplant ist, braucht einen Savepoint.

    **Die Fehlerklasse:** In PostgreSQL lässt eine Transaktion nach einem
    Fehler keinen weiteren Befehl mehr zu. Ein gefangener DDL-Fehler nimmt
    deshalb alles mit, was in derselben Transaktion schon getan wurde — und
    das fällt nicht auf, weil nichts fehlschlägt.

    Das Backup-Modul kennt die Lehre seit #1785 (``with conn.transaction()``);
    ``_migrate_sbom_unique`` war die Stelle, die sie nicht hatte. Dieser
    Wächter findet die nächste.

    Gesucht wird nach ``ADD CONSTRAINT``/``ADD PRIMARY KEY``/``ADD UNIQUE``
    (ohne ``IF NOT EXISTS``, das es dafür nicht gibt) in einer Datei, die
    weder ``SAVEPOINT`` noch ``conn.transaction()`` kennt.
    """
    riskant = re.compile(r"ADD\s+(?:CONSTRAINT|PRIMARY\s+KEY|UNIQUE)\b",
                         re.IGNORECASE)
    befunde: list[str] = []
    for datei in _python_dateien():
        text = datei.read_text(encoding="utf-8", errors="ignore")
        if not riskant.search(text):
            continue
        programm = _ohne_kommentare(text)
        if "SAVEPOINT" in programm or ".transaction()" in programm:
            continue
        befunde.append(str(datei.relative_to(REPO)))
    assert befunde == [], (
        "riskantes DDL ohne Savepoint — ein gefangener Fehler reißt in "
        f"PostgreSQL die ganze Transaktion auf: {befunde}")


def test_die_vorab_pruefung_ist_verdrahtet():
    """Ein Wächter, der nur die Datei liest, prüft die Verdrahtung nicht."""
    import inspect

    import cra.db as cdb

    programm = _ohne_kommentare(inspect.getsource(cdb._migrate_sbom_unique))
    assert "_constraint_vorhanden" in programm
    assert "SAVEPOINT" in inspect.getsource(cdb._migrate_sbom_unique)
