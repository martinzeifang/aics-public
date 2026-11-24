"""Die Sicherung erfasst die ganze Installation — und läuft zurück (#1785).

Bis v8.0.4 sammelte ``create_backup`` ``data/db/*.sqlite`` ein. Die Suite läuft
seit Juni 2026 auf PostgreSQL; die Dateien im Volume waren tote Reste. Auf der
Produktivinstallation enthielt ein Archiv vom Oktober den Stand vom Juni, und
ein Restore daraus meldete Erfolg, ohne etwas zu ändern.

Diese Tests halten fest, was eine Sicherung können muss, damit sie eine ist.
Der wichtigste ist :func:`test_rundlauf_in_leere_datenbank` — er spielt ein
Archiv in eine **leere** Datenbank ein, also in die Lage nach einer
Neuinstallation, und vergleicht anschließend den Inhalt. Fünf Fehler sind genau
dabei aufgefallen und nirgends sonst:

* die Funktion ``aics_now()`` fehlte, ohne die sich keine Tabelle anlegen lässt,
* CSV schrieb die leere Zeichenkette wie NULL (stille Veränderung der Daten),
* eine inzwischen zur Pflicht gewordene Spalte ließ das Einspielen scheitern,
* ``GENERATED ALWAYS``-Schlüssel ließen sich nicht zurückschreiben,
* Sequenzstände blieben auf 1, womit die erste neue Zeile kollidiert wäre.
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

import psycopg
import pytest


def _dsn_mit_datenbank(name: str) -> str:
    basis = os.environ["DATABASE_URL"]
    return basis.rsplit("/", 1)[0] + "/" + name


@pytest.fixture
def probe_schema(pg):
    """Ein Schema mit den Eigenheiten, die in dieser Anwendung vorkommen."""
    from shared.db import connect

    con = connect("data/db/pytest_backup_1785.sqlite")
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS probe_daten (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name TEXT NOT NULL,
            notiz TEXT NOT NULL DEFAULT '',
            zahl INTEGER,
            erstellt TEXT DEFAULT aics_now()
        )
    """)
    cur.execute(
        "INSERT INTO probe_daten (name, notiz, zahl) VALUES (?, ?, ?)",
        ("mit leerem Text", "", 1))
    cur.execute(
        "INSERT INTO probe_daten (name, notiz, zahl) VALUES (?, ?, ?)",
        ("mit NULL", "etwas", None))
    con.commit()
    con.close()
    return "pytest_backup_1785"


def test_archiv_enthaelt_datenbank_dateien_und_konfiguration(tmp_path, probe_schema,
                                                             monkeypatch):
    from shared.backup import erstelle_backup, paket

    daten = tmp_path / "daten"
    (daten / "templates").mkdir(parents=True)
    (daten / "templates" / "vorlage.docx").write_bytes(b"PK\x03\x04 vorlage")
    (daten / "gutachten" / "final_exports").mkdir(parents=True)
    (daten / "gutachten" / "final_exports" / "g.docx").write_bytes(b"PK\x03\x04 gutachten")
    # Arbeitsdateien gehören nicht hinein.
    (daten / "tmp").mkdir()
    (daten / "tmp" / "wegwerf.bin").write_bytes(b"x")
    monkeypatch.setenv("AICS_DATA_DIR", str(daten))

    ziel = tmp_path / "sicherung.zip"
    manifest = erstelle_backup(ziel, erstellt_von="pytest")

    assert manifest["format"] == paket.FORMAT_VERSION
    assert manifest["datenbank"]["tabellen"] > 0
    assert manifest["datenbank"]["zeilen"] > 0

    with zipfile.ZipFile(ziel) as zf:
        namen = zf.namelist()
    assert "MANIFEST.json" in namen and "struktur.json" in namen
    # Die Word-Vorlage und das Gutachten sind der Grund für die Dateisicherung.
    assert "dateien/templates/vorlage.docx" in namen
    assert "dateien/gutachten/final_exports/g.docx" in namen
    assert not any(n.startswith("dateien/tmp/") for n in namen)
    assert any(n.startswith(f"db/{probe_schema}/") for n in namen)


