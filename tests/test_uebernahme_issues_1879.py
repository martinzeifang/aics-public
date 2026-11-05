"""Die Übernahme bringt die Issue-Verknüpfungen mit (#1879).

DER BEFUND AUS DEM BETRIEB
„Beim Restore der Daten ohne Benutzer wurden die Issues nicht mit
wiederhergestellt." Auf Produktiv standen in ``cra.linked_issues`` und
``risikobewertung.linked_issues`` 0 Zeilen, auf Test 222 — bei sonst
inhaltlich identischem Datenbestand.

Nicht der Restore war es: Der ruft ``datenbank.struktur_herstellen`` und legt
fehlende Tabellen vorher an. Die **Übernahme** hatte dazu kein Gegenstück —
``_gemeinsame_spalten`` fand im Ziel keine Spalten, meldete „Tabelle gibt es auf
dieser Installation nicht" und ließ die Zeilen liegen. Und ``linked_issues``
steht in keinem ``ensure_db`` und nicht im Warmup: Sie entsteht erst, wenn das
erste Issue verknüpft wird.

WARUM HIER EIN RUNDLAUF UND KEIN QUELLTEXT-GREP
Beides war am Quelltext **nicht** zu sehen. Die Auswahlregel (``_filter``) ist
richtig — ``projekt_name`` steht in ``ZUORDNUNGSSPALTEN``, und bei vorhandener
Zieltabelle kamen die Zeilen auch an. Sichtbar wird der Fehler erst im Lauf:
Tabelle weg → Null im Bericht, kein Fehler. Dasselbe beim zweiten Befund,
``object_id``: Die Spalte ist TEXT, also greift die Versatz-Regel nicht, und das
Ergebnis ist eine Verknüpfung, die auf eine **fremde** Schwachstelle zeigt.
Ein Grep hätte beides bestätigt gefunden (die Lehre aus #1834/#1870).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from shared.backup import paket, uebernehmen as ue

FIRMA = "pytest-issues-1879-firma"
PROJEKT = "pytest-issues-1879-produkt"
CRA = Path("data/db/cra.sqlite")
FIRMEN = Path("data/db/firmen.sqlite")


# ── Die Zuordnung der Objektarten ist vollständig ───────────────────────────

#: ``object_kind``-Werte, die **außerhalb** der Issue-Fabrik geschrieben werden:
#: ein ``add_link``-Aufruf mit einem Literal.
#:
#: Die Einschränkung auf Dateien, die ``add_link`` wirklich rufen, ist nötig und
#: nicht Bequemlichkeit: ``object_kind`` ist ein Spaltenname, den es noch zweimal
#: gibt — ``rb_change_log`` führt ``'projekt'|'risk'``, die lokale Code-Analyse
#: ``'owasp'|'cra'``. Ein Grep über alle ``object_kind=`` meldete beide, und ein
#: Wächter mit Fehlalarmen wird nicht mehr gelesen (die Lehre aus #1805).
_ADD_LINK = re.compile(r"\badd_link\s*\(")
_OBJECT_KIND = re.compile(r"object_kind\s*=\s*['\"]([a-z_]+)['\"]")


def _arten_ausserhalb_der_fabrik() -> dict[str, str]:
    wurzel = Path(__file__).resolve().parent.parent
    gefunden: dict[str, str] = {}
    for pfad in sorted(wurzel.rglob("*.py")):
        rel = pfad.relative_to(wurzel)
        if set(rel.parts) & {"tests", "node_modules", ".git", ".claude",
                             "scripts", "tools"}:
            continue
        try:
            text = pfad.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover
            continue
        if "def add_link" in text:
            continue  # die Definition selbst, nicht ein Aufruf
        if _ADD_LINK.search(text):
            for art in _OBJECT_KIND.findall(text):
                gefunden.setdefault(art, str(rel))
    return gefunden


def test_jede_objektart_ist_eingeordnet(app):
    """Wächter gegen die Spiegel-Liste (#1731/#1735).

    Es gibt zwei Arten von ``object_id`` — laufende Nummer und fachlicher
    Schlüssel —, und nur die erste darf mit dem Versatz wandern. Eine neue
    Objektart, die in keiner der beiden Mengen steht, würde stillschweigend als
    „fachlicher Schlüssel" behandelt. Bei einer Nummer wäre das genau der stille
    Fehler, den #1879 behoben hat: eine Verknüpfung, die auf eine fremde Zeile
    zeigt und wie eine Aussage aussieht.

    Die Arten der Fabrik kommen aus der **laufenden Anwendung**
    (``issue_api._ARTEN``, gefüllt von ``register_routes``), nicht aus einem
    Grep: WiBA übergibt ``art=_OBJECT_KIND``, also eine Konstante — im Quelltext
    steht die Zeichenkette dort gar nicht, und ein Quelltext-Wächter wäre genau
    an dieser Stelle grün geblieben, ohne sie zu kennen. Geprüft wird das
    Programm, nicht die Erzählung (#1834).
    """
    from shared import issue_api

    assert app is not None  # die Adapter registrieren beim Import ihrer Module
    aus_fabrik = {a.art: f"{modul} (Fabrik)"
                  for modul, arten in issue_api._ARTEN.items() for a in arten}
    assert len(aus_fabrik) >= 5, \
        f"Die Fabrik hat fast keine Arten registriert — Wächter wertlos: {aus_fabrik}"

    gefunden = {**aus_fabrik, **_arten_ausserhalb_der_fabrik()}
    bekannt = ue.OBJEKT_ID_IST_NUMMER | ue.OBJEKT_ID_IST_FACHSCHLUESSEL
    offen = {a: q for a, q in gefunden.items() if a not in bekannt}
    assert not offen, (
        "Nicht eingeordnete Objektarten — ist die object_id eine laufende "
        "Nummer (dann in OBJEKT_ID_IST_NUMMER) oder ein fachlicher Schlüssel "
        f"(dann in OBJEKT_ID_IST_FACHSCHLUESSEL)? {offen}")


def test_die_beiden_mengen_sind_disjunkt():
    """Eine Art kann nicht beides sein — sonst entscheidet die Reihenfolge."""
    assert not (ue.OBJEKT_ID_IST_NUMMER & ue.OBJEKT_ID_IST_FACHSCHLUESSEL)


def test_geteilte_register_sind_vorgesehen():
    """``ki_herkunft`` und ``prompt_hinweise`` liegen in eigenen Schemata und
    fehlten in ``FACHSCHEMATA``. Beim KI-Prüfvermerk ist die Folge mehr als eine
    Lücke: Das CRA-Release-Gate meldet nach einer Übernahme ungeprüfte
    KI-Entwürfe, die längst geprüft sind (#1765)."""
    for schema in ("ki_herkunft", "prompt_hinweise"):
        assert schema in ue.FACHSCHEMATA
        assert not ue._ueberspringen(schema, schema, False)


# ── Der Rundlauf ────────────────────────────────────────────────────────────

def _sql(stmt: str, args: tuple = ()) -> list[tuple]:
    pool, conn = paket._roh_verbindung()
    try:
        cur = conn.cursor()
        cur.execute(stmt, args)
        try:
            raus = [tuple(r) for r in cur.fetchall()]
        except Exception:  # noqa: BLE001 — Anweisung ohne Ergebnismenge
            raus = []
        conn.commit()
        return raus
    finally:
        # putconn, nicht close: Der Pool gehört der Anwendung (#1808).
        pool.putconn(conn)


def _aufraeumen() -> None:
    for stmt, args in (
        ("DELETE FROM cra.linked_issues WHERE projekt_name = %s", (PROJEKT,)),
        ("DELETE FROM cra.cra_vuln WHERE projekt_name = %s", (PROJEKT,)),
        ("DELETE FROM cra.cra_projekte WHERE name = %s", (PROJEKT,)),
        ("DELETE FROM firmen.firmen WHERE name = %s", (FIRMA,)),
    ):
        try:
            _sql(stmt, args)
        except Exception:  # noqa: BLE001 — Tabelle kann in diesem Lauf fehlen
            pass


def _issue_tabelle_herstellen() -> None:
    """``cra.linked_issues`` wieder anlegen — zwingend nach einem ``DROP``.

    Die Per-Test-Isolation (:func:`shared.db.drop_test_schemas`) **truncatet**,
    sie droppt nicht; die Tabellen gelten danach als vorhanden. Ein echtes
    ``DROP TABLE`` in diesem Test wäre deshalb für alle folgenden Testdateien
    sichtbar — und zwar unsichtbar: ``shared.db`` merkt sich ausgeführte DDL
    prozessweit (#1396), also legte ``issue_links.ensure_tables`` sie **nicht**
    wieder an. Die Folge wären rote Tests ohne Bezug zur Änderung.
    """
    from shared import db as _sdb
    from shared import issue_links as il

    _sdb._ensured_scripts.clear()
    _sdb._ensured_ddl.clear()
    il.ensure_tables(CRA)


@pytest.fixture
def archiv_mit_issues(pg, tmp_path):
    """Ein Archiv mit Mandant, CRA-Projekt, Schwachstelle und zwei Links."""
    from cra import db as cdb
    from firmen import db as fdb
    from shared import issue_links as il

    fdb.ensure_db(FIRMEN)
    cdb.ensure_db(CRA)
    il.ensure_tables(CRA)
    _aufraeumen()

    fdb.save_firma(FIRMEN, FIRMA, unternehmen=FIRMA, produkt=PROJEKT)
    cdb.save_projekt(CRA, PROJEKT, unternehmen=FIRMA, produkt=PROJEKT)
    cdb.upsert_vuln(CRA, PROJEKT, {
        "cve_id": "CVE-2026-1879", "titel": "Prüffall", "schwere": "high",
        "status": "open", "source": "manual"})
    vuln_id = _sql("SELECT id FROM cra.cra_vuln WHERE projekt_name = %s",
                   (PROJEKT,))[0][0]

    # Zwei Links: einer auf eine laufende Nummer, einer auf einen fachlichen
    # Schlüssel. Nur der erste darf wandern.
    il.add_link(CRA, projekt_name=PROJEKT, object_kind="vuln",
                object_id=str(vuln_id), provider="github", repo="o/r",
                url="https://github.com/o/r/issues/1879", issue_number=1879,
                title="Schwachstelle")
    il.add_link(CRA, projekt_name=PROJEKT, object_kind="requirement",
                object_id="CRA-A-01", provider="github", repo="o/r",
                url="https://github.com/o/r/issues/1880", issue_number=1880,
                title="Anforderung")

    ziel = tmp_path / "mit-issues.zip"
    paket.erstelle_backup(ziel, erstellt_von="pytest-1879", mit_dateien=False)
    yield ziel
    _issue_tabelle_herstellen()
    _aufraeumen()


def _links() -> dict[str, str]:
    return {art: oid for art, oid in _sql(
        "SELECT object_kind, object_id FROM cra.linked_issues "
        "WHERE projekt_name = %s", (PROJEKT,))}


@pytest.mark.timeout(600)
def test_issues_kommen_mit_wenn_die_zieltabelle_fehlt(archiv_mit_issues):
    """Der gemeldete Fall.

    ``linked_issues`` entsteht erst beim ersten Issue-Zugriff. Fehlt sie im
    Ziel, ließ die Übernahme die Zeilen liegen und meldete dazu nichts außer
    einer Null — und niemand liest eine Null.
    """
    _aufraeumen()
    _sql("DROP TABLE IF EXISTS cra.linked_issues CASCADE")
    assert not _sql(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'cra' AND table_name = 'linked_issues'")

    bericht = ue.uebernimm(archiv_mit_issues, mandanten=[FIRMA])

    assert "cra.linked_issues" in (bericht.get("tabellen_angelegt") or []), (
        "Die fehlende Tabelle wurde nicht angelegt — "
        f"ausgelassen: {(bericht.get('ausgelassen') or {}).get('cra.linked_issues')}")
    assert bericht["je_tabelle"].get("cra.linked_issues") == 2, bericht["je_tabelle"]
    assert set(_links()) == {"vuln", "requirement"}, \
        "Die Issue-Verknüpfungen sind nicht angekommen"


@pytest.mark.timeout(600)
def test_object_id_wandert_nur_wo_sie_eine_nummer_ist(archiv_mit_issues):
    """Der zweite, stillere Fehler.

    ``object_id`` ist TEXT; bei ``vuln`` steht darin die ``cra_vuln.id``. Wandert
    sie nicht mit dem Versatz, zeigt die Verknüpfung auf eine **fremde, hier
    bereits vorhandene** Schwachstelle — sie sieht aus wie eine Aussage (#1773).
    """
    from shared import issue_links as il

    il.ensure_tables(CRA)
    _aufraeumen()

    bericht = ue.uebernimm(archiv_mit_issues, mandanten=[FIRMA])
    neue_vuln_id = _sql("SELECT id FROM cra.cra_vuln WHERE projekt_name = %s",
                        (PROJEKT,))[0][0]
    links = _links()

    assert links["vuln"] == str(neue_vuln_id), (
        f"Der vuln-Link zeigt auf {links['vuln']!r}, die Schwachstelle liegt "
        f"aber unter id={neue_vuln_id} (Versatz {bericht['versatz']})")
    assert links["requirement"] == "CRA-A-01", \
        "Ein fachlicher Schlüssel darf nicht verschoben werden"


@pytest.mark.timeout(600)
def test_soc_und_revisionspfad_entstehen_nicht_nebenbei(archiv_mit_issues):
    """``struktur_herstellen`` pauschal zu rufen wäre der bequeme Weg gewesen —
    und hätte leere SOC-, Revisions- und Zeitplan-Tabellen angelegt. Das ist das
    Gegenteil der Zusage aus ``NICHT_UEBERNOMMEN``, dass sie nicht mitwandern.

    Die Tabelle wird vorher gedroppt, damit überhaupt etwas angelegt wird —
    sonst wäre ``tabellen_angelegt`` leer und die Prüfung ginge grün durch, ohne
    etwas zu prüfen.
    """
    _aufraeumen()
    _sql("DROP TABLE IF EXISTS cra.linked_issues CASCADE")

    bericht = ue.uebernimm(archiv_mit_issues, mandanten=[FIRMA],
                           trockenlauf=True)
    angelegt = bericht.get("tabellen_angelegt") or []
    assert "cra.linked_issues" in angelegt, \
        "Der Lauf hat nichts angelegt — die Prüfung darunter ist wertlos"
    fremd = [t for t in angelegt if t.split(".", 1)[0] in ue.NICHT_UEBERNOMMEN]
    assert not fremd, f"Nicht zu übernehmende Tabellen wurden angelegt: {fremd}"

    # Der Trockenlauf darf auch die Struktur nicht hinterlassen — sonst wäre er
    # keiner.
    assert not _sql(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'cra' AND table_name = 'linked_issues'"), \
        "Der Trockenlauf hat die Tabelle angelegt und stehen gelassen"
