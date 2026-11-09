"""Querleser zwischen Mandanten — #2030/#2031/#2032/#2033/#2034.

Fünf Fundstellen aus dem Prüflauf 09.11.2026, die alle dieselbe Wurzel haben:
Die Mandantentrennung entscheidet sich an **Zeichenketten, die anderswo
entstehen** — Modulschlüssel, Dateinamen, URL-Parameternamen —, und für diese
Zuordnungen gab es keinen Prüfer, der beide Seiten gegeneinander hält. Das ist
die Spiegel-Liste aus #1731/#1735 in ihrer leisesten Form (#1870), hier mit dem
teuersten Ausgang: ``firma_acl`` ist **fail-open**, also wird aus einer
fehlenden Zeile kein Fehler, sondern ein offener Weg auf fremde Mandanten.

#2031 hat diesen Test ausdrücklich verlangt: „ein Test, der jede projektbezogene
Route gegen die auflösbaren Parameternamen **und** gegen diese Liste hält, würde
#2030, diesen Vorgang und #2032 auf einmal rot werden lassen."

**Geprüft wird das Programm, nicht die Erzählung** (#1834/#1867/#1878/#1903):
Wo kein Request-Kontext aufgebaut werden kann, läuft die Prüfung über den
**Syntaxbaum** — ein Kommentar, der die Reparatur zitiert, erfüllt sie damit
nicht. Jede einzelne Zusage unten wurde durch Rückbau rot gesehen.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from shared.firmen_link import MODULE_PROJECT_TABLES


# ── Werkzeug: Aufrufe im Rumpf EINER Funktion, ohne Kommentare ───────────────

def _funktionsrumpf(pfad: str, name: str) -> ast.FunctionDef:
    baum = ast.parse(Path(pfad).read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.FunctionDef) and knoten.name == name:
            return knoten
    raise AssertionError(f"{name}() nicht in {pfad} gefunden")


def _gerufene_namen(fn: ast.FunctionDef) -> set[str]:
    """Alle im Rumpf **aufgerufenen** Namen (auch importierte Aliase)."""
    namen: set[str] = set()
    for knoten in ast.walk(fn):
        if isinstance(knoten, ast.Call):
            ziel = knoten.func
            if isinstance(ziel, ast.Name):
                namen.add(ziel.id)
            elif isinstance(ziel, ast.Attribute):
                namen.add(ziel.attr)
        # `from x import y as z` im Rumpf: beide Schreibweisen zählen.
        if isinstance(knoten, ast.ImportFrom):
            for alias in knoten.names:
                namen.add(alias.asname or alias.name)
    return namen


# ══════════════════════════════════════════════════════════════════════════════
# #2031 — die abgeleitete Modul-Zuordnung
# ══════════════════════════════════════════════════════════════════════════════

def test_jedes_modul_mit_projekttabelle_ist_aufloesbar():
    """Kein Modul aus ``MODULE_PROJECT_TABLES`` bleibt in ``firma_acl`` unversorgt.

    Das ist die Zusage, die vor v8.6.3 für **drei** Module gebrochen war
    (``firmen``, ``compliance_audit``, ``gutachten``) — ihre ``firmen_id`` war
    längst auflösbar, nur fehlte die Zeile in der handgeführten Kopie.
    """
    from server.middleware.firma_acl import _MODULE_DBFILE

    fehlt = {d for d in MODULE_PROJECT_TABLES if d not in _MODULE_DBFILE.values()}
    assert not fehlt, (
        f"Projekt-Tabellen ohne Auflösung in firma_acl: {sorted(fehlt)} — "
        "fail-open heißt hier: fremde Mandanten lesbar")


def test_die_zuordnung_ist_abgeleitet_und_nicht_abgetippt():
    """Der Dateistamm trägt die Zuordnung; nur echte Aliase stehen von Hand da.

    Wird die Ableitung durch eine Literal-Liste ersetzt, wächst sie beim nächsten
    Modul nicht mit — genau der Defekt, den #2031 beschreibt.
    """
    from server.middleware.firma_acl import _MODULE_ALIASES, _MODULE_DBFILE

    abgeleitet = {Path(d).stem for d in MODULE_PROJECT_TABLES}
    assert abgeleitet <= set(_MODULE_DBFILE), "Ableitung über den Dateistamm fehlt"
    # Die Aliase sind die *Ausnahmen* — sie dürfen nicht die ganze Liste sein.
    assert set(_MODULE_ALIASES) < set(_MODULE_DBFILE)
    for schluessel, datei in _MODULE_ALIASES.items():
        assert datei in MODULE_PROJECT_TABLES, (
            f"Alias {schluessel!r} zeigt auf {datei!r}, das es in "
            "MODULE_PROJECT_TABLES nicht gibt")


def test_compliance_audit_und_gutachten_zeigen_auf_die_historische_tabelle():
    """v7.4.0 hat das Modul getrennt, der Tabellenname blieb (#1713)."""
    from server.middleware.firma_acl import _MODULE_DBFILE

    assert _MODULE_DBFILE["compliance_audit"] == "gutachten.sqlite"
    assert _MODULE_DBFILE["gutachten"] == "gutachten.sqlite"
    assert MODULE_PROJECT_TABLES["gutachten.sqlite"][0] == "gutachten_projects"


def test_aiact_alias_folgt_der_authz_schreibweise():
    """``_module_for_path`` leitet ``/api/aiact-…`` auf ``aiact`` ab (#1169)."""
    from server.middleware.firma_acl import _MODULE_DBFILE

    assert _MODULE_DBFILE["aiact"] == _MODULE_DBFILE["ai_act"] == "ai_act.sqlite"


# ── Parameternamen: die zweite Hälfte derselben Wurzel ───────────────────────

def test_project_name_wird_gelesen(monkeypatch):
    """``project_name`` ist die Schreibweise aller 35 Compliance-Audit-Routen.

    Sie wurde in keinem Schritt von ``request_firmen_id`` gelesen — damit war
    **jede** Detailroute des Moduls fail-open, während die Liste korrekt
    gefiltert war (#2031).
    """
    from server.middleware import firma_acl

    gefragt: list[tuple[str, str]] = []
    monkeypatch.setattr(firma_acl, "project_firmen_id",
                        lambda m, p: gefragt.append((m, p)) or 42)

    assert firma_acl.request_firmen_id(
        "compliance_audit", {"project_name": "Audit-X"}) == 42
    assert gefragt == [("compliance_audit", "Audit-X")]


@pytest.mark.parametrize("parameter", ["projekt_name", "projekt", "project_name"])
def test_alle_drei_projekt_schreibweisen(monkeypatch, parameter):
    from server.middleware import firma_acl

    monkeypatch.setattr(firma_acl, "project_firmen_id", lambda m, p: 7)
    assert firma_acl.request_firmen_id("cra", {parameter: "P"}) == 7


def test_bei_firmen_traegt_der_projekt_parameter_einen_firmennamen(monkeypatch):
    """Das Berichts-Center registriert ``firmen`` project_scoped — der Wert von
    ``<projekt>`` ist dort der **Firmenname** (#2031).

    Ohne diese Unterscheidung lief
    ``GET /api/firmen/projekte/<fremde Firma>/berichte/gesamt`` in die
    Projekt-Auflösung, fand nichts, und der Detail-Guard ließ durch — ein
    Konto mit Rolle ``viewer`` las den Gesamtüberblick eines fremden Mandanten.
    """
    from server.middleware import firma_acl

    nach_name: list[str] = []
    monkeypatch.setattr(firma_acl, "firma_id_by_name",
                        lambda n: nach_name.append(n) or 5)
    monkeypatch.setattr(firma_acl, "project_firmen_id",
                        lambda m, p: pytest.fail(
                            "bei modul='firmen' darf NICHT über die "
                            "Projekt-Tabelle aufgelöst werden"))

    assert firma_acl.request_firmen_id("firmen", {"projekt": "Fremde AG"}) == 5
    assert nach_name == ["Fremde AG"]


def test_zugriff_wird_verweigert_wenn_die_firma_nicht_in_der_whitelist_steht(monkeypatch):
    """Der Rundlauf: auflösbare Fremdfirma → geblockt, eigene → erlaubt."""
    from server.middleware import firma_acl

    monkeypatch.setattr(firma_acl, "project_firmen_id", lambda m, p: 2)
    claims = {"allowed_firmen": [1]}
    assert firma_acl.access_denied_for_firma(
        claims, "compliance_audit", {"project_name": "Fremd"}) is True

    monkeypatch.setattr(firma_acl, "project_firmen_id", lambda m, p: 1)
    assert firma_acl.access_denied_for_firma(
        claims, "compliance_audit", {"project_name": "Eigen"}) is False


def test_ohne_whitelist_bleibt_alles_offen(monkeypatch):
    """Admins (``allowed_firmen=None``) sind unberührt — die Regel aus #1703/S4."""
    from server.middleware import firma_acl

    monkeypatch.setattr(firma_acl, "project_firmen_id", lambda m, p: 99)
    assert firma_acl.access_denied_for_firma(
        {"allowed_firmen": None}, "cra", {"projekt_name": "X"}) is False
    assert firma_acl.access_denied_for_firma({}, "cra", {"projekt_name": "X"}) is False


# ══════════════════════════════════════════════════════════════════════════════
# #2032 — die vier flachen Legacy-Routen
# ══════════════════════════════════════════════════════════════════════════════

FLACHE_ROUTEN = [
    ("server/api/cra/__init__.py", "server.api.cra", "list_all_legacy"),
    ("server/api/nis2.py", "server.api.nis2", "list_all_legacy"),
    ("server/api/aiact.py", "server.api.aiact", "list_all_legacy"),
]


@pytest.mark.parametrize("pfad,modulname,funktion", FLACHE_ROUTEN)
def test_flache_route_delegiert_an_das_gefilterte_geschwister(
        monkeypatch, client, auth_headers, pfad, modulname, funktion):
    """Behaviour über HTTP, nicht Quelltext: Wird ``get_projekte`` ersetzt, muss
    die flache Route **dessen** Ergebnis ausliefern.

    Bringt jemand die eigene Schleife zurück, wird der Ersatz nicht gerufen und
    der Vergleich schlägt fehl. Genau diese vier Kopien sind der Grund, warum
    #1703/S4 sie übersehen hat — die gefilterte Fassung stand in derselben
    Datei.
    """
    import importlib

    modul = importlib.import_module(modulname)
    monkeypatch.setattr(modul, "get_projekte",
                        lambda: ([{"name": "nur-eigene"}], 200))
    pfad_url = {"server.api.cra": "/api/cra",
                "server.api.nis2": "/api/nis2",
                "server.api.aiact": "/api/aiact"}[modulname]
    antwort = client.get(pfad_url, headers=auth_headers)
    assert antwort.status_code == 200
    assert antwort.get_json() == [{"name": "nur-eigene"}]


def test_flache_rb_route_liest_nur_erlaubte_projekte(
        monkeypatch, client, auth_headers):
    """Der härteste Fall: ``GET /api/risikobewertung`` gibt keine Namensliste,
    sondern **jedes Risiko mit vollem Inhalt** — Bewertungstext,
    Akzeptanzbegründung, Behandlungsstand. Bis v8.6.3 über alle Mandanten.
    """
    from server.api import risikobewertung as rb

    monkeypatch.setattr(rb, "get_projekte", lambda: ([{"name": "Eigen"}], 200))
    gelesen: list[str] = []

    def _risiken(_db, projekt):
        gelesen.append(projekt)
        return [{"id": 1}]

    monkeypatch.setattr(rb, "load_risiken", _risiken)
    monkeypatch.setattr(rb, "_serialize_risiko", lambda r: dict(r))

    antwort = client.get("/api/risikobewertung", headers=auth_headers)
    assert antwort.status_code == 200
    assert gelesen == ["Eigen"], (
        "nur Projekte aus dem gefilterten Geschwister dürfen gelesen werden — "
        f"gelesen wurden {gelesen}")
    assert [r["projekt_name"] for r in antwort.get_json()] == ["Eigen"]


def test_die_flache_rb_route_holt_die_projektliste_nicht_selbst():
    """Gegenprobe auf der Programmebene: ``list_projekte`` darf im Rumpf nicht
    mehr vorkommen — sonst wäre die Filterung umgehbar, ohne dass der Test oben
    es merkt (die eigene Schleife *neben* der Delegation)."""
    fn = _funktionsrumpf("server/api/risikobewertung.py", "list_all_risiken")
    gerufen = _gerufene_namen(fn)
    assert "get_projekte" in gerufen
    assert "list_projekte" not in gerufen, (
        "die flache Route holt die Projektliste wieder selbst (ungefiltert)")


def test_fehler_des_geschwisters_wird_durchgereicht(monkeypatch, client, auth_headers):
    """Ein 500 aus ``get_projekte`` darf nicht als leere Risikoliste erscheinen —
    sonst sähe ein Fehlerfall wie Risikofreiheit aus (dieselbe Richtung wie
    #2037)."""
    from server.api import risikobewertung as rb

    monkeypatch.setattr(rb, "get_projekte",
                        lambda: ({"error": "Interner Serverfehler"}, 500))
    antwort = client.get("/api/risikobewertung", headers=auth_headers)
    assert antwort.status_code == 500


# ══════════════════════════════════════════════════════════════════════════════
# #2033 / #2034 / #2030 — die drei Endpunkte mit Request-Kontext
# ══════════════════════════════════════════════════════════════════════════════

def test_risiko_cockpit_prueft_die_aufgeloeste_firma():
    """#2033: Der Endpunkt löst die ``firmen_id`` aus der **richtigen**
    Modultabelle auf — er weiß also, zu welcher Firma er antwortet. ``firma_acl``
    wusste es nicht (``/api/risk-cockpit`` ist dem Modul ``risikobewertung``
    zugeordnet, ein CRA-Projekt steht nicht in ``rb_projekte`` → ``None`` →
    fail-open). Also muss der Endpunkt selbst prüfen.
    """
    fn = _funktionsrumpf("server/api/risk_cockpit.py",
                         "get_risk_cockpit_by_projekt")
    assert "filter_allowed_firmen_ids" in _gerufene_namen(fn), (
        "by-projekt prüft die aufgelöste Firma nicht gegen allowed_firmen")


def test_risiko_cockpit_modulliste_ist_abgeleitet():
    """Dies war die dritte Kopie derselben Zuordnung (#2033)."""
    from server.api.risk_cockpit import _MODULE_ALIASES

    for datei in _MODULE_ALIASES.values():
        assert datei in MODULE_PROJECT_TABLES, (
            f"{datei!r} steht nicht in MODULE_PROJECT_TABLES")
    # Das Cockpit aggregiert rb_risiken + cra_vuln — beide müssen dabei sein.
    assert {"risikobewertung", "cra"} <= set(_MODULE_ALIASES)


def test_cra_projektliste_im_aiact_modul_ist_gescopet():
    """#2034: zweite Tür auf dieselben Daten, hinter ``aiact:read`` statt
    ``cra:read`` und ohne URL-Parameter für ``firma_acl``. Sie liefert zugleich
    die Eingabewerte für #2030/#2031/#2033."""
    fn = _funktionsrumpf("server/api/aiact_conformity.py", "cra_projekte")
    assert "scope_current_request" in _gerufene_namen(fn), (
        "die CRA-Auswahlliste filtert nicht auf freigegebene Mandanten")


def test_vorlagen_render_prueft_die_firma_des_projekts():
    """#2030: Geprüft wurde nur die Firma **der Vorlage** — bei einer
    Haus-Vorlage (``firmen_id IS NULL``) ist das wirkungslos, und das ``projekt``
    aus dem Rumpf ging ungeprüft an den Kontext-Builder."""
    fn = _funktionsrumpf("server/api/templates/__init__.py", "render")
    gerufen = _gerufene_namen(fn)
    assert "_firma_erlaubt" in gerufen
    assert {"project_firmen_id", "_projekt_firma"} & gerufen, (
        "render() löst die Firma des Projekts nicht auf — eine Haus-Vorlage "
        "exportiert damit fremde Mandanten")


def test_alle_drei_template_manage_routen_pruefen_die_firma():
    """``put_mapping`` war die einzige ohne Prüfung (#2030, Nebenbefund)."""
    for name in ("put_mapping", "put_default", "delete_one"):
        fn = _funktionsrumpf("server/api/templates/__init__.py", name)
        assert "_firma_erlaubt" in _gerufene_namen(fn), f"{name}() prüft nicht"


# ── Der Wächter über den Wächter ─────────────────────────────────────────────

def test_ast_pruefung_laesst_sich_nicht_durch_einen_kommentar_erfuellen():
    """Die Lehre aus #1834 in ihrer Testform: ``ast`` sieht Kommentare nicht.

    Ohne diese Zusage wäre jede AST-Prüfung oben durch eine Kommentarzeile
    erfüllbar — und ein Prüfer, der die Erzählung prüft, prüft nichts.
    """
    quelle = "def f():\n    # filter_allowed_firmen_ids(claims, [1])\n    return 1\n"
    baum = ast.parse(quelle)
    fn = next(k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef))
    assert "filter_allowed_firmen_ids" not in _gerufene_namen(fn)


def test_werkzeug_findet_echte_aufrufe():
    """Gegenprobe: ein echter Aufruf wird gefunden (sonst wäre oben alles grün)."""
    quelle = ("def f(c):\n"
              "    from server.middleware.firma_acl import filter_allowed_firmen_ids\n"
              "    return filter_allowed_firmen_ids(c, [1])\n")
    baum = ast.parse(quelle)
    fn = next(k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef))
    assert "filter_allowed_firmen_ids" in _gerufene_namen(fn)