def test_leerer_text_bleibt_leerer_text(tmp_path, probe_schema, monkeypatch):
    """Die Falle, die ein Backup lautlos zur Datenveränderung macht.

    PostgreSQL schreibt in CSV die leere Zeichenkette wie NULL, wenn man nicht
    ausdrücklich quoten lässt. Beim Zurücklesen würde aus ``notiz = ''`` ein
    ``notiz IS NULL`` — über die ganze Datenbank hinweg, ohne eine einzige
    Fehlermeldung.
    """
    from shared.backup import erstelle_backup

    monkeypatch.setenv("AICS_DATA_DIR", str(tmp_path / "leer"))
    ziel = tmp_path / "sicherung.zip"
    erstelle_backup(ziel, mit_dateien=False)

    with zipfile.ZipFile(ziel) as zf:
        roh = zf.read(f"db/{probe_schema}/probe_daten.csv").decode()

    zeilen = [z for z in roh.splitlines() if z]
    # Die leere Zeichenkette steht als "" da, NULL als gar nichts. Wären beide
    # gleich kodiert, liefe die Unterscheidung beim Einspielen verloren.
    assert any('""' in z for z in zeilen), f"leerer Text nicht unterscheidbar: {zeilen}"
    assert any(z.endswith(",") or ",," in z for z in zeilen), \
        f"NULL nicht unterscheidbar: {zeilen}"


def test_rundlauf_in_leere_datenbank(tmp_path, probe_schema, monkeypatch):
    """Sicherung → leere Datenbank → identischer Inhalt.

    Das ist die Zusage, um die es geht: Nach einem Totalverlust installiert man
    neu und spielt das Archiv ein. Geprüft wird nicht die Zeilenzahl, sondern
    eine Prüfsumme über den Zeileninhalt — eine stille Verfälschung (leerer Text
    zu NULL) ließe die Zahl unverändert.
    """
    from shared.backup import erstelle_backup, stelle_wieder_her
    import shared.db as sdb

    monkeypatch.setenv("AICS_DATA_DIR", str(tmp_path / "leer"))
    archiv = tmp_path / "sicherung.zip"
    erstelle_backup(archiv, mit_dateien=False)

    quelle = os.environ["DATABASE_URL"]
    vorher = _pruefsummen(quelle)
    assert vorher, "Testaufbau liefert keine Tabellen"

    ziel_name = "pytest_restore_1785"
    _datenbank_neu(ziel_name)
    try:
        monkeypatch.setenv("DATABASE_URL", _dsn_mit_datenbank(ziel_name))
        sdb.reset_pool()
        bericht = stelle_wieder_her(archiv, nur_datenbank=True)
        assert bericht["tabellen"] > 0

        nachher = _pruefsummen(_dsn_mit_datenbank(ziel_name))
        fehlend = sorted(set(vorher) - set(nachher))
        ungleich = sorted(k for k in vorher if k in nachher and nachher[k] != vorher[k])
        assert not fehlend, f"Tabellen fehlen nach dem Einspielen: {fehlend[:5]}"
        assert not ungleich, f"Inhalt weicht ab: {ungleich[:5]}"
    finally:
        monkeypatch.setenv("DATABASE_URL", quelle)
        sdb.reset_pool()
        _datenbank_weg(ziel_name)


