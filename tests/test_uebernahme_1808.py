"""Daten übernehmen statt überschreiben — mit echtem Rundlauf (#1808/#1810).

Der Befund, der dieses Modul erzwungen hat, ist in ``shared/backup/uebernehmen.py``
beschrieben: Ein Restore löschte elf von zwölf Mandanten, weil er für den
Wiederanlauf gebaut ist und nicht für die Übernahme.

Der Kern dieser Datei ist ``test_rundlauf_mandant_kommt_dazu``: Bestand anlegen,
sichern, Bestand verändern, übernehmen — und nachsehen, dass **beides** da ist.
Nur dieser Weg findet die Fehler, die zählen; die Behauptung „fügt nur ein"
lässt sich nicht aus dem Quelltext ablesen (die Lehre aus #1785, wo erst der
Rundlauf in eine leere Datenbank fünf Fehler zeigte).
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from shared.backup import paket, uebernehmen as ue


# ── Die Grenzen sind benannt, nicht geraten ─────────────────────────────────

def test_installationsdaten_bleiben_draussen():
    """Revisionspfad, Zeitpläne, SOC — jeweils mit Grund."""
    for schema in ("audit", "scheduler", "soc"):
        assert schema in ue.NICHT_UEBERNOMMEN, f"{schema} ist nicht geregelt"
        assert len(ue.NICHT_UEBERNOMMEN[schema]) > 30, \
            f"{schema}: der Grund gehört in den Bericht, nicht nur ins Verbot"


def test_passkeys_wandern_nicht_mit():
    """Ein Passkey gilt nur für seine Domain (#1811) — mitgenommen erzeugt er
    ein Konto, das einen zweiten Faktor verlangt, den niemand erfüllen kann.
    Genau der Fall, der den Betreiber ausgesperrt hat."""
    assert "webauthn_credentials" not in ue.BENUTZER_TABELLEN
    assert "webauthn_challenges" not in ue.BENUTZER_TABELLEN
    assert ue._ueberspringen("users", "webauthn_credentials", True)
    assert not ue._ueberspringen("users", "users", True)


def test_ohne_anforderung_keine_konten():
    assert ue._ueberspringen("users", "users", False)


def test_aenderungsprotokoll_bleibt_bei_der_quelle():
    """Ein Protokoll über Handlungen auf der Quellinstanz hierher zu kopieren
    wäre die Behauptung, sie seien hier geschehen."""
    assert ("risikobewertung", "rb_change_log") in ue.UEBERGANGEN
    assert ue._ueberspringen("risikobewertung", "rb_change_log", True)


def test_unbekanntes_schema_wird_nicht_angefasst():
    assert ue._ueberspringen("irgendwas_neues", "tabelle", True)


# ── Die Auswahl je Tabelle ──────────────────────────────────────────────────

def test_projekttabelle_wird_ueber_den_namen_gefiltert():
    """`cra_projekte` trägt `name` **und** `unternehmen`. Gefiltert wird über
    den Projektnamen: Ein über den Namen zugeordnetes Projekt (Auto-Anlage
    #430) hat `unternehmen` womöglich leer und fiele sonst weg."""
    art, angabe = ue._filter("cra", "cra_projekte",
                             ["id", "name", "unternehmen", "firmen_id"])
    assert art == "spalte"
    assert angabe == ("name", "projekt")


def test_kind_wird_ueber_die_eltern_gefiltert():
    art, angabe = ue._filter("cra", "cra_doc_checklist", ["doc_id", "item_id"])
    assert art == "eltern"
    assert angabe == ("cra_managed_docs", "doc_id")


def test_katalog_bleibt_unberuehrt():
    """Fail-closed: Was sich keinem Mandanten zuordnen lässt, wird nicht
    eingefügt. Lieber ein Katalog, der nicht mitkommt, als Zeilen, die
    irgendwohin wandern."""
    assert ue._filter("wiba", "wiba_prueffragen",
                      ["control_id", "theme_key", "nr", "frage"]) is None
    assert ue._filter("wiba", "wiba_themen", ["theme_key", "titel"]) is None


def test_stammdaten_kommen_vollstaendig():
    """Ließe man sie weg, zeigte `gutachter_profil_id` ins Leere."""
    art, _ = ue._filter("gutachten", "gutachter_profile", ["id", "name"])
    assert art == "alles"


# ── Eingaben ────────────────────────────────────────────────────────────────

def test_ohne_auswahl_passiert_nichts(tmp_path):
    leer = tmp_path / "x.zip"
    leer.write_bytes(b"PK\x05\x06" + b"\0" * 18)
    with pytest.raises(ValueError, match="kein Mandant"):
        ue.uebernimm(leer, mandanten=[])


def test_unbekannte_kollisionsregel_wird_abgelehnt(tmp_path):
    leer = tmp_path / "x.zip"
    leer.write_bytes(b"PK\x05\x06" + b"\0" * 18)
    with pytest.raises(ValueError, match="Kollisionsregel"):
        ue.uebernimm(leer, mandanten=["A"], bei_kollision="egal")


def test_altes_format_wird_abgelehnt(tmp_path):
    """Ein Format-1-Archiv enthält keine Datenbankinhalte (#1785). Es
    anzunehmen hieße, eine Übernahme zu melden, die nichts übernimmt."""
    import json
    import zipfile

    archiv = tmp_path / "alt.zip"
    with zipfile.ZipFile(archiv, "w") as zf:
        zf.writestr("MANIFEST.json", json.dumps({"format": 1}))
    with pytest.raises(ue.UebernahmeFehler, match="alten Format"):
        ue.inhalt(archiv)


# ── Der Rundlauf ────────────────────────────────────────────────────────────

def _firma(name: str, *, produkt: str = "") -> None:
    from firmen import db as fdb
    fdb.ensure_db(Path("data/db/firmen.sqlite"))
    fdb.save_firma(Path("data/db/firmen.sqlite"), name,
                   unternehmen=name, produkt=produkt)


def _cra_projekt(name: str, firma: str) -> None:
    from cra import db as cdb
    p = Path("data/db/cra.sqlite")
    cdb.ensure_db(p)
    cdb.save_projekt(p, name, unternehmen=firma, produkt=name)


def _firma_hart_weg(name: str) -> None:
    """Die Zeile wirklich entfernen.

    ``firmen.db.delete_firma`` ist ein Soft-Delete: Der Name bleibt in der
    Tabelle stehen und belegt den eindeutigen Index. Für „der Mandant ist hier
    nicht vorhanden" braucht es die Zeile weg — sonst prüft der Test die
    Reaktivierung statt der Neuanlage.
    """
    from firmen import db as fdb
    con = fdb._connect(Path("data/db/firmen.sqlite"))
    try:
        con.execute("DELETE FROM firmen WHERE name = ?", (name,))
        con.commit()
    finally:
        con.close()


def _firmen_namen() -> set[str]:
    from firmen import db as fdb
    return set(fdb.list_firmen(Path("data/db/firmen.sqlite")))


def _cra_namen() -> set[str]:
    from cra import db as cdb
    return set(cdb.list_projekte(Path("data/db/cra.sqlite")))


@pytest.mark.timeout(600)
def test_rundlauf_mandant_kommt_dazu(tmp_path):
    """Der eigentliche Test: Übernehmen darf den Bestand nicht anfassen.

    Ablauf wie im Betrieb — Quelle sichern, Ziel hat **andere** Mandanten,
    übernehmen, und hinterher sind es alle. Genau das war beim Restore nicht
    so: Dort blieb nur, was die Quelle gar nicht hatte.
    """
    from firmen import db as fdb

    quelle_firma = "pytest-quelle-1808"
    ziel_firma = "pytest-ziel-1808"
    quelle_projekt = "pytest-quelle-1808-produkt"

    _firma(quelle_firma)
    _cra_projekt(quelle_projekt, quelle_firma)

    archiv = tmp_path / "quelle.zip"
    paket.erstelle_backup(archiv, erstellt_von="pytest", mit_dateien=False)

    # Das Ziel sieht anders aus: Der Quell-Mandant ist weg, ein anderer da.
    _firma_hart_weg(quelle_firma)
    from cra import db as cdb
    cdb.delete_projekt(Path("data/db/cra.sqlite"), quelle_projekt)
    _firma(ziel_firma)

    assert quelle_firma not in _firmen_namen()
    vorher_ziel = _firmen_namen()

    try:
        uebersicht = ue.inhalt(archiv)
        namen = {m["name"] for m in uebersicht["mandanten"]}
        assert quelle_firma in namen, f"Archiv-Inhalt nennt den Mandanten nicht: {namen}"

        bericht = ue.uebernimm(archiv, mandanten=[quelle_firma])
        assert not bericht["uebersprungen"], bericht["uebersprungen"]
        assert bericht["zeilen"] > 0, bericht

        nachher = _firmen_namen()
        assert quelle_firma in nachher, "Der Mandant ist nicht angekommen"
        assert vorher_ziel <= nachher, (
            f"Bestand verloren: {vorher_ziel - nachher}")
        assert quelle_projekt in _cra_namen(), "Das CRA-Projekt fehlt"
    finally:
        _firma_hart_weg(quelle_firma)
        _firma_hart_weg(ziel_firma)
        cdb.delete_projekt(Path("data/db/cra.sqlite"), quelle_projekt)
        _ = fdb


@pytest.mark.timeout(600)
def test_vorhandener_mandant_wird_behalten(tmp_path):
    """Der Bestand ist eine Aussage. Ohne ausdrückliches „ersetzen" bleibt er."""
    from firmen import db as fdb

    name = "pytest-kollision-1808"
    _firma(name, produkt="Stand im Archiv")
    archiv = tmp_path / "k.zip"
    paket.erstelle_backup(archiv, erstellt_von="pytest", mit_dateien=False)

    try:
        # Im Ziel inzwischen ein anderer Stand.
        _firma(name, produkt="Stand im Ziel")

        bericht = ue.uebernimm(archiv, mandanten=[name])
        assert bericht["uebersprungen"] == [name]
        assert bericht["zeilen"] == 0

        firma = fdb.load_firma(Path("data/db/firmen.sqlite"), name)
        assert firma["produkt"] == "Stand im Ziel", \
            "Der Bestand wurde überschrieben — genau das sollte nicht passieren"
    finally:
        fdb.delete_firma(Path("data/db/firmen.sqlite"), name)


@pytest.mark.timeout(600)
def test_als_geloescht_markierter_mandant_wird_zurueckgeholt(tmp_path):
    """Der Fall, den der Soft-Delete erzeugt.

    ``firmen.db.delete_firma`` markiert nur; die Zeile bleibt und belegt den
    eindeutigen Namen. Eine Übernahme würde daran stillschweigend scheitern —
    eingefügt werden kann nichts, und der Mandant bliebe unsichtbar. Also wird
    die vorhandene Zeile zurückgeholt, und der Bericht sagt es.
    """
    from firmen import db as fdb

    name = "pytest-wiederbelebt-1808"
    projekt = "pytest-wiederbelebt-1808-produkt"
    _firma(name)
    _cra_projekt(projekt, name)
    archiv = tmp_path / "w.zip"
    paket.erstelle_backup(archiv, erstellt_von="pytest", mit_dateien=False)

    from cra import db as cdb
    fdb.delete_firma(Path("data/db/firmen.sqlite"), name)
    cdb.delete_projekt(Path("data/db/cra.sqlite"), projekt)
    assert name not in _firmen_namen(), "Soft-Delete wirkt nicht"

    try:
        uebersicht = ue.inhalt(archiv)
        eintrag = next(m for m in uebersicht["mandanten"] if m["name"] == name)
        assert eintrag["im_ziel"] is False, \
            "Ein gelöschter Mandant darf nicht als vorhanden gelten — sonst " \
            "überspringt die Übernahme ihn"
        assert eintrag["im_ziel_gelöscht"] is True

        bericht = ue.uebernimm(archiv, mandanten=[name])
        assert bericht["firmen_reaktiviert"] == [name], bericht
        assert name in _firmen_namen(), "Der Mandant ist nicht zurück"
        assert projekt in _cra_namen(), "Das Projekt ist nicht angekommen"
    finally:
        _firma_hart_weg(name)
        cdb.delete_projekt(Path("data/db/cra.sqlite"), projekt)


@pytest.mark.timeout(600)
def test_trockenlauf_schreibt_nichts(tmp_path):
    """Vor dem Klick wissen, was passiert — ohne dass es passiert."""
    from firmen import db as fdb

    name = "pytest-trocken-1808"
    _firma(name)
    archiv = tmp_path / "t.zip"
    paket.erstelle_backup(archiv, erstellt_von="pytest", mit_dateien=False)
    _firma_hart_weg(name)

    try:
        bericht = ue.uebernimm(archiv, mandanten=[name], trockenlauf=True)
        assert bericht["zeilen"] > 0, "Der Trockenlauf muss die Zahlen liefern"
        assert name not in _firmen_namen(), \
            "Der Trockenlauf hat geschrieben"
    finally:
        _firma_hart_weg(name)
        _ = fdb


# ── Der Versatz ─────────────────────────────────────────────────────────────

def test_versatz_ist_der_kern_und_steht_im_quelltext():
    """Warum es nur **eine** Ausnahme braucht, muss nachlesbar sein — sonst
    baut der nächste eine Liste aller Verweise (die Spiegel-Liste aus
    #1731/#1735)."""
    q = inspect.getsource(ue._versatz)
    assert "firmen_id" in q and "Kollision" in q

    q2 = inspect.getsource(ue._ids_verschieben)
    assert "firmen_abbildung" in q2
    assert "firmen_id = NULL" in q2, \
        "Ein Verweis auf eine nicht mitgekommene Firma muss gelöst, nicht geraten werden"


def test_csv_wird_von_postgres_gelesen():
    """Pythons CSV-Leser kennt den Unterschied zwischen '' und NULL nicht —
    er würde den Datenbestand bei der Übernahme stillschweigend verändern
    (die Lehre aus #1785)."""
    q = inspect.getsource(ue._temp_befuellen)
    assert "COPY" in q and "FORMAT csv" in q
    assert "WITH NO DATA" in q


def test_alles_oder_nichts():
    q = inspect.getsource(ue._einspielen)
    assert "conn.rollback()" in q and "conn.commit()" in q
    assert "trockenlauf" in q


# ── Dateien ─────────────────────────────────────────────────────────────────

def test_dateien_werden_ergaenzt_nicht_ersetzt():
    """Ohne die Dateien wäre die Übernahme halb.

    Die Datensätze verweisen auf Dateien: hochgeladene Word-Vorlagen,
    Nachweisdokumente, finalisierte Gutachten, Pentest-PDFs. Kämen die Zeilen
    ohne sie, zeigte jeder Download ins Leere — und das sieht nach einem Defekt
    der Anwendung aus statt nach einer unvollständigen Übernahme.

    Überschrieben wird nichts: Die Dateinamen tragen Prüfsummen, und eine
    ersetzte Datei stimmte nicht mehr mit dem SHA-256 im hiesigen Datensatz.
    """
    q = inspect.getsource(ue._dateien_ergaenzen)
    assert "if ziel.exists():" in q, "Vorhandene Dateien würden überschrieben"
    assert "ziel_pruefen" in q, "Pfade aus dem Archiv werden nicht geprüft"
    assert "dateien_neu" in q and "dateien_vorhanden" in q, \
        "Der Bericht nennt die Zahlen nicht"


def test_trockenlauf_legt_keine_dateien_ab():
    q = inspect.getsource(ue.uebernimm)
    assert "mit_dateien and not trockenlauf" in q, \
        "Ein Trockenlauf, der Dateien ablegt, ist keiner"


@pytest.mark.timeout(600)
def test_rundlauf_bringt_die_datei_mit(tmp_path, monkeypatch):
    """Gegenprobe am echten Archiv: Die Datei fehlt, dann ist sie da."""
    import os

    datenwurzel = tmp_path / "daten"
    (datenwurzel / "gutachten" / "templates").mkdir(parents=True)
    probe = datenwurzel / "gutachten" / "templates" / "pytest-1808.bin"
    probe.write_bytes(b"Inhalt der Vorlage")
    monkeypatch.setenv("AICS_DATA_DIR", str(datenwurzel))

    name = "pytest-dateien-1808"
    _firma(name)
    archiv = tmp_path / "d.zip"
    paket.erstelle_backup(archiv, erstellt_von="pytest", mit_dateien=True)
    _firma_hart_weg(name)
    probe.unlink()
    assert not probe.exists()

    try:
        bericht = ue.uebernimm(archiv, mandanten=[name])
        assert probe.exists(), "Die Datei ist nicht mitgekommen"
        assert probe.read_bytes() == b"Inhalt der Vorlage"
        assert bericht["dateien_neu"] >= 1, bericht

        # Zweiter Lauf: Die Datei liegt jetzt hier und darf nicht ersetzt werden.
        probe.write_bytes(b"hiesiger Stand")
        ue.uebernimm(archiv, mandanten=[name], bei_kollision="ersetzen")
        assert probe.read_bytes() == b"hiesiger Stand", \
            "Eine vorhandene Datei wurde überschrieben"
    finally:
        _firma_hart_weg(name)
        os.environ.pop("AICS_DATA_DIR", None)


def test_ersetzen_legt_vorher_eine_sicherheitskopie_an():
    """Die Zusage dieses Endpunkts ist „es geht nichts verloren".

    `ersetzen` bricht sie als einziger Weg — dann gilt dieselbe Regel wie beim
    Restore. Beim Übernehmen *ohne* Ersetzen entfällt die Kopie: Eine
    minutenlange Vollsicherung für einen Vorgang, der nur einfügt, wäre
    Zeremonie.
    """
    quelle = Path("server/api/admin.py").read_text(encoding="utf-8")
    anfang = quelle.index("def backup_uebernehmen")
    # Bis zur nächsten Funktion auf Modulebene, nicht auf eine Zeichenzahl
    # geschätzt — eine zu kurze Scheibe lässt den Test grün werden, wenn der
    # Code wächst, und rot, wenn er nur umsortiert wird.
    ende = quelle.index("\n@admin_bp", anfang + 1)
    stelle = quelle[anfang:ende]
    assert "bei_kollision == 'ersetzen' and not trockenlauf" in stelle, \
        "Vor dem Ersetzen wird keine Sicherheitskopie angelegt"
    assert "ohne_sicherheitskopie" in stelle, \
        "Kein Rückweg muss eine ausdrückliche Entscheidung bleiben"
    assert "safety_backup" in stelle, "Die Antwort nennt die Kopie nicht"


def test_kein_rollback_mitten_im_lauf():
    """Die Transaktion ist die Zusage — ein Rollback im Fehlerzweig bricht sie.

    ``conn.rollback()`` wirft in PostgreSQL die **ganze** Transaktion weg. In
    einem Fehlerzweig mitten im Lauf hieße das: die schon eingefügten Mandanten
    sind weg, die folgenden Anweisungen laufen in einer neuen Transaktion, und
    der abschließende Commit committet nur noch einen Teil. Gemeldet würde
    trotzdem Erfolg. Riskante Einzelschritte gehören in einen Savepoint
    (``with conn.transaction():``) — dieselbe Entscheidung wie in #1785.
    """
    def _ohne_kommentare(text: str) -> str:
        """Kommentare und Docstrings heraus — sonst prüft der Test seine
        eigene Erklärung. Genau das ist hier passiert: Die Begründung im
        Code nennt `conn.rollback()` wörtlich."""
        import io
        import tokenize

        stuecke = []
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            stuecke.append(tok.string)
        return " ".join(stuecke)

    # Erlaubt sind die Rollbacks am Rand: Verbindung säubern, abgebrochenes
    # `SET session_replication_role`, der Trockenlauf und der Abbruch im
    # äußeren `except`. Diese Funktionen laufen mitten im Lauf.
    for name in ("_bestand_entfernen", "_sequenzen_nachziehen",
                 "_tabelle_uebernehmen", "_firmen_uebernehmen", "_versatz"):
        fn = getattr(ue, name)
        code = _ohne_kommentare(inspect.getsource(fn))
        assert "conn . rollback" not in code, \
            f"{name} wirft die Transaktion weg, statt einen Savepoint zu nutzen"

    assert "with conn.transaction():" in inspect.getsource(ue), \
        "Keine Savepoints vorhanden"