def test_sequenzstand_laeuft_mit(tmp_path, probe_schema, monkeypatch):
    """Sonst vergibt die wiederhergestellte Installation Schlüssel ab 1."""
    from shared.backup import erstelle_backup, stelle_wieder_her
    import shared.db as sdb

    monkeypatch.setenv("AICS_DATA_DIR", str(tmp_path / "leer"))
    archiv = tmp_path / "sicherung.zip"
    erstelle_backup(archiv, mit_dateien=False)

    quelle = os.environ["DATABASE_URL"]
    ziel_name = "pytest_restore_seq_1785"
    _datenbank_neu(ziel_name)
    try:
        monkeypatch.setenv("DATABASE_URL", _dsn_mit_datenbank(ziel_name))
        sdb.reset_pool()
        stelle_wieder_her(archiv, nur_datenbank=True)

        # Eine neue Zeile darf nicht mit einer eingespielten kollidieren.
        con = sdb.connect(f"data/db/{probe_schema}.sqlite")
        cur = con.cursor()
        cur.execute("INSERT INTO probe_daten (name) VALUES (?)", ("nach dem Restore",))
        con.commit()
        cur.execute("SELECT count(*) FROM probe_daten")
        assert cur.fetchone()[0] == 3
        con.close()
    finally:
        monkeypatch.setenv("DATABASE_URL", quelle)
        sdb.reset_pool()
        _datenbank_weg(ziel_name)


def test_dateien_laufen_zurueck(tmp_path, probe_schema, monkeypatch):
    from shared.backup import erstelle_backup, stelle_wieder_her

    quelle = tmp_path / "quelle"
    (quelle / "templates").mkdir(parents=True)
    (quelle / "templates" / "haus.docx").write_bytes(b"PK\x03\x04 inhalt")
    monkeypatch.setenv("AICS_DATA_DIR", str(quelle))
    archiv = tmp_path / "sicherung.zip"
    erstelle_backup(archiv)

    ziel = tmp_path / "ziel"
    monkeypatch.setenv("AICS_DATA_DIR", str(ziel))
    bericht = stelle_wieder_her(archiv, nur_dateien=True)

    assert bericht["dateien"] >= 1
    assert (ziel / "templates" / "haus.docx").read_bytes() == b"PK\x03\x04 inhalt"


def test_pfade_aus_dem_archiv_brechen_nicht_aus(tmp_path, monkeypatch):
    """Ein hochgeladenes Archiv ist fremde Eingabe."""
    from shared.backup.dateien import ziel_pruefen

    wurzel = tmp_path / "daten"
    wurzel.mkdir()
    for boese in ("../draussen.txt", "/etc/passwd", "a/../../raus.txt"):
        assert ziel_pruefen(boese, wurzel) is None
    assert ziel_pruefen("templates/gut.docx", wurzel) is not None


def test_altes_archiv_wird_als_unvollstaendig_erkannt(tmp_path):
    """Format 1 enthält die Nutzdaten nicht — das muss vorher dastehen.

    Ohne diesen Hinweis sähe ein Restore aus einem Archiv von 2026 erfolgreich
    aus und bliebe folgenlos: genau der Befund, der zu diesem Modul geführt hat.
    """
    from shared.backup import beschreibe

    alt = tmp_path / "backup_20260511_120000.zip"
    with zipfile.ZipFile(alt, "w") as zf:
        zf.writestr("MANIFEST.json", '{"created_at": "2026-05-11", "version": "1.0.0"}')
        zf.writestr("data/db/cra.sqlite", b"SQLite format 3\x00")

    info = beschreibe(alt)
    assert info["format"] == 1
    assert info["tabellen"] == 0
    assert info["warnungen"], "Ein Archiv ohne Datenbank muss gemeldet werden"
    assert "NICHT" in " ".join(info["warnungen"])


def test_zeitplan_ist_standardmaessig_an():
    """Eine Sicherung, die man erst einschalten muss, bleibt aus."""
    from shared.backup.zeitplan import cron_ausdruck, zeitplan_aktiv

    assert zeitplan_aktiv({}) is True
    assert zeitplan_aktiv({"backup": {}}) is True
    assert zeitplan_aktiv({"backup": {"schedule_enabled": False}}) is False
    assert cron_ausdruck({"backup": {"schedule_cron": "30 3 * * *"}}) == "30 3 * * *"
    # Unsinn fällt auf den Standard zurück statt den Job zu verhindern.
    assert cron_ausdruck({"backup": {"schedule_cron": "kaputt"}}) == "0 2 * * *"


# ── Helfer ──────────────────────────────────────────────────────────────────

def _pruefsummen(dsn: str) -> dict[str, str]:
    """Je Tabelle eine Prüfsumme über den sortierten Zeileninhalt."""
    out: dict[str, str] = {}
    with psycopg.connect(dsn) as con:
        cur = con.cursor()
        cur.execute("""
            SELECT n.nspname, c.relname FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r' AND n.nspname LIKE 'pytest\\_%'
            ORDER BY 1, 2
        """)
        for schema, tabelle in cur.fetchall():
            cur.execute(
                "SELECT attname FROM pg_attribute WHERE attrelid = "
                "(quote_ident(%s) || '.' || quote_ident(%s))::regclass "
                "AND attnum > 0 AND NOT attisdropped ORDER BY attname",
                (schema, tabelle))
            spalten = ", ".join(f'"{r[0]}"' for r in cur.fetchall())
            cur.execute(
                f"SELECT md5(string_agg(z, E'\\n' ORDER BY z)) FROM "
                f'(SELECT ROW({spalten})::text AS z FROM "{schema}"."{tabelle}") q')
            out[f"{schema}.{tabelle}"] = cur.fetchone()[0]
    return out


def _datenbank_neu(name: str) -> None:
    verwaltung = _dsn_mit_datenbank("postgres")
    with psycopg.connect(verwaltung, autocommit=True) as con:
        con.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
        con.execute(f"CREATE DATABASE {name}")


def _datenbank_weg(name: str) -> None:
    try:
        with psycopg.connect(_dsn_mit_datenbank("postgres"), autocommit=True) as con:
            con.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
    except Exception:  # noqa: BLE001 — Aufräumen darf den Lauf nicht kippen
        pass


def test_boesartiges_archiv_kommt_nicht_durch(tmp_path, pg):
    """Ein hochgeladenes Archiv liefert die Namen, aus denen SQL gebaut wird.

    SQL kennt keine Parameter für Bezeichner — Schema-, Tabellen- und
    Spaltennamen müssen in den Befehlstext. Beim Einspielen stammen sie aus
    ``struktur.json``, also möglicherweise aus fremder Hand. Geprüft wird
    deshalb an einer Stelle, und zwar gegen eine Positivliste.
    """
    import json

    from shared.backup import stelle_wieder_her
    from shared.backup.datenbank import BezeichnerFehler, pruefe_ausdruck

    archiv = tmp_path / "boese.zip"
    struktur = {
        "schemata": {
            'x" ; DROP TABLE users; --': {
                "tabellen": {"t": {"spalten": [{"name": "a", "typ": "text"}],
                                   "constraints": [], "indizes": []}},
                "sequenzen": [],
            }
        },
        "funktionen": [],
    }
    with zipfile.ZipFile(archiv, "w") as zf:
        zf.writestr("MANIFEST.json", json.dumps({"format": 2}))
        zf.writestr("struktur.json", json.dumps(struktur))

    with pytest.raises(BezeichnerFehler):
        stelle_wieder_her(archiv, nur_datenbank=True)

    # Dasselbe für die SQL-Fragmente, die sich nicht auf eine Positivliste
    # bringen lassen: mehrere Anweisungen in einer Angabe werden abgelehnt.
    with pytest.raises(BezeichnerFehler):
        pruefe_ausdruck("0; DROP TABLE users", "Vorgabewert")
    assert pruefe_ausdruck("''::text", "Vorgabewert") == "''::text"
    assert pruefe_ausdruck("aics_now();", "Vorgabewert") == "aics_now()"
